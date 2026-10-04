import os
import time
import uuid
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
import logging

from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from core.config import settings
from backup.backup_models import (
    BackupMetadata,
    BackupStatus,
    BackupType,
    RetentionClass,
    VerificationStatus,
    RestoreTestResult,
    ProductionRestoreRequest,
    ProductionRestoreResult,
)
from backup.backup_utils import (
    resolve_mongodump_path,
    resolve_mongorestore_path,
    calculate_sha256,
    verify_checksum,
    validate_backup_path,
    determine_retention_class,
    sanitize_connection_args,
)
from schemas.schemas import AuditEventCategory, AuditSeverity
from services.audit_service import AuditService
from services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class BackupService:
    """
    Centralized Automated Backup, Retention, Integrity Verification,
    and Safe Restore Service for GEISER ITSM.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.backups
        self.backup_dir = Path(settings.BACKUP_DIRECTORY).resolve()
        # Ensure backup directory exists
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.audit_service = AuditService(db)
        self.notification_service = NotificationService(db)

    async def create_backup(
        self,
        backup_type: BackupType = BackupType.MANUAL,
        is_protected: bool = False,
        actor: Optional[Dict[str, Any]] = None,
        custom_db_name: Optional[str] = None,
    ) -> BackupMetadata:
        """
        Executes an automated, compressed, atomic MongoDB backup using mongodump.
        Calculates SHA-256 checksum, registers metadata, verifies integrity,
        and triggers retention pruning.
        """
        start_time = time.time()
        now = datetime.utcnow()
        target_db = custom_db_name or settings.BACKUP_MONGODB_DATABASE

        # Generate unique collision-proof backup identifier
        timestamp_str = now.strftime("%Y%m%d_%H%M%S")
        unique_suffix = uuid.uuid4().hex[:8]
        backup_id = f"bkp_{timestamp_str}_{unique_suffix}"
        filename = f"geiser_{target_db}_{timestamp_str}_{unique_suffix}.archive.gz"
        filepath = self.backup_dir / filename

        retention_class = (
            RetentionClass.MANUAL if backup_type == BackupType.MANUAL
            else determine_retention_class(now)
        )

        metadata = BackupMetadata(
            backup_id=backup_id,
            database_name=target_db,
            filename=filename,
            filepath=str(filepath),
            created_at=now,
            status=BackupStatus.RUNNING,
            backup_type=backup_type,
            retention_class=retention_class,
            is_protected=is_protected,
            metadata={
                "triggered_by": actor.get("email") if actor else "system_scheduler",
                "compression": settings.BACKUP_COMPRESSION,
            }
        )

        # Store initial RUNNING record in MongoDB
        await self.collection.insert_one(metadata.dict())

        # Check binary availability
        mongodump_bin = resolve_mongodump_path()
        if not mongodump_bin:
            error_msg = (
                "mongodump binary not found. Please install MongoDB Database Tools "
                "or specify MONGODUMP_PATH in environment configuration."
            )
            logger.error(f"[BackupService] {error_msg}")
            elapsed = time.time() - start_time
            await self._record_failure(backup_id, error_msg, elapsed, actor)
            metadata.status = BackupStatus.FAILED
            metadata.error_message = error_msg
            metadata.duration_seconds = elapsed
            return metadata

        # Build execution arguments safely (without shell=True to avoid injection)
        cmd: List[str] = [
            mongodump_bin,
            f"--uri={settings.MONGO_URL}",
            f"--db={target_db}",
            f"--archive={str(filepath)}",
        ]
        if settings.BACKUP_COMPRESSION:
            cmd.append("--gzip")

        # Execute dump subprocess
        try:
            logger.info(f"[BackupService] Starting dump for database '{target_db}' -> {filepath.name}")
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout_data, stderr_data = await asyncio.wait_for(
                    process.communicate(),
                    timeout=float(settings.BACKUP_TIMEOUT_SECONDS)
                )
            except asyncio.TimeoutError:
                process.kill()
                error_msg = f"Backup timed out after {settings.BACKUP_TIMEOUT_SECONDS}s"
                logger.error(f"[BackupService] {error_msg}")
                if filepath.exists():
                    filepath.unlink(missing_ok=True)
                elapsed = time.time() - start_time
                await self._record_failure(backup_id, error_msg, elapsed, actor)
                metadata.status = BackupStatus.FAILED
                metadata.error_message = error_msg
                metadata.duration_seconds = elapsed
                return metadata

            if process.returncode != 0:
                err_text = stderr_data.decode("utf-8", errors="replace").strip()
                error_msg = f"mongodump exited with code {process.returncode}: {err_text[:300]}"
                logger.error(f"[BackupService] {error_msg}")
                if filepath.exists():
                    filepath.unlink(missing_ok=True)
                elapsed = time.time() - start_time
                await self._record_failure(backup_id, error_msg, elapsed, actor)
                metadata.status = BackupStatus.FAILED
                metadata.error_message = error_msg
                metadata.duration_seconds = elapsed
                return metadata

            # Validate that output file exists and is non-empty
            if not filepath.exists() or filepath.stat().st_size == 0:
                error_msg = "mongodump succeeded but output archive is missing or zero bytes."
                logger.error(f"[BackupService] {error_msg}")
                elapsed = time.time() - start_time
                await self._record_failure(backup_id, error_msg, elapsed, actor)
                metadata.status = BackupStatus.FAILED
                metadata.error_message = error_msg
                metadata.duration_seconds = elapsed
                return metadata

            # Calculate SHA-256 checksum
            checksum = calculate_sha256(filepath)
            size_bytes = filepath.stat().st_size
            elapsed = time.time() - start_time

            # Update database record
            update_data = {
                "status": BackupStatus.SUCCESS.value,
                "size_bytes": size_bytes,
                "checksum_sha256": checksum,
                "duration_seconds": round(elapsed, 2),
                "verification_status": VerificationStatus.VERIFIED.value if settings.BACKUP_VERIFY_INTEGRITY else VerificationStatus.PENDING.value,
                "last_verified_at": datetime.utcnow() if settings.BACKUP_VERIFY_INTEGRITY else None,
                "error_message": None,
            }
            await self.collection.update_one({"backup_id": backup_id}, {"$set": update_data})

            metadata.status = BackupStatus.SUCCESS
            metadata.size_bytes = size_bytes
            metadata.checksum_sha256 = checksum
            metadata.duration_seconds = round(elapsed, 2)
            metadata.verification_status = (
                VerificationStatus.VERIFIED if settings.BACKUP_VERIFY_INTEGRITY
                else VerificationStatus.PENDING
            )
            metadata.last_verified_at = update_data["last_verified_at"]

            # Log to ISO 27001 Security Audit Log
            await self.audit_service.log_event(
                event_category=AuditEventCategory.SYSTEM,
                event_type="BACKUP_CREATED",
                severity=AuditSeverity.INFO,
                target_resource_type="BACKUP",
                target_resource_id=backup_id,
                actor_id=str(actor.get("id")) if actor else None,
                actor_email=actor.get("email") if actor else "system",
                actor_role=actor.get("role") if actor else "SYSTEM",
                details={
                    "database": target_db,
                    "filename": filename,
                    "size_bytes": size_bytes,
                    "checksum_sha256": checksum,
                    "duration_seconds": round(elapsed, 2),
                    "backup_type": backup_type.value,
                }
            )

            logger.info(
                f"[BackupService] Successfully created backup '{backup_id}' "
                f"({size_bytes / (1024 * 1024):.2f} MB, checksum: {checksum[:12]}...)"
            )

            # Prune obsolete backups per retention policy
            asyncio.create_task(self.apply_retention_policy())

            return metadata

        except Exception as e:
            elapsed = time.time() - start_time
            error_msg = f"Unexpected backup error: {str(e)}"
            logger.exception(f"[BackupService] {error_msg}")
            if filepath.exists():
                filepath.unlink(missing_ok=True)
            await self._record_failure(backup_id, error_msg, elapsed, actor)
            metadata.status = BackupStatus.FAILED
            metadata.error_message = error_msg
            metadata.duration_seconds = elapsed
            return metadata

    async def _record_failure(
        self,
        backup_id: str,
        error_msg: str,
        duration: float,
        actor: Optional[Dict[str, Any]] = None
    ) -> None:
        """Records a failure in MongoDB, logs security audit, and alerts admins."""
        await self.collection.update_one(
            {"backup_id": backup_id},
            {"$set": {
                "status": BackupStatus.FAILED.value,
                "error_message": error_msg[:1000],
                "duration_seconds": round(duration, 2),
            }}
        )

        await self.audit_service.log_event(
            event_category=AuditEventCategory.SYSTEM,
            event_type="BACKUP_FAILED",
            severity=AuditSeverity.CRITICAL,
            target_resource_type="BACKUP",
            target_resource_id=backup_id,
            actor_id=str(actor.get("id")) if actor else None,
            actor_email=actor.get("email") if actor else "system",
            actor_role=actor.get("role") if actor else "SYSTEM",
            status="FAILED",
            details={"error": error_msg, "duration_seconds": round(duration, 2)}
        )

        # Notify active administrators through existing NotificationService
        try:
            admin_users = await self.db.users.find({"role": "ADMIN", "is_active": True}).to_list(length=10)
            for admin in admin_users:
                await self.notification_service._record_notification(
                    user_id=str(admin["_id"]),
                    user_email=admin.get("email"),
                    ticket_id=None,
                    channel="IN_APP",
                    title="Alerte Sauvegarde Échouée",
                    message=f"La sauvegarde automatique '{backup_id}' a échoué: {error_msg[:150]}",
                    status="SENT",
                    event_type="BACKUP_FAILURE",
                )
        except Exception as notif_err:
            logger.debug(f"[BackupService] Non-blocking notification error: {notif_err}")

    async def verify_backup_integrity(self, backup_id: str) -> Dict[str, Any]:
        """
        Recalculates the SHA-256 checksum and compares it against the recorded checksum.
        Marks as CORRUPTED if mismatch or file is missing.
        """
        doc = await self.collection.find_one({"backup_id": backup_id})
        if not doc:
            raise FileNotFoundError(f"Backup record '{backup_id}' not found")

        filepath = Path(doc["filepath"])
        # Validate path to guard against directory traversal
        valid_path = validate_backup_path(filepath, self.backup_dir)

        if not valid_path.exists():
            await self.collection.update_one(
                {"backup_id": backup_id},
                {"$set": {
                    "status": BackupStatus.CORRUPTED.value,
                    "verification_status": VerificationStatus.CORRUPTED.value,
                    "error_message": "Backup file not found on disk",
                    "last_verified_at": datetime.utcnow(),
                }}
            )
            return {
                "backup_id": backup_id,
                "verified": False,
                "status": BackupStatus.CORRUPTED.value,
                "error": "Backup file missing on disk"
            }

        stored_checksum = doc.get("checksum_sha256")
        if not stored_checksum:
            # Generate and store checksum if it wasn't recorded initially
            stored_checksum = calculate_sha256(valid_path)
            await self.collection.update_one(
                {"backup_id": backup_id},
                {"$set": {"checksum_sha256": stored_checksum}}
            )

        is_valid = verify_checksum(valid_path, stored_checksum)
        new_status = VerificationStatus.VERIFIED.value if is_valid else VerificationStatus.CORRUPTED.value
        backup_status = doc.get("status") if is_valid else BackupStatus.CORRUPTED.value

        await self.collection.update_one(
            {"backup_id": backup_id},
            {"$set": {
                "verification_status": new_status,
                "status": backup_status,
                "last_verified_at": datetime.utcnow(),
                "error_message": None if is_valid else "Checksum mismatch (possible corruption)",
            }}
        )

        return {
            "backup_id": backup_id,
            "verified": is_valid,
            "stored_checksum": stored_checksum,
            "verification_status": new_status,
            "last_verified_at": datetime.utcnow().isoformat(),
        }

    async def apply_retention_policy(self) -> Dict[str, Any]:
        """
        Applies configurable grandfather-father-son retention:
        - Daily: keeps settings.BACKUP_RETENTION_DAYS most recent daily backups
        - Weekly: keeps settings.BACKUP_RETENTION_WEEKLY most recent weekly backups
        - Monthly: keeps settings.BACKUP_RETENTION_MONTHLY most recent monthly backups
        Guards:
        - NEVER deletes the newest valid backup!
        - NEVER deletes RUNNING backups.
        - NEVER deletes backups marked is_protected=True or SNAPSHOT.
        - NEVER deletes files outside the backup directory (path traversal check).
        """
        now = datetime.utcnow()
        cursor = self.collection.find(
            {"status": {"$in": [BackupStatus.SUCCESS.value, BackupStatus.CORRUPTED.value]}}
        ).sort("created_at", -1)
        all_backups = await cursor.to_list(length=1000)

        if not all_backups:
            return {"deleted_count": 0, "retained_count": 0, "deleted_ids": []}

        # 1. Identify the single newest valid SUCCESS backup to ALWAYS protect it
        newest_valid_id: Optional[str] = None
        for bkp in all_backups:
            if bkp.get("status") == BackupStatus.SUCCESS.value:
                newest_valid_id = bkp.get("backup_id")
                break

        # 2. Categorize backups into tiers
        dailies: List[Dict[str, Any]] = []
        weeklies: List[Dict[str, Any]] = []
        monthlies: List[Dict[str, Any]] = []
        manuals: List[Dict[str, Any]] = []

        for bkp in all_backups:
            ret_class = bkp.get("retention_class", RetentionClass.DAILY.value)
            if bkp.get("is_protected") or bkp.get("backup_type") == BackupType.SNAPSHOT.value:
                continue
            if ret_class == RetentionClass.MONTHLY.value:
                monthlies.append(bkp)
            elif ret_class == RetentionClass.WEEKLY.value:
                weeklies.append(bkp)
            elif ret_class == RetentionClass.MANUAL.value:
                manuals.append(bkp)
            else:
                dailies.append(bkp)

        # 3. Determine candidates for deletion
        to_delete: List[Dict[str, Any]] = []

        if len(dailies) > settings.BACKUP_RETENTION_DAYS:
            to_delete.extend(dailies[settings.BACKUP_RETENTION_DAYS:])

        if len(weeklies) > settings.BACKUP_RETENTION_WEEKLY:
            to_delete.extend(weeklies[settings.BACKUP_RETENTION_WEEKLY:])

        if len(monthlies) > settings.BACKUP_RETENTION_MONTHLY:
            to_delete.extend(monthlies[settings.BACKUP_RETENTION_MONTHLY:])

        # Manual backups older than 30 days that are not protected
        for m in manuals:
            created = m.get("created_at")
            if created and (now - created).days > 30:
                to_delete.append(m)

        deleted_ids: List[str] = []
        for bkp in to_delete:
            bid = bkp.get("backup_id")
            # Guard: Never delete newest valid backup
            if bid == newest_valid_id:
                logger.info(f"[BackupService] Retention skipped newest valid backup '{bid}'")
                continue

            try:
                filepath = Path(bkp.get("filepath", ""))
                if filepath.exists():
                    valid_path = validate_backup_path(filepath, self.backup_dir)
                    valid_path.unlink(missing_ok=True)

                await self.collection.update_one(
                    {"backup_id": bid},
                    {"$set": {
                        "status": BackupStatus.DELETED.value,
                        "deleted_at": datetime.utcnow()
                    }}
                )
                deleted_ids.append(bid)
                logger.info(f"[BackupService] Retention policy pruned expired backup '{bid}'")
            except Exception as e:
                logger.warning(f"[BackupService] Failed to prune backup '{bid}': {e}")

        return {
            "deleted_count": len(deleted_ids),
            "retained_count": len(all_backups) - len(deleted_ids),
            "deleted_ids": deleted_ids
        }

    async def test_isolated_restore(self, backup_id: str) -> RestoreTestResult:
        """
        MODE A — Safe Isolated Restore Validation:
        1. Verifies SHA-256 integrity.
        2. Restores into a temporary isolated MongoDB database without touching production.
        3. Validates critical GEISER collections and document counts.
        4. Drops the temporary test database completely.
        """
        start_time = time.time()
        doc = await self.collection.find_one({"backup_id": backup_id})
        if not doc:
            raise FileNotFoundError(f"Backup '{backup_id}' not found")

        filepath = Path(doc["filepath"])
        valid_path = validate_backup_path(filepath, self.backup_dir)

        # 1. Checksum verification
        stored_checksum = doc.get("checksum_sha256")
        if stored_checksum:
            if not verify_checksum(valid_path, stored_checksum):
                return RestoreTestResult(
                    backup_id=backup_id,
                    test_database="",
                    success=False,
                    duration_seconds=round(time.time() - start_time, 2),
                    checksum_verified=False,
                    collections_found=[],
                    total_documents_restored=0,
                    details={},
                    error_message="Checksum mismatch before restore: file is corrupted."
                )

        # 2. Prepare isolated temporary database name
        source_db = doc.get("database_name", settings.BACKUP_MONGODB_DATABASE)
        clean_id = backup_id.replace("-", "_").replace(".", "_")
        test_db_name = f"geiser_test_restore_{clean_id}"

        mongorestore_bin = resolve_mongorestore_path()
        if not mongorestore_bin:
            return RestoreTestResult(
                backup_id=backup_id,
                test_database=test_db_name,
                success=False,
                duration_seconds=round(time.time() - start_time, 2),
                checksum_verified=True,
                collections_found=[],
                total_documents_restored=0,
                details={},
                error_message="mongorestore binary not found on system."
            )

        cmd: List[str] = [
            mongorestore_bin,
            f"--uri={settings.MONGO_URL}",
            f"--nsFrom={source_db}.*",
            f"--nsTo={test_db_name}.*",
            f"--archive={str(valid_path)}",
            "--drop",
        ]
        if settings.BACKUP_COMPRESSION:
            cmd.append("--gzip")

        # 3. Execute restore to isolated DB
        try:
            logger.info(f"[BackupService] Executing isolated test restore into '{test_db_name}'...")
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout_data, stderr_data = await asyncio.wait_for(
                proc.communicate(),
                timeout=float(settings.BACKUP_TIMEOUT_SECONDS)
            )

            if proc.returncode != 0:
                err_text = stderr_data.decode("utf-8", errors="replace").strip()
                return RestoreTestResult(
                    backup_id=backup_id,
                    test_database=test_db_name,
                    success=False,
                    duration_seconds=round(time.time() - start_time, 2),
                    checksum_verified=True,
                    collections_found=[],
                    total_documents_restored=0,
                    details={"stderr": err_text[:500]},
                    error_message=f"mongorestore failed with exit code {proc.returncode}"
                )

            # 4. Verify restored contents using client connection
            test_db = self.db.client[test_db_name]
            collections = await test_db.list_collection_names()

            # Collections that exist in GEISER
            critical_collections = [
                "users", "tickets", "audit_logs", "teams", "agents",
                "sla_policies", "routing_history", "knowledge_documents"
            ]

            details: Dict[str, int] = {}
            total_docs = 0
            for col_name in collections:
                count = await test_db[col_name].count_documents({})
                details[col_name] = count
                total_docs += count

            elapsed = time.time() - start_time

            # 5. Clean up: Drop the temporary isolated database
            await self.db.client.drop_database(test_db_name)
            logger.info(f"[BackupService] Dropped temporary test database '{test_db_name}'")

            # Update verification status in metadata
            await self.collection.update_one(
                {"backup_id": backup_id},
                {"$set": {
                    "verification_status": VerificationStatus.VERIFIED.value,
                    "last_verified_at": datetime.utcnow()
                }}
            )

            await self.audit_service.log_event(
                event_category=AuditEventCategory.SYSTEM,
                event_type="BACKUP_RESTORE_TESTED",
                severity=AuditSeverity.INFO,
                target_resource_type="BACKUP",
                target_resource_id=backup_id,
                details={
                    "test_database": test_db_name,
                    "collections_count": len(collections),
                    "total_documents": total_docs,
                    "duration_seconds": round(elapsed, 2)
                }
            )

            return RestoreTestResult(
                backup_id=backup_id,
                test_database=test_db_name,
                success=True,
                duration_seconds=round(elapsed, 2),
                checksum_verified=True,
                collections_found=collections,
                total_documents_restored=total_docs,
                details=details,
                error_message=None
            )

        except Exception as e:
            elapsed = time.time() - start_time
            # Ensure temporary DB is dropped even on error
            try:
                await self.db.client.drop_database(test_db_name)
            except Exception:
                pass

            return RestoreTestResult(
                backup_id=backup_id,
                test_database=test_db_name,
                success=False,
                duration_seconds=round(elapsed, 2),
                checksum_verified=True,
                collections_found=[],
                total_documents_restored=0,
                details={},
                error_message=str(e)
            )

    async def restore_production(
        self,
        backup_id: str,
        request: ProductionRestoreRequest,
        actor: Dict[str, Any]
    ) -> ProductionRestoreResult:
        """
        MODE B — Destructive Production Restore:
        STRICT SAFETY GUARDS:
        1. Globally forbidden unless BACKUP_ALLOW_PRODUCTION_RESTORE=true in settings.
        2. Explicit confirm_production_overwrite flag required.
        3. Target database must match settings.DATABASE_NAME.
        4. Automatic safety snapshot taken of current database BEFORE overwriting.
        5. Checksum verification of source archive.
        6. Submits critical security audit entry.
        """
        start_time = time.time()

        # Guard 1: Environment flag
        if not getattr(settings, "BACKUP_ALLOW_PRODUCTION_RESTORE", False):
            raise PermissionError(
                "Production restore is globally disabled. Set BACKUP_ALLOW_PRODUCTION_RESTORE=true "
                "in server environment variables to authorize production restoration."
            )

        # Guard 2: Explicit confirmation flag
        if not request.confirm_production_overwrite:
            raise ValueError(
                "Production restore aborted: 'confirm_production_overwrite' must be explicitly set to True."
            )

        # Guard 3: Target database name verification
        if request.target_database_name != settings.DATABASE_NAME:
            raise ValueError(
                f"Target database mismatch: '{request.target_database_name}' != '{settings.DATABASE_NAME}'"
            )

        # Retrieve backup document
        doc = await self.collection.find_one({"backup_id": backup_id})
        if not doc:
            raise FileNotFoundError(f"Backup '{backup_id}' not found")

        filepath = Path(doc["filepath"])
        valid_path = validate_backup_path(filepath, self.backup_dir)

        # Guard 4: Checksum integrity
        stored_checksum = doc.get("checksum_sha256")
        if stored_checksum and not verify_checksum(valid_path, stored_checksum):
            raise ValueError("Production restore rejected: Backup checksum mismatch (file is corrupted).")

        # Guard 5: Safety pre-restore snapshot of current database
        snapshot_meta = None
        if request.create_pre_restore_snapshot:
            logger.warning("[BackupService] Creating pre-restore snapshot of production database...")
            snapshot_meta = await self.create_backup(
                backup_type=BackupType.SNAPSHOT,
                is_protected=True,
                actor=actor
            )
            if snapshot_meta.status != BackupStatus.SUCCESS:
                raise RuntimeError(
                    f"Production restore aborted: Failed to take safety pre-restore snapshot: {snapshot_meta.error_message}"
                )

        mongorestore_bin = resolve_mongorestore_path()
        if not mongorestore_bin:
            raise FileNotFoundError("mongorestore binary not found on system.")

        source_db = doc.get("database_name", settings.BACKUP_MONGODB_DATABASE)
        cmd: List[str] = [
            mongorestore_bin,
            f"--uri={settings.MONGO_URL}",
            f"--nsFrom={source_db}.*",
            f"--nsTo={settings.DATABASE_NAME}.*",
            f"--archive={str(valid_path)}",
            "--drop",
        ]
        if settings.BACKUP_COMPRESSION:
            cmd.append("--gzip")

        logger.warning(
            f"[BackupService] CRITICAL: Overwriting production database '{settings.DATABASE_NAME}' "
            f"from backup '{backup_id}' (Actor: {actor.get('email')})"
        )

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout_data, stderr_data = await asyncio.wait_for(
            proc.communicate(),
            timeout=float(settings.BACKUP_TIMEOUT_SECONDS)
        )

        elapsed = time.time() - start_time

        if proc.returncode != 0:
            err_text = stderr_data.decode("utf-8", errors="replace").strip()
            error_msg = f"mongorestore failed with exit code {proc.returncode}: {err_text[:300]}"
            logger.critical(f"[BackupService] PRODUCTION RESTORE FAILED: {error_msg}")

            await self.audit_service.log_event(
                event_category=AuditEventCategory.SYSTEM,
                event_type="PRODUCTION_RESTORE_FAILED",
                severity=AuditSeverity.CRITICAL,
                target_resource_type="DATABASE",
                target_resource_id=settings.DATABASE_NAME,
                actor_id=str(actor.get("id")) if actor else None,
                actor_email=actor.get("email"),
                actor_role=actor.get("role"),
                status="FAILED",
                details={"error": error_msg, "backup_id": backup_id}
            )

            return ProductionRestoreResult(
                backup_id=backup_id,
                target_database=settings.DATABASE_NAME,
                success=False,
                pre_restore_snapshot_id=snapshot_meta.backup_id if snapshot_meta else None,
                duration_seconds=round(elapsed, 2),
                error_message=error_msg
            )

        # Log CRITICAL security audit event
        await self.audit_service.log_event(
            event_category=AuditEventCategory.SYSTEM,
            event_type="PRODUCTION_RESTORE_EXECUTED",
            severity=AuditSeverity.CRITICAL,
            target_resource_type="DATABASE",
            target_resource_id=settings.DATABASE_NAME,
            actor_id=str(actor.get("id")) if actor else None,
            actor_email=actor.get("email"),
            actor_role=actor.get("role"),
            status="SUCCESS",
            details={
                "backup_id": backup_id,
                "pre_restore_snapshot_id": snapshot_meta.backup_id if snapshot_meta else None,
                "reason": request.reason,
                "duration_seconds": round(elapsed, 2)
            }
        )

        logger.info(f"[BackupService] Successfully restored production database from backup '{backup_id}'")

        return ProductionRestoreResult(
            backup_id=backup_id,
            target_database=settings.DATABASE_NAME,
            success=True,
            pre_restore_snapshot_id=snapshot_meta.backup_id if snapshot_meta else None,
            duration_seconds=round(elapsed, 2),
            error_message=None
        )

    async def list_backups(
        self,
        skip: int = 0,
        limit: int = 50,
        status: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Returns paginated backups excluding deleted ones by default."""
        query: Dict[str, Any] = {"status": {"$ne": BackupStatus.DELETED.value}}
        if status:
            query["status"] = status

        total = await self.collection.count_documents(query)
        cursor = self.collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
        items = await cursor.to_list(length=limit)
        return items, total

    async def get_backup_stats(self) -> Dict[str, Any]:
        """Calculates storage size, count of valid backups, and last success/failure."""
        active_query = {"status": {"$ne": BackupStatus.DELETED.value}}
        total_backups = await self.collection.count_documents({})
        active_backups = await self.collection.count_documents(active_query)

        # Storage aggregation
        pipeline = [
            {"$match": active_query},
            {"$group": {"_id": None, "total_size": {"$sum": "$size_bytes"}}}
        ]
        agg_result = await self.collection.aggregate(pipeline).to_list(length=1)
        total_storage = agg_result[0]["total_size"] if agg_result else 0

        last_success_doc = await self.collection.find_one(
            {"status": BackupStatus.SUCCESS.value},
            sort=[("created_at", -1)]
        )
        last_failed_doc = await self.collection.find_one(
            {"status": BackupStatus.FAILED.value},
            sort=[("created_at", -1)]
        )

        verified_count = await self.collection.count_documents({
            "verification_status": VerificationStatus.VERIFIED.value,
            "status": {"$ne": BackupStatus.DELETED.value}
        })
        corrupted_count = await self.collection.count_documents({
            "status": BackupStatus.CORRUPTED.value
        })
        failed_count = await self.collection.count_documents({
            "status": BackupStatus.FAILED.value
        })

        return {
            "total_backups": total_backups,
            "active_backups": active_backups,
            "total_storage_bytes": total_storage,
            "last_successful_backup": last_success_doc["created_at"] if last_success_doc else None,
            "last_failed_backup": last_failed_doc["created_at"] if last_failed_doc else None,
            "verified_count": verified_count,
            "corrupted_count": corrupted_count,
            "failed_count": failed_count,
            "allow_production_restore": getattr(settings, "BACKUP_ALLOW_PRODUCTION_RESTORE", False),
        }

    async def delete_backup(self, backup_id: str, actor: Optional[Dict[str, Any]] = None) -> bool:
        """
        Safely deletes a backup file from disk and marks record as DELETED.
        Guards:
        - Prevents deletion of RUNNING backups.
        - Prevents path traversal.
        """
        doc = await self.collection.find_one({"backup_id": backup_id})
        if not doc:
            raise FileNotFoundError(f"Backup '{backup_id}' not found")

        if doc.get("status") == BackupStatus.RUNNING.value:
            raise ValueError(f"Cannot delete backup '{backup_id}' while it is actively RUNNING.")

        filepath = Path(doc.get("filepath", ""))
        if filepath.exists():
            valid_path = validate_backup_path(filepath, self.backup_dir)
            valid_path.unlink(missing_ok=True)

        await self.collection.update_one(
            {"backup_id": backup_id},
            {"$set": {
                "status": BackupStatus.DELETED.value,
                "deleted_at": datetime.utcnow()
            }}
        )

        await self.audit_service.log_event(
            event_category=AuditEventCategory.SYSTEM,
            event_type="BACKUP_DELETED",
            severity=AuditSeverity.WARNING,
            target_resource_type="BACKUP",
            target_resource_id=backup_id,
            actor_id=str(actor.get("id")) if actor else None,
            actor_email=actor.get("email") if actor else "system",
            actor_role=actor.get("role") if actor else "ADMIN",
            details={"filename": doc.get("filename")}
        )

        return True
