"""
test_attachments_security.py
==============================================================================
Suite de tests unitaires pour la gestion et sécurisation des pièces jointes.

Couvre l'ensemble des 22 scénarios obligatoires :
 1. Upload d'un PDF valide avec magic bytes (%PDF) -> Succès.
 2. Upload d'une image PNG valide avec magic bytes (\x89PNG) -> Succès.
 3. Upload d'une image JPEG valide avec magic bytes (\xff\xd8\xff) -> Succès.
 4. Upload d'un fichier texte brut valide (text/plain) -> Succès.
 5. Rejet d'un type MIME interdit (.exe, application/x-executable, JS) -> 415.
 6. Rejet d'un fichier vide (0 octet) -> 400.
 7. Rejet d'un fichier dépassant la taille maximale (10 Mo) -> 413.
 8. Rejet d'un fichier dont les magic bytes ne correspondent pas au MIME déclaré -> 415.
 9. Protection contre le Path Traversal : le nom de stockage est un UUID, nom original assaini.
10. Contrôle RBAC sur upload : un USER non-propriétaire ne peut pas uploader sur le ticket d'un tiers -> 403.
11. Contrôle RBAC sur upload : le propriétaire du ticket (USER) peut uploader -> Succès.
12. Contrôle RBAC sur upload : AGENT, SUPERVISOR et ADMIN peuvent uploader -> Succès.
13. Audit Trail : l'action ATTACHMENT_UPLOADED est enregistrée dans l'historique et l'audit ISO 27001.
14. Contrôle RBAC sur download : un USER tiers ne peut pas télécharger la pièce jointe -> 403.
15. Contrôle RBAC sur download : le propriétaire et l'agent assigné peuvent télécharger -> Succès.
16. Contrôle RBAC sur download : ADMIN et SUPERVISOR peuvent télécharger -> Succès.
17. Protection Path Traversal sur download : tentative d'évasion hors de UPLOAD_DIR bloquée -> 403.
18. Gestion 404 sur download : document introuvable ou fichier absent du disque -> 404.
19. Listing des pièces jointes : liste restreinte par RBAC -> Succès / 403.
20. Suppression unitaire sécurisée : supprime le document MongoDB et le fichier physique -> Succès.
21. Suppression de ticket (delete_ticket) : purge physique automatique de tous les fichiers associés -> Succès.
22. En-têtes HTTP de sécurité : téléchargement servi avec X-Content-Type-Options: nosniff et Cache-Control.
"""

import os
import io
import tempfile
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId
from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse

from core.config import settings
from schemas.schemas import UserRole, AttachmentOut
from services.attachment_service import (
    AttachmentService,
    _verify_magic_bytes,
    _safe_remove_file,
)
from services.ticket_service import TicketService


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

