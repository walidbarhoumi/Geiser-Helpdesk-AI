"""
websocket/dispatcher.py
=======================
STEP 5 — WebSocket Real-Time Communication & Live Notifications

Centralized Event Dispatcher translating domain operations to authorized WebSocket broadcasts.
Enforces Role-Based Access Control (RBAC):
- Users (USER) receive ONLY events pertaining to their own tickets.
- Agents (AGENT) receive events for their assigned tickets and team tickets.
- Supervisors (SUPERVISOR) receive events for their supervised teams.
- Administrators (ADMIN) receive platform-wide operational events.
- Never crashes or breaks the calling business transaction (strict error isolation).
"""

import logging
from typing import Dict, Any, Optional, Set, List
from datetime import datetime

from websocket.manager import ConnectionManager, connection_manager
from websocket.events import EventType, create_event

logger = logging.getLogger(__name__)


class EventDispatcher:
    """
    Decoupled event publication service.
    Accepts domain entities and dispatches targeted, authorized WebSocket events.
    """

    def __init__(self, manager: Optional[ConnectionManager] = None):
        self.manager = manager or connection_manager

    # ──────────────────────────────────────────────────────────
    # Helper: Recipient Resolution & Payload Sanitization
    # ──────────────────────────────────────────────────────────

    def _get_ticket_authorized_recipients(self, ticket: Dict[str, Any]) -> Set[str]:
        """
        Determines the list of user IDs explicitly authorized to receive ticket updates:
        - Ticket creator (user_id)
        - Assigned agent user (if agent_user_id or assigned_agent_id)
        """
        recipients = set()
        user_id = str(ticket.get("user_id", ""))
        if user_id:
            recipients.add(user_id)

        # Agent user id if present in ticket or metadata
        agent_user_id = str(ticket.get("assigned_agent_user_id") or ticket.get("agent_user_id") or "")
        if agent_user_id:
            recipients.add(agent_user_id)

        return recipients

    def _sanitize_ticket_data(self, ticket: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts safe fields for client consumption."""
        ticket_id = str(ticket.get("_id") or ticket.get("id") or "")
        return {
            "ticket_id": ticket_id,
            "id": ticket_id,
            "ticket_number": ticket.get("ticket_number") or f"TK-{ticket_id[-6:].upper()}",
            "subject": ticket.get("subject", ""),
            "priority": ticket.get("priority", "MEDIUM"),
            "status": ticket.get("status", "OPEN"),
            "category": ticket.get("category"),
            "user_id": str(ticket.get("user_id", "")),
            "assigned_agent_id": str(ticket["assigned_agent_id"]) if ticket.get("assigned_agent_id") else None,
            "team_id": str(ticket["team_id"]) if ticket.get("team_id") else None,
            "sla_status": ticket.get("sla_status", "ON_TRACK"),
            "sla_deadline": ticket.get("sla_deadline").isoformat() if isinstance(ticket.get("sla_deadline"), datetime) else ticket.get("sla_deadline"),
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }

    # ──────────────────────────────────────────────────────────
    # 1. Ticket Lifecycle Events
    # ──────────────────────────────────────────────────────────

    async def publish_ticket_created(
        self,
        ticket: Dict[str, Any],
        actor: Optional[Dict[str, Any]] = None
    ) -> None:
        """Dispatched when a new ticket is submitted."""
        try:
            data = self._sanitize_ticket_data(ticket)
            if actor:
                data["actor"] = {"id": str(actor.get("id") or actor.get("_id", "")), "name": actor.get("full_name") or actor.get("email")}

            event = create_event(EventType.TICKET_CREATED, data)
            creator_id = str(ticket.get("user_id", ""))
            team_id = str(ticket.get("team_id", "")) if ticket.get("team_id") else None

            # Filter-based authorized broadcast:
            # - Creator receives it
            # - Admins receive it
            # - Supervisors & Agents of the team receive it
            def is_authorized(user_meta: Dict[str, Any]) -> bool:
                uid = user_meta.get("user_id")
                role = user_meta.get("role")
                if uid == creator_id:
                    return True
                if role == "ADMIN":
                    return True
                if team_id and user_meta.get("team_id") == team_id:
                    return True
                return False

            await self.manager.broadcast_authorized(event, is_authorized)
        except Exception as e:
            logger.warning(f"[WS Dispatcher] Error in publish_ticket_created: {e}")

    async def publish_ticket_status_changed(
        self,
        ticket: Dict[str, Any],
        old_status: str,
        new_status: str,
        actor: Optional[Dict[str, Any]] = None
    ) -> None:
        """Dispatched on ticket status transition (OPEN, IN_PROGRESS, PENDING, RESOLVED, CLOSED)."""
        try:
            data = self._sanitize_ticket_data(ticket)
            data["old_status"] = old_status
            data["new_status"] = new_status
            data["status"] = new_status
            if actor:
                data["actor"] = {"id": str(actor.get("id") or actor.get("_id", "")), "name": actor.get("full_name") or actor.get("email")}

            status_event = create_event(EventType.TICKET_STATUS_CHANGED, data)
            creator_id = str(ticket.get("user_id", ""))
            team_id = str(ticket.get("team_id", "")) if ticket.get("team_id") else None

            def is_authorized(user_meta: Dict[str, Any]) -> bool:
                uid = user_meta.get("user_id")
                role = user_meta.get("role")
                if uid == creator_id:
                    return True
                if role == "ADMIN":
                    return True
                if team_id and user_meta.get("team_id") == team_id:
                    return True
                return False

            await self.manager.broadcast_authorized(status_event, is_authorized)

            # Specific terminal events
            if new_status in ("RESOLVED",):
                resolved_event = create_event(EventType.TICKET_RESOLVED, data)
                await self.manager.broadcast_authorized(resolved_event, is_authorized)
            elif new_status in ("CLOSED",):
                closed_event = create_event(EventType.TICKET_CLOSED, data)
                await self.manager.broadcast_authorized(closed_event, is_authorized)

        except Exception as e:
            logger.warning(f"[WS Dispatcher] Error in publish_ticket_status_changed: {e}")

    async def publish_ticket_assigned(
        self,
        ticket: Dict[str, Any],
        agent_id: str,
        prior_agent_id: Optional[str] = None,
        actor: Optional[Dict[str, Any]] = None
    ) -> None:
        """Dispatched when a ticket is assigned or reassigned to an agent."""
        try:
            data = self._sanitize_ticket_data(ticket)
            data["agent_id"] = agent_id
            data["prior_agent_id"] = prior_agent_id
            if actor:
                data["actor"] = {"id": str(actor.get("id") or actor.get("_id", "")), "name": actor.get("full_name") or actor.get("email")}

            event_type = EventType.TICKET_REASSIGNED if prior_agent_id else EventType.TICKET_ASSIGNED
            event = create_event(event_type, data)
            creator_id = str(ticket.get("user_id", ""))
            team_id = str(ticket.get("team_id", "")) if ticket.get("team_id") else None

            def is_authorized(user_meta: Dict[str, Any]) -> bool:
                uid = user_meta.get("user_id")
                role = user_meta.get("role")
                if uid == creator_id:
                    return True
                if role in ("ADMIN", "SUPERVISOR"):
                    return True
                if team_id and user_meta.get("team_id") == team_id:
                    return True
                return False

            await self.manager.broadcast_authorized(event, is_authorized)
        except Exception as e:
            logger.warning(f"[WS Dispatcher] Error in publish_ticket_assigned: {e}")

    async def publish_ticket_priority_changed(
        self,
        ticket: Dict[str, Any],
        old_priority: str,
        new_priority: str,
        actor: Optional[Dict[str, Any]] = None
    ) -> None:
        """Dispatched when ticket priority is updated."""
        try:
            data = self._sanitize_ticket_data(ticket)
            data["old_priority"] = old_priority
            data["new_priority"] = new_priority
            data["priority"] = new_priority
            if actor:
                data["actor"] = {"id": str(actor.get("id") or actor.get("_id", "")), "name": actor.get("full_name") or actor.get("email")}

            event = create_event(EventType.TICKET_PRIORITY_CHANGED, data)
            creator_id = str(ticket.get("user_id", ""))
            team_id = str(ticket.get("team_id", "")) if ticket.get("team_id") else None

            def is_authorized(user_meta: Dict[str, Any]) -> bool:
                uid = user_meta.get("user_id")
                role = user_meta.get("role")
                if uid == creator_id:
                    return True
                if role == "ADMIN":
                    return True
                if team_id and user_meta.get("team_id") == team_id:
                    return True
                return False

            await self.manager.broadcast_authorized(event, is_authorized)
        except Exception as e:
            logger.warning(f"[WS Dispatcher] Error in publish_ticket_priority_changed: {e}")

    async def publish_ticket_comment(
        self,
        ticket: Dict[str, Any],
        response_data: Dict[str, Any],
        actor: Optional[Dict[str, Any]] = None
    ) -> None:
        """Dispatched when a technician response or comment is added to a ticket."""
        try:
            ticket_id = str(ticket.get("_id") or ticket.get("id") or "")
            data = {
                "ticket_id": ticket_id,
                "ticket_number": ticket.get("ticket_number") or f"TK-{ticket_id[-6:].upper()}",
                "sender_id": str(response_data.get("sender_id", "")),
                "sender_name": response_data.get("sender_name", "Support Technician"),
                "role": response_data.get("role", "AGENT"),
                "content": response_data.get("content", ""),
                "created_at": response_data.get("created_at").isoformat() if isinstance(response_data.get("created_at"), datetime) else str(response_data.get("created_at")),
            }
            if actor:
                data["actor"] = {"id": str(actor.get("id") or actor.get("_id", "")), "name": actor.get("full_name") or actor.get("email")}

            event = create_event(EventType.TICKET_COMMENT_ADDED, data)
            creator_id = str(ticket.get("user_id", ""))
            team_id = str(ticket.get("team_id", "")) if ticket.get("team_id") else None

            def is_authorized(user_meta: Dict[str, Any]) -> bool:
                uid = user_meta.get("user_id")
                role = user_meta.get("role")
                if uid == creator_id:
                    return True
                if role == "ADMIN":
                    return True
                if team_id and user_meta.get("team_id") == team_id:
                    return True
                return False

            await self.manager.broadcast_authorized(event, is_authorized)
        except Exception as e:
            logger.warning(f"[WS Dispatcher] Error in publish_ticket_comment: {e}")

    # ──────────────────────────────────────────────────────────
    # 2. SLA Lifecycle Events (STEP 4 Integration)
    # ──────────────────────────────────────────────────────────

    async def publish_sla_state_changed(
        self,
        ticket: Dict[str, Any],
        sla_state: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Dispatches targeted SLA risk events (AT_RISK, BREACHED, PAUSED, RESUMED, COMPLETED).
        """
        try:
            state_str = sla_state.value if hasattr(sla_state, "value") else str(sla_state)
            event_type_map = {
                "AT_RISK": EventType.SLA_AT_RISK,
                "BREACHED": EventType.SLA_BREACHED,
                "PAUSED": EventType.SLA_PAUSED,
                "RESUMED": EventType.SLA_RESUMED,
                "COMPLETED": EventType.SLA_COMPLETED,
            }
            event_type = event_type_map.get(state_str, EventType.SLA_AT_RISK)

            ticket_id = str(ticket.get("_id") or ticket.get("id") or "")
            deadline = ticket.get("sla_deadline")
            deadline_str = deadline.isoformat() if isinstance(deadline, datetime) else str(deadline) if deadline else None

            data = {
                "ticket_id": ticket_id,
                "ticket_number": ticket.get("ticket_number") or f"TK-{ticket_id[-6:].upper()}",
                "subject": ticket.get("subject", ""),
                "priority": ticket.get("priority", "HIGH"),
                "sla_state": state_str,
                "sla_deadline": deadline_str,
                "remaining_seconds": details.get("remaining_seconds") if details else None,
                "crossed_threshold": details.get("crossed_threshold") if details else None,
                "crossed_threshold_label": details.get("crossed_threshold_label") if details else None,
            }

            event = create_event(event_type, data)
            creator_id = str(ticket.get("user_id", ""))
            team_id = str(ticket.get("team_id", "")) if ticket.get("team_id") else None

            # SLA alerts are broadcast to Admins, Supervisors, and the assigned team
            def is_authorized(user_meta: Dict[str, Any]) -> bool:
                role = user_meta.get("role")
                uid = user_meta.get("user_id")
                if role in ("ADMIN", "SUPERVISOR"):
                    return True
                if team_id and user_meta.get("team_id") == team_id:
                    return True
                if uid == creator_id and state_str in ("COMPLETED", "PAUSED", "RESUMED"):
                    return True
                return False

            await self.manager.broadcast_authorized(event, is_authorized)
        except Exception as e:
            logger.warning(f"[WS Dispatcher] Error in publish_sla_state_changed: {e}")

    # ──────────────────────────────────────────────────────────
    # 3. Direct User Notifications
    # ──────────────────────────────────────────────────────────

    async def publish_notification(
        self,
        user_id: str,
        notification: Dict[str, Any]
    ) -> None:
        """Dispatches an in-app notification directly to a specific user."""
        try:
            event = create_event(EventType.NOTIFICATION_CREATED, notification)
            await self.manager.send_to_user(str(user_id), event)
        except Exception as e:
            logger.warning(f"[WS Dispatcher] Error in publish_notification to user {user_id}: {e}")


# Global singleton dispatcher instance
event_dispatcher = EventDispatcher(connection_manager)
