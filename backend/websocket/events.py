"""
websocket/events.py
===================
STEP 5 — WebSocket Real-Time Communication & Live Notifications

Standardized event schemas and event constants for the GEISER Helpdesk IA platform.
Guarantees consistent, predictable event structures across all real-time channels:
- Event envelope: { event: str, event_id: str, timestamp: str, data: dict }
- Automatic UUID generation for client-side deduplication
- ISO 8601 UTC timestamps
"""

from datetime import datetime
from typing import Dict, Any, Optional
import uuid


class EventType:
    # ── Ticket Events ──────────────────────────────────────────
    TICKET_CREATED = "ticket.created"
    TICKET_UPDATED = "ticket.updated"
    TICKET_ASSIGNED = "ticket.assigned"
    TICKET_REASSIGNED = "ticket.reassigned"
    TICKET_STATUS_CHANGED = "ticket.status_changed"
    TICKET_RESOLVED = "ticket.resolved"
    TICKET_CLOSED = "ticket.closed"
    TICKET_PRIORITY_CHANGED = "ticket.priority_changed"
    TICKET_COMMENT_ADDED = "ticket.comment_added"

    # ── SLA Events ─────────────────────────────────────────────
    SLA_AT_RISK = "sla.at_risk"
    SLA_BREACHED = "sla.breached"
    SLA_PAUSED = "sla.paused"
    SLA_RESUMED = "sla.resumed"
    SLA_COMPLETED = "sla.completed"

    # ── In-App Notifications ───────────────────────────────────
    NOTIFICATION_CREATED = "notification.created"

    # ── System / Heartbeat ─────────────────────────────────────
    SYSTEM_PING = "system.ping"
    SYSTEM_PONG = "system.pong"
    SYSTEM_CONNECTED = "system.connection_established"


def create_event(
    event_type: str,
    data: Dict[str, Any],
    event_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Constructs a standardized, validated WebSocket event envelope.
    All clients receive the exact same predictable payload structure.
    """
    return {
        "event": event_type,
        "event_id": event_id or f"evt_{uuid.uuid4().hex[:12]}",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "data": data,
    }