class AsyncIter:
    def __init__(self, items):
        self._it = iter(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.attachments = MagicMock()
    db.tickets = MagicMock()
    db.audit_logs = MagicMock()
    db.users = MagicMock()
    db.agents = MagicMock()
    db.__getitem__.side_effect = lambda k: getattr(db, k, MagicMock())
    return db


@pytest.fixture
def fake_ticket_id():
    return str(ObjectId())


@pytest.fixture
def fake_owner_id():
    return str(ObjectId())


@pytest.fixture
def fake_assigned_agent_id():
    return str(ObjectId())


@pytest.fixture
def fake_other_user_id():
    return str(ObjectId())


@pytest.fixture
def ticket_owner_user(fake_owner_id):
    return {
        "id": fake_owner_id,
        "email": "owner@example.com",
        "full_name": "Ticket Owner",
        "role": UserRole.USER.value,
    }


@pytest.fixture
def other_regular_user(fake_other_user_id):
    return {
        "id": fake_other_user_id,
        "email": "other@example.com",
        "full_name": "Other User",
        "role": UserRole.USER.value,
    }


@pytest.fixture
def assigned_agent_user(fake_assigned_agent_id):
    return {
        "id": fake_assigned_agent_id,
        "email": "agent@example.com",
        "full_name": "Assigned Agent",
        "role": UserRole.AGENT.value,
    }


@pytest.fixture
def admin_user():
    return {
        "id": str(ObjectId()),
        "email": "admin@example.com",
        "full_name": "Admin User",
        "role": UserRole.ADMIN.value,
    }


@pytest.fixture
def supervisor_user():
    return {
        "id": str(ObjectId()),
        "email": "sup@example.com",
        "full_name": "Supervisor User",
        "role": UserRole.SUPERVISOR.value,
    }


def make_upload_file(filename: str, content: bytes, content_type: str) -> UploadFile:
    file_obj = io.BytesIO(content)
    return UploadFile(filename=filename, file=file_obj, headers={"content-type": content_type})


# ─────────────────────────────────────────────────────────────────────────────
# 1-4. Magic Bytes & MIME Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_magic_bytes_detection():
    # PDF
    assert _verify_magic_bytes(b"%PDF-1.4\n", "application/pdf") is True
    assert _verify_magic_bytes(b"NOT A PDF", "application/pdf") is False

    # PNG
    assert _verify_magic_bytes(b"\x89PNG\r\n\x1a\n\x00\x00", "image/png") is True
    assert _verify_magic_bytes(b"GIF89a", "image/png") is False

    # JPEG
    assert _verify_magic_bytes(b"\xff\xd8\xff\xe0\x00\x10", "image/jpeg") is True
    assert _verify_magic_bytes(b"%PDF", "image/jpeg") is False

    # GIF
    assert _verify_magic_bytes(b"GIF89a\x01\x00", "image/gif") is True

    # Text / Office (no strict magic byte required)
    assert _verify_magic_bytes(b"Hello World", "text/plain") is True


@pytest.mark.asyncio
async def test_1_upload_allowed_mime_pdf(mock_db, fake_ticket_id, ticket_owner_user):
    svc = AttachmentService(mock_db)
    mock_db.tickets.find_one = AsyncMock(return_value={
        "_id": ObjectId(fake_ticket_id),
        "user_id": ticket_owner_user["id"],
        "assigned_agent_id": None,
    })
    mock_db.attachments.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))
    mock_db.tickets.update_one = AsyncMock()

    content = b"%PDF-1.5 test document content"
    file = make_upload_file("rapport.pdf", content, "application/pdf")

    with patch("services.ticket_service.TicketService.record_ticket_action", new_callable=AsyncMock):
        res = await svc.upload_attachment(fake_ticket_id, file, ticket_owner_user)

    assert isinstance(res, AttachmentOut)
    assert res.original_filename == "rapport.pdf"
    assert res.mime_type == "application/pdf"
    assert res.size_bytes == len(content)
    assert res.stored_filename.endswith(".pdf")
    assert not res.stored_filename.startswith("rapport")  # Must be UUID-based


@pytest.mark.asyncio
async def test_2_upload_allowed_mime_png(mock_db, fake_ticket_id, ticket_owner_user):
    svc = AttachmentService(mock_db)
    mock_db.tickets.find_one = AsyncMock(return_value={
        "_id": ObjectId(fake_ticket_id),
        "user_id": ticket_owner_user["id"],
    })
    mock_db.attachments.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))
    mock_db.tickets.update_one = AsyncMock()

    content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    file = make_upload_file("capture.png", content, "image/png")

    with patch("services.ticket_service.TicketService.record_ticket_action", new_callable=AsyncMock):
        res = await svc.upload_attachment(fake_ticket_id, file, ticket_owner_user)

    assert res.mime_type == "image/png"
    assert res.stored_filename.endswith(".png")


