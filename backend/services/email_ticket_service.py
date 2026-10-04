"""
email_ticket_service.py
=======================
STEP 8 — Inbound Email-to-Ticket Ingestion & Threading Engine.
Orchestrates:
1. Gmail IMAP polling with idempotency locks (Message-ID deduplication)
2. Advanced Threading Engine (In-Reply-To, References, Ticket References in Subject)
3. Sender resolution & Non-privileged user auto-provisioning
4. Attachment security & Path traversal protection
5. AI Classification, ITIL priority, Auto-routing, and SLA initialization
6. Atomic persistence before marking emails as read
"""

import logging
import os
import re
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from core.config import settings
from core.security import get_password_hash
from models.base import MongoModel
from schemas.schemas import UserRole, TicketStatus, TicketActionType
from services.ai.chatbot_service import ChatbotService
from services.email_service import EmailService
from services.imap_service import InboundEmail, mark_email_as_read
from services.ticket_service import TicketService
from services.audit_service import AuditService

logger = logging.getLogger(__name__)

# Patterns for automated / system senders to ignore
IGNORED_SENDER_PATTERNS = [
    r"noreply@",
    r"no-reply@",
    r"mailer-daemon@",
    r"postmaster@",
    r"notification@",
    r"donotreply@",
]

# Regex patterns for matching ticket numbers or IDs in email subjects
TICKET_SUBJECT_PATTERNS = [
    r"\[(?:GEISER|TICK)-([A-Za-z0-9\-]+)\]",
    r"#([A-Za-z0-9]{6,24})",
    r"(?:Ticket|Demande)\s*#?\s*([A-Za-z0-9]{6,24})",
    r"TICK-\d{4}-\d+",
]


