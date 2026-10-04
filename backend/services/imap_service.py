"""
IMAP inbound email fetching and parsing for GEISER ITSM.
Uses stdlib imaplib — blocking calls are run via asyncio.to_thread from the monitor.
Supports full MIME extraction, threading headers (In-Reply-To, References),
HTML sanitization, and safe credential isolation.
"""

import email
import imaplib
import logging
import re
import ssl
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime
from html import unescape
from typing import List, Optional, Tuple, Dict, Any

from core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class EmailAttachment:
    filename: str
    content: bytes
    content_type: str = "application/octet-stream"
    size_bytes: int = 0

    def __post_init__(self):
        if not self.size_bytes and self.content:
            self.size_bytes = len(self.content)


@dataclass
class InboundEmail:
    message_id: str
    sender_email: str
    sender_name: str
    subject: str
    body: str
    html_body: Optional[str] = None
    in_reply_to: Optional[str] = None
    references: List[str] = field(default_factory=list)
    date: Optional[datetime] = None
    to: Optional[str] = None
    cc: List[str] = field(default_factory=list)
    attachments: List[EmailAttachment] = field(default_factory=list)
    imap_uid: str = ""


def _decode_header_value(value: Optional[str]) -> str:
    """Decodes MIME encoded header strings into standard utf-8 unicode."""
    if not value:
        return ""
    try:
        parts = decode_header(value)
        decoded = []
        for part, charset in parts:
            if isinstance(part, bytes):
                decoded.append(part.decode(charset or "utf-8", errors="replace"))
            else:
                decoded.append(str(part))
        return "".join(decoded).strip()
    except Exception as e:
        logger.debug(f"Header decoding fallback for '{value}': {e}")
        return str(value).strip()


