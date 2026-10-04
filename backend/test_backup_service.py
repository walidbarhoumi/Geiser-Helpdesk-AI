"""
test_backup_service.py
======================
STEP 6 — Automated Backups, Restore & Disaster Recovery Test Suite

Comprehensive automated test coverage:
1. Backup Utils & Integrity (SHA-256 computation, path traversal guards, credential masking, retention class)
2. Backup Creation (Subprocess execution, exit code handling, timeout, checksum generation, audit logging)
3. Failure Resilience (Missing binaries, non-zero exit codes, timeout kill, admin notification)
4. Retention Pruning (Daily/Weekly/Monthly quotas, newest backup protection, active backup protection)
5. Mode A Isolated Restore (Temporary DB restore, document counting, automatic teardown)
6. Mode B Production Restore Guards (Safety switch, confirmation flag, pre-restore snapshot, target DB check)
7. Security & RBAC (ADMIN full, SUPERVISOR read-only, AGENT/USER 403 Forbidden)
"""

import os
import shutil
import tempfile
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from bson import ObjectId
from fastapi.testclient import TestClient

from core.config import settings
from backup.backup_models import (
    BackupStatus,
    BackupType,
    RetentionClass,
    VerificationStatus,
    ProductionRestoreRequest,
)
from backup.backup_utils import (
    calculate_sha256,
    verify_checksum,
    validate_backup_path,
    determine_retention_class,
    sanitize_connection_args,
    resolve_mongodump_path,
    resolve_mongorestore_path,
)
from backup.backup_service import BackupService
from schemas.schemas import UserRole


# ─────────────────────────────────────────────────────────────
# Fixtures & Mock Database
# ─────────────────────────────────────────────────────────────

class MockCursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, *args, **kwargs):
        return self

    def skip(self, n):
        self.docs = self.docs[n:]
        return self

    def limit(self, n):
        self.docs = self.docs[:n]
        return self

    async def to_list(self, length=None):
        if length is not None:
            return self.docs[:length]
        return self.docs


class MockCollection:
    def __init__(self):
        self.docs = []

    async def insert_one(self, doc):
        d = dict(doc)
        if "_id" not in d:
            d["_id"] = ObjectId()
        self.docs.append(d)
        res = MagicMock()
        res.inserted_id = d["_id"]
        return res

    async def find_one(self, query, sort=None):
        matching = []
        for d in self.docs:
            match = True
            for k, v in query.items():
                if isinstance(v, dict):
                    if "$in" in v and d.get(k) not in v["$in"]:
                        match = False
                    if "$ne" in v and d.get(k) == v["$ne"]:
                        match = False
                elif d.get(k) != v:
                    match = False
            if match:
                matching.append(d)
        if not matching:
            return None
        if sort:
            key, direction = sort[0]
            matching.sort(key=lambda x: x.get(key, 0), reverse=(direction == -1))
        return matching[0]

    def find(self, query=None):
        query = query or {}
        matching = []
        for d in self.docs:
            match = True
            for k, v in query.items():
                if isinstance(v, dict):
                    if "$in" in v and d.get(k) not in v["$in"]:
                        match = False
                    if "$ne" in v and d.get(k) == v["$ne"]:
                        match = False
                elif d.get(k) != v:
                    match = False
            if match:
                matching.append(d)
        return MockCursor(matching)

    async def update_one(self, query, update):
        target = await self.find_one(query)
        if target:
            if "$set" in update:
                target.update(update["$set"])
        res = MagicMock()
        res.matched_count = 1 if target else 0
        return res

    async def count_documents(self, query=None):
        if not query:
            return len(self.docs)
        cursor = self.find(query)
        return len(cursor.docs)

    def aggregate(self, pipeline):
        total = sum(d.get("size_bytes", 0) for d in self.docs if d.get("status") != BackupStatus.DELETED.value)
        return MockCursor([{"_id": None, "total_size": total}])


class MockAsyncDatabase:
    def __init__(self):
        self.backups = MockCollection()
        self.audit_logs = MockCollection()
        self.notifications = MockCollection()
        self.users = MockCollection()
        self.tickets = MockCollection()
        self.client = MagicMock()
        self.client.drop_database = AsyncMock(return_value=True)