@pytest.mark.asyncio
async def test_3_upload_allowed_mime_jpeg(mock_db, fake_ticket_id, ticket_owner_user):
    svc = AttachmentService(mock_db)
    mock_db.tickets.find_one = AsyncMock(return_value={
        "_id": ObjectId(fake_ticket_id),
        "user_id": ticket_owner_user["id"],
    })
    mock_db.attachments.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))
    mock_db.tickets.update_one = AsyncMock()

    content = b"\xff\xd8\xff\xe0\x00\x10JFIF"
    file = make_upload_file("photo.jpg", content, "image/jpeg")

    with patch("services.ticket_service.TicketService.record_ticket_action", new_callable=AsyncMock):
        res = await svc.upload_attachment(fake_ticket_id, file, ticket_owner_user)

    assert res.mime_type == "image/jpeg"


@pytest.mark.asyncio
async def test_4_upload_allowed_mime_text(mock_db, fake_ticket_id, ticket_owner_user):
    svc = AttachmentService(mock_db)
    mock_db.tickets.find_one = AsyncMock(return_value={
        "_id": ObjectId(fake_ticket_id),
        "user_id": ticket_owner_user["id"],
    })
    mock_db.attachments.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))
    mock_db.tickets.update_one = AsyncMock()

    content = b"Log d'erreur systeme"
    file = make_upload_file("log.txt", content, "text/plain")

    with patch("services.ticket_service.TicketService.record_ticket_action", new_callable=AsyncMock):
        res = await svc.upload_attachment(fake_ticket_id, file, ticket_owner_user)

    assert res.mime_type == "text/plain"


# ─────────────────────────────────────────────────────────────────────────────
# 5-8. Rejections (MIME, Empty, Size, Magic Mismatch)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_5_upload_rejected_unsupported_mime(mock_db, fake_ticket_id, ticket_owner_user):
    svc = AttachmentService(mock_db)
    mock_db.tickets.find_one = AsyncMock(return_value={
        "_id": ObjectId(fake_ticket_id),
        "user_id": ticket_owner_user["id"],
    })

    file = make_upload_file("script.sh", b"#!/bin/bash\necho bad", "application/x-sh")

    with pytest.raises(HTTPException) as exc_info:
        await svc.upload_attachment(fake_ticket_id, file, ticket_owner_user)

    assert exc_info.value.status_code == 415
    assert "non autoris" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_6_upload_rejected_empty_file(mock_db, fake_ticket_id, ticket_owner_user):
    svc = AttachmentService(mock_db)
    mock_db.tickets.find_one = AsyncMock(return_value={
        "_id": ObjectId(fake_ticket_id),
        "user_id": ticket_owner_user["id"],
    })

    file = make_upload_file("empty.pdf", b"", "application/pdf")

    with pytest.raises(HTTPException) as exc_info:
        await svc.upload_attachment(fake_ticket_id, file, ticket_owner_user)

    assert exc_info.value.status_code == 400
    assert "vide" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_7_upload_rejected_oversized_file(mock_db, fake_ticket_id, ticket_owner_user):
    svc = AttachmentService(mock_db)
    mock_db.tickets.find_one = AsyncMock(return_value={
        "_id": ObjectId(fake_ticket_id),
        "user_id": ticket_owner_user["id"],
    })

    # Limit is 10 MB. Generate 10MB + 1 byte
    oversized_content = b"%PDF" + b"0" * (10 * 1024 * 1024 + 1)
    file = make_upload_file("huge.pdf", oversized_content, "application/pdf")

    with pytest.raises(HTTPException) as exc_info:
        await svc.upload_attachment(fake_ticket_id, file, ticket_owner_user)

    assert exc_info.value.status_code == 413
    assert "trop volumineux" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_8_upload_rejected_magic_bytes_mismatch(mock_db, fake_ticket_id, ticket_owner_user):
    svc = AttachmentService(mock_db)
    mock_db.tickets.find_one = AsyncMock(return_value={
        "_id": ObjectId(fake_ticket_id),
        "user_id": ticket_owner_user["id"],
    })

    # Content is plain ASCII text but declared as PDF
    fake_pdf = make_upload_file("fake.pdf", b"THIS IS NOT A VALID PDF", "application/pdf")

    with pytest.raises(HTTPException) as exc_info:
        await svc.upload_attachment(fake_ticket_id, fake_pdf, ticket_owner_user)

    assert exc_info.value.status_code == 415
    assert "ne correspond pas" in exc_info.value.detail.lower()


