from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from schemas.schemas import TicketPriority, SLAStatus, TicketStatus
from models.base import MongoModel
from services.email_service import EmailService

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Default SLA Policies (hours) — configurable via DB overrides
# ──────────────────────────────────────────────────────────────
DEFAULT_SLA_POLICIES: Dict[str, Dict] = {
    TicketPriority.URGENT: {
        "response_time_hours": 1.0,
        "resolution_time_hours": 4.0,
        "at_risk_threshold_pct": 0.20,
    },
    TicketPriority.HIGH: {
        "response_time_hours": 4.0,
        "resolution_time_hours": 8.0,
        "at_risk_threshold_pct": 0.20,
    },
    TicketPriority.MEDIUM: {
        "response_time_hours": 8.0,
        "resolution_time_hours": 24.0,
        "at_risk_threshold_pct": 0.20,
    },
    TicketPriority.LOW: {
        "response_time_hours": 24.0,
        "resolution_time_hours": 72.0,
        "at_risk_threshold_pct": 0.20,
    },
}


class SLAService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.tickets = db.tickets
        self.sla_policies = db.sla_policies
        self.sla_alerts = db.sla_alerts

    async def get_policy(self, priority: str) -> Dict:
        """Get SLA policy — DB override first, then default."""
        override = await self.sla_policies.find_one({"priority": priority})
        if override:
            return override
        return DEFAULT_SLA_POLICIES.get(priority, DEFAULT_SLA_POLICIES[TicketPriority.MEDIUM])

    async def get_all_policies(self) -> List[Dict]:
        """Return all SLA policies (merged defaults + DB overrides)."""
        result = []
        for prio in [TicketPriority.URGENT, TicketPriority.HIGH, TicketPriority.MEDIUM, TicketPriority.LOW]:
            policy = await self.get_policy(prio)
            result.append({
                "priority": prio,
                "response_time_hours": policy["response_time_hours"],
                "resolution_time_hours": policy["resolution_time_hours"],
                "at_risk_threshold_pct": policy.get("at_risk_threshold_pct", 0.20),
            })
        return result

    async def update_policy(self, priority: str, update: Dict) -> Dict:
        """Admin override of SLA policy for a given priority."""
        update["priority"] = priority
        await self.sla_policies.update_one(
            {"priority": priority},
            {"$set": update},
            upsert=True
        )
        return await self.get_policy(priority)

    async def compute_sla_deadline(self, priority: str, created_at: datetime) -> datetime:
        """Compute resolution SLA deadline from creation time."""
        policy = await self.get_policy(priority)
        hours = policy["resolution_time_hours"]
        return created_at + timedelta(hours=hours)

    async def compute_sla_response_deadline(self, priority: str, created_at: datetime) -> datetime:
        """Compute response SLA deadline from creation time."""
        policy = await self.get_policy(priority)
        hours = policy["response_time_hours"]
        return created_at + timedelta(hours=hours)

    async def compute_sla_status(self, ticket: Dict) -> SLAStatus:
        """
        Evaluates current SLA status for a ticket:
        - BREACHED: deadline has passed
        - AT_RISK: less than threshold% of time remaining
        - ON_TRACK: otherwise
        """
        deadline = ticket.get("sla_deadline")
        created_at = ticket.get("created_at")

        if not deadline or not created_at:
            return SLAStatus.ON_TRACK

        now = datetime.utcnow()

        if now >= deadline:
            return SLAStatus.BREACHED

        total_seconds = (deadline - created_at).total_seconds()
        remaining_seconds = (deadline - now).total_seconds()

        if total_seconds <= 0:
            return SLAStatus.BREACHED

        remaining_pct = remaining_seconds / total_seconds
        policy = await self.get_policy(ticket.get("priority", TicketPriority.MEDIUM))
        threshold = policy.get("at_risk_threshold_pct", 0.20)

        if remaining_pct <= threshold:
            return SLAStatus.AT_RISK

        return SLAStatus.ON_TRACK

    async def scan_tickets_and_alert(self) -> Dict:
        """
        Background job: scan all active tickets, update SLA statuses,
        fire email alerts for AT_RISK and BREACHED tickets.
        Returns summary stats.
        """
        now = datetime.utcnow()
        active_statuses = [TicketStatus.OPEN.value, TicketStatus.IN_PROGRESS.value]

        tickets = await self.tickets.find(
            {"status": {"$in": active_statuses}}
        ).to_list(1000)

        stats = {"scanned": 0, "at_risk": 0, "breached": 0, "alerted": 0}

        for ticket in tickets:
            stats["scanned"] += 1
            ticket_id = str(ticket["_id"])
            old_status = ticket.get("sla_status", SLAStatus.ON_TRACK.value)
            if hasattr(old_status, "value"):
                old_status = old_status.value
            new_status = await self.compute_sla_status(ticket)
            new_status_val = new_status.value if hasattr(new_status, "value") else new_status

            update_fields: Dict = {"sla_status": new_status_val}
            if new_status_val == SLAStatus.BREACHED.value and old_status != SLAStatus.BREACHED.value:
                update_fields["sla_breached_at"] = now

            # Persist updated SLA status
            await self.tickets.update_one(
                {"_id": ticket["_id"]},
                {"$set": update_fields}
            )

            if new_status_val == SLAStatus.AT_RISK.value:
                stats["at_risk"] += 1
            elif new_status_val == SLAStatus.BREACHED.value:
                stats["breached"] += 1

            # Fire alert only if status changed to AT_RISK or BREACHED
            if new_status_val in (SLAStatus.AT_RISK.value, SLAStatus.BREACHED.value) and new_status_val != old_status:
                await self._fire_alert(ticket, new_status, now)
                stats["alerted"] += 1

        logger.info(f"SLA Scan complete: {stats}")
        return stats

    async def _fire_alert(self, ticket: Dict, sla_status: SLAStatus, now: datetime):
        """Persist alert record and send email notification."""
        ticket_id = str(ticket["_id"])
        deadline = ticket.get("sla_deadline")
        remaining_min = int((deadline - now).total_seconds() / 60) if deadline and deadline > now else 0

        # Store alert in DB
        alert_doc = {
            "ticket_id": ticket_id,
            "subject": ticket.get("subject", ""),
            "priority": ticket.get("priority"),
            "sla_status": sla_status,
            "sla_deadline": deadline,
            "time_remaining_minutes": remaining_min,
            "assigned_agent_id": ticket.get("assigned_agent_id"),
            "created_at": now,
        }
        await self.sla_alerts.insert_one(alert_doc)

        # Build and send email alert
        priority = ticket.get("priority", "")
        subject_line = ticket.get("subject", "")

        if sla_status == SLAStatus.BREACHED:
            email_subject = f"🔴 [SLA DÉPASSÉ] Ticket #{ticket_id[-6:].upper()} — {subject_line}"
            body = (
                f"<h2 style='color:#dc2626'>SLA Dépassé</h2>"
                f"<p>Le ticket <b>#{ticket_id[-6:].upper()}</b> a dépassé son accord de niveau de service.</p>"
                f"<p><b>Objet :</b> {subject_line}<br/>"
                f"<b>Priorité :</b> {priority}<br/>"
                f"<b>Échéance SLA :</b> {deadline.strftime('%d/%m/%Y %H:%M') if deadline else 'N/A'}</p>"
                f"<p>Action immédiate requise.</p>"
            )
        else:
            email_subject = f"⚠️ [SLA À RISQUE] Ticket #{ticket_id[-6:].upper()} — {subject_line}"
            body = (
                f"<h2 style='color:#d97706'>SLA À Risque — {remaining_min} min restantes</h2>"
                f"<p>Le ticket <b>#{ticket_id[-6:].upper()}</b> risque de dépasser son SLA dans <b>{remaining_min} minutes</b>.</p>"
                f"<p><b>Objet :</b> {subject_line}<br/>"
                f"<b>Priorité :</b> {priority}<br/>"
                f"<b>Échéance SLA :</b> {deadline.strftime('%d/%m/%Y %H:%M') if deadline else 'N/A'}</p>"
                f"<p>Veuillez traiter ce ticket en priorité.</p>"
            )

        # Notify assigned agent
        if ticket.get("assigned_agent_id"):
            try:
                agent = await self.db.agents.find_one(
                    {"_id": MongoModel.to_object_id(ticket["assigned_agent_id"])}
                )
                if agent and agent.get("user_id"):
                    user = await self.db.users.find_one(
                        {"_id": MongoModel.to_object_id(agent["user_id"])}
                    )
                    if user and user.get("email"):
                        EmailService.send_email(user["email"], email_subject, body)
            except Exception as e:
                logger.warning(f"Could not send SLA alert email to agent: {e}")

        # Notify admins
        try:
            admins = await self.db.users.find({"role": "ADMIN"}).to_list(10)
            for admin in admins:
                if admin.get("email"):
                    EmailService.send_email(admin["email"], email_subject, body)
        except Exception as e:
            logger.warning(f"Could not send SLA alert email to admins: {e}")

    async def get_active_alerts(self, limit: int = 50) -> List[Dict]:
        """Return most recent SLA alerts for the dashboard."""
        alerts = await self.sla_alerts.find().sort("created_at", -1).limit(limit).to_list(limit)
        return [MongoModel.format_id(a) for a in alerts]

    async def get_at_risk_tickets(self, limit: int = 100) -> List[Dict]:
        """Return active tickets with AT_RISK or BREACHED SLA status."""
        active_statuses = [TicketStatus.OPEN.value, TicketStatus.IN_PROGRESS.value]
        tickets = await self.tickets.find({
            "status": {"$in": active_statuses},
            "sla_status": {"$in": [SLAStatus.AT_RISK.value, SLAStatus.BREACHED.value]},
        }).sort("sla_deadline", 1).limit(limit).to_list(limit)

        now = datetime.utcnow()
        result = []
        for ticket in tickets:
            formatted = MongoModel.format_id(ticket)
            deadline = ticket.get("sla_deadline")
            remaining_min = None
            if deadline:
                remaining_min = max(0, int((deadline - now).total_seconds() / 60))
            result.append({
                "ticket_id": formatted["id"],
                "subject": ticket.get("subject", ""),
                "priority": ticket.get("priority"),
                "sla_status": ticket.get("sla_status"),
                "sla_deadline": deadline,
                "time_remaining_minutes": remaining_min,
                "assigned_agent_id": ticket.get("assigned_agent_id"),
                "created_at": ticket.get("created_at", now),
            })
        return result

    async def get_ticket_sla_detail(self, ticket_id: str) -> Optional[Dict]:
        """Get full SLA details for a specific ticket."""
        ticket = await self.tickets.find_one({"_id": MongoModel.to_object_id(ticket_id)})
        if not ticket:
            return None

        now = datetime.utcnow()
        deadline = ticket.get("sla_deadline")
        current_status = await self.compute_sla_status(ticket)
        policy = await self.get_policy(ticket.get("priority", TicketPriority.MEDIUM))

        time_remaining_min = None
        pct_consumed = None
        if deadline and ticket.get("created_at"):
            total_sec = (deadline - ticket["created_at"]).total_seconds()
            elapsed_sec = (now - ticket["created_at"]).total_seconds()
            remaining_sec = (deadline - now).total_seconds() if deadline > now else 0
            time_remaining_min = max(0, int(remaining_sec / 60))
            pct_consumed = min(100.0, round(elapsed_sec / total_sec * 100, 1)) if total_sec > 0 else 100.0

        return {
            "ticket_id": ticket_id,
            "subject": ticket.get("subject"),
            "priority": ticket.get("priority"),
            "sla_status": current_status,
            "sla_deadline": deadline,
            "sla_response_deadline": ticket.get("sla_response_deadline"),
            "sla_breached_at": ticket.get("sla_breached_at"),
            "time_remaining_minutes": time_remaining_min,
            "pct_consumed": pct_consumed,
            "policy": policy,
        }
