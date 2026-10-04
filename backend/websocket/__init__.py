"""
backend/websocket package
WebSocket real-time communication & live notifications for GEISER Helpdesk.
"""

from websocket.manager import ConnectionManager, connection_manager
from websocket.events import EventType, create_event
from websocket.dispatcher import EventDispatcher, event_dispatcher

__all__ = [
    "ConnectionManager",
    "connection_manager",
    "EventType",
    "create_event",
    "EventDispatcher",
    "event_dispatcher",
]