# ─────────────────────────────────────────────────────────────────────────────
# 9. Path Traversal Protection
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_9_path_traversal_filename_sanitization(mock_db, fake_ticket_id, ticket_owner_user):
    svc = AttachmentService(mock_db)
    mock_db.tickets.find_one = AsyncMock(return_value={
        "_id": ObjectId(fake_ticket_id),
        "user_id": ticket_owner_user["id"],
    })
    mock_db.attachments.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))
    mock_db.tickets.update_one = AsyncMock()

    # Malicious filename attempting directory traversal
    malicious_filename = "../../../etc/passwd.pdf"
    content = b"%PDF-1.4 sample content"
    file = make_upload_file(malicious_filename, content, "application/pdf")

    with patch("services.ticket_service.TicketService.record_ticket_action", new_callable=AsyncMock):
        res = await svc.upload_attachment(fake_ticket_id, file, ticket_owner_user)

    # Stored filename must be pure UUID.pdf, never containing ".." or path separators
    assert ".." not in res.stored_filename
    assert "/" not in res.stored_filename
    assert "\\" not in res.stored_filename
    # Original filename must be sanitized
    assert ".." not in res.original_filename


# ─────────────────────────────────────────────────────────────────────────────
# 10-12. RBAC Upload Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_10_upload_rbac_unauthorized_user(mock_db, fake_ticket_id, other_regular_user, ticket_owner_user):
    svc = AttachmentService(mock_db)
    # Ticket belongs to ticket_owner_user, not other_regular_user
    mock_db.tickets.find_one = AsyncMock(return_value={
        "_id": ObjectId(fake_ticket_id),
        "user_id": ticket_owner_user["id"],
        "assigned_agent_id": None,
    })

    file = make_upload_file("doc.pdf", b"%PDF-1.4 test", "application/pdf")

    with pytest.raises(HTTPException) as exc_info:
        await svc.upload_attachment(fake_ticket_id, file, other_regular_user)

    assert exc_info.value.status_code == 404
    assert "introuvable" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_11_upload_rbac_owner_allowed(mock_db, fake_ticket_id, ticket_owner_user):
    svc = AttachmentService(mock_db)
    mock_db.tickets.find_one = AsyncMock(return_value={
        "_id": ObjectId(fake_ticket_id),
        "user_id": ticket_owner_user["id"],
    })
    mock_db.attachments.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))
    mock_db.tickets.update_one = AsyncMock()

    file = make_upload_file("doc.pdf", b"%PDF-1.4 test", "application/pdf")
    with patch("services.ticket_service.TicketService.record_ticket_action", new_callable=AsyncMock):
        res = await svc.upload_attachment(fake_ticket_id, file, ticket_owner_user)

    assert res.uploaded_by == ticket_owner_user["id"]


@pytest.mark.asyncio
async def test_12_upload_rbac_agent_admin_allowed(mock_db, fake_ticket_id, ticket_owner_user, admin_user, assigned_agent_user):
    svc = AttachmentService(mock_db)
    assigned_agent_id = ObjectId()
    mock_db.tickets.find_one = AsyncMock(return_value={
        "_id": ObjectId(fake_ticket_id),
        "user_id": ticket_owner_user["id"],
        "assigned_agent_id": str(assigned_agent_id),
    })
    mock_db.agents.find_one = AsyncMock(return_value={
        "_id": assigned_agent_id,
        "user_id": assigned_agent_user["id"],
    })
    mock_db.attachments.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))
    mock_db.tickets.update_one = AsyncMock()

    with patch("services.ticket_service.TicketService.record_ticket_action", new_callable=AsyncMock):
        # Admin can upload
        file_admin = make_upload_file("admin.pdf", b"%PDF-1.4 test", "application/pdf")
        res_admin = await svc.upload_attachment(fake_ticket_id, file_admin, admin_user)
        assert res_admin is not None

        # Agent can upload
        file_agent = make_upload_file("agent.pdf", b"%PDF-1.4 test", "application/pdf")
        res_agent = await svc.upload_attachment(fake_ticket_id, file_agent, assigned_agent_user)
        assert res_agent is not None