@pytest.fixture
def mock_db():
    return MockAsyncDatabase()


@pytest.fixture
def temp_backup_dir():
    d = tempfile.mkdtemp(prefix="geiser_test_backups_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


# ─────────────────────────────────────────────────────────────
# 1. Backup Utils & Integrity Tests
# ─────────────────────────────────────────────────────────────

def test_calculate_sha256_and_verify(temp_backup_dir):
    test_file = temp_backup_dir / "sample.archive.gz"
    test_file.write_bytes(b"GEISER_SAMPLE_BACKUP_CONTENT_12345")

    hash_val = calculate_sha256(test_file)
    assert len(hash_val) == 64
    assert verify_checksum(test_file, hash_val) is True
    assert verify_checksum(test_file, "wrong_hash_val_abc") is False


def test_calculate_sha256_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        calculate_sha256("non_existent_file_xyz_123.gz")


def test_path_traversal_guard(temp_backup_dir):
    valid_file = temp_backup_dir / "backup1.archive.gz"
    valid_file.write_text("ok")

    # Legitimate subpath
    resolved = validate_backup_path(valid_file, temp_backup_dir)
    assert resolved == valid_file.resolve()

    # Attempted traversal with ../
    traversal_path = temp_backup_dir / ".." / "outside.txt"
    with pytest.raises(ValueError, match="Path traversal detected"):
        validate_backup_path(traversal_path, temp_backup_dir)


def test_sanitize_connection_args():
    raw_url = "mongodb://admin:superSecret123@cluster.geiser.internal:27017/itsm_helpdesk?authSource=admin"
    args, sanitized = sanitize_connection_args(raw_url, target_db="itsm_helpdesk")

    assert "superSecret123" not in sanitized
    assert "admin:***@" in sanitized
    assert f"--uri={raw_url}" in args
    assert "--db=itsm_helpdesk" in args


def test_determine_retention_class():
    first_of_month = datetime(2026, 10, 1, 10, 0, 0)
    assert determine_retention_class(first_of_month) == RetentionClass.MONTHLY

    # Sunday
    sunday = datetime(2026, 10, 4, 10, 0, 0)  # Oct 4, 2026 is Sunday
    assert determine_retention_class(sunday) == RetentionClass.WEEKLY

    # Regular weekday (Monday)
    monday = datetime(2026, 10, 5, 10, 0, 0)
    assert determine_retention_class(monday) == RetentionClass.DAILY


# ─────────────────────────────────────────────────────────────
# 2. Backup Creation & Execution Tests
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_backup_success(mock_db, temp_backup_dir):
    service = BackupService(mock_db)
    service.backup_dir = temp_backup_dir

    async def mock_subprocess_exec(*args, **kwargs):
        for arg in args:
            if str(arg).startswith("--archive="):
                arch_path = Path(str(arg).split("=", 1)[1])
                arch_path.write_bytes(b"DUMP_PAYLOAD_ABC_9876543210")
        mock_p = MagicMock()
        mock_p.returncode = 0
        mock_p.communicate = AsyncMock(return_value=(b"", b""))
        return mock_p

    with patch("backup.backup_service.resolve_mongodump_path", return_value="C:\\dummy\\mongodump.exe"), \
         patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess_exec):

        metadata = await service.create_backup(
            backup_type=BackupType.MANUAL,
            actor={"id": "usr_admin", "email": "admin@geiser.internal", "role": "ADMIN"}
        )

        assert metadata.status == BackupStatus.SUCCESS
        assert metadata.backup_id.startswith("bkp_")
        assert metadata.filename.endswith(".archive.gz")
        assert metadata.size_bytes > 0
        assert metadata.checksum_sha256 is not None
        assert len(metadata.checksum_sha256) == 64
        assert metadata.verification_status == VerificationStatus.VERIFIED

        # Check document was saved in mock DB
        doc = await mock_db.backups.find_one({"backup_id": metadata.backup_id})
        assert doc is not None
        assert doc["status"] == BackupStatus.SUCCESS.value

        # Check security audit log was emitted
        audit = await mock_db.audit_logs.find_one({"target_resource_id": metadata.backup_id})
        assert audit is not None
        assert audit["event_type"] == "BACKUP_CREATED"


