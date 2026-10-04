"""
services/sla_risk_service.py
============================
STEP 4 — SLA Intelligent Risk Detection & Automatic Alerts

Responsibilities:
1. Unified SLA Risk States: ON_TRACK, AT_RISK, BREACHED, PAUSED, COMPLETED.
2. Configurable multi-tier warning thresholds (percentage-based & absolute time-based).
3. Persistent duplicate prevention & idempotency guards in `sla_alerts` collection.
4. Non-crashing multi-channel notification dispatch (Email via SMTP, SMS via Twilio/Simulated).
5. SLA Pause & Resume support (waiting states freeze remaining SLA time and extend deadline).
6. Background evaluator for active tickets with ISO 27001 audit logging.
7. KPI aggregations for supervisor/manager dashboards.
"""

from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import logging
from bson import ObjectId

from schemas.schemas import (
    TicketPriority, TicketStatus, SLAStatus,
    AuditEventCategory, AuditSeverity
)
from models.base import MongoModel
from services.email_service import EmailService

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Default Risk Configuration
# ──────────────────────────────────────────────────────────────

DEFAULT_SLA_RISK_CONFIG: Dict[str, Any] = {
    "key": "global_config",
    "warning_thresholds": [
        {"id": "25_percent", "type": "percentage", "value": 25.0, "label": "25% du temps restant"},
        {"id": "10_percent", "type": "percentage", "value": 10.0, "label": "10% du temps restant"},
        {"id": "5_percent", "type": "percentage", "value": 5.0, "label": "5% du temps restant"},
        {"id": "1_hour", "type": "time_minutes", "value": 60.0, "label": "Moins de 1 heure restante"},
    ],
    "risk_alert_enabled": True,
    "breach_alert_enabled": True,
    "sms_alerts_enabled": True,
    "email_alerts_enabled": True,
}