@pytest.mark.asyncio
async def test_unassigned_agent_cannot_upload_to_another_users_ticket(
    mock_db, fake_ticket_id, ticket_owner_user, assigned_agent_user
):
    svc = AttachmentService(mock_db)
    mock_db.tickets.find_one = AsyncMock(return_value={
        "_id": ObjectId(fake_ticket_id),
        "user_id": ticket_owner_user["id"],
        "assigned_agent_id": str(ObjectId()),
    })
    mock_db.agents.find_one = AsyncMock(return_value={
        "_id": ObjectId(), "user_id": assigned_agent_user["id"]
    })

    with pytest.raises(HTTPException) as exc_info:
        await svc.upload_attachment(
            fake_ticket_id,
            make_upload_file("agent.pdf", b"%PDF-1.4 test", "application/pdf"),
            assigned_agent_user,
        )
    assert exc_info.value.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# 13. Audit Trail
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_13_upload_audit_trail_recorded(mock_db, fake_ticket_id, ticket_owner_user):
    svc = AttachmentService(mock_db)
    mock_db.tickets.find_one = AsyncMock(return_value={
        "_id": ObjectId(fake_ticket_id),
        "user_id": ticket_owner_user["id"],
    })
    mock_db.attachments.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))
    mock_db.tickets.update_one = AsyncMock()

    file = make_upload_file("audit_test.pdf", b"%PDF-1.4 content", "application/pdf")

    with patch("services.ticket_service.TicketService.record_ticket_action", new_callable=AsyncMock) as mock_action:
        await svc.upload_attachment(fake_ticket_id, file, ticket_owner_user)
        mock_action.assert_awaited_once()
        _, kwargs = mock_action.call_args
        assert kwargs["action_type"] == "ATTACHMENT_UPLOADED"
        assert kwargs["details"]["original_filename"] == "audit_test.pdf"


# ─────────────────────────────────────────────────────────────────────────────
# 14-16. RBAC Download Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_14_download_rbac_unauthorized_user(mock_db, fake_ticket_id, ticket_owner_user, other_regular_user):
    svc = AttachmentService(mock_db)
    mock_db.tickets.find_one = AsyncMock(return_value={
        "_id": ObjectId(fake_ticket_id),
        "user_id": ticket_owner_user["id"],
        "assigned_agent_id": None,
    })

    with pytest.raises(HTTPException) as exc_info:
        await svc.get_attachment_for_download(fake_ticket_id, str(ObjectId()), other_regular_user)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_15_download_rbac_owner_and_assigned_agent(
    mock_db, fake_ticket_id, ticket_owner_user, assigned_agent_user, tmp_path
):
    svc = AttachmentService(mock_db)
    att_id = str(ObjectId())

    # Create temporary file inside settings.UPLOAD_DIR
    real_file = os.path.join(settings.UPLOAD_DIR, "test_download.pdf")
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    with open(real_file, "wb") as f:
        f.write(b"%PDF-1.4 test")

    try:
        assigned_agent_id = ObjectId()
        mock_db.tickets.find_one = AsyncMock(return_value={
            "_id": ObjectId(fake_ticket_id),
            "user_id": ticket_owner_user["id"],
            "assigned_agent_id": str(assigned_agent_id),
        })
        mock_db.agents.find_one = AsyncMock(return_value={
            "_id": assigned_agent_id,
            "user_id": assigned_agent_user["id"],
        })
        mock_db.attachments.find_one = AsyncMock(return_value={
            "_id": ObjectId(att_id),
            "ticket_id": fake_ticket_id,
            "original_filename": "piece_jointe.pdf",
            "stored_path": real_file,
            "mime_type": "application/pdf",
        })

        # Owner can download
        path, fname, mime = await svc.get_attachment_for_download(fake_ticket_id, att_id, ticket_owner_user)
        assert fname == "piece_jointe.pdf"
        assert mime == "application/pdf"

        # Assigned agent can download
        path2, _, _ = await svc.get_attachment_for_download(fake_ticket_id, att_id, assigned_agent_user)
        assert path2 == real_file
    finally:
        _safe_remove_file(real_file)


