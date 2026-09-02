"""
Orchestrates inbound email → AI triage → ticket creation.
"""
import logging
import os
import re
import secrets
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from core.config import settings
from core.security import get_password_hash
from models.base import MongoModel
from schemas.schemas import UserRole
from services.ai.chatbot_service import ChatbotService
from services.email_service import EmailService
from services.imap_service import InboundEmail, mark_email_as_read

logger = logging.getLogger(__name__)

# Ignore system / noreply senders
IGNORED_SENDER_PATTERNS = [
    r"noreply@",
    r"no-reply@",
    r"mailer-daemon@",
    r"postmaster@",
]


class EmailTicketService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.processed_emails = db.processed_emails
        self.users = db.users
        self.chatbot = ChatbotService(db)

    def _should_ignore_sender(self, sender_email: str) -> bool:
        sender = sender_email.lower()
        if sender == (settings.FROM_EMAIL or "").lower():
            return True
        imap_user = (settings.IMAP_USER or settings.SMTP_USER or "").lower()
        if imap_user and sender == imap_user:
            return True
        return any(re.search(p, sender) for p in IGNORED_SENDER_PATTERNS)

    async def _is_already_processed(self, message_id: str) -> bool:
        existing = await self.processed_emails.find_one({"message_id": message_id})
        return existing is not None

    async def _mark_processed(
        self,
        message_id: str,
        sender_email: str,
        subject: str,
        result: str,
        ticket_id: Optional[str] = None,
        reason: Optional[str] = None,
    ):
        await self.processed_emails.insert_one({
            "message_id": message_id,
            "sender_email": sender_email,
            "subject": subject,
            "result": result,
            "ticket_id": ticket_id,
            "reason": reason,
            "processed_at": datetime.utcnow(),
        })

    async def resolve_user(self, sender_email: str, sender_name: str = "") -> Optional[dict]:
        """Find user by email, optionally auto-provision a USER account."""
        email_lower = sender_email.lower().strip()
        user = await self.users.find_one({"email": {"$regex": f"^{re.escape(email_lower)}$", "$options": "i"}})
        if user:
            return MongoModel.format_id(user)

        if not settings.EMAIL_AUTO_PROVISION_USERS:
            logger.info(f"No user found for {email_lower} and auto-provision disabled")
            return None

        user_dict = {
            "email": email_lower,
            "full_name": sender_name or email_lower.split("@")[0],
            "role": UserRole.USER.value,
            "hashed_password": get_password_hash(secrets.token_urlsafe(24)),
            "created_at": datetime.utcnow(),
            "is_active": True,
            "two_factor_enabled": False,
            "provisioned_via": "email",
        }
        result = await self.users.insert_one(user_dict)
        user_dict["_id"] = result.inserted_id
        logger.info(f"Auto-provisioned user for inbound email: {email_lower}")
        return MongoModel.format_id(user_dict)

    def save_attachments(self, inbound: InboundEmail) -> List[str]:
        """Save email attachments to UPLOAD_DIR and return file paths."""
        if not inbound.attachments:
            return []

        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        paths: List[str] = []

        for att in inbound.attachments:
            safe_name = re.sub(r"[^\w.\-]", "_", att.filename) or "attachment"
            file_path = os.path.join(settings.UPLOAD_DIR, f"email_{uuid.uuid4().hex[:8]}_{safe_name}")
            try:
                with open(file_path, "wb") as f:
                    f.write(att.content)
                paths.append(file_path)
            except Exception as e:
                logger.warning(f"Failed to save attachment {att.filename}: {e}")

        return paths

    async def process_inbound_email(self, inbound: InboundEmail) -> Dict:
        """
        Process a single inbound email:
        1. Dedup & sender checks
        2. AI triage
        3. Create ticket if valid
        4. Send confirmation
        """
        if self._should_ignore_sender(inbound.sender_email):
            return {"created": False, "skipped": True, "reason": "ignored_sender"}

        if await self._is_already_processed(inbound.message_id):
            return {"created": False, "skipped": True, "reason": "already_processed"}

        user = await self.resolve_user(inbound.sender_email, inbound.sender_name)
        if not user:
            await self._mark_processed(
                inbound.message_id, inbound.sender_email, inbound.subject,
                result="rejected", reason="unknown_sender",
            )
            return {"created": False, "reason": "unknown_sender"}

        attachment_paths = self.save_attachments(inbound)

        try:
            ticket = await self.chatbot.create_ticket_from_email(
                subject=inbound.subject,
                body=inbound.body,
                user_id=user["id"],
                attachments=attachment_paths,
            )
        except ValueError as e:
            reason = str(e)
            await self._mark_processed(
                inbound.message_id, inbound.sender_email, inbound.subject,
                result="rejected", reason=reason,
            )
            logger.info(f"Email rejected (no ticket): {inbound.subject} — {reason}")
            if inbound.imap_uid:
                mark_email_as_read(inbound.imap_uid)
            return {"created": False, "reason": str(e)}

        await self._mark_processed(
            inbound.message_id, inbound.sender_email, inbound.subject,
            result="ticket_created", ticket_id=ticket["id"],
        )

        if inbound.imap_uid:
            mark_email_as_read(inbound.imap_uid)

        # Confirmation email to sender
        ticket_ref = ticket["id"][-6:].upper()
        EmailService.send_email(
            inbound.sender_email,
            f"Ticket #{ticket_ref} créé — {ticket['subject']}",
            (
                f"<h2>Votre demande a été enregistrée</h2>"
                f"<p>Nous avons bien reçu votre email et créé un ticket de support.</p>"
                f"<p><b>Numéro :</b> #{ticket_ref}<br/>"
                f"<b>Objet :</b> {ticket['subject']}<br/>"
                f"<b>Catégorie :</b> {ticket['category']} &gt; {ticket.get('subcategory', 'Général')}<br/>"
                f"<b>Priorité :</b> {ticket['priority']}<br/>"
                f"<b>Statut :</b> {ticket['status']}</p>"
                f"<p>Notre équipe traitera votre demande dans les meilleurs délais.</p>"
            ),
        )

        logger.info(f"Ticket created from email: #{ticket_ref} — {ticket['subject']}")
        return {
            "created": True,
            "ticket_id": ticket["id"],
            "subject": ticket["subject"],
            "priority": ticket["priority"],
            "category": ticket["category"],
        }

    async def poll_and_process(self) -> Dict:
        """Fetch unread emails via IMAP and process each one."""
        import asyncio
        from services.imap_service import fetch_unread_emails, is_imap_configured

        if not is_imap_configured():
            return {"fetched": 0, "created": 0, "rejected": 0, "skipped": 0, "error": "imap_not_configured"}

        inbound_list = await asyncio.to_thread(fetch_unread_emails)
        stats = {"fetched": len(inbound_list), "created": 0, "rejected": 0, "skipped": 0, "tickets": []}

        for inbound in inbound_list:
            result = await self.process_inbound_email(inbound)
            if result.get("skipped"):
                stats["skipped"] += 1
            elif result.get("created"):
                stats["created"] += 1
                stats["tickets"].append({
                    "ticket_id": result.get("ticket_id"),
                    "subject": result.get("subject"),
                })
            else:
                stats["rejected"] += 1

        logger.info(f"Email poll complete: {stats}")
        return stats