class EmailTicketService:
    """
    Centralized Inbound Email-to-Ticket and Threading Service.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.processed_emails = db.processed_emails
        self.users = db.users
        self.tickets = db.tickets
        self.chatbot = ChatbotService(db)
        self.ticket_service = TicketService(db)
        self.audit_service = AuditService(db)

    def _should_ignore_sender(self, sender_email: str) -> bool:
        """Ignores loopback support addresses and system noreply bots."""
        sender = (sender_email or "").strip().lower()
        from_email = (getattr(settings, "FROM_EMAIL", "") or "").lower()
        if sender and from_email and sender == from_email:
            return True

        imap_user = (
            getattr(settings, "EMAIL_IMAP_USERNAME", None)
            or getattr(settings, "IMAP_USER", None)
            or getattr(settings, "SMTP_USER", "")
        ).lower()
        if imap_user and sender == imap_user:
            return True

        return any(re.search(p, sender, re.IGNORECASE) for p in IGNORED_SENDER_PATTERNS)

    async def _acquire_processing_lock(self, inbound: InboundEmail) -> bool:
        """
        Idempotency Guard:
        Attempts to register or lock the inbound email by its Message-ID.
        Returns False if email is already PROCESSED or actively locked by another worker.
        """
        existing = await self.processed_emails.find_one({"message_id": inbound.message_id})
        now = datetime.utcnow()

        if existing:
            status = existing.get("status")
            if status == "PROCESSED":
                logger.info(f"[EmailToTicket] Skipping already processed Message-ID: {inbound.message_id}")
                return False
            if status == "PROCESSING":
                received_at = existing.get("received_at", now)
                # If currently processing for less than 5 minutes, respect the lock
                if now - received_at < timedelta(minutes=5):
                    logger.info(f"[EmailToTicket] Email is actively locked by another worker: {inbound.message_id}")
                    return False
                # Stale lock takeover
                logger.warning(f"[EmailToTicket] Reclaiming stale lock for Message-ID: {inbound.message_id}")
                await self.processed_emails.update_one(
                    {"message_id": inbound.message_id},
                    {"$set": {"received_at": now, "status": "PROCESSING"}}
                )
                return True

        # Insert fresh lock record
        try:
            await self.processed_emails.insert_one({
                "message_id": inbound.message_id,
                "sender_email": inbound.sender_email,
                "subject": inbound.subject,
                "in_reply_to": inbound.in_reply_to,
                "references": inbound.references,
                "status": "PROCESSING",
                "received_at": now,
            })
            return True
        except Exception:
            # Duplicate key error: another worker inserted concurrently
            return False

    async def _record_outcome(
        self,
        message_id: str,
        status: str,
        action: str,
        ticket_id: Optional[str] = None,
        error_message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Persists the final processing outcome in the processed_emails collection."""
        update_data = {
            "status": status,
            "action": action,
            "ticket_id": ticket_id,
            "error_message": error_message,
            "processed_at": datetime.utcnow(),
            "details": details or {},
        }
        await self.processed_emails.update_one(
            {"message_id": message_id},
            {"$set": update_data}
        )

    async def resolve_user(self, sender_email: str, sender_name: str = "") -> Optional[dict]:
        """
        Resolves sender to an existing user account or auto-provisions a strictly
        non-privileged USER account. Never creates ADMIN, SUPERVISOR, or AGENT.
        """
        email_clean = (sender_email or "").strip().lower()
        if not email_clean:
            return None

        user = await self.users.find_one({"email": {"$regex": f"^{re.escape(email_clean)}$", "$options": "i"}})
        if user:
            return MongoModel.format_id(user)

        if not getattr(settings, "EMAIL_AUTO_PROVISION_USERS", True):
            logger.info(f"[EmailToTicket] Auto-provision disabled; no user for {email_clean}")
            return None

        # Auto-provision strict USER role
        user_dict = {
            "email": email_clean,
            "full_name": sender_name or email_clean.split("@")[0],
            "role": UserRole.USER.value,  # Strictly non-privileged
            "hashed_password": get_password_hash(secrets.token_urlsafe(24)),
            "created_at": datetime.utcnow(),
            "is_active": True,
            "two_factor_enabled": False,
            "provisioned_via": "email",
        }
        res = await self.users.insert_one(user_dict)
        user_dict["_id"] = res.inserted_id
        logger.info(f"[EmailToTicket] Auto-provisioned non-privileged USER account: {email_clean}")
        return MongoModel.format_id(user_dict)

    def save_attachments(self, inbound: InboundEmail) -> List[str]:
        """
        Saves inbound attachments with strict path traversal guards
        and unique filenames into settings.UPLOAD_DIR.
        """
        if not inbound.attachments:
            return []

        upload_dir = settings.UPLOAD_DIR
        os.makedirs(upload_dir, exist_ok=True)
        paths: List[str] = []

        for att in inbound.attachments:
            # Strip path separators to prevent directory traversal
            clean_filename = os.path.basename(att.filename)
            safe_name = re.sub(r"[^\w.\-]", "_", clean_filename) or "attachment"
            unique_name = f"email_{uuid.uuid4().hex[:10]}_{safe_name}"
            file_path = os.path.join(upload_dir, unique_name)

            try:
                with open(file_path, "wb") as f:
                    f.write(att.content)
                paths.append(file_path)
            except Exception as e:
                logger.warning(f"[EmailToTicket] Failed to save attachment {att.filename}: {e}")

        return paths

    async def find_existing_ticket_for_email(self, inbound: InboundEmail) -> Optional[dict]:
        """
        Email Threading Resolution:
        Determines whether the incoming email is a response to an existing ticket.
        Order of reliability:
        1. In-Reply-To header matching a stored message_id
        2. References header matching any stored message_id
        3. Subject line containing GEISER ticket identifiers
        """
        # 1. In-Reply-To matching
        if inbound.in_reply_to:
            match = await self.processed_emails.find_one({
                "message_id": inbound.in_reply_to,
                "ticket_id": {"$ne": None}
            })
            if match and match.get("ticket_id"):
                ticket = await self.ticket_service.get_ticket(match["ticket_id"])
                if ticket:
                    logger.info(f"[Threading] Matched ticket {ticket['id']} via In-Reply-To: {inbound.in_reply_to}")
                    return ticket

        # 2. References matching
        if inbound.references:
            match = await self.processed_emails.find_one({
                "message_id": {"$in": inbound.references},
                "ticket_id": {"$ne": None}
            })
            if match and match.get("ticket_id"):
                ticket = await self.ticket_service.get_ticket(match["ticket_id"])
                if ticket:
                    logger.info(f"[Threading] Matched ticket {ticket['id']} via References")
                    return ticket

        # 3. Subject-based ticket reference extraction
        subject = inbound.subject or ""
        for pattern in TICKET_SUBJECT_PATTERNS:
            matches = re.findall(pattern, subject, re.IGNORECASE)
            for ref in matches:
                # ref could be full ObjectId or ticket_number
                ref_clean = ref.strip()
                # Try ticket_number
                ticket_by_num = await self.tickets.find_one({"ticket_number": ref_clean})
                if ticket_by_num:
                    return MongoModel.format_id(ticket_by_num)

                # Try 24-character ObjectId
                if len(ref_clean) == 24:
                    ticket_by_id = await self.ticket_service.get_ticket(ref_clean)
                    if ticket_by_id:
                        return ticket_by_id

                # Try last 6 characters of ObjectId (GEISER ticket ref format)
                if len(ref_clean) == 6:
                    matching_tickets = await self.tickets.find().to_list(length=200)
                    for t in matching_tickets:
                        if str(t.get("_id", "")).endswith(ref_clean.lower()):
                            return MongoModel.format_id(t)

        return None

    async def append_reply_to_ticket(
        self,
        ticket: dict,
        inbound: InboundEmail,
        user: dict,
        attachment_paths: List[str]
    ) -> Dict[str, Any]:
        """
        Appends an incoming email reply to an existing ticket conversation.
        Reopens ticket if closed, logs audit action, and dispatches WebSocket update.
        """
        ticket_id = ticket["id"]
        now = datetime.utcnow()

        response_doc = {
            "id": uuid.uuid4().hex[:12],
            "sender_id": str(user["id"]),
            "sender_name": user.get("full_name") or user.get("email"),
            "role": user.get("role", "USER"),
            "content": inbound.body,
            "created_at": now,
            "source": "EMAIL",
            "message_id": inbound.message_id,
            "attachments": attachment_paths,
        }

        update_fields: Dict[str, Any] = {
            "updated_at": now,
        }

        # If ticket was resolved or closed, automatically reopen it
        current_status = ticket.get("status")
        status_reopened = False
        if current_status in [TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value]:
            update_fields["status"] = TicketStatus.IN_PROGRESS.value
            status_reopened = True

        await self.tickets.update_one(
            {"_id": MongoModel.to_object_id(ticket_id)},
            {
                "$push": {"responses": response_doc},
                "$set": update_fields,
            }
        )

        # ISO 27001 Action history
        await self.ticket_service.record_ticket_action(
            ticket_id=ticket_id,
            action_type=TicketActionType.RESPONSE_SENT.value,
            actor_user=user,
            details={
                "source": "EMAIL",
                "message_id": inbound.message_id,
                "reopened": status_reopened,
            },
            comment=f"Réponse par email reçue du demandeur ({user.get('email')})"
        )

        # Dispatch WebSocket event to notify agents viewing the ticket live
        try:
            from websocket.dispatcher import event_dispatcher
            await event_dispatcher.publish_ticket_comment(
                ticket=ticket,
                response_data=response_doc,
                actor=user
            )
            if status_reopened:
                refreshed = await self.ticket_service.get_ticket(ticket_id)
                if refreshed:
                    await event_dispatcher.publish_ticket_status_changed(
                        ticket=refreshed,
                        old_status=current_status,
                        new_status=TicketStatus.IN_PROGRESS.value,
                        actor=user
                    )
        except Exception as ws_err:
            logger.debug(f"[WS] Non-blocking WebSocket dispatch error: {ws_err}")

        # Send acknowledgment email to sender
        ticket_ref = ticket_id[-6:].upper()
        try:
            EmailService.send_email(
                inbound.sender_email,
                f"Re: [TICK-{ticket_ref}] Réponse bien reçue — {ticket.get('subject')}",
                (
                    f"<h2>Votre réponse a été ajoutée au ticket #{ticket_ref}</h2>"
                    f"<p>Nous avons bien reçu votre complément d'information.</p>"
                    f"<p><b>Ticket :</b> #{ticket_ref} — {ticket.get('subject')}<br/>"
                    f"<b>Statut actuel :</b> {update_fields.get('status', current_status)}</p>"
                    f"<p>L'équipe support a été notifiée.</p>"
                )
            )
        except Exception as email_err:
            logger.warning(f"[EmailToTicket] Could not send reply ack: {email_err}")

        logger.info(f"[Threading] Successfully appended reply to Ticket #{ticket_ref} from {inbound.sender_email}")
        return {
            "created": False,
            "replied": True,
            "ticket_id": ticket_id,
            "ticket_subject": ticket.get("subject"),
            "status": update_fields.get("status", current_status),
        }

    async def process_inbound_email(self, inbound: InboundEmail) -> Dict[str, Any]:
        """
        Full inbound processing pipeline for a single email:
        1. Ignore check (system senders)
        2. Idempotency acquisition
        3. Sender resolution / Non-privileged auto-provision
        4. Attachment saving
        5. Threading check:
           - Existing ticket -> Append reply
           - New incident -> AI triage & Ticket creation
        6. Persist outcome & mark read in IMAP
        """
        # Step 1: Filter system loops
        if self._should_ignore_sender(inbound.sender_email):
            logger.debug(f"[EmailToTicket] Skipped ignored sender: {inbound.sender_email}")
            return {"created": False, "skipped": True, "reason": "ignored_sender"}

        # Step 2: Acquire idempotency lock
        acquired = await self._acquire_processing_lock(inbound)
        if not acquired:
            return {"created": False, "skipped": True, "reason": "already_processed"}

        # Step 3: Resolve sender
        user = await self.resolve_user(inbound.sender_email, inbound.sender_name)
        if not user:
            await self._record_outcome(
                inbound.message_id,
                status="FAILED",
                action="REJECTED",
                error_message="Unknown sender and auto-provision is disabled."
            )
            return {"created": False, "reason": "unknown_sender"}

        # Step 4: Save attachments safely
        attachment_paths = self.save_attachments(inbound)

        # Step 5: Check threading (is this an existing ticket reply?)
        existing_ticket = await self.find_existing_ticket_for_email(inbound)
        if existing_ticket:
            reply_result = await self.append_reply_to_ticket(
                ticket=existing_ticket,
                inbound=inbound,
                user=user,
                attachment_paths=attachment_paths
            )
            await self._record_outcome(
                inbound.message_id,
                status="PROCESSED",
                action="REPLY_ADDED",
                ticket_id=existing_ticket["id"],
                details=reply_result
            )
            if inbound.imap_uid:
                mark_email_as_read(inbound.imap_uid)
            return reply_result

        # Step 6: Create new ticket via AI Chatbot pipeline
        try:
            ticket = await self.chatbot.create_ticket_from_email(
                subject=inbound.subject,
                body=inbound.body,
                user_id=user["id"],
                attachments=attachment_paths,
            )
        except ValueError as val_err:
            # Email rejected by AI triage as not a valid support incident
            reason = str(val_err)
            await self._record_outcome(
                inbound.message_id,
                status="FAILED",
                action="REJECTED",
                error_message=reason
            )
            logger.info(f"[EmailToTicket] Email rejected by triage: {inbound.subject} — {reason}")
            if inbound.imap_uid:
                mark_email_as_read(inbound.imap_uid)
            return {"created": False, "reason": reason}
        except Exception as exc:
            reason = f"Unexpected ticket creation error: {exc}"
            await self._record_outcome(
                inbound.message_id,
                status="FAILED",
                action="ERROR",
                error_message=reason
            )
            logger.exception(f"[EmailToTicket] {reason}")
            return {"created": False, "error": reason}

        # Step 7: Record successful creation and acknowledge
        await self._record_outcome(
            inbound.message_id,
            status="PROCESSED",
            action="TICKET_CREATED",
            ticket_id=ticket["id"],
            details={"priority": ticket.get("priority"), "category": ticket.get("category")}
        )

        if inbound.imap_uid:
            mark_email_as_read(inbound.imap_uid)

        # Send confirmation email formatted with [TICK-...] reference for robust threading
        ticket_ref = ticket["id"][-6:].upper()
        try:
            EmailService.send_email(
                inbound.sender_email,
                f"Ticket [TICK-{ticket_ref}] créé — {ticket['subject']}",
                (
                    f"<h2>Votre demande a été enregistrée</h2>"
                    f"<p>Nous avons bien reçu votre email et créé un ticket de support.</p>"
                    f"<p><b>Référence :</b> [TICK-{ticket_ref}]<br/>"
                    f"<b>Objet :</b> {ticket['subject']}<br/>"
                    f"<b>Catégorie :</b> {ticket['category']} &gt; {ticket.get('subcategory', 'Général')}<br/>"
                    f"<b>Priorité :</b> {ticket['priority']}<br/>"
                    f"<b>Statut :</b> {ticket['status']}</p>"
                    f"<p>Pour ajouter un complément, répondez simplement à cet email en conservant l'objet.</p>"
                    f"<p>Cordialement,<br/><b>Support GEISER Helpdesk IA</b></p>"
                )
            )
        except Exception as email_err:
            logger.warning(f"[EmailToTicket] Confirmation email dispatch notice: {email_err}")

        logger.info(f"[EmailToTicket] Successfully created Ticket [TICK-{ticket_ref}] for {inbound.sender_email}")
        return {
            "created": True,
            "replied": False,
            "ticket_id": ticket["id"],
            "subject": ticket["subject"],
            "priority": ticket["priority"],
            "category": ticket["category"],
        }

    async def poll_and_process(self) -> Dict[str, Any]:
        """
        Polls IMAP inbox, extracts unread messages, processes each one with error isolation,
        and returns execution statistics.
        """
        import asyncio
        from services.imap_service import fetch_unread_emails, is_imap_configured

        if not is_imap_configured():
            return {
                "fetched": 0, "created": 0, "replied": 0, "rejected": 0,
                "skipped": 0, "error": "imap_not_configured"
            }

        try:
            inbound_list = await asyncio.to_thread(fetch_unread_emails)
        except Exception as e:
            logger.error(f"[EmailToTicket] IMAP fetch thread exception: {e}")
            return {
                "fetched": 0, "created": 0, "replied": 0, "rejected": 0,
                "skipped": 0, "error": str(e)
            }

        stats: Dict[str, Any] = {
            "fetched": len(inbound_list),
            "created": 0,
            "replied": 0,
            "rejected": 0,
            "skipped": 0,
            "tickets": []
        }

        for inbound in inbound_list:
            try:
                res = await self.process_inbound_email(inbound)
                if res.get("skipped"):
                    stats["skipped"] += 1
                elif res.get("created"):
                    stats["created"] += 1
                    stats["tickets"].append({
                        "ticket_id": res.get("ticket_id"),
                        "subject": res.get("subject"),
                        "type": "NEW_TICKET"
                    })
                elif res.get("replied"):
                    stats["replied"] += 1
                    stats["tickets"].append({
                        "ticket_id": res.get("ticket_id"),
                        "subject": res.get("ticket_subject"),
                        "type": "THREADED_REPLY"
                    })
                else:
                    stats["rejected"] += 1
            except Exception as e:
                logger.error(f"[EmailToTicket] Error processing email {inbound.message_id}: {e}")
                stats["rejected"] += 1

        logger.info(f"[EmailToTicket] Poll complete: {stats}")
        return stats