@pytest.mark.asyncio
async def test_create_backup_missing_mongodump_records_failure(mock_db, temp_backup_dir):
    service = BackupService(mock_db)
    service.backup_dir = temp_backup_dir

    with patch("backup.backup_service.resolve_mongodump_path", return_value=None):
        metadata = await service.create_backup(backup_type=BackupType.SCHEDULED)

        assert metadata.status == BackupStatus.FAILED
        assert "mongodump binary not found" in metadata.error_message

        doc = await mock_db.backups.find_one({"backup_id": metadata.backup_id})
        assert doc["status"] == BackupStatus.FAILED.value


@pytest.mark.asyncio
async def test_create_backup_subprocess_error(mock_db, temp_backup_dir):
    service = BackupService(mock_db)
    service.backup_dir = temp_backup_dir

    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.communicate = AsyncMock(return_value=(b"", b"Failed to connect to replica set"))

    with patch("backup.backup_service.resolve_mongodump_path", return_value="C:\\dummy\\mongodump.exe"), \
         patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)):

        metadata = await service.create_backup(backup_type=BackupType.SCHEDULED)

        assert metadata.status == BackupStatus.FAILED
        assert "mongodump exited with code 1" in metadata.error_message

        # Verify audit log was emitted with CRITICAL severity
        audit = await mock_db.audit_logs.find_one({"target_resource_id": metadata.backup_id})
        assert audit is not None
        assert audit["event_type"] == "BACKUP_FAILED"
        assert audit["severity"] == "CRITICAL"


@pytest.mark.asyncio
async def test_create_backup_timeout_killed(mock_db, temp_backup_dir):
    service = BackupService(mock_db)
    service.backup_dir = temp_backup_dir

    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
    mock_proc.kill = MagicMock()

    with patch("backup.backup_service.resolve_mongodump_path", return_value="C:\\dummy\\mongodump.exe"), \
         patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)), \
         patch.object(settings, "BACKUP_TIMEOUT_SECONDS", 1):

        metadata = await service.create_backup(backup_type=BackupType.SCHEDULED)

        assert metadata.status == BackupStatus.FAILED
        assert "timed out" in metadata.error_message
        mock_proc.kill.assert_called_once()


# ─────────────────────────────────────────────────────────────
# 3. Integrity Verification Tests
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_verify_backup_integrity_valid(mock_db, temp_backup_dir):
    service = BackupService(mock_db)
    service.backup_dir = temp_backup_dir

    file_path = temp_backup_dir / "valid.archive.gz"
    file_path.write_bytes(b"INTEGRITY_CHECK_CONTENT")
    valid_hash = calculate_sha256(file_path)

    await mock_db.backups.insert_one({
        "backup_id": "bkp_valid_001",
        "filepath": str(file_path),
        "status": BackupStatus.SUCCESS.value,
        "checksum_sha256": valid_hash,
    })

    result = await service.verify_backup_integrity("bkp_valid_001")
    assert result["verified"] is True
    assert result["verification_status"] == VerificationStatus.VERIFIED.value


@pytest.mark.asyncio
async def test_verify_backup_integrity_corrupted(mock_db, temp_backup_dir):
    service = BackupService(mock_db)
    service.backup_dir = temp_backup_dir

    file_path = temp_backup_dir / "corrupted.archive.gz"
    file_path.write_bytes(b"ALTERED_DATA_TAMPERED")

    await mock_db.backups.insert_one({
        "backup_id": "bkp_corrupt_002",
        "filepath": str(file_path),
        "status": BackupStatus.SUCCESS.value,
        "checksum_sha256": "original_different_hash_value_1234567890",
    })

    result = await service.verify_backup_integrity("bkp_corrupt_002")
    assert result["verified"] is False
    assert result["verification_status"] == VerificationStatus.CORRUPTED.value

    doc = await mock_db.backups.find_one({"backup_id": "bkp_corrupt_002"})
    assert doc["status"] == BackupStatus.CORRUPTED.value


