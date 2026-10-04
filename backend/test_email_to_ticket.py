"""
test_email_to_ticket.py
=======================
STEP 8 — Inbound Email-to-Ticket and Threading Engine Test Suite (20 Tests).
Covers:
- MIME header decoding & RFC 822 parsing
- HTML sanitization & anti-XSS protection
- Attachment security (size, disallowed extensions, path traversal)
- Sender resolution & Non-privileged user auto-provisioning
- Idempotency locking & duplicate suppression
- Multi-level Threading Engine (In-Reply-To, References, Subject regexes)
- Ticket reopening upon customer reply
- Auto-acknowledgment email dispatch
- IMAP read flag application
- Diagnostic connection test without secret leakage
- Fast API routes & RBAC enforcement
"""

import os
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from bson import ObjectId
from jose import jwt
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.config import settings
from database.mongodb import get_database
from routes.email import router as email_router
from schemas.schemas import UserRole, UserOut
from core.deps import get_current_user
from services.imap_service import (
    _decode_header_value,
    sanitize_html,
    _parse_message,
    test_imap_connection as imap_test_connection_fn,
    mark_email_as_read,
    InboundEmail,
    EmailAttachment,
)
from services.email_ticket_service import EmailTicketService


# ─────────────────────────────────────────────────────────────
# Test Fixtures & Helpers
# ─────────────────────────────────────────────────────────────

ADMIN_ID = "6abba6e6702d1408c1f39851"
USER_ID = "6abba6e6702d1408c1f39852"


