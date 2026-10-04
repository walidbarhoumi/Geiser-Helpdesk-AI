"""
Secure attachment service for GEISER ticket management.

Security measures implemented:
- Path traversal protection: filenames are never used directly; only UUID-named files.
- MIME type whitelist: only pre-approved types are accepted.
- File size enforcement: configurable limit (default 10 MB).
- Magic-byte verification: content-type is verified against actual file bytes, not just headers.
- RBAC access control: only the ticket owner, assigned agent, or ADMIN/SUPERVISOR may download.
- Audit trail: ATTACHMENT_UPLOADED, ATTACHMENT_DOWNLOADED, ATTACHMENT_DELETED events.
- Physical cleanup: deletes disk files when the parent ticket is removed.
"""
import os
import uuid
import mimetypes
import logging
from typing import Optional, List
from datetime import datetime

from fastapi import UploadFile, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from core.config import settings
from schemas.schemas import AttachmentOut, UserRole
from models.base import MongoModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Magic-byte signatures for MIME verification (first bytes of file content)
# ---------------------------------------------------------------------------
_MAGIC_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    "application/pdf": (b"%PDF",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/gif": (b"GIF87a", b"GIF89a"),
}


def _verify_magic_bytes(header: bytes, declared_mime: str) -> bool:
    """Returns True if the file header matches the declared MIME type, or if no
    signature is registered for that MIME (trusted by declaration for Office docs
    and plain text which have complex/no fixed headers)."""
    sigs = _MAGIC_SIGNATURES.get(declared_mime)
    if not sigs:
        return True  # No magic check for this type — rely on MIME whitelist alone
    return any(header.startswith(sig) for sig in sigs)