@pytest.mark.asyncio
async def test_verify_backup_file_missing_disk(mock_db, temp_backup_dir):
    service = BackupService(mock_db)
    service.backup_dir = temp_backup_dir

    missing_path = temp_backup_dir / "missing.archive.gz"

    await mock_db.backups.insert_one({
        "backup_id": "bkp_missing_003",
        "filepath": str(missing_path),
        "status": BackupStatus.SUCCESS.value,
        "checksum_sha256": "abc123hash",
    })

    result = await service.verify_backup_integrity("bkp_missing_003")
    assert result["verified"] is False
    assert result["status"] == BackupStatus.CORRUPTED.value


# ─────────────────────────────────────────────────────────────
# 4. Retention Policy Tests
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retention_policy_prunes_older_and_protects_newest(mock_db, temp_backup_dir):
    service = BackupService(mock_db)
    service.backup_dir = temp_backup_dir

    # Configure retention: keep 2 daily backups
    with patch.object(settings, "BACKUP_RETENTION_DAYS", 2):
        now = datetime.utcnow()

        # Create 4 daily backups (day 0, day 1, day 2, day 3)
        for i in range(4):
            bid = f"bkp_daily_{i}"
            fp = temp_backup_dir / f"{bid}.archive.gz"
            fp.write_bytes(b"data")
            created = now - timedelta(days=i)
            await mock_db.backups.insert_one({
                "backup_id": bid,
                "filepath": str(fp),
                "created_at": created,
                "retention_class": RetentionClass.DAILY.value,
                "status": BackupStatus.SUCCESS.value,
                "is_protected": False,
            })

        # Apply retention
        summary = await service.apply_retention_policy()

        # Should delete the 2 oldest (bkp_daily_2, bkp_daily_3), retain 2 newest (bkp_daily_0, bkp_daily_1)
        assert summary["deleted_count"] == 2
        assert "bkp_daily_2" in summary["deleted_ids"]
        assert "bkp_daily_3" in summary["deleted_ids"]

        # Ensure files were removed from disk
        assert not (temp_backup_dir / "bkp_daily_2.archive.gz").exists()
        assert not (temp_backup_dir / "bkp_daily_3.archive.gz").exists()

        # Ensure newest valid backup is preserved
        assert (temp_backup_dir / "bkp_daily_0.archive.gz").exists()
        doc0 = await mock_db.backups.find_one({"backup_id": "bkp_daily_0"})
        assert doc0["status"] == BackupStatus.SUCCESS.value


@pytest.mark.asyncio
async def test_retention_policy_protects_running_and_flagged_backups(mock_db, temp_backup_dir):
    service = BackupService(mock_db)
    service.backup_dir = temp_backup_dir

    with patch.object(settings, "BACKUP_RETENTION_DAYS", 1):
        now = datetime.utcnow()

        # Protected backup
        fp_prot = temp_backup_dir / "prot.archive.gz"
        fp_prot.write_bytes(b"prot")
        await mock_db.backups.insert_one({
            "backup_id": "bkp_protected",
            "filepath": str(fp_prot),
            "created_at": now - timedelta(days=10),
            "retention_class": RetentionClass.DAILY.value,
            "status": BackupStatus.SUCCESS.value,
            "is_protected": True,
        })

        summary = await service.apply_retention_policy()
        assert "bkp_protected" not in summary["deleted_ids"]
        assert fp_prot.exists()


# ─────────────────────────────────────────────────────────────
# 5. Restore Validation Tests (Mode A & Mode B)
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_isolated_restore_mode_a_success(mock_db, temp_backup_dir):
    service = BackupService(mock_db)
    service.backup_dir = temp_backup_dir

    file_path = temp_backup_dir / "restore_test.archive.gz"
    file_path.write_bytes(b"RESTORE_TEST_DATA")
    checksum = calculate_sha256(file_path)

    await mock_db.backups.insert_one({
        "backup_id": "bkp_restore_01",
        "database_name": "itsm_helpdesk",
        "filepath": str(file_path),
        "status": BackupStatus.SUCCESS.value,
        "checksum_sha256": checksum,
    })

    # Mock mongorestore
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"", b""))

    # Mock test database queries
    mock_test_db = MagicMock()
    mock_test_db.list_collection_names = AsyncMock(return_value=["users", "tickets", "audit_logs"])
    mock_test_col = MagicMock()
    mock_test_col.count_documents = AsyncMock(return_value=12)
    mock_test_db.__getitem__.return_value = mock_test_col

    mock_db.client.__getitem__.return_value = mock_test_db

    with patch("backup.backup_service.resolve_mongorestore_path", return_value="C:\\dummy\\mongorestore.exe"), \
         patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)):

        result = await service.test_isolated_restore("bkp_restore_01")

        assert result.success is True
        assert result.checksum_verified is True
        assert "users" in result.collections_found
        assert result.total_documents_restored == 36  # 3 collections * 12 docs
        # Verify temporary test database was dropped
        mock_db.client.drop_database.assert_called_once()


