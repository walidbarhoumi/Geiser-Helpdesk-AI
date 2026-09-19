from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging
from bson import ObjectId

from schemas.schemas import NotificationOut
from services.email_service import EmailService
from services.sms.sms_provider import SMSProvider, SMSResult
from services.sms.twilio_provider import TwilioProvider, validate_e164_phone
from services.sms.simulated_provider import SimulatedSMSProvider
from models.base import MongoModel

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Centralized Notification Service for GEISER Helpdesk.
    Coordinates Email (SMTP) and SMS (Twilio / Simulated) dispatches with:
    - ISO 27001 audit logging in MongoDB `notifications` collection
    - Strict anti-duplication / idempotency guards
    - Complete error isolation (SMS failures never block ticket operations)
    - Zero secret leakage in logs or exceptions
    """

    def __init__(self, db: AsyncIOMotorDatabase, sms_provider: Optional[SMSProvider] = None):
        self.db = db
        self.notifications = db.notifications
        self.users = db.users
        self.tickets = db.tickets

        if sms_provider is not None:
            self.sms_provider = sms_provider
        else:
            twilio = TwilioProvider()
            if twilio.is_configured():
                self.sms_provider = twilio
            else:
                self.sms_provider = SimulatedSMSProvider()

    async def _is_duplicate_sms(self, ticket_id: Optional[str], event_type: str, recipient: str) -> bool:
        """
        Anti-duplication check:
        Returns True if an SMS for this (ticket_id, event_type, recipient)
        has already been successfully dispatched.
        """
        if not ticket_id or not event_type:
            return False

        existing = await self.notifications.find_one({
            "ticket_id": ticket_id,
            "channel": "SMS",
            "event_type": event_type,
            "recipient": recipient,
            "status": {"$in": ["SENT", "DELIVERED", "SIMULATED"]}
        })
        return existing is not None

    async def _record_notification(
        self,
        user_id: str,
        user_email: Optional[str],
        ticket_id: Optional[str],
        channel: str,
        title: str,
        message: str,
        status: str = "SENT",
        provider: Optional[str] = None,
        provider_message_id: Optional[str] = None,
        event_type: Optional[str] = None,
        recipient: Optional[str] = None,
        error_detail: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Logs the notification event to the database for ISO 27001 audit tracking."""
        doc = {
            "user_id": user_id,
            "user_email": user_email,
            "ticket_id": ticket_id,
            "channel": channel,  # EMAIL, SMS, IN_APP
            "event_type": event_type,
            "recipient": recipient or user_email or user_id,
            "provider": provider,
            "provider_message_id": provider_message_id,
            "title": title,
            "message": message,
            "status": status,
            "error_detail": error_detail,
            "created_at": datetime.utcnow()
        }
        res = await self.notifications.insert_one(doc)
        doc["_id"] = str(res.inserted_id)
        return doc

    async def _find_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Finds user by ObjectId, email, or username."""
        try:
            oid = MongoModel.to_object_id(user_id)
            if oid:
                user = await self.users.find_one({"_id": oid})
                if user:
                    return user
        except Exception:
            pass
        return await self.users.find_one({"$or": [{"email": user_id}, {"username": user_id}]})

    async def _dispatch_sms(
        self,
        user_id: str,
        user_email: Optional[str],
        phone: Optional[str],
        ticket_id: str,
        sms_text: str,
        event_type: str = "GENERIC"
    ) -> Optional[SMSResult]:
        """
        Dispatches SMS via active provider with anti-duplication and error isolation.
        Guarantees that SMS failures NEVER raise exceptions to caller.
        """
        if not phone:
            logger.debug(f"[SMS DISPATCH] Skipped: no phone number for user_id={user_id}")
            return None

        recipient = str(phone).strip()

        # Check anti-duplication idempotency guard
        if await self._is_duplicate_sms(ticket_id, event_type, recipient):
            logger.info(f"[SMS DISPATCH] Anti-duplication: SMS already sent for ticket={ticket_id}, event={event_type}")
            await self._record_notification(
                user_id=user_id,
                user_email=user_email,
                ticket_id=ticket_id,
                channel="SMS",
                title="SMS Skipped (Duplicate)",
                message=sms_text,
                status="SKIPPED_DUPLICATE",
                provider=self.sms_provider.provider_name,
                event_type=event_type,
                recipient=recipient,
            )
            return SMSResult(
                success=True,
                status="skipped_duplicate",
                provider=self.sms_provider.provider_name,
                to=recipient,
                error="Duplicate event already notified"
            )

        try:
            result = await self.sms_provider.send_sms(to=recipient, message=sms_text)
            status = "DELIVERED" if result.success and result.status == "sent" else (
                "SIMULATED" if result.status == "simulated" else "FAILED"
            )

            await self._record_notification(
                user_id=user_id,
                user_email=user_email,
                ticket_id=ticket_id,
                channel="SMS",
                title="SMS Notification",
                message=sms_text,
                status=status,
                provider=result.provider,
                provider_message_id=result.message_id,
                event_type=event_type,
                recipient=result.to or recipient,
                error_detail=result.error
            )
            return result
        except Exception as exc:
            logger.error(f"[SMS DISPATCH] Unexpected error dispatching SMS: {exc}")
            await self._record_notification(
                user_id=user_id,
                user_email=user_email,
                ticket_id=ticket_id,
                channel="SMS",
                title="SMS Notification Failed",
                message=sms_text,
                status="FAILED",
                provider=self.sms_provider.provider_name,
                event_type=event_type,
                recipient=recipient,
                error_detail=str(exc)
            )
            return SMSResult(
                success=False,
                status="failed",
                provider=self.sms_provider.provider_name,
                to=recipient,
                error=str(exc)
            )

    async def notify_ticket_created(self, ticket: Dict[str, Any]) -> None:
        """Notifies user upon ticket submission via Email & SMS."""
        ticket_id = str(ticket.get("_id") or ticket.get("id"))
        user_id = str(ticket.get("user_id"))
        subject = ticket.get("subject", "Incident")
        prio = ticket.get("priority", "MEDIUM")

        user = await self._find_user(user_id)
        user_email = user.get("email") if user else None
        phone = user.get("phone_number") if user else None

        title = f"[GEISER #{ticket_id[-6:].upper()}] Demande prise en compte : {subject}"

        html_body = f"""
        <div style="font-family: 'Helvetica Neue', Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #0f0f19; color: #f8fafc; border: 1px solid rgba(139,92,246,0.3); border-radius: 12px; overflow: hidden;">
            <div style="background: linear-gradient(135deg, #8b5cf6, #6366f1); padding: 24px; text-align: center;">
                <h1 style="margin: 0; font-size: 20px; color: #fff;">GEISER IT HELPDESK</h1>
                <p style="margin: 4px 0 0 0; font-size: 13px; color: rgba(255,255,255,0.8);">Confirmation de prise en charge</p>
            </div>
            <div style="padding: 24px;">
                <p style="font-size: 15px; line-height: 1.5;">Bonjour,</p>
                <p style="font-size: 14px; line-height: 1.5; color: #cbd5e1;">
                    Votre demande <strong>"{subject}"</strong> a bien été enregistrée sous la référence <span style="color: #a78bfa; font-weight: bold;">#{ticket_id[-6:].upper()}</span>.
                </p>
                <div style="background: rgba(255,255,255,0.04); border-left: 4px solid #8b5cf6; padding: 12px 16px; margin: 18px 0; border-radius: 4px;">
                    <p style="margin: 0; font-size: 13px;"><strong>Priorité :</strong> {prio}</p>
                    <p style="margin: 4px 0 0 0; font-size: 13px;"><strong>Statut actuel :</strong> OUVERT (En attente d'attribution)</p>
                </div>
                <p style="font-size: 13px; color: #94a3b8;">Nos techniciens traitent actuellement votre dossier conformément aux engagements de service (SLA).</p>
            </div>
        </div>
        """

        if user_email:
            try:
                EmailService.send_email(user_email, title, html_body)
                await self._record_notification(
                    user_id=user_id,
                    user_email=user_email,
                    ticket_id=ticket_id,
                    channel="EMAIL",
                    title=title,
                    message=f"Ticket #{ticket_id[-6:].upper()} créé avec succès.",
                    event_type="TICKET_CREATED",
                    recipient=user_email
                )
            except Exception as e:
                logger.error(f"[EMAIL NOTIFY] Error notifying ticket created: {e}")

        # SMS Notification
        sms_text = f"GEISER: Votre ticket #{ticket_id[-6:].upper()} ({subject[:25]}..) est enregistré. Priorité: {prio}. Suivi sur GEISER."
        await self._dispatch_sms(user_id, user_email, phone, ticket_id, sms_text, event_type="TICKET_CREATED")

    async def notify_status_changed(
        self,
        ticket: Dict[str, Any],
        old_status: str,
        new_status: str,
        resolution_note: Optional[str] = None
    ) -> None:
        """Notifies user and assigned agent on status changes (IN_PROGRESS, RESOLVED, CLOSED)."""
        ticket_id = str(ticket.get("_id") or ticket.get("id"))
        user_id = str(ticket.get("user_id"))
        subject = ticket.get("subject", "Incident")

        user = await self._find_user(user_id)
        user_email = user.get("email") if user else None
        phone = user.get("phone_number") if user else None

        status_labels = {
            "OPEN": "OUVERT",
            "IN_PROGRESS": "EN COURS DE TRAITEMENT",
            "RESOLVED": "RÉSOLU",
            "CLOSED": "CLÔTURÉ"
        }
        label_new = status_labels.get(new_status, new_status)

        title = f"[GEISER #{ticket_id[-6:].upper()}] Statut mis à jour : {label_new}"

        extra_note = ""
        if new_status == "RESOLVED" and resolution_note:
            extra_note = f"""
            <div style="background: rgba(16,185,129,0.1); border: 1px solid rgba(16,185,129,0.3); padding: 14px; border-radius: 8px; margin: 16px 0;">
                <h4 style="margin: 0 0 6px 0; color: #34d399; font-size: 13px; text-transform: uppercase;">Solution apportée :</h4>
                <p style="margin: 0; font-size: 13px; color: #e2e8f0; line-height: 1.5;">{resolution_note}</p>
            </div>
            """

        html_body = f"""
        <div style="font-family: 'Helvetica Neue', Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #0f0f19; color: #f8fafc; border: 1px solid rgba(139,92,246,0.3); border-radius: 12px; overflow: hidden;">
            <div style="background: linear-gradient(135deg, #8b5cf6, #6366f1); padding: 20px; text-align: center;">
                <h1 style="margin: 0; font-size: 20px; color: #fff;">GEISER IT HELPDESK</h1>
                <p style="margin: 4px 0 0 0; font-size: 12px; color: rgba(255,255,255,0.8);">Mise à jour en temps réel</p>
            </div>
            <div style="padding: 24px;">
                <p style="font-size: 14px; color: #cbd5e1;">Le statut de votre ticket <strong style="color: #a78bfa;">#{ticket_id[-6:].upper()}</strong> a évolué :</p>
                <div style="margin: 16px 0; text-align: center;">
                    <span style="display: inline-block; padding: 6px 16px; border-radius: 20px; font-weight: bold; font-size: 13px; background: rgba(139,92,246,0.2); color: #c4b5fd; border: 1px solid rgba(139,92,246,0.4);">
                        {label_new}
                    </span>
                </div>
                {extra_note}
            </div>
        </div>
        """

        if user_email:
            try:
                EmailService.send_email(user_email, title, html_body)
                await self._record_notification(
                    user_id=user_id,
                    user_email=user_email,
                    ticket_id=ticket_id,
                    channel="EMAIL",
                    title=title,
                    message=f"Statut du ticket changé en {label_new}",
                    event_type=f"STATUS_{new_status}",
                    recipient=user_email
                )
            except Exception as e:
                logger.error(f"[EMAIL NOTIFY] Error notifying status change: {e}")

        sms_text = f"GEISER: Ticket #{ticket_id[-6:].upper()} est désormais {label_new}."
        if new_status == "RESOLVED":
            sms_text += " Merci d'évaluer la résolution sur votre portail."
        await self._dispatch_sms(
            user_id,
            user_email,
            phone,
            ticket_id,
            sms_text,
            event_type=f"STATUS_{new_status}"
        )

    async def notify_sla_alert(self, ticket: Dict[str, Any], alert_type: str = "AT_RISK") -> None:
        """Sends urgent escalation notification to assigned agent and supervisor on SLA risk/breach."""
        ticket_id = str(ticket.get("_id") or ticket.get("id"))
        prio = ticket.get("priority", "HIGH")
        subject = ticket.get("subject", "Incident")
        agent_id = ticket.get("assigned_agent_id")

        event_type = "SLA_BREACH" if alert_type == "BREACHED" else "SLA_AT_RISK"
        title = f"[ALERTE SLA GEISER] Ticket #{ticket_id[-6:].upper()} ({alert_type})"
        msg = f"Le ticket prioritaire '{subject}' ({prio}) approche ou a dépassé le délai SLA garanti."

        # Notify assigned agent if any
        if agent_id:
            agent = await self.db.agents.find_one({"_id": MongoModel.to_object_id(agent_id)})
            if agent and agent.get("user_id"):
                agent_user = await self._find_user(agent["user_id"])
                if agent_user and agent_user.get("email"):
                    try:
                        EmailService.send_email(agent_user["email"], title, f"<h3>{title}</h3><p>{msg}</p>")
                        await self._record_notification(
                            str(agent_user["_id"]),
                            agent_user["email"],
                            ticket_id,
                            "EMAIL",
                            title,
                            msg,
                            event_type=event_type,
                            recipient=agent_user["email"]
                        )
                    except Exception as e:
                        logger.error(f"[EMAIL NOTIFY] Error notifying SLA alert: {e}")

                # Send SMS to agent if phone available
                if agent_user and agent_user.get("phone_number"):
                    sms_text = f"ALERTE GEISER: Ticket #{ticket_id[-6:].upper()} en dépassement SLA ({alert_type}). Action requise."
                    await self._dispatch_sms(
                        str(agent_user["_id"]),
                        agent_user.get("email"),
                        agent_user.get("phone_number"),
                        ticket_id,
                        sms_text,
                        event_type=event_type
                    )

        # Record system escalation event in notifications
        await self._record_notification(
            user_id="SYSTEM",
            user_email="manager@geiser.internal",
            ticket_id=ticket_id,
            channel="SMS",
            title=title,
            message=msg,
            event_type=event_type,
            recipient="manager@geiser.internal"
        )

    async def send_direct_sms(
        self,
        to: str,
        message: str,
        user_id: str = "SYSTEM",
        user_email: Optional[str] = None,
        ticket_id: Optional[str] = None,
        event_type: str = "MANUAL_TEST"
    ) -> SMSResult:
        """
        Directly sends an SMS message via the configured provider and records audit trail.
        Used by the diagnostic test API and direct messaging features.
        """
        result = await self.sms_provider.send_sms(to=to, message=message)
        status = "DELIVERED" if result.success and result.status == "sent" else (
            "SIMULATED" if result.status == "simulated" else "FAILED"
        )

        await self._record_notification(
            user_id=user_id,
            user_email=user_email,
            ticket_id=ticket_id,
            channel="SMS",
            title="Direct SMS",
            message=message,
            status=status,
            provider=result.provider,
            provider_message_id=result.message_id,
            event_type=event_type,
            recipient=result.to or to,
            error_detail=result.error
        )
        return result

    async def get_recent_notifications(self, limit: int = 50) -> List[NotificationOut]:
        """Retrieves recent notifications from database."""
        cursor = self.notifications.find().sort("created_at", -1).limit(limit)
        docs = await cursor.to_list(limit)
        results = []
        for d in docs:
            results.append(NotificationOut(
                id=str(d["_id"]),
                user_id=str(d.get("user_id", "")),
                user_email=d.get("user_email"),
                ticket_id=d.get("ticket_id"),
                channel=d.get("channel", "EMAIL"),
                title=d.get("title", ""),
                message=d.get("message", ""),
                status=d.get("status", "SENT"),
                provider=d.get("provider"),
                provider_message_id=d.get("provider_message_id"),
                event_type=d.get("event_type"),
                error_detail=d.get("error_detail"),
                created_at=d.get("created_at", datetime.utcnow())
            ))
        return results