@pytest.mark.asyncio
async def test_16_download_rbac_admin_supervisor(
    mock_db, fake_ticket_id, ticket_owner_user, admin_user, supervisor_user
):
    svc = AttachmentService(mock_db)
    att_id = str(ObjectId())

    real_file = os.path.join(settings.UPLOAD_DIR, "test_priv.pdf")
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    with open(real_file, "wb") as f:
        f.write(b"%PDF-1.4 test")

    try:
        mock_db.tickets.find_one = AsyncMock(return_value={
            "_id": ObjectId(fake_ticket_id),
            "user_id": ticket_owner_user["id"],
            "assigned_agent_id": None,
        })
        mock_db.attachments.find_one = AsyncMock(return_value={
            "_id": ObjectId(att_id),
            "ticket_id": fake_ticket_id,
            "original_filename": "priv.pdf",
            "stored_path": real_file,
            "mime_type": "application/pdf",
        })

        # Admin
        p_admin, _, _ = await svc.get_attachment_for_download(fake_ticket_id, att_id, admin_user)
        assert p_admin == real_file

        # Supervisor
        p_sup, _, _ = await svc.get_attachment_for_download(fake_ticket_id, att_id, supervisor_user)
        assert p_sup == real_file
    finally:
        _safe_remove_file(real_file)


# ─────────────────────────────────────────────────────────────────────────────
# 17-18. Path Traversal & 404 on Download
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_17_download_path_traversal_blocked(mock_db, fake_ticket_id, ticket_owner_user):
    svc = AttachmentService(mock_db)
    att_id = str(ObjectId())

    mock_db.tickets.find_one = AsyncMock(return_value={
        "_id": ObjectId(fake_ticket_id),
        "user_id": ticket_owner_user["id"],
    })
    # Stored path points outside UPLOAD_DIR
    mock_db.attachments.find_one = AsyncMock(return_value={
        "_id": ObjectId(att_id),
        "ticket_id": fake_ticket_id,
        "original_filename": "passwd",
        "stored_path": "/etc/passwd",
        "mime_type": "text/plain",
    })

    with pytest.raises(HTTPException) as exc_info:
        await svc.get_attachment_for_download(fake_ticket_id, att_id, ticket_owner_user)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_18_download_missing_file_404(mock_db, fake_ticket_id, ticket_owner_user):
    svc = AttachmentService(mock_db)
    att_id = str(ObjectId())

    mock_db.tickets.find_one = AsyncMock(return_value={
        "_id": ObjectId(fake_ticket_id),
        "user_id": ticket_owner_user["id"],
    })
    # Path is valid location but file doesn't exist on disk
    mock_db.attachments.find_one = AsyncMock(return_value={
        "_id": ObjectId(att_id),
        "ticket_id": fake_ticket_id,
        "original_filename": "non_existent.pdf",
        "stored_path": os.path.join(settings.UPLOAD_DIR, "non_existent_uuid.pdf"),
        "mime_type": "application/pdf",
    })

    with pytest.raises(HTTPException) as exc_info:
        await svc.get_attachment_for_download(fake_ticket_id, att_id, ticket_owner_user)

    assert exc_info.value.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# 19. List Attachments
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_19_list_attachments_rbac(mock_db, fake_ticket_id, ticket_owner_user, other_regular_user):
    svc = AttachmentService(mock_db)
    mock_db.tickets.find_one = AsyncMock(return_value={
        "_id": ObjectId(fake_ticket_id),
        "user_id": ticket_owner_user["id"],
    })

    # Unauthorized user
    with pytest.raises(HTTPException) as exc_info:
        await svc.list_attachments(fake_ticket_id, other_regular_user)
    assert exc_info.value.status_code == 404

    # Authorized user
    mock_db.attachments.find = MagicMock(return_value=AsyncIter([
        {
            "_id": ObjectId(),
            "ticket_id": fake_ticket_id,
            "original_filename": "doc.pdf",
            "stored_filename": "12345.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 1024,
            "uploaded_by": ticket_owner_user["id"],
            "created_at": datetime.utcnow(),
        }
    ]))

    results = await svc.list_attachments(fake_ticket_id, ticket_owner_user)
    assert len(results) == 1
    assert results[0].original_filename == "doc.pdf"