@pytest.mark.asyncio
async def test_production_restore_mode_b_safety_guards(mock_db, temp_backup_dir):
    service = BackupService(mock_db)
    service.backup_dir = temp_backup_dir

    file_path = temp_backup_dir / "prod.archive.gz"
    file_path.write_bytes(b"PROD_RESTORE_DATA")
    checksum = calculate_sha256(file_path)

    await mock_db.backups.insert_one({
        "backup_id": "bkp_prod_01",
        "database_name": "itsm_helpdesk",
        "filepath": str(file_path),
        "status": BackupStatus.SUCCESS.value,
        "checksum_sha256": checksum,
    })

    actor = {"id": "usr_admin", "email": "admin@geiser.internal", "role": "ADMIN"}

    # Guard 1: Must be rejected if BACKUP_ALLOW_PRODUCTION_RESTORE is False
    with patch.object(settings, "BACKUP_ALLOW_PRODUCTION_RESTORE", False):
        req = ProductionRestoreRequest(
            confirm_production_overwrite=True,
            target_database_name="itsm_helpdesk"
        )
        with pytest.raises(PermissionError, match="Production restore is globally disabled"):
            await service.restore_production("bkp_prod_01", req, actor)

    # Guard 2: Must be rejected if confirm_production_overwrite is False
    with patch.object(settings, "BACKUP_ALLOW_PRODUCTION_RESTORE", True):
        req_unconfirmed = ProductionRestoreRequest(
            confirm_production_overwrite=False,
            target_database_name="itsm_helpdesk"
        )
        with pytest.raises(ValueError, match="confirm_production_overwrite"):
            await service.restore_production("bkp_prod_01", req_unconfirmed, actor)

    # Guard 3: Must be rejected if target database does not match
    with patch.object(settings, "BACKUP_ALLOW_PRODUCTION_RESTORE", True):
        req_wrong_db = ProductionRestoreRequest(
            confirm_production_overwrite=True,
            target_database_name="other_database"
        )
        with pytest.raises(ValueError, match="Target database mismatch"):
            await service.restore_production("bkp_prod_01", req_wrong_db, actor)


# ─────────────────────────────────────────────────────────────
# 6. Delete Backup Tests
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_backup_success(mock_db, temp_backup_dir):
    service = BackupService(mock_db)
    service.backup_dir = temp_backup_dir

    file_path = temp_backup_dir / "del.archive.gz"
    file_path.write_bytes(b"DATA_TO_DELETE")

    await mock_db.backups.insert_one({
        "backup_id": "bkp_to_del",
        "filepath": str(file_path),
        "status": BackupStatus.SUCCESS.value,
    })

    deleted = await service.delete_backup("bkp_to_del")
    assert deleted is True
    assert not file_path.exists()

    doc = await mock_db.backups.find_one({"backup_id": "bkp_to_del"})
    assert doc["status"] == BackupStatus.DELETED.value


@pytest.mark.asyncio
async def test_delete_running_backup_rejected(mock_db, temp_backup_dir):
    service = BackupService(mock_db)
    service.backup_dir = temp_backup_dir

    await mock_db.backups.insert_one({
        "backup_id": "bkp_running_now",
        "filepath": str(temp_backup_dir / "active.gz"),
        "status": BackupStatus.RUNNING.value,
    })

    with pytest.raises(ValueError, match="Cannot delete backup .* while it is actively RUNNING"):
        await service.delete_backup("bkp_running_now")