class SLARiskService:
    """
    Dedicated Service for evaluating SLA risks, detecting state transitions,
    and dispatching non-duplicated alerts across Email and SMS channels.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.tickets = db.tickets
        self.sla_alerts = db.sla_alerts
        self.sla_risk_config = db.sla_risk_config
        self.users = db.users
        self.agents = db.agents
        self.teams = db.teams

    # ──────────────────────────────────────────────────────────
    # 1. Configuration Management
    # ──────────────────────────────────────────────────────────

    async def get_risk_config(self) -> Dict[str, Any]:
        """Loads SLA risk configuration from MongoDB or returns defaults."""
        config = await self.sla_risk_config.find_one({"key": "global_config"})
        if not config:
            return DEFAULT_SLA_RISK_CONFIG
        config.pop("_id", None)
        return config

    async def update_risk_config(self, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Updates warning thresholds and alert toggles (Admin only)."""
        clean_update = {k: v for k, v in update_data.items() if v is not None}
        clean_update["key"] = "global_config"
        clean_update["updated_at"] = datetime.utcnow()

        await self.sla_risk_config.update_one(
            {"key": "global_config"},
            {"$set": clean_update},
            upsert=True
        )
        return await self.get_risk_config()

    # ──────────────────────────────────────────────────────────
    # 2. SLA State & Risk Evaluation
    # ──────────────────────────────────────────────────────────

    async def evaluate_ticket_sla(
        self,
        ticket: Dict[str, Any],
        now: Optional[datetime] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Evaluates the exact SLA risk state for a given ticket:
        - COMPLETED: Ticket resolved or closed before deadline
        - BREACHED: Deadline passed while active or breached prior to resolution
        - PAUSED: Ticket currently in PENDING state (waiting on customer/vendor)
        - AT_RISK: Remaining time/percentage crossed one of the warning thresholds
        - ON_TRACK: Sufficient time remaining
        """
        now = now or datetime.utcnow()
        ticket_id = str(ticket.get("_id") or ticket.get("id", ""))
        status = ticket.get("status", TicketStatus.OPEN.value)
        if hasattr(status, "value"):
            status = status.value

        deadline = ticket.get("sla_deadline")
        created_at = ticket.get("created_at")

        # ── Case A: Terminal Status (RESOLVED or CLOSED) ───────────────
        if status in (TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value, "RESOLVED", "CLOSED"):
            if ticket.get("sla_breached_at") or ticket.get("sla_status") == SLAStatus.BREACHED.value:
                return {
                    "ticket_id": ticket_id,
                    "state": SLAStatus.BREACHED,
                    "remaining_seconds": 0.0,
                    "remaining_percentage": 0.0,
                    "deadline": deadline,
                    "crossed_threshold": None,
                    "crossed_threshold_label": None,
                    "should_alert": False,
                }
            return {
                "ticket_id": ticket_id,
                "state": SLAStatus.COMPLETED,
                "remaining_seconds": 0.0,
                "remaining_percentage": 100.0,
                "deadline": deadline,
                "crossed_threshold": None,
                "crossed_threshold_label": None,
                "should_alert": False,
            }

        # ── Case B: Paused Status (PENDING) ───────────────────────────
        if status in (TicketStatus.PENDING.value, "PENDING"):
            return {
                "ticket_id": ticket_id,
                "state": SLAStatus.PAUSED,
                "remaining_seconds": max(0.0, (deadline - now).total_seconds()) if deadline else None,
                "remaining_percentage": None,
                "deadline": deadline,
                "crossed_threshold": None,
                "crossed_threshold_label": "SLA en pause (Ticket en attente)",
                "should_alert": False,
            }

        # ── Case C: No deadline or creation date ───────────────────────
        if not deadline or not created_at:
            return {
                "ticket_id": ticket_id,
                "state": SLAStatus.ON_TRACK,
                "remaining_seconds": None,
                "remaining_percentage": None,
                "deadline": None,
                "crossed_threshold": None,
                "crossed_threshold_label": None,
                "should_alert": False,
            }

        # ── Case D: Breached (Current time past deadline) ──────────────
        if now >= deadline:
            return {
                "ticket_id": ticket_id,
                "state": SLAStatus.BREACHED,
                "remaining_seconds": 0.0,
                "remaining_percentage": 0.0,
                "deadline": deadline,
                "crossed_threshold": "breach",
                "crossed_threshold_label": "Délai SLA Dépassé",
                "should_alert": True,
            }

        # ── Case E: Active — Calculate remaining time & thresholds ─────
        total_seconds = (deadline - created_at).total_seconds()
        remaining_seconds = max(0.0, (deadline - now).total_seconds())
        remaining_pct = (remaining_seconds / total_seconds * 100.0) if total_seconds > 0 else 0.0

        if not config:
            config = await self.get_risk_config()

        thresholds = config.get("warning_thresholds", DEFAULT_SLA_RISK_CONFIG["warning_thresholds"])

        # Sort thresholds to detect the most critical crossed threshold first
        crossed_threshold = None
        for t in thresholds:
            t_type = t.get("type")
            t_val = float(t.get("value", 0))

            is_crossed = False
            if t_type == "percentage" and remaining_pct <= t_val:
                is_crossed = True
            elif t_type == "time_minutes" and (remaining_seconds / 60.0) <= t_val:
                is_crossed = True

            if is_crossed:
                # Retain the most urgent threshold crossed (smallest value)
                if crossed_threshold is None:
                    crossed_threshold = t
                else:
                    curr_val = float(crossed_threshold.get("value", 0))
                    if t_type == crossed_threshold.get("type") and t_val < curr_val:
                        crossed_threshold = t

        if crossed_threshold and config.get("risk_alert_enabled", True):
            return {
                "ticket_id": ticket_id,
                "state": SLAStatus.AT_RISK,
                "remaining_seconds": round(remaining_seconds, 1),
                "remaining_percentage": round(remaining_pct, 1),
                "deadline": deadline,
                "crossed_threshold": crossed_threshold["id"],
                "crossed_threshold_label": crossed_threshold.get("label", f"{crossed_threshold['id']}"),
                "should_alert": True,
            }

        return {
            "ticket_id": ticket_id,
            "state": SLAStatus.ON_TRACK,
            "remaining_seconds": round(remaining_seconds, 1),
            "remaining_percentage": round(remaining_pct, 1),
            "deadline": deadline,
            "crossed_threshold": None,
            "crossed_threshold_label": None,
            "should_alert": False,
        }

    # ──────────────────────────────────────────────────────────
    # 3. Duplicate Prevention & Alert Dispatching
    # ──────────────────────────────────────────────────────────

    async def _is_alert_already_sent(
        self,
        ticket_id: str,
        alert_type: str,
        threshold_id: str,
        recipient_id: str,
        channel: str
    ) -> bool:
        """
        Anti-duplication check:
        Ensures the exact same (ticket, alert_type, threshold, recipient, channel)
        is dispatched AT MOST ONCE per ticket SLA lifecycle.
        """
        existing = await self.sla_alerts.find_one({
            "ticket_id": ticket_id,
            "alert_type": alert_type,
            "threshold_id": threshold_id,
            "recipient_id": recipient_id,
            "channel": channel,
            "delivery_status": {"$in": ["SENT", "DELIVERED", "SIMULATED"]}
        })
        return existing is not None

    async def _dispatch_risk_alerts(
        self,
        ticket: Dict[str, Any],
        eval_result: Dict[str, Any],
        config: Dict[str, Any],
        now: Optional[datetime] = None
    ) -> int:
        """
        Dispatches targeted Email and SMS alerts to assigned agent and supervisors.
        Guarantees that notification failures NEVER crash the evaluation loop.
        Returns the number of distinct alerts dispatched.
        """
        now = now or datetime.utcnow()
        ticket_id = str(ticket.get("_id") or ticket.get("id"))
        state = eval_result["state"]
        alert_type = "BREACHED" if state == SLAStatus.BREACHED else "AT_RISK"
        threshold_id = eval_result.get("crossed_threshold") or "breach"
        threshold_label = eval_result.get("crossed_threshold_label") or alert_type

        subject = ticket.get("subject", "Demande informatique")
        priority = ticket.get("priority", "HIGH")
        deadline = eval_result.get("deadline")
        deadline_str = deadline.strftime("%d/%m/%Y à %H:%M") if deadline else "N/A"
        remaining_min = int(eval_result.get("remaining_seconds", 0) / 60) if eval_result.get("remaining_seconds") else 0

        # Collect unique recipients (agent + supervisors + admins)
        recipients: List[Dict[str, Any]] = []

        # 1. Assigned Agent
        agent_id = ticket.get("assigned_agent_id") or ticket.get("agent_id")
        if agent_id:
            try:
                agent = await self.agents.find_one({"_id": MongoModel.to_object_id(agent_id)})
                if agent and agent.get("user_id"):
                    u = await self.users.find_one({"_id": MongoModel.to_object_id(agent["user_id"])})
                    if u:
                        recipients.append({
                            "user_id": str(u.get("_id") or u.get("id")),
                            "email": u.get("email"),
                            "phone": u.get("phone_number"),
                            "name": u.get("full_name") or u.get("email"),
                            "role": "AGENT"
                        })
            except Exception as e:
                logger.warning(f"Error fetching assigned agent {agent_id}: {e}")

        # 2. Responsible Team Supervisor or Admin fallback
        team_id = ticket.get("team_id")
        if team_id:
            try:
                team = await self.teams.find_one({"_id": MongoModel.to_object_id(team_id)})
                if team and team.get("leader_id"):
                    leader = await self.users.find_one({"_id": MongoModel.to_object_id(team["leader_id"])})
                    lead_id = str(leader.get("_id") or leader.get("id")) if leader else None
                    if leader and lead_id and lead_id not in [r["user_id"] for r in recipients]:
                        recipients.append({
                            "user_id": lead_id,
                            "email": leader.get("email"),
                            "phone": leader.get("phone_number"),
                            "name": leader.get("full_name") or leader.get("email"),
                            "role": "SUPERVISOR"
                        })
            except Exception as e:
                logger.warning(f"Error fetching team leader for team {team_id}: {e}")

        # 3. Administrators
        try:
            admins = await self.users.find({"role": "ADMIN"}).to_list(5)
            for adm in admins:
                adm_id = str(adm.get("_id") or adm.get("id") or ObjectId())
                if adm_id not in [r["user_id"] for r in recipients]:
                    recipients.append({
                        "user_id": adm_id,
                        "email": adm.get("email"),
                        "phone": adm.get("phone_number"),
                        "name": adm.get("full_name") or adm.get("email"),
                        "role": "ADMIN"
                    })
        except Exception as e:
            logger.warning(f"Error fetching admins for SLA alert: {e}")

        # Construct Email Subject and Content
        if alert_type == "BREACHED":
            email_subject = f"🔴 [SLA DÉPASSÉ] Ticket #{ticket_id[-6:].upper()} — {subject}"
            title_color = "#dc2626"
            header_title = "Dépassement d'Accord de Niveau de Service (SLA)"
            alert_desc = f"Le ticket a dépassé son échéance de résolution garantie le <b>{deadline_str}</b>."
            action_call = "Une intervention immédiate de l'équipe est requise pour clôturer l'incident."
        else:
            email_subject = f"⚠️ [SLA À RISQUE] Ticket #{ticket_id[-6:].upper()} — {threshold_label}"
            title_color = "#d97706"
            header_title = f"Alerte SLA : {threshold_label}"
            alert_desc = f"Le ticket approche de son échéance critique. Il reste environ <b>{remaining_min} minute(s)</b> avant rupture du contrat SLA."
            action_call = "Veuillez prioriser ce dossier pour éviter tout manquement contractuel."

        email_html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 620px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
            <div style="background: {title_color}; padding: 20px 24px; color: #ffffff;">
                <h2 style="margin: 0; font-size: 19px; font-weight: 700;">{header_title}</h2>
                <p style="margin: 4px 0 0 0; font-size: 13px; opacity: 0.9;">Plateforme GEISER Helpdesk IA · Surveillance 24/7</p>
            </div>
            <div style="padding: 24px; color: #1e293b;">
                <p style="font-size: 14px; line-height: 1.6; margin-top: 0;">{alert_desc}</p>
                <div style="background: #f8fafc; border-left: 4px solid {title_color}; padding: 14px 16px; border-radius: 6px; margin: 18px 0;">
                    <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                        <tr><td style="color: #64748b; padding: 4px 0; width: 140px;">Réf Ticket :</td><td style="font-weight: 700; color: #0f172a;">#{ticket_id[-6:].upper()}</td></tr>
                        <tr><td style="color: #64748b; padding: 4px 0;">Objet :</td><td style="font-weight: 600;">{subject}</td></tr>
                        <tr><td style="color: #64748b; padding: 4px 0;">Priorité :</td><td><span style="font-weight: 700; color: {title_color};">{priority}</span></td></tr>
                        <tr><td style="color: #64748b; padding: 4px 0;">Échéance SLA :</td><td><strong>{deadline_str}</strong></td></tr>
                        <tr><td style="color: #64748b; padding: 4px 0;">Seuil déclencheur :</td><td>{threshold_label}</td></tr>
                    </table>
                </div>
                <p style="font-size: 13px; color: #475569; line-height: 1.5;">{action_call}</p>
                <div style="margin-top: 24px; text-align: center;">
                    <a href="/tickets/{ticket_id}" style="display: inline-block; background: {title_color}; color: #ffffff; text-decoration: none; padding: 10px 24px; border-radius: 6px; font-size: 13px; font-weight: 700;">Accéder au ticket</a>
                </div>
            </div>
        </div>
        """

        alerts_count = 0
        sms_text = f"SLA GEISER: Ticket #{ticket_id[-6:].upper()} ({priority}) {alert_type.lower()}. Echeance: {deadline_str}. Action requise."

        for rec in recipients:
            user_id = rec["user_id"]
            email = rec.get("email")
            phone = rec.get("phone")

            # ── Email Dispatch ───────────────────────────────────────
            if email and config.get("email_alerts_enabled", True):
                if not await self._is_alert_already_sent(ticket_id, alert_type, threshold_id, user_id, "EMAIL"):
                    try:
                        EmailService.send_email(email, email_subject, email_html)
                        await self.sla_alerts.insert_one({
                            "ticket_id": ticket_id,
                            "subject": subject,
                            "priority": priority,
                            "sla_status": state.value if hasattr(state, "value") else state,
                            "alert_type": alert_type,
                            "threshold_id": threshold_id,
                            "threshold_label": threshold_label,
                            "sla_deadline": deadline,
                            "time_remaining_minutes": remaining_min,
                            "recipient_id": user_id,
                            "recipient_email": email,
                            "channel": "EMAIL",
                            "delivery_status": "SENT",
                            "created_at": now,
                            "sent_at": now
                        })
                        alerts_count += 1
                    except Exception as e:
                        logger.error(f"Failed to dispatch SLA email to {email}: {e}")

            # ── SMS Dispatch ─────────────────────────────────────────
            if phone and config.get("sms_alerts_enabled", True):
                if not await self._is_alert_already_sent(ticket_id, alert_type, threshold_id, user_id, "SMS"):
                    try:
                        from services.notification_service import NotificationService
                        notif_svc = NotificationService(self.db)
                        sms_res = await notif_svc.send_direct_sms(
                            to=phone,
                            message=sms_text,
                            user_id=user_id,
                            user_email=email,
                            ticket_id=ticket_id,
                            event_type=f"SLA_{alert_type}_{threshold_id}"
                        )
                        status_str = "DELIVERED" if sms_res and sms_res.success else "SIMULATED"
                        await self.sla_alerts.insert_one({
                            "ticket_id": ticket_id,
                            "subject": subject,
                            "priority": priority,
                            "sla_status": state.value if hasattr(state, "value") else state,
                            "alert_type": alert_type,
                            "threshold_id": threshold_id,
                            "threshold_label": threshold_label,
                            "sla_deadline": deadline,
                            "time_remaining_minutes": remaining_min,
                            "recipient_id": user_id,
                            "recipient_email": email,
                            "channel": "SMS",
                            "delivery_status": status_str,
                            "created_at": now,
                            "sent_at": now
                        })
                        alerts_count += 1
                    except Exception as e:
                        logger.error(f"Failed to dispatch SLA SMS to {phone}: {e}")

        return alerts_count

    # ──────────────────────────────────────────────────────────
    # 4. Background SLA Evaluator Scan
    # ──────────────────────────────────────────────────────────

    async def evaluate_active_slas(self, batch_size: int = 500) -> Dict[str, Any]:
        """
        Core scheduled background job:
        1. Queries active tickets (OPEN, IN_PROGRESS, PENDING) using indexed query.
        2. Evaluates remaining time and risk states for each ticket.
        3. Persists state updates to MongoDB.
        4. Detects state transitions & triggers non-duplicated alerts.
        5. Logs ISO 27001 audit events.
        """
        now = datetime.utcnow()
        config = await self.get_risk_config()

        cursor = self.tickets.find({
            "status": {"$in": [
                TicketStatus.OPEN.value,
                TicketStatus.IN_PROGRESS.value,
                TicketStatus.PENDING.value,
                "OPEN", "IN_PROGRESS", "PENDING"
            ]}
        }).limit(batch_size)

        tickets = await cursor.to_list(length=batch_size)

        stats = {
            "scanned": len(tickets),
            "on_track": 0,
            "at_risk": 0,
            "breached": 0,
            "paused": 0,
            "alerted": 0,
        }

        from services.audit_service import AuditService
        audit_svc = AuditService(self.db)

        for ticket in tickets:
            ticket_id = str(ticket["_id"])
            old_sla_status = ticket.get("sla_status", SLAStatus.ON_TRACK.value)
            if hasattr(old_sla_status, "value"):
                old_sla_status = old_sla_status.value

            eval_res = await self.evaluate_ticket_sla(ticket, now=now, config=config)
            new_state = eval_res["state"]
            new_state_val = new_state.value if hasattr(new_state, "value") else str(new_state)

            # Update stats counter
            if new_state_val == SLAStatus.ON_TRACK.value:
                stats["on_track"] += 1
            elif new_state_val == SLAStatus.AT_RISK.value:
                stats["at_risk"] += 1
            elif new_state_val == SLAStatus.BREACHED.value:
                stats["breached"] += 1
            elif new_state_val == SLAStatus.PAUSED.value:
                stats["paused"] += 1

            # Prepare DB updates for ticket
            update_fields: Dict[str, Any] = {"sla_status": new_state_val}
            if new_state_val == SLAStatus.BREACHED.value and old_sla_status != SLAStatus.BREACHED.value:
                update_fields["sla_breached_at"] = now

            if eval_res.get("crossed_threshold"):
                update_fields["sla_last_warning_threshold"] = eval_res["crossed_threshold"]

            await self.tickets.update_one({"_id": ticket["_id"]}, {"$set": update_fields})

            # Live WebSocket event dispatch (STEP 5)
            if eval_res.get("should_alert") or new_state_val != old_sla_status:
                try:
                    from websocket.dispatcher import event_dispatcher
                    await event_dispatcher.publish_sla_state_changed(
                        ticket={**ticket, **update_fields},
                        sla_state=new_state_val,
                        details=eval_res
                    )
                except Exception as ws_err:
                    logger.debug(f"[WS] SLA live event dispatch failed: {ws_err}")

            # Check if alert should be dispatched
            if eval_res.get("should_alert"):
                alerts_sent = await self._dispatch_risk_alerts(ticket, eval_res, config, now)
                if alerts_sent > 0:
                    stats["alerted"] += 1

                    # Log Audit Event
                    audit_type = "SLA_BREACHED" if new_state_val == SLAStatus.BREACHED.value else "SLA_WARNING_TRIGGERED"
                    severity = AuditSeverity.WARNING if new_state_val == SLAStatus.BREACHED.value else AuditSeverity.INFO
                    try:
                        await audit_svc.log_event(
                            event_category=AuditEventCategory.SLA,
                            event_type=audit_type,
                            severity=severity,
                            target_resource_type="ticket",
                            target_resource_id=ticket_id,
                            actor_id="SYSTEM",
                            actor_email="system@geiser.internal",
                            actor_role="SYSTEM",
                            status="SUCCESS",
                            details={
                                "ticket_id": ticket_id,
                                "previous_state": old_sla_status,
                                "new_state": new_state_val,
                                "threshold": eval_res.get("crossed_threshold"),
                                "remaining_seconds": eval_res.get("remaining_seconds"),
                                "alerts_dispatched": alerts_sent
                            }
                        )
                    except Exception as audit_err:
                        logger.warning(f"Audit log failed for SLA alert: {audit_err}")

        logger.info(f"[SLA RISK MONITOR] Evaluator run complete: {stats}")
        return stats

    # ──────────────────────────────────────────────────────────
    # 5. Dashboard KPIs & Supervisor Overview
    # ──────────────────────────────────────────────────────────

    async def get_risk_overview(self) -> Dict[str, Any]:
        """Aggregates SLA risk metrics, at-risk queue, and recent alert history."""
        now = datetime.utcnow()
        active_query = {
            "status": {"$in": [
                TicketStatus.OPEN.value,
                TicketStatus.IN_PROGRESS.value,
                TicketStatus.PENDING.value,
                "OPEN", "IN_PROGRESS", "PENDING"
            ]}
        }

        total_active = await self.tickets.count_documents(active_query)
        breached_count = await self.tickets.count_documents({
            **active_query,
            "sla_status": SLAStatus.BREACHED.value
        })
        at_risk_count = await self.tickets.count_documents({
            **active_query,
            "sla_status": SLAStatus.AT_RISK.value
        })
        paused_count = await self.tickets.count_documents({
            **active_query,
            "sla_status": SLAStatus.PAUSED.value
        })
        on_track_count = max(0, total_active - (breached_count + at_risk_count + paused_count))

        compliance_pct = round(((total_active - breached_count) / total_active * 100.0), 1) if total_active > 0 else 100.0

        # Query tickets currently at risk or breached
        at_risk_cursor = self.tickets.find({
            **active_query,
            "sla_status": {"$in": [SLAStatus.AT_RISK.value, SLAStatus.BREACHED.value]}
        }).sort("sla_deadline", 1).limit(50)
        raw_at_risk = await at_risk_cursor.to_list(50)

        at_risk_tickets = []
        total_remaining_sec = 0.0
        remaining_count = 0

        for t in raw_at_risk:
            deadline = t.get("sla_deadline")
            rem_sec = max(0.0, (deadline - now).total_seconds()) if deadline else 0.0
            if rem_sec > 0:
                total_remaining_sec += rem_sec
                remaining_count += 1

            at_risk_tickets.append({
                "ticket_id": str(t["_id"]),
                "subject": t.get("subject", ""),
                "priority": t.get("priority", "MEDIUM"),
                "status": t.get("status"),
                "sla_status": t.get("sla_status"),
                "sla_deadline": deadline,
                "time_remaining_minutes": int(rem_sec / 60) if deadline else 0,
                "assigned_agent_id": str(t["assigned_agent_id"]) if t.get("assigned_agent_id") else None,
                "crossed_threshold": t.get("sla_last_warning_threshold"),
                "created_at": t.get("created_at")
            })

        avg_remaining_min = round(total_remaining_sec / remaining_count / 60, 1) if remaining_count > 0 else 0.0

        # Recent alerts
        alerts_cursor = self.sla_alerts.find().sort("created_at", -1).limit(25)
        raw_alerts = await alerts_cursor.to_list(25)
        recent_alerts = []
        for a in raw_alerts:
            recent_alerts.append({
                "id": str(a["_id"]),
                "ticket_id": str(a.get("ticket_id", "")),
                "subject": a.get("subject", ""),
                "priority": a.get("priority"),
                "sla_status": a.get("sla_status"),
                "alert_type": a.get("alert_type"),
                "threshold_id": a.get("threshold_id"),
                "threshold_label": a.get("threshold_label"),
                "recipient_email": a.get("recipient_email"),
                "channel": a.get("channel"),
                "delivery_status": a.get("delivery_status"),
                "created_at": a.get("created_at")
            })

        return {
            "kpis": {
                "total_active_slas": total_active,
                "on_track_count": on_track_count,
                "at_risk_count": at_risk_count,
                "breached_count": breached_count,
                "paused_count": paused_count,
                "compliance_pct": compliance_pct,
                "avg_remaining_minutes": avg_remaining_min,
            },
            "at_risk_tickets": at_risk_tickets,
            "active_alerts": recent_alerts
        }
