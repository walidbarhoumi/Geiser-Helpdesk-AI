"""
IMAP inbound email fetching and parsing.
Uses stdlib imaplib — blocking calls are run via asyncio.to_thread from the monitor.
"""
import email
import imaplib
import logging
import re
import uuid
from dataclasses import dataclass, field
from email.header import decode_header
from email.utils import parseaddr
from html import unescape
from typing import List, Optional, Tuple

from core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class EmailAttachment:
    filename: str
    content: bytes
    content_type: str = "application/octet-stream"


@dataclass
class InboundEmail:
    message_id: str
    sender_email: str
    sender_name: str
    subject: str
    body: str
    attachments: List[EmailAttachment] = field(default_factory=list)
    imap_uid: str = ""


def _decode_header_value(value: Optional[str]) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(str(part))
    return "".join(decoded).strip()


def _strip_html(html: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return unescape(text).strip()


def _extract_body(msg: email.message.Message) -> str:
    plain_parts: List[str] = []
    html_parts: List[str] = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in disposition.lower():
                continue
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            charset = part.get_content_charset() or "utf-8"
            try:
                text = payload.decode(charset, errors="replace")
            except Exception:
                text = payload.decode("utf-8", errors="replace")
            if content_type == "text/plain":
                plain_parts.append(text.strip())
            elif content_type == "text/html":
                html_parts.append(_strip_html(text))
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            try:
                text = payload.decode(charset, errors="replace")
            except Exception:
                text = payload.decode("utf-8", errors="replace")
            if msg.get_content_type() == "text/html":
                html_parts.append(_strip_html(text))
            else:
                plain_parts.append(text.strip())

    if plain_parts:
        return "\n\n".join(p for p in plain_parts if p)
    if html_parts:
        return "\n\n".join(p for p in html_parts if p)
    return ""


def _extract_attachments(msg: email.message.Message) -> List[EmailAttachment]:
    attachments: List[EmailAttachment] = []
    max_bytes = settings.EMAIL_MAX_ATTACHMENT_MB * 1024 * 1024

    if not msg.is_multipart():
        return attachments

    for part in msg.walk():
        disposition = str(part.get("Content-Disposition", ""))
        if "attachment" not in disposition.lower() and not part.get_filename():
            continue
        filename = part.get_filename()
        if filename:
            filename = _decode_header_value(filename)
        else:
            filename = "attachment"
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        if len(payload) > max_bytes:
            logger.warning(f"Skipping attachment {filename}: exceeds {settings.EMAIL_MAX_ATTACHMENT_MB}MB")
            continue
        attachments.append(EmailAttachment(
            filename=filename,
            content=payload,
            content_type=part.get_content_type(),
        ))
    return attachments


def _parse_message(raw_bytes: bytes, imap_uid: str) -> Optional[InboundEmail]:
    msg = email.message_from_bytes(raw_bytes)
    message_id = msg.get("Message-ID", "").strip() or f"generated-{uuid.uuid4().hex}"
    subject = _decode_header_value(msg.get("Subject", "")) or "(Sans objet)"
    sender_name, sender_email = parseaddr(_decode_header_value(msg.get("From", "")))
    sender_email = sender_email.strip().lower()

    if not sender_email:
        return None

    body = _extract_body(msg).strip()
    # Remove common quoted reply blocks for cleaner analysis
    body = re.split(r"\n-{2,}\s*Original Message\s*-{2,}", body, flags=re.IGNORECASE)[0]
    body = re.split(r"\nOn .+ wrote:\n", body)[0]
    body = body.strip()

    attachments = _extract_attachments(msg)

    return InboundEmail(
        message_id=message_id,
        sender_email=sender_email,
        sender_name=sender_name or sender_email.split("@")[0],
        subject=subject,
        body=body,
        attachments=attachments,
        imap_uid=imap_uid,
    )


def _get_imap_credentials() -> Tuple[str, str]:
    user = settings.IMAP_USER or settings.SMTP_USER
    password = settings.IMAP_PASSWORD or settings.SMTP_PASSWORD
    return user, password


def is_imap_configured() -> bool:
    user, password = _get_imap_credentials()
    return bool(settings.IMAP_ENABLED and settings.IMAP_HOST and user and password)


def fetch_unread_emails() -> List[InboundEmail]:
    """Fetch unread emails from IMAP inbox. Blocking — call via asyncio.to_thread."""
    if not is_imap_configured():
        logger.debug("IMAP not configured — skipping fetch")
        return []

    user, password = _get_imap_credentials()
    emails: List[InboundEmail] = []

    try:
        if settings.IMAP_USE_SSL:
            mail = imaplib.IMAP4_SSL(settings.IMAP_HOST, settings.IMAP_PORT)
        else:
            mail = imaplib.IMAP4(settings.IMAP_HOST, settings.IMAP_PORT)

        mail.login(user, password)
        mail.select(settings.IMAP_FOLDER)

        status, data = mail.search(None, "UNSEEN")
        if status != "OK" or not data[0]:
            mail.logout()
            return []

        for uid in data[0].split():
            uid_str = uid.decode() if isinstance(uid, bytes) else str(uid)
            status, msg_data = mail.fetch(uid, "(RFC822)")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue
            raw = msg_data[0][1]
            if not isinstance(raw, bytes):
                continue
            parsed = _parse_message(raw, uid_str)
            if parsed:
                emails.append(parsed)

        mail.logout()
    except Exception as e:
        logger.error(f"IMAP fetch failed: {e}")
        return []

    return emails


def mark_email_as_read(imap_uid: str) -> bool:
    """Mark a message as read after processing."""
    if not imap_uid or not is_imap_configured():
        return False

    user, password = _get_imap_credentials()
    try:
        if settings.IMAP_USE_SSL:
            mail = imaplib.IMAP4_SSL(settings.IMAP_HOST, settings.IMAP_PORT)
        else:
            mail = imaplib.IMAP4(settings.IMAP_HOST, settings.IMAP_PORT)
        mail.login(user, password)
        mail.select(settings.IMAP_FOLDER)
        mail.store(imap_uid.encode() if isinstance(imap_uid, str) else imap_uid, "+FLAGS", "\\Seen")
        mail.logout()
        return True
    except Exception as e:
        logger.warning(f"Could not mark email {imap_uid} as read: {e}")
        return False