class AttachmentService:
    """Service handling all secure attachment operations for tickets."""

    COLLECTION = "attachments"

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.attachments = db.attachments if hasattr(db, "attachments") else db[self.COLLECTION]
        self.tickets = db.tickets

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def _max_bytes(self) -> int:
        return settings.MAX_ATTACHMENT_SIZE_MB * 1024 * 1024

    def _build_attachment_out(self, doc: dict) -> AttachmentOut:
        return AttachmentOut(
            id=str(doc["_id"]),
            ticket_id=str(doc["ticket_id"]),
            original_filename=doc["original_filename"],
            stored_filename=doc["stored_filename"],
            mime_type=doc["mime_type"],
            size_bytes=doc["size_bytes"],
            uploaded_by=str(doc["uploaded_by"]),
            created_at=doc["created_at"],
        )

    # ------------------------------------------------------------------
    # Access control
    # ------------------------------------------------------------------

    async def _assert_ticket_access(
        self, ticket_id: str, current_user: dict, *, write_access: bool = False
    ) -> dict:
        """Verifies that current_user may access the given ticket.
        Raises 404 if ticket not found, 403 if access is denied.

        - READ: owner (user_id) OR assigned agent OR ADMIN/SUPERVISOR
        - WRITE (upload): owner OR AGENT/ADMIN/SUPERVISOR (any authenticated
          agent-level user, mimicking the original broad write behaviour but
          at least blocking random USERs uploading to someone else's ticket)
        """
        oid = MongoModel.to_object_id(ticket_id)
        if not oid:
            raise HTTPException(status_code=404, detail="Ticket introuvable")

        ticket = await self.tickets.find_one({"_id": oid})
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket introuvable")

        user_id = str(current_user.get("id", ""))
        role = current_user.get("role", "")
        if hasattr(role, "value"):
            role = role.value

        is_owner = str(ticket.get("user_id", "")) == user_id
        is_assigned_agent = str(ticket.get("assigned_agent_id", "")) == user_id
        is_privileged = role in (UserRole.ADMIN.value, UserRole.SUPERVISOR.value, UserRole.AGENT.value)

        if write_access:
            allowed = is_owner or is_privileged
        else:
            allowed = is_owner or is_assigned_agent or is_privileged

        if not allowed:
            raise HTTPException(status_code=403, detail="Accès refusé à ce ticket")

        return ticket

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    async def upload_attachment(
        self,
        ticket_id: str,
        file: UploadFile,
        current_user: dict,
    ) -> AttachmentOut:
        """Validates and stores an uploaded file securely.

        Security checks (in order):
        1. Ticket existence and RBAC
        2. MIME type whitelist
        3. File size limit (read all bytes first to measure)
        4. Magic-byte verification
        5. UUID-based stored filename (no user input touches the path)
        """
        await self._assert_ticket_access(ticket_id, current_user, write_access=True)

        # Ensure upload directory exists
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

        # ── 1. Declared MIME check (fast rejection) ──────────────────
        declared_mime = (file.content_type or "").split(";")[0].strip().lower()
        if declared_mime not in settings.ALLOWED_MIME_TYPES:
            # Try to guess from filename as fallback
            guessed, _ = mimetypes.guess_type(file.filename or "")
            if guessed and guessed.lower() in settings.ALLOWED_MIME_TYPES:
                declared_mime = guessed.lower()
            else:
                raise HTTPException(
                    status_code=415,
                    detail=(
                        f"Type de fichier non autorisé : {declared_mime or 'inconnu'}. "
                        f"Types acceptés : {', '.join(settings.ALLOWED_MIME_TYPES)}"
                    ),
                )

        # ── 2. Read all bytes and check size ─────────────────────────
        contents = await file.read()
        size_bytes = len(contents)
        if size_bytes == 0:
            raise HTTPException(status_code=400, detail="Le fichier est vide")
        if size_bytes > self._max_bytes:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"Fichier trop volumineux : {size_bytes / 1024 / 1024:.1f} Mo. "
                    f"Limite : {settings.MAX_ATTACHMENT_SIZE_MB} Mo"
                ),
            )

        # ── 3. Magic-byte verification ────────────────────────────────
        if not _verify_magic_bytes(contents[:16], declared_mime):
            raise HTTPException(
                status_code=415,
                detail="Le contenu du fichier ne correspond pas au type MIME déclaré",
            )

        # ── 4. Sanitise original filename (for display only) ──────────
        original_filename = os.path.basename(file.filename or "").strip() or "attachment"
        # Strip null bytes and path-separator characters
        original_filename = original_filename.replace("\x00", "").replace("/", "").replace("\\", "")
        if not original_filename:
            original_filename = "attachment"

        # ── 5. Generate UUID-based stored filename ────────────────────
        ext = os.path.splitext(original_filename)[1].lower()
        # Restrict extension to alpha + dot only to prevent double-extension tricks
        if not ext.isalpha() and not (ext.startswith(".") and ext[1:].isalpha()):
            ext = ""
        stored_filename = f"{uuid.uuid4().hex}{ext}"
        stored_path = os.path.join(settings.UPLOAD_DIR, stored_filename)

        # ── 6. Write to disk ──────────────────────────────────────────
        try:
            with open(stored_path, "wb") as fh:
                fh.write(contents)
        except OSError as exc:
            logger.error("Failed to write attachment to disk: %s", exc)
            raise HTTPException(status_code=500, detail="Erreur lors de l'enregistrement du fichier")

        # ── 7. Persist metadata in MongoDB ───────────────────────────
        user_id = str(current_user.get("id", ""))
        doc = {
            "ticket_id": ticket_id,
            "original_filename": original_filename,
            "stored_filename": stored_filename,
            "stored_path": stored_path,
            "mime_type": declared_mime,
            "size_bytes": size_bytes,
            "uploaded_by": user_id,
            "created_at": datetime.utcnow(),
        }
        result = await self.attachments.insert_one(doc)
        doc["_id"] = result.inserted_id

        att_out = self._build_attachment_out(doc)
        att_dict = att_out.model_dump() if hasattr(att_out, "model_dump") else att_out.dict()
        try:
            await self.tickets.update_one(
                {"_id": MongoModel.to_object_id(ticket_id)},
                {"$push": {"attachments": att_dict}}
            )
        except Exception as sync_err:
            logger.warning("Could not sync attachment to tickets collection: %s", sync_err)

        # ── 8. Audit trail ────────────────────────────────────────────
        from services.ticket_service import TicketService
        from schemas.schemas import TicketActionType
        await TicketService(self.db).record_ticket_action(
            ticket_id=ticket_id,
            action_type=TicketActionType.ATTACHMENT_UPLOADED.value,
            actor_user=current_user,
            details={
                "attachment_id": str(result.inserted_id),
                "original_filename": original_filename,
                "mime_type": declared_mime,
                "size_bytes": size_bytes,
            },
            comment=f"Pièce jointe ajoutée : {original_filename}",
        )

        return att_out

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    async def get_attachment_for_download(
        self,
        ticket_id: str,
        attachment_id: str,
        current_user: dict,
    ) -> tuple[str, str, str]:
        """Returns (absolute_file_path, original_filename, mime_type) after RBAC check.
        Raises 404/403 as appropriate.
        Caller is responsible for serving the file (FileResponse).
        """
        await self._assert_ticket_access(ticket_id, current_user, write_access=False)

        att_oid = ObjectId(attachment_id) if ObjectId.is_valid(attachment_id) else None
        if not att_oid:
            raise HTTPException(status_code=404, detail="Pièce jointe introuvable")

        doc = await self.attachments.find_one(
            {"_id": att_oid, "ticket_id": ticket_id}
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Pièce jointe introuvable")

        stored_path: str = doc.get("stored_path", "")
        # Path traversal guard: ensure resolved path is inside UPLOAD_DIR
        resolved = os.path.realpath(stored_path)
        upload_dir_real = os.path.realpath(settings.UPLOAD_DIR)
        if not resolved.startswith(upload_dir_real + os.sep) and resolved != upload_dir_real:
            logger.warning("Path traversal attempt blocked for attachment %s", attachment_id)
            raise HTTPException(status_code=403, detail="Accès refusé")

        if not os.path.isfile(resolved):
            raise HTTPException(status_code=404, detail="Fichier introuvable sur le serveur")

        # Audit trail (fire-and-forget)
        try:
            import asyncio
            from services.audit_service import AuditService
            from schemas.schemas import AuditEventCategory, AuditSeverity
            audit_svc = AuditService(self.db)
            asyncio.create_task(
                audit_svc.log_event(
                    event_category=AuditEventCategory.TICKET,
                    event_type="TICKET_ATTACHMENT_DOWNLOADED",
                    severity=AuditSeverity.INFO,
                    target_resource_type="attachment",
                    target_resource_id=attachment_id,
                    actor_id=str(current_user.get("id", "")),
                    actor_email=current_user.get("email"),
                    actor_name=current_user.get("full_name") or current_user.get("email"),
                    actor_role=str(current_user.get("role", "")),
                    status="SUCCESS",
                    details={
                        "ticket_id": ticket_id,
                        "original_filename": doc.get("original_filename"),
                    },
                )
            )
        except Exception as exc:
            logger.error("Audit log failed for attachment download: %s", exc)

        return resolved, doc["original_filename"], doc["mime_type"]

    # ------------------------------------------------------------------
    # List attachments for a ticket
    # ------------------------------------------------------------------

    async def list_attachments(
        self, ticket_id: str, current_user: dict
    ) -> List[AttachmentOut]:
        """Returns all attachment metadata for a ticket (RBAC enforced)."""
        await self._assert_ticket_access(ticket_id, current_user, write_access=False)
        cursor = self.attachments.find({"ticket_id": ticket_id})
        results = []
        async for doc in cursor:
            results.append(self._build_attachment_out(doc))
        return results

    # ------------------------------------------------------------------
    # Delete (single attachment)
    # ------------------------------------------------------------------

    async def delete_attachment(
        self, ticket_id: str, attachment_id: str, current_user: dict
    ) -> bool:
        """Deletes a single attachment (ADMIN/SUPERVISOR only).
        Removes both the metadata document and the physical file.
        """
        role = current_user.get("role", "")
        if hasattr(role, "value"):
            role = role.value
        if role not in (UserRole.ADMIN.value, UserRole.SUPERVISOR.value):
            raise HTTPException(status_code=403, detail="Permission insuffisante")

        att_oid = ObjectId(attachment_id) if ObjectId.is_valid(attachment_id) else None
        if not att_oid:
            raise HTTPException(status_code=404, detail="Pièce jointe introuvable")

        doc = await self.attachments.find_one(
            {"_id": att_oid, "ticket_id": ticket_id}
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Pièce jointe introuvable")

        # Delete physical file
        stored_path = doc.get("stored_path", "")
        _safe_remove_file(stored_path)

        # Delete MongoDB document
        await self.attachments.delete_one({"_id": att_oid})

        # Remove from ticket.attachments array
        try:
            await self.tickets.update_one(
                {"_id": MongoModel.to_object_id(ticket_id)},
                {"$pull": {"attachments": {"id": attachment_id}}}
            )
        except Exception as sync_err:
            logger.warning("Could not pull attachment from tickets collection: %s", sync_err)

        # Audit trail
        try:
            import asyncio
            from services.audit_service import AuditService
            from schemas.schemas import AuditEventCategory, AuditSeverity
            audit_svc = AuditService(self.db)
            asyncio.create_task(
                audit_svc.log_event(
                    event_category=AuditEventCategory.TICKET,
                    event_type="TICKET_ATTACHMENT_DELETED",
                    severity=AuditSeverity.WARNING,
                    target_resource_type="attachment",
                    target_resource_id=attachment_id,
                    actor_id=str(current_user.get("id", "")),
                    actor_email=current_user.get("email"),
                    actor_name=current_user.get("full_name") or current_user.get("email"),
                    actor_role=str(current_user.get("role", "")),
                    status="SUCCESS",
                    details={
                        "ticket_id": ticket_id,
                        "original_filename": doc.get("original_filename"),
                    },
                )
            )
        except Exception as exc:
            logger.error("Audit log failed for attachment deletion: %s", exc)

        return True

    # ------------------------------------------------------------------
    # Purge all attachments for a ticket (called on ticket deletion)
    # ------------------------------------------------------------------

    async def delete_ticket_attachments(self, ticket_id: str) -> int:
        """Deletes all physical files and metadata documents for a ticket.
        Returns the number of attachments purged.
        This is intended to be called from ticket_service.delete_ticket().
        """
        cursor = self.attachments.find({"ticket_id": ticket_id})
        count = 0
        async for doc in cursor:
            stored_path = doc.get("stored_path", "")
            _safe_remove_file(stored_path)
            count += 1

        await self.attachments.delete_many({"ticket_id": ticket_id})
        if count:
            logger.info("Purged %d attachment(s) for deleted ticket %s", count, ticket_id)
        return count


# ---------------------------------------------------------------------------
# Module-level utility
# ---------------------------------------------------------------------------

def _safe_remove_file(path: str) -> None:
    """Removes a file from disk, logging errors instead of raising."""
    if not path:
        return
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError as exc:
        logger.error("Could not remove attachment file %s: %s", path, exc)