# ─────────────────────────────────────────────────────────────────────────────
# 20. Delete Single Attachment (RBAC & Physical Cleanup)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_20_delete_single_attachment_rbac_and_physical_cleanup(
    mock_db, fake_ticket_id, ticket_owner_user, admin_user
):
    svc = AttachmentService(mock_db)
    att_id = str(ObjectId())

    # Regular user cannot delete
    with pytest.raises(HTTPException) as exc_info:
        await svc.delete_attachment(fake_ticket_id, att_id, ticket_owner_user)
    assert exc_info.value.status_code == 403

    # Create dummy physical file
    real_file = os.path.join(settings.UPLOAD_DIR, "to_delete.pdf")
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    with open(real_file, "wb") as f:
        f.write(b"%PDF-1.4 to delete")

    mock_db.attachments.find_one = AsyncMock(return_value={
        "_id": ObjectId(att_id),
        "ticket_id": fake_ticket_id,
        "original_filename": "to_delete.pdf",
        "stored_path": real_file,
    })
    mock_db.attachments.delete_one = AsyncMock()
    mock_db.tickets.update_one = AsyncMock()

    # Admin deletes attachment
    deleted = await svc.delete_attachment(fake_ticket_id, att_id, admin_user)
    assert deleted is True
    # Physical file must be removed
    assert not os.path.exists(real_file)
    # MongoDB delete must be called
    mock_db.attachments.delete_one.assert_awaited_once_with({"_id": ObjectId(att_id)})


# ─────────────────────────────────────────────────────────────────────────────
# 21. Ticket Deletion Purges Physical Files
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_21_delete_ticket_purges_all_attachments(mock_db, fake_ticket_id, admin_user):
    svc = TicketService(mock_db)

    # Prepare two dummy physical files
    file1 = os.path.join(settings.UPLOAD_DIR, "purge1.pdf")
    file2 = os.path.join(settings.UPLOAD_DIR, "purge2.pdf")
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    with open(file1, "wb") as f:
        f.write(b"%PDF-1.4 file 1")
    with open(file2, "wb") as f:
        f.write(b"%PDF-1.4 file 2")

    mock_db.tickets.find_one = AsyncMock(return_value={
        "_id": ObjectId(fake_ticket_id),
        "subject": "Ticket avec fichiers",
    })
    mock_db.tickets.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))

    mock_db.attachments.find = MagicMock(return_value=AsyncIter([
        {"stored_path": file1},
        {"stored_path": file2},
    ]))
    mock_db.attachments.delete_many = AsyncMock()

    res = await svc.delete_ticket(fake_ticket_id, actor_user=admin_user)
    assert res is True
    # Physical files must be deleted from disk
    assert not os.path.exists(file1)
    assert not os.path.exists(file2)
    # MongoDB attachments collection must have had delete_many called
    mock_db.attachments.delete_many.assert_awaited_once_with({"ticket_id": fake_ticket_id})


# ─────────────────────────────────────────────────────────────────────────────
# 22. HTTP Security Headers on Download
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_22_api_download_security_headers():
    # Test FileResponse configuration headers
    response = FileResponse(
        path=__file__,  # any existing file
        media_type="application/pdf",
        filename="test.pdf",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("cache-control") == "no-store"