def create_token(role: str, user_id: str = None, email_addr: str = None) -> str:
    uid = user_id or (ADMIN_ID if role == "ADMIN" else USER_ID)
    mail = email_addr or f"{role.lower()}@geiser.internal"
    payload = {
        "sub": uid,
        "role": role,
        "email": mail,
        "type": "access",
        "exp": datetime.utcnow() + timedelta(hours=1),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


# 1. Header decoding
def test_decode_mime_headers_utf8():
    raw_utf8 = "=?UTF-8?B?UHJvYmzDqG1lIGRlIGNvbm5leGlvbg==?="
    decoded = _decode_header_value(raw_utf8)
    assert decoded == "Problème de connexion"

    raw_ascii = "Standard ASCII Subject"
    assert _decode_header_value(raw_ascii) == "Standard ASCII Subject"
    assert _decode_header_value(None) == ""


# 2. HTML sanitization
def test_sanitize_html_strips_scripts_and_events():
    malicious_html = """
    <div>
        <p>Texte légitime</p>
        <script>alert('XSS')</script>
        <iframe src="http://evil.com"></iframe>
        <a href="javascript:stealCookie()">Cliquez ici</a>
        <img src="pic.jpg" onload="alert('hack')" />
        <style>body { display:none; }</style>
    </div>
    """
    clean = sanitize_html(malicious_html)
    assert "<script" not in clean.lower()
    assert "<iframe" not in clean.lower()
    assert "javascript:" not in clean.lower()
    assert "onload=" not in clean.lower()
    assert "<style" not in clean.lower()
    assert "Texte légitime" in clean


# 3. Parse raw RFC 822 message
def test_parse_raw_rfc822_message():
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Serveur VPN inaccessible"
    msg["From"] = "Alice Martin <alice.martin@client.com>"
    msg["To"] = "geiser.support@gmail.com"
    msg["Message-ID"] = "<unique-msg-12345@client.com>"
    msg["Date"] = "Wed, 29 Sep 2026 10:00:00 +0000"

    plain_part = MIMEText("Le serveur VPN ne répond plus depuis 9h.", "plain", "utf-8")
    html_part = MIMEText("<p>Le serveur VPN ne répond plus depuis 9h.</p>", "html", "utf-8")
    msg.attach(plain_part)
    msg.attach(html_part)

    raw_bytes = msg.as_bytes()
    inbound = _parse_message(raw_bytes, imap_uid="101")

    assert inbound is not None
    assert inbound.message_id == "unique-msg-12345@client.com"
    assert inbound.sender_email == "alice.martin@client.com"
    assert inbound.sender_name == "Alice Martin"
    assert inbound.subject == "Serveur VPN inaccessible"
    assert "Le serveur VPN ne répond plus" in inbound.body
    assert inbound.imap_uid == "101"


# 4. Parse raw RFC 822 with attachments
def test_parse_raw_rfc822_with_attachments():
    msg = MIMEMultipart("mixed")
    msg["Subject"] = "Capture d'erreur"
    msg["From"] = "bob@client.com"
    msg["To"] = "geiser.support@gmail.com"
    msg["Message-ID"] = "<msg-with-att-999@client.com>"

    text_part = MIMEText("Voir la capture en pièce jointe.", "plain")
    msg.attach(text_part)

    # Attach file
    att = MIMEBase("image", "png")
    att.set_payload(b"\x89PNG\r\n\x1a\nFakeImageData")
    encoders.encode_base64(att)
    att.add_header("Content-Disposition", 'attachment; filename="screenshot.png"')
    msg.attach(att)

    inbound = _parse_message(msg.as_bytes(), imap_uid="102")
    assert inbound is not None
    assert len(inbound.attachments) == 1
    assert inbound.attachments[0].filename == "screenshot.png"
    assert inbound.attachments[0].size_bytes > 0


# 5. Disallowed attachment extensions skipped
def test_inbound_disallowed_extension_skipped():
    msg = MIMEMultipart("mixed")
    msg["Subject"] = "Mise à jour urgente"
    msg["From"] = "bob@client.com"
    msg["To"] = "geiser.support@gmail.com"
    msg["Message-ID"] = "<msg-disallowed-att@client.com>"

    msg.attach(MIMEText("Voici le binaire.", "plain"))

    att = MIMEBase("application", "octet-stream")
    att.set_payload(b"malicious-payload")
    encoders.encode_base64(att)
    att.add_header("Content-Disposition", 'attachment; filename="malware.exe"')
    msg.attach(att)

    inbound = _parse_message(msg.as_bytes(), imap_uid="103")
    assert inbound is not None
    # .exe must be excluded by dangerous extension filter
    assert len(inbound.attachments) == 0


# 6. Oversized attachment skipped
def test_inbound_oversized_attachment_skipped():
    msg = MIMEMultipart("mixed")
    msg["Subject"] = "Gros rapport"
    msg["From"] = "bob@client.com"
    msg["To"] = "geiser.support@gmail.com"
    msg["Message-ID"] = "<msg-oversized@client.com>"

    msg.attach(MIMEText("Fichier trop volumineux.", "plain"))

    # Attachment > 10MB
    att = MIMEBase("application", "octet-stream")
    att.set_payload(b"0" * (11 * 1024 * 1024))
    encoders.encode_base64(att)
    att.add_header("Content-Disposition", 'attachment; filename="large.dat"')
    msg.attach(att)

    inbound = _parse_message(msg.as_bytes(), imap_uid="104")
    assert inbound is not None
    assert len(inbound.attachments) == 0


# 7. Path traversal attachment filename sanitized
def test_path_traversal_attachment_filename_sanitized():
    db = MagicMock()
    service = EmailTicketService(db)

    traversal_att = EmailAttachment(
        filename="../../etc/passwd",
        content=b"test data",
        content_type="text/plain"
    )

    inbound = InboundEmail(
        message_id="msg-att-test",
        sender_email="user@test.com",
        sender_name="User",
        subject="Test",
        body="Body",
        attachments=[traversal_att]
    )

    with patch("os.makedirs"), patch("builtins.open", MagicMock()):
        saved = service.save_attachments(inbound)
        assert len(saved) == 1
        # Path traversal characters must not exist in saved path
        assert ".." not in os.path.basename(saved[0])
        assert "passwd" in saved[0]


# 8. Ignored senders
def test_ignored_senders():
    db = MagicMock()
    service = EmailTicketService(db)

    assert service._should_ignore_sender("noreply@company.com") is True
    assert service._should_ignore_sender("no-reply@service.fr") is True
    assert service._should_ignore_sender("mailer-daemon@googlemail.com") is True
    assert service._should_ignore_sender("postmaster@outlook.com") is True
    assert service._should_ignore_sender("valid.user@customer.org") is False


# 9. Idempotency lock prevents duplicate processing
@pytest.mark.asyncio
async def test_idempotency_lock_prevents_duplicate_processing():
    db = MagicMock()
    service = EmailTicketService(db)

    # Return existing PROCESSED email
    service.processed_emails.find_one = AsyncMock(return_value={
        "message_id": "test-id-123",
        "status": "PROCESSED",
        "ticket_id": "ticket-abc"
    })

    inbound = InboundEmail(
        message_id="test-id-123",
        sender_email="user@test.com",
        sender_name="Test User",
        subject="Problème",
        body="Contenu",
    )

    result = await service.process_inbound_email(inbound)
    assert result["created"] is False
    assert result["skipped"] is True
    assert result["reason"] == "already_processed"


# 10. Idempotency stale lock recovery
@pytest.mark.asyncio
async def test_idempotency_stale_lock_recovery():
    db = MagicMock()
    service = EmailTicketService(db)

    # Stale lock: status PROCESSING from 20 minutes ago
    stale_time = datetime.utcnow() - timedelta(minutes=20)
    service.processed_emails.find_one = AsyncMock(return_value={
        "message_id": "test-stale-id",
        "status": "PROCESSING",
        "received_at": stale_time
    })
    service.processed_emails.update_one = AsyncMock()

    acquired = await service._acquire_processing_lock(
        InboundEmail(
            message_id="test-stale-id",
            sender_email="user@test.com",
            sender_name="User",
            subject="Sub",
            body="Body"
        )
    )
    assert acquired is True


# 11. Sender auto-provisioning always creates USER (never ADMIN or AGENT)
@pytest.mark.asyncio
async def test_sender_auto_provisioning_non_privileged():
    db = MagicMock()
    service = EmailTicketService(db)

    # User does not exist
    service.users.find_one = AsyncMock(return_value=None)
    inserted_id = ObjectId()
    service.users.insert_one = AsyncMock(return_value=MagicMock(inserted_id=inserted_id))

    user_doc = await service.resolve_user("new.client@corp.com", "New Client")

    assert str(user_doc["id"]) == str(inserted_id)
    assert user_doc["role"] == UserRole.USER.value
    assert user_doc["role"] != UserRole.ADMIN.value
    assert user_doc["role"] != UserRole.AGENT.value
    assert user_doc["is_active"] is True


# 12. Existing user linked correctly
@pytest.mark.asyncio
async def test_sender_existing_user_linked():
    db = MagicMock()
    service = EmailTicketService(db)

    existing_user = {
        "_id": ObjectId("6abba6e6702d1408c1f39899"),
        "email": "existing@corp.com",
        "username": "existing_user",
        "role": "USER",
    }
    service.users.find_one = AsyncMock(return_value=existing_user)

    user_doc = await service.resolve_user("existing@corp.com", "Existing")
    assert str(user_doc["id"]) == str(existing_user["_id"])
    service.users.insert_one.assert_not_called()


# 13. Threading: matches In-Reply-To header
@pytest.mark.asyncio
async def test_threading_matches_in_reply_to():
    db = MagicMock()
    service = EmailTicketService(db)

    service.processed_emails.find_one = AsyncMock(return_value={
        "message_id": "parent-msg-id@domain.com",
        "ticket_id": "matched-ticket-111"
    })
    service.ticket_service.get_ticket = AsyncMock(return_value={
        "id": "matched-ticket-111",
        "subject": "Incident VPN"
    })

    inbound = InboundEmail(
        message_id="reply-msg-id@domain.com",
        sender_email="user@test.com",
        sender_name="User",
        subject="Re: Incident",
        body="Toujours en panne",
        in_reply_to="parent-msg-id@domain.com"
    )

    ticket = await service.find_existing_ticket_for_email(inbound)
    assert ticket is not None
    assert ticket["id"] == "matched-ticket-111"


# 14. Threading: matches References header
@pytest.mark.asyncio
async def test_threading_matches_references():
    db = MagicMock()
    service = EmailTicketService(db)

    service.processed_emails.find_one = AsyncMock(return_value={
        "message_id": "ref-msg-id-2@domain.com",
        "ticket_id": "matched-ticket-222"
    })
    service.ticket_service.get_ticket = AsyncMock(return_value={
        "id": "matched-ticket-222",
        "subject": "Incident DB"
    })

    inbound = InboundEmail(
        message_id="reply-msg-id@domain.com",
        sender_email="user@test.com",
        sender_name="User",
        subject="Re: Incident",
        body="Toujours en panne",
        references=["ref-msg-id-1@domain.com", "ref-msg-id-2@domain.com"]
    )

    ticket = await service.find_existing_ticket_for_email(inbound)
    assert ticket is not None
    assert ticket["id"] == "matched-ticket-222"


# 15. Threading: matches Subject regex ticket number
@pytest.mark.asyncio
async def test_threading_matches_subject_ticket_number():
    db = MagicMock()
    service = EmailTicketService(db)

    service.processed_emails.find_one = AsyncMock(return_value=None)
    service.tickets.find_one = AsyncMock(return_value=None)
    fake_ticket_id = "6abba6e6702d1408c1f39877"
    service.ticket_service.get_ticket = AsyncMock(return_value={
        "id": fake_ticket_id,
        "subject": "Demande d'assistance"
    })

    inbound = InboundEmail(
        message_id="random-msg@domain.com",
        sender_email="user@test.com",
        sender_name="User",
        subject=f"Re: Demande d'assistance [GEISER-{fake_ticket_id}]",
        body="Nouveau message",
    )

    ticket = await service.find_existing_ticket_for_email(inbound)
    assert ticket is not None
    assert ticket["id"] == fake_ticket_id


# 16. Reply reopens resolved ticket
@pytest.mark.asyncio
async def test_reply_reopens_resolved_ticket():
    db = MagicMock()
    service = EmailTicketService(db)

    ticket_id = "6abba6e6702d1408c1f39866"
    ticket_doc = {
        "id": ticket_id,
        "subject": "Problème VPN",
        "status": "RESOLVED",
        "user_id": "user-123",
        "responses": [],
    }

    service.tickets.update_one = AsyncMock()
    service.ticket_service.record_ticket_action = AsyncMock()
    service.ticket_service.get_ticket = AsyncMock(return_value={**ticket_doc, "status": "IN_PROGRESS"})

    inbound = InboundEmail(
        message_id="reply-reopen@test.com",
        sender_email="user@test.com",
        sender_name="User",
        subject="Re: Problème VPN",
        body="Le problème persiste malgré le redémarrage.",
    )

    with patch("websocket.dispatcher.event_dispatcher.publish_ticket_comment", new_callable=AsyncMock), \
         patch("websocket.dispatcher.event_dispatcher.publish_ticket_status_changed", new_callable=AsyncMock):
        res = await service.append_reply_to_ticket(
            ticket=ticket_doc,
            inbound=inbound,
            user={"id": "user-123", "email": "user@test.com", "full_name": "User 123", "role": "USER"},
            attachment_paths=[]
        )

        assert res["replied"] is True
        assert res["ticket_id"] == ticket_id
        assert res["status"] == "IN_PROGRESS"
        service.tickets.update_one.assert_called_once()
        update_call = service.tickets.update_one.call_args[0][1]
        assert update_call["$set"]["status"] == "IN_PROGRESS"


# 17. Auto-acknowledgment sent upon ticket creation
@pytest.mark.asyncio
async def test_auto_acknowledgment_sent():
    db = MagicMock()
    service = EmailTicketService(db)

    service._should_ignore_sender = MagicMock(return_value=False)
    service._acquire_processing_lock = AsyncMock(return_value=True)
    service.resolve_user = AsyncMock(return_value={"id": "user-1", "email": "client@corp.com", "role": "USER"})
    service.save_attachments = MagicMock(return_value=[])
    service.find_existing_ticket_for_email = AsyncMock(return_value=None)
    service._record_outcome = AsyncMock()

    created_ticket = {
        "id": "6abba6e6702d1408c1f39811",
        "subject": "Demande de souris",
        "category": "Matériel",
        "priority": "LOW",
        "status": "OPEN",
    }
    service.chatbot.create_ticket_from_email = AsyncMock(return_value=created_ticket)

    inbound = InboundEmail(
        message_id="msg-new-ticket@corp.com",
        sender_email="client@corp.com",
        sender_name="Client",
        subject="Demande de souris",
        body="J'ai besoin d'une nouvelle souris optique.",
    )

    with patch("services.email_service.EmailService.send_email") as mock_send:
        res = await service.process_inbound_email(inbound)
        assert res["created"] is True
        assert res["ticket_id"] == "6abba6e6702d1408c1f39811"
        mock_send.assert_called_once()
        args, _ = mock_send.call_args
        assert args[0] == "client@corp.com"
        assert "[TICK-" in args[1]


# 18. Mark email as read
def test_mark_email_as_read_success():
    with patch("services.imap_service.is_imap_configured", return_value=True), \
         patch("services.imap_service._get_imap_credentials", return_value=("geiser.support@gmail.com", "mock_pass")), \
         patch("imaplib.IMAP4_SSL") as mock_imap_ssl:

        mock_server = MagicMock()
        mock_imap_ssl.return_value = mock_server

        success = mark_email_as_read("55")
        assert success is True
        mock_server.store.assert_called_with(b"55", "+FLAGS", "\\Seen")


# 19. Diagnostic test_imap_connection does not leak credentials
def test_diagnostics_safe_connection():
    with patch("services.imap_service.is_imap_configured", return_value=True), \
         patch("services.imap_service._get_imap_credentials", return_value=("geiser.support@gmail.com", "super_secret_pw")), \
         patch("imaplib.IMAP4_SSL") as mock_imap:

        mock_server = MagicMock()
        mock_server.select.return_value = ("OK", [b"10"])
        mock_server.search.side_effect = [("OK", [b"1 2 3"]), ("OK", [b"1"])]
        mock_imap.return_value = mock_server

        diag = imap_test_connection_fn()
        assert diag["connected"] is True
        assert diag["authenticated"] is True
        assert diag["folder_accessible"] is True
        assert diag["total_messages"] == 3
        assert diag["unread_messages"] == 1
        # Crucial check: password must not be in the dictionary
        assert "password" not in diag
        assert "super_secret_pw" not in str(diag)


# 20. Fast API Endpoints & RBAC for /api/v1/email
def test_api_endpoints_email():
    app = FastAPI()
    app.include_router(email_router, prefix="/api/v1/email")

    mock_db = MagicMock()
    app.dependency_overrides[get_database] = lambda: mock_db

    # Test without auth -> 401/403
    client = TestClient(app)
    res_unauth = client.get("/api/v1/email/status")
    assert res_unauth.status_code in [401, 403]

    # Test with USER -> 403
    user_token = create_token("USER")
    app.dependency_overrides[get_current_user] = lambda: {
        "id": USER_ID, "email": "user@geiser.internal", "role": "USER"
    }
    res_user = client.get("/api/v1/email/status", headers={"Authorization": f"Bearer {user_token}"})
    assert res_user.status_code == 403

    # Test with ADMIN -> 200
    admin_token = create_token("ADMIN")
    app.dependency_overrides[get_current_user] = lambda: {
        "id": ADMIN_ID, "email": "admin@geiser.internal", "role": "ADMIN"
    }
    res_admin = client.get("/api/v1/email/status", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_admin.status_code == 200
    assert "imap_configured" in res_admin.json()

    # Diagnostic test connection endpoint
    with patch("services.imap_service.test_imap_connection", return_value={"configured": True, "connected": False, "error": "Simulated"}):
        res_diag = client.post("/api/v1/email/test-connection", headers={"Authorization": f"Bearer {admin_token}"})
        assert res_diag.status_code == 200
        assert res_diag.json()["configured"] is True