def sanitize_html(html: str) -> str:
    """
    Sanitizes HTML content to prevent XSS or script execution.
    Removes script, style, iframe, object, embed tags and inline event handlers.
    Converts linebreaks and paragraphs into standard newlines.
    """
    if not html:
        return ""
    # Strip dangerous executable elements
    text = re.sub(
        r"<(script|style|iframe|object|embed|applet)[^>]*>.*?</\1>",
        "",
        html,
        flags=re.DOTALL | re.IGNORECASE
    )
    # Strip inline on* handlers and javascript: URIs
    text = re.sub(r"\son\w+\s*=\s*['\"][^'\"]*['\"]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"href\s*=\s*['\"]javascript:[^'\"]*['\"]", "href='#'", text, flags=re.IGNORECASE)
    # Normalize structural spacing
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</div>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<li[^>]*>", "• ", text, flags=re.IGNORECASE)
    text = re.sub(r"</li>", "\n", text, flags=re.IGNORECASE)
    # Strip remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    return unescape(text).strip()


def _clean_message_id(msg_id: Optional[str]) -> str:
    """Strips angle brackets and extra whitespace from Message-ID headers."""
    if not msg_id:
        return ""
    cleaned = msg_id.strip()
    if cleaned.startswith("<") and cleaned.endswith(">"):
        cleaned = cleaned[1:-1].strip()
    return cleaned


def _extract_references(ref_header: Optional[str]) -> List[str]:
    """Parses a References header into a list of clean message IDs."""
    if not ref_header:
        return []
    # Match all <id> patterns or space-separated tokens
    tokens = re.findall(r"<([^>]+)>", ref_header)
    if not tokens:
        tokens = [t.strip() for t in ref_header.split() if t.strip()]
    return [_clean_message_id(t) for t in tokens if t]


def _extract_body(msg: email.message.Message) -> Tuple[str, Optional[str]]:
    """
    Extracts plain text and HTML bodies from a MIME message.
    Returns (cleaned_text_body, raw_or_sanitized_html).
    """
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
                html_parts.append(text)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            try:
                text = payload.decode(charset, errors="replace")
            except Exception:
                text = payload.decode("utf-8", errors="replace")
            if msg.get_content_type() == "text/html":
                html_parts.append(text)
            else:
                plain_parts.append(text.strip())

    combined_plain = "\n\n".join(p for p in plain_parts if p)
    raw_html = "\n\n".join(h for h in html_parts if h) if html_parts else None

    # If plain text exists, prefer it. If only HTML exists, sanitize HTML to readable text.
    if combined_plain:
        final_body = combined_plain
    elif raw_html:
        final_body = sanitize_html(raw_html)
    else:
        final_body = ""

    return final_body, raw_html


def _extract_attachments(msg: email.message.Message) -> List[EmailAttachment]:
    """Extracts valid attachments respecting size limits and blocking executable files."""
    import os
    DANGEROUS_EXTENSIONS = {".exe", ".bat", ".cmd", ".sh", ".ps1", ".msi", ".vbs", ".js", ".scr", ".com", ".pif"}
    attachments: List[EmailAttachment] = []
    max_bytes = getattr(settings, "EMAIL_MAX_ATTACHMENT_MB", 10) * 1024 * 1024

    if not msg.is_multipart():
        return attachments

    for part in msg.walk():
        disposition = str(part.get("Content-Disposition", ""))
        filename = part.get_filename()
        if "attachment" not in disposition.lower() and not filename:
            continue

        if filename:
            filename = _decode_header_value(filename)
        else:
            filename = "attachment"

        # Sanitize filename: strip path separators to prevent traversal
        filename = filename.replace("\\", "_").replace("/", "_")

        # Check dangerous file extensions
        ext = os.path.splitext(filename)[1].lower()
        if ext in DANGEROUS_EXTENSIONS:
            logger.warning(f"[IMAP] Blocked attachment '{filename}' with dangerous extension '{ext}'")
            continue

        payload = part.get_payload(decode=True)
        if not payload:
            continue

        if len(payload) > max_bytes:
            logger.warning(
                f"[IMAP] Skipping attachment '{filename}': {len(payload)} bytes "
                f"exceeds max limit {settings.EMAIL_MAX_ATTACHMENT_MB}MB"
            )
            continue

        attachments.append(EmailAttachment(
            filename=filename,
            content=payload,
            content_type=part.get_content_type() or "application/octet-stream",
            size_bytes=len(payload),
        ))
    return attachments


def _parse_message(raw_bytes: bytes, imap_uid: str) -> Optional[InboundEmail]:
    """Parses raw RFC 822 MIME bytes into a rich InboundEmail object."""
    try:
        msg = email.message_from_bytes(raw_bytes)
    except Exception as e:
        logger.error(f"[IMAP] Failed to parse MIME bytes: {e}")
        return None

    raw_msg_id = msg.get("Message-ID", "").strip()
    message_id = _clean_message_id(raw_msg_id) or f"generated-{uuid.uuid4().hex}"
    subject = _decode_header_value(msg.get("Subject", "")) or "(Sans objet)"
    sender_name, sender_email = parseaddr(_decode_header_value(msg.get("From", "")))
    sender_email = sender_email.strip().lower()

    if not sender_email:
        logger.warning(f"[IMAP] Ignored email without valid sender address (Message-ID: {message_id})")
        return None

    # Threading headers
    in_reply_to = _clean_message_id(msg.get("In-Reply-To", "")) or None
    references = _extract_references(msg.get("References", ""))

    # Date header
    date_val = None
    if msg.get("Date"):
        try:
            date_val = parsedate_to_datetime(msg.get("Date"))
        except Exception:
            date_val = datetime.utcnow()

    # To and CC
    to_addr = _decode_header_value(msg.get("To", ""))
    cc_header = _decode_header_value(msg.get("Cc", ""))
    cc_list = [addr.strip() for addr in cc_header.split(",") if addr.strip()] if cc_header else []

    body, raw_html = _extract_body(msg)

    # Clean quoted reply blocks from body to avoid redundant quotes in tickets
    body_clean = re.split(r"\n-{2,}\s*Original Message\s*-{2,}", body, flags=re.IGNORECASE)[0]
    body_clean = re.split(r"\nOn .+ wrote:\n", body_clean)[0]
    body_clean = body_clean.strip()

    attachments = _extract_attachments(msg)

    return InboundEmail(
        message_id=message_id,
        sender_email=sender_email,
        sender_name=sender_name or sender_email.split("@")[0],
        subject=subject,
        body=body_clean or body,
        html_body=raw_html,
        in_reply_to=in_reply_to,
        references=references,
        date=date_val,
        to=to_addr,
        cc=cc_list,
        attachments=attachments,
        imap_uid=imap_uid,
    )


def _get_imap_credentials() -> Tuple[str, str]:
    """Retrieves configured IMAP username and password."""
    user = getattr(settings, "EMAIL_IMAP_USERNAME", None) or getattr(settings, "IMAP_USER", None) or getattr(settings, "SMTP_USER", "")
    password = getattr(settings, "EMAIL_IMAP_PASSWORD", None) or getattr(settings, "IMAP_PASSWORD", None) or getattr(settings, "SMTP_PASSWORD", "")
    return user, password


def is_imap_configured() -> bool:
    """Returns True if IMAP is enabled and credentials/hosts are provided."""
    enabled = getattr(settings, "EMAIL_TO_TICKET_ENABLED", None) or getattr(settings, "IMAP_ENABLED", False)
    host = getattr(settings, "EMAIL_IMAP_HOST", None) or getattr(settings, "IMAP_HOST", "")
    user, password = _get_imap_credentials()
    return bool(enabled and host and user and password)


def test_imap_connection() -> Dict[str, Any]:
    """
    Performs a safe, comprehensive diagnostic test of the configured IMAP endpoint.
    Never exposes passwords or sensitive credentials in returns or exceptions.
    """
    user, password = _get_imap_credentials()
    host = getattr(settings, "EMAIL_IMAP_HOST", None) or getattr(settings, "IMAP_HOST", "imap.gmail.com")
    port = int(getattr(settings, "EMAIL_IMAP_PORT", None) or getattr(settings, "IMAP_PORT", 993))
    use_ssl = bool(getattr(settings, "EMAIL_IMAP_USE_SSL", None) or getattr(settings, "IMAP_USE_SSL", True))
    folder = getattr(settings, "EMAIL_IMAP_FOLDER", None) or getattr(settings, "IMAP_FOLDER", "INBOX")

    diag: Dict[str, Any] = {
        "configured": is_imap_configured(),
        "host": host,
        "port": port,
        "use_ssl": use_ssl,
        "username": user,
        "folder": folder,
        "connected": False,
        "authenticated": False,
        "folder_accessible": False,
        "total_messages": 0,
        "unread_messages": 0,
        "error": None,
    }

    if not is_imap_configured():
        diag["error"] = "IMAP is not configured (missing host, username, or password)"
        return diag

    mail = None
    try:
        if use_ssl:
            context = ssl.create_default_context()
            mail = imaplib.IMAP4_SSL(host, port, ssl_context=context, timeout=12)
        else:
            mail = imaplib.IMAP4(host, port, timeout=12)

        diag["connected"] = True

        mail.login(user, password)
        diag["authenticated"] = True

        status, _ = mail.select(folder)
        if status == "OK":
            diag["folder_accessible"] = True
            # Count total
            typ, all_data = mail.search(None, "ALL")
            if typ == "OK" and all_data[0]:
                diag["total_messages"] = len(all_data[0].split())
            # Count unread
            typ_unseen, unseen_data = mail.search(None, "UNSEEN")
            if typ_unseen == "OK" and unseen_data[0]:
                diag["unread_messages"] = len(unseen_data[0].split())

        mail.logout()

    except imaplib.IMAP4.error as imap_err:
        err_msg = str(imap_err)
        diag["error"] = f"IMAP authentication error: {err_msg}"
        logger.warning(f"[IMAP TEST] Auth error for {user}: {err_msg}")
    except (socket.timeout, TimeoutError):
        diag["error"] = f"Connection timed out connecting to {host}:{port}"
        logger.warning(f"[IMAP TEST] Timeout connecting to {host}:{port}")
    except Exception as e:
        diag["error"] = f"Connection failed: {type(e).__name__} - {str(e)[:150]}"
        logger.warning(f"[IMAP TEST] Unexpected error: {e}")
    finally:
        if mail:
            try:
                mail.close()
            except Exception:
                pass

    return diag


def fetch_unread_emails() -> List[InboundEmail]:
    """Fetch unread emails from IMAP inbox. Blocking — call via asyncio.to_thread."""
    if not is_imap_configured():
        logger.debug("[IMAP] Inbound email polling skipped: IMAP not configured.")
        return []

    user, password = _get_imap_credentials()
    host = getattr(settings, "EMAIL_IMAP_HOST", None) or getattr(settings, "IMAP_HOST", "imap.gmail.com")
    port = int(getattr(settings, "EMAIL_IMAP_PORT", None) or getattr(settings, "IMAP_PORT", 993))
    use_ssl = bool(getattr(settings, "EMAIL_IMAP_USE_SSL", None) or getattr(settings, "IMAP_USE_SSL", True))
    folder = getattr(settings, "EMAIL_IMAP_FOLDER", None) or getattr(settings, "IMAP_FOLDER", "INBOX")

    emails: List[InboundEmail] = []

    try:
        if use_ssl:
            context = ssl.create_default_context()
            mail = imaplib.IMAP4_SSL(host, port, ssl_context=context, timeout=20)
        else:
            mail = imaplib.IMAP4(host, port, timeout=20)

        mail.login(user, password)
        mail.select(folder)

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
        logger.error(f"[IMAP] Fetch failed on {host}:{port}: {e}")
        return []

    return emails


def mark_email_as_read(imap_uid: str) -> bool:
    """Marks a message as read (\\Seen) after successful ticket creation/reply."""
    if not imap_uid or not is_imap_configured():
        return False

    user, password = _get_imap_credentials()
    host = getattr(settings, "EMAIL_IMAP_HOST", None) or getattr(settings, "IMAP_HOST", "imap.gmail.com")
    port = int(getattr(settings, "EMAIL_IMAP_PORT", None) or getattr(settings, "IMAP_PORT", 993))
    use_ssl = bool(getattr(settings, "EMAIL_IMAP_USE_SSL", None) or getattr(settings, "IMAP_USE_SSL", True))
    folder = getattr(settings, "EMAIL_IMAP_FOLDER", None) or getattr(settings, "IMAP_FOLDER", "INBOX")

    try:
        if use_ssl:
            context = ssl.create_default_context()
            mail = imaplib.IMAP4_SSL(host, port, ssl_context=context, timeout=10)
        else:
            mail = imaplib.IMAP4(host, port, timeout=10)
        mail.login(user, password)
        mail.select(folder)
        mail.store(imap_uid.encode() if isinstance(imap_uid, str) else imap_uid, "+FLAGS", "\\Seen")
        mail.logout()
        return True
    except Exception as e:
        logger.warning(f"[IMAP] Could not mark email UID {imap_uid} as read: {e}")
        return False
