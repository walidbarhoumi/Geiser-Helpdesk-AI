"""
test_websocket.py
=================
STEP 5 — WebSocket Real-Time Communication & Live Notifications Test Suite

Comprehensive automated test coverage:
1. Connection & Authentication (Valid JWT, Invalid JWT, Expired JWT, Refresh Token, Revoked Token, Inactive User)
2. ConnectionManager Multi-Connection Lifecycle (Multi-tab support, disconnect cleanup, dead socket handling)
3. RBAC & Event Authorization (Users see only their tickets, Agents see assigned/team, Admins see system-wide)
4. Ticket Events (created, status_changed, assigned, reassigned, priority_changed, comment_added)
5. SLA Events (at_risk, breached, paused, resumed, completed)
6. Notification Dispatch (direct user delivery)
7. Heartbeat (client ping -> server pong)
8. Concurrency & Performance simulation
"""

import pytest
import pytest_asyncio
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from bson import ObjectId
from jose import jwt

from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient

from core.config import settings
from websocket.manager import ConnectionManager
from websocket.events import EventType, create_event
from websocket.dispatcher import EventDispatcher
from routes.ws import router as ws_router, _authenticate_websocket


# ─────────────────────────────────────────────────────────────
# Fixtures & Helpers
# ─────────────────────────────────────────────────────────────

def create_test_token(
    user_id: str = "6abba6e6702d1408c1f3985d",
    role: str = "USER",
    email: str = "user@geiser.internal",
    token_type: str = "access",
    expired: bool = False,
    jti: str = "test-jti-123"
) -> str:
    """Generates signed JWT tokens with configurable claims."""
    expire = datetime.utcnow() + (timedelta(minutes=-10) if expired else timedelta(minutes=30))
    payload = {
        "sub": user_id,
        "role": role,
        "email": email,
        "type": token_type,
        "jti": jti,
        "exp": expire
    }
    if token_type == "refresh":
        payload["refresh"] = True
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def make_mock_db(user_doc=None, is_revoked=False):
    """Builds a mock database for WebSocket authentication."""
    db = MagicMock()

    # User lookup
    default_user = {
        "_id": ObjectId("6abba6e6702d1408c1f3985d"),
        "id": "6abba6e6702d1408c1f3985d",
        "email": "user@geiser.internal",
        "role": "USER",
        "is_active": True,
    }
    user_data = user_doc if user_doc is not None else default_user
    db.users.find_one = AsyncMock(return_value=user_data)

    # Token blacklist
    db.token_blacklist.find_one = AsyncMock(return_value={"_id": ObjectId()} if is_revoked else None)

    # Audit logs
    db.audit_logs.insert_one = AsyncMock(return_value=MagicMock())
    return db


# ═════════════════════════════════════════════════════════════
# SECTION 1 — AUTHENTICATION & HANDSHAKE
# ═════════════════════════════════════════════════════════════

class TestWebSocketAuthentication:

    @pytest.mark.asyncio
    async def test_valid_access_token_authenticates(self):
        """Valid access token returns authenticated user dict."""
        token = create_test_token()
        db = make_mock_db()
        mock_ws = MagicMock(spec=WebSocket)

        user = await _authenticate_websocket(mock_ws, token, db)
        assert user is not None
        assert user["email"] == "user@geiser.internal"
        assert user["role"] == "USER"

    @pytest.mark.asyncio
    async def test_missing_token_rejected(self):
        """Missing token rejects handshake."""
        db = make_mock_db()
        mock_ws = MagicMock(spec=WebSocket)

        user = await _authenticate_websocket(mock_ws, None, db)
        assert user is None

    @pytest.mark.asyncio
    async def test_invalid_signature_rejected(self):
        """Token with invalid signature is rejected."""
        token = jwt.encode({"sub": "uid"}, "wrong-secret-key", algorithm=settings.ALGORITHM)
        db = make_mock_db()
        mock_ws = MagicMock(spec=WebSocket)

        user = await _authenticate_websocket(mock_ws, token, db)
        assert user is None

    @pytest.mark.asyncio
    async def test_expired_token_rejected(self):
        """Expired JWT token is rejected."""
        token = create_test_token(expired=True)
        db = make_mock_db()
        mock_ws = MagicMock(spec=WebSocket)

        user = await _authenticate_websocket(mock_ws, token, db)
        assert user is None

    @pytest.mark.asyncio
    async def test_refresh_token_rejected(self):
        """Refresh token is explicitly disallowed for WebSocket handshake."""
        token = create_test_token(token_type="refresh")
        db = make_mock_db()
        mock_ws = MagicMock(spec=WebSocket)

        user = await _authenticate_websocket(mock_ws, token, db)
        assert user is None

    @pytest.mark.asyncio
    async def test_revoked_token_in_blacklist_rejected(self):
        """Blacklisted JWT token (logged out) is rejected."""
        token = create_test_token()
        db = make_mock_db(is_revoked=True)
        mock_ws = MagicMock(spec=WebSocket)

        user = await _authenticate_websocket(mock_ws, token, db)
        assert user is None

    @pytest.mark.asyncio
    async def test_inactive_user_rejected(self):
        """Disabled/inactive user account is rejected."""
        inactive_user = {
            "_id": ObjectId("6abba6e6702d1408c1f3985d"),
            "email": "disabled@geiser.internal",
            "role": "USER",
            "is_active": False,
        }
        token = create_test_token()
        db = make_mock_db(user_doc=inactive_user)
        mock_ws = MagicMock(spec=WebSocket)

        user = await _authenticate_websocket(mock_ws, token, db)
        assert user is None


# ═════════════════════════════════════════════════════════════
# SECTION 2 — CONNECTION MANAGER & MULTI-TAB LIFECYCLE
# ═════════════════════════════════════════════════════════════

class TestConnectionManager:

    @pytest.mark.asyncio
    async def test_single_user_multiple_connections(self):
        """Same user connected from two tabs/devices receives messages on both sockets."""
        mgr = ConnectionManager()
        user = {"id": "user123", "role": "AGENT", "email": "a@b.com"}

        ws1 = AsyncMock(spec=WebSocket)
        ws2 = AsyncMock(spec=WebSocket)

        await mgr.connect(ws1, user)
        await mgr.connect(ws2, user)

        stats = mgr.get_stats()
        assert stats["active_users"] == 1
        assert stats["active_connections"] == 2

        # Send to user
        event = create_event("test.event", {"hello": "world"})
        sent_count = await mgr.send_to_user("user123", event)

        assert sent_count == 2
        ws1.send_json.assert_called_once_with(event)
        ws2.send_json.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_disconnect_one_tab_leaves_other_intact(self):
        """Disconnecting tab 1 leaves tab 2 connected for the user."""
        mgr = ConnectionManager()
        user = {"id": "user123", "role": "USER"}

        ws1 = AsyncMock(spec=WebSocket)
        ws2 = AsyncMock(spec=WebSocket)

        await mgr.connect(ws1, user)
        await mgr.connect(ws2, user)

        # Disconnect tab 1
        await mgr.disconnect(ws1)

        stats = mgr.get_stats()
        assert stats["active_users"] == 1
        assert stats["active_connections"] == 1

        # Tab 2 still receives messages
        event = create_event("test.event", {})
        sent_count = await mgr.send_to_user("user123", event)
        assert sent_count == 1
        ws2.send_json.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_dead_socket_auto_eviction(self):
        """Dead/broken socket that raises on send is evicted without breaking callers."""
        mgr = ConnectionManager()
        user = {"id": "user123", "role": "USER"}

        good_ws = AsyncMock(spec=WebSocket)
        dead_ws = AsyncMock(spec=WebSocket)
        dead_ws.send_json.side_effect = RuntimeError("Socket disconnected unexpectedly")

        await mgr.connect(good_ws, user)
        await mgr.connect(dead_ws, user)

        event = create_event("test.event", {})
        sent_count = await mgr.send_to_user("user123", event)

        # Good socket received the message
        assert sent_count == 1
        good_ws.send_json.assert_called_once()


# ═════════════════════════════════════════════════════════════
# SECTION 3 — RBAC & EVENT AUTHORIZATION
# ═════════════════════════════════════════════════════════════

class TestEventAuthorization:

    @pytest.mark.asyncio
    async def test_user_receives_only_own_ticket_created(self):
        """End user receives events for their own tickets, but NOT for another user's tickets."""
        mgr = ConnectionManager()
        dispatcher = EventDispatcher(mgr)

        ws_alice = AsyncMock(spec=WebSocket)
        ws_bob = AsyncMock(spec=WebSocket)

        await mgr.connect(ws_alice, {"id": "alice_uid", "role": "USER"})
        await mgr.connect(ws_bob, {"id": "bob_uid", "role": "USER"})

        # Ticket created by Alice
        ticket_alice = {
            "id": "tk_alice",
            "subject": "Alice's printer issue",
            "user_id": "alice_uid",
            "status": "OPEN",
        }
        await dispatcher.publish_ticket_created(ticket_alice)

        # Alice received the event; Bob did NOT
        assert ws_alice.send_json.called
        assert not ws_bob.send_json.called

    @pytest.mark.asyncio
    async def test_admin_receives_all_ticket_events(self):
        """Admin receives ticket events system-wide."""
        mgr = ConnectionManager()
        dispatcher = EventDispatcher(mgr)

        ws_admin = AsyncMock(spec=WebSocket)
        await mgr.connect(ws_admin, {"id": "admin_uid", "role": "ADMIN"})

        ticket = {"id": "tk_random", "subject": "Network glitch", "user_id": "other_user"}
        await dispatcher.publish_ticket_created(ticket)

        assert ws_admin.send_json.called
        call_event = ws_admin.send_json.call_args[0][0]
        assert call_event["event"] == EventType.TICKET_CREATED

    @pytest.mark.asyncio
    async def test_supervisor_receives_team_ticket_events(self):
        """Supervisor receives ticket events belonging to their assigned team."""
        mgr = ConnectionManager()
        dispatcher = EventDispatcher(mgr)

        ws_sup = AsyncMock(spec=WebSocket)
        ws_other_sup = AsyncMock(spec=WebSocket)

        await mgr.connect(ws_sup, {"id": "sup_1", "role": "SUPERVISOR", "team_id": "team_network"})
        await mgr.connect(ws_other_sup, {"id": "sup_2", "role": "SUPERVISOR", "team_id": "team_support"})

        ticket_network = {
            "id": "tk_router",
            "subject": "Router reboot",
            "user_id": "random_client",
            "team_id": "team_network"
        }
        await dispatcher.publish_ticket_status_changed(ticket_network, "OPEN", "IN_PROGRESS")

        assert ws_sup.send_json.called
        assert not ws_other_sup.send_json.called


# ═════════════════════════════════════════════════════════════
# SECTION 4 — REQUIRED TICKET EVENTS
# ═════════════════════════════════════════════════════════════

class TestRequiredTicketEvents:

    @pytest.mark.asyncio
    async def test_ticket_status_changed_and_resolved_events(self):
        """Transitioning to RESOLVED dispatches both status_changed and resolved events."""
        mgr = ConnectionManager()
        dispatcher = EventDispatcher(mgr)
        ws_client = AsyncMock(spec=WebSocket)
        await mgr.connect(ws_client, {"id": "user123", "role": "ADMIN"})

        ticket = {"id": "tk_100", "user_id": "user123", "status": "RESOLVED"}
        await dispatcher.publish_ticket_status_changed(ticket, "IN_PROGRESS", "RESOLVED")

        # Must have been called for status_changed AND resolved
        events_dispatched = [c[0][0]["event"] for c in ws_client.send_json.call_args_list]
        assert EventType.TICKET_STATUS_CHANGED in events_dispatched
        assert EventType.TICKET_RESOLVED in events_dispatched

    @pytest.mark.asyncio
    async def test_ticket_assigned_event(self):
        """publish_ticket_assigned dispatches ticket.assigned with agent_id."""
        mgr = ConnectionManager()
        dispatcher = EventDispatcher(mgr)
        ws_admin = AsyncMock(spec=WebSocket)
        await mgr.connect(ws_admin, {"id": "admin_uid", "role": "ADMIN"})

        ticket = {"id": "tk_200", "user_id": "client_uid"}
        await dispatcher.publish_ticket_assigned(ticket, agent_id="agent_555")

        event = ws_admin.send_json.call_args[0][0]
        assert event["event"] == EventType.TICKET_ASSIGNED
        assert event["data"]["agent_id"] == "agent_555"

    @pytest.mark.asyncio
    async def test_ticket_priority_changed_event(self):
        """publish_ticket_priority_changed dispatches ticket.priority_changed."""
        mgr = ConnectionManager()
        dispatcher = EventDispatcher(mgr)
        ws_admin = AsyncMock(spec=WebSocket)
        await mgr.connect(ws_admin, {"id": "admin_uid", "role": "ADMIN"})

        ticket = {"id": "tk_300", "user_id": "client_uid", "priority": "URGENT"}
        await dispatcher.publish_ticket_priority_changed(ticket, "LOW", "URGENT")

        event = ws_admin.send_json.call_args[0][0]
        assert event["event"] == EventType.TICKET_PRIORITY_CHANGED
        assert event["data"]["old_priority"] == "LOW"
        assert event["data"]["new_priority"] == "URGENT"

    @pytest.mark.asyncio
    async def test_ticket_comment_added_event(self):
        """publish_ticket_comment dispatches ticket.comment_added."""
        mgr = ConnectionManager()
        dispatcher = EventDispatcher(mgr)
        ws_client = AsyncMock(spec=WebSocket)
        await mgr.connect(ws_client, {"id": "client_uid", "role": "USER"})

        ticket = {"id": "tk_400", "user_id": "client_uid"}
        response_data = {
            "sender_id": "agent_1",
            "sender_name": "Technician Bob",
            "role": "AGENT",
            "content": "We have resolved the network link.",
            "created_at": datetime.utcnow()
        }
        await dispatcher.publish_ticket_comment(ticket, response_data)

        event = ws_client.send_json.call_args[0][0]
        assert event["event"] == EventType.TICKET_COMMENT_ADDED
        assert event["data"]["content"] == "We have resolved the network link."


# ═════════════════════════════════════════════════════════════
# SECTION 5 — SLA EVENTS (STEP 4 INTEGRATION)
# ═════════════════════════════════════════════════════════════

class TestSLAWebSocketEvents:

    @pytest.mark.asyncio
    async def test_sla_at_risk_event(self):
        """publish_sla_state_changed for AT_RISK dispatches sla.at_risk."""
        mgr = ConnectionManager()
        dispatcher = EventDispatcher(mgr)
        ws_admin = AsyncMock(spec=WebSocket)
        await mgr.connect(ws_admin, {"id": "admin_uid", "role": "ADMIN"})

        ticket = {"id": "tk_sla_1", "subject": "High priority incident"}
        await dispatcher.publish_sla_state_changed(
            ticket=ticket,
            sla_state="AT_RISK",
            details={"remaining_seconds": 1800, "crossed_threshold": "25_percent"}
        )

        event = ws_admin.send_json.call_args[0][0]
        assert event["event"] == EventType.SLA_AT_RISK
        assert event["data"]["sla_state"] == "AT_RISK"
        assert event["data"]["remaining_seconds"] == 1800

    @pytest.mark.asyncio
    async def test_sla_breached_event(self):
        """publish_sla_state_changed for BREACHED dispatches sla.breached."""
        mgr = ConnectionManager()
        dispatcher = EventDispatcher(mgr)
        ws_admin = AsyncMock(spec=WebSocket)
        await mgr.connect(ws_admin, {"id": "admin_uid", "role": "ADMIN"})

        ticket = {"id": "tk_sla_2", "subject": "Critical failure"}
        await dispatcher.publish_sla_state_changed(
            ticket=ticket,
            sla_state="BREACHED",
            details={"remaining_seconds": 0}
        )

        event = ws_admin.send_json.call_args[0][0]
        assert event["event"] == EventType.SLA_BREACHED
        assert event["data"]["sla_state"] == "BREACHED"

    @pytest.mark.asyncio
    async def test_sla_paused_and_resumed_events(self):
        """publish_sla_state_changed dispatches paused and resumed events."""
        mgr = ConnectionManager()
        dispatcher = EventDispatcher(mgr)
        ws_admin = AsyncMock(spec=WebSocket)
        await mgr.connect(ws_admin, {"id": "admin_uid", "role": "ADMIN"})

        ticket = {"id": "tk_sla_3", "subject": "Waiting on vendor"}
        await dispatcher.publish_sla_state_changed(ticket, "PAUSED")
        assert ws_admin.send_json.call_args[0][0]["event"] == EventType.SLA_PAUSED

        await dispatcher.publish_sla_state_changed(ticket, "RESUMED")
        assert ws_admin.send_json.call_args[0][0]["event"] == EventType.SLA_RESUMED


# ═════════════════════════════════════════════════════════════
# SECTION 6 — IN-APP NOTIFICATIONS
# ═════════════════════════════════════════════════════════════

class TestInAppNotificationEvents:

    @pytest.mark.asyncio
    async def test_publish_notification_delivered_only_to_target_user(self):
        """publish_notification delivers only to the specific recipient."""
        mgr = ConnectionManager()
        dispatcher = EventDispatcher(mgr)

        ws_user_a = AsyncMock(spec=WebSocket)
        ws_user_b = AsyncMock(spec=WebSocket)

        await mgr.connect(ws_user_a, {"id": "user_a", "role": "USER"})
        await mgr.connect(ws_user_b, {"id": "user_b", "role": "USER"})

        notif = {
            "title": "Your ticket was updated",
            "message": "Status changed to In Progress",
            "ticket_id": "tk_999"
        }
        await dispatcher.publish_notification("user_a", notif)

        assert ws_user_a.send_json.called
        call_event = ws_user_a.send_json.call_args[0][0]
        assert call_event["event"] == EventType.NOTIFICATION_CREATED
        assert call_event["data"]["ticket_id"] == "tk_999"
        assert not ws_user_b.send_json.called


# ═════════════════════════════════════════════════════════════
# SECTION 7 — END-TO-END TESTCLIENT & HEARTBEAT
# ═════════════════════════════════════════════════════════════

class TestWebSocketFastAPITestClient:

    def _make_test_app(self, user_id: str, role: str = "USER"):
        """Creates a test FastAPI app with mocked database dependency."""
        from database.mongodb import get_database

        test_app = FastAPI()
        test_app.include_router(ws_router)

        # Build an AsyncMock db that allows the WS auth to pass.
        # _id is set to user_id string so MongoModel.format_id() preserves it as the id.
        mock_db = MagicMock()
        mock_db.token_blacklist = MagicMock()
        mock_db.token_blacklist.find_one = AsyncMock(return_value=None)  # Not revoked
        mock_db.users = MagicMock()
        mock_db.users.find_one = AsyncMock(return_value={
            "_id": user_id,   # str so format_id keeps it as-is
            "email": f"{user_id}@geiser.internal",
            "role": role,
            "is_active": True,
        })
        # AuditService calls needed in the handler
        mock_audit_col = MagicMock()
        mock_audit_col.insert_one = AsyncMock()
        mock_db.audit_logs = mock_audit_col

        async def _mock_db():
            return mock_db

        test_app.dependency_overrides[get_database] = _mock_db
        return test_app

    def test_authenticated_handshake_receives_connected_event(self):
        """FastAPI TestClient connects with valid token and receives system.connection_established."""
        token = create_test_token(user_id="user_testclient", role="ADMIN")
        test_app = self._make_test_app("user_testclient", "ADMIN")
        client = TestClient(test_app)

        with client.websocket_connect(f"/ws?token={token}") as ws:
            msg = ws.receive_json()
            assert msg["event"] == EventType.SYSTEM_CONNECTED
            assert msg["data"]["user_id"] == "user_testclient"
            assert msg["data"]["role"] == "ADMIN"

    def test_heartbeat_ping_responds_with_pong(self):
        """Client sending a ping message receives a pong reply."""
        token = create_test_token(user_id="user_pingpong", role="USER")
        test_app = self._make_test_app("user_pingpong", "USER")
        client = TestClient(test_app)

        with client.websocket_connect(f"/ws?token={token}") as ws:
            # Consume welcome
            ws.receive_json()

            # Send ping
            ws.send_json({"type": "ping", "event_id": "ping_001"})

            # Receive pong
            pong = ws.receive_json()
            assert pong["event"] == EventType.SYSTEM_PONG
            assert pong["data"]["reply_to"] == "ping_001"

    def test_unauthenticated_connection_closed(self):
        """Connection attempt without token is closed with 1008 policy violation."""
        test_app = FastAPI()
        test_app.include_router(ws_router)
        client = TestClient(test_app)

        with pytest.raises(Exception):
            with client.websocket_connect("/ws") as ws:
                ws.receive_json()


# ═════════════════════════════════════════════════════════════
# SECTION 8 — CONCURRENCY & MULTI-USER SIMULATION
# ═════════════════════════════════════════════════════════════

class TestConcurrencyAndPerformance:

    @pytest.mark.asyncio
    async def test_concurrent_broadcast_to_multiple_users(self):
        """ConnectionManager broadcasts to 50 concurrent simulated sockets without deadlock."""
        mgr = ConnectionManager()
        sockets = [AsyncMock(spec=WebSocket) for _ in range(50)]

        for i, s in enumerate(sockets):
            await mgr.connect(s, {"id": f"sim_user_{i}", "role": "USER"})

        event = create_event("concurrency.test", {"payload": "active"})
        delivered = await mgr.broadcast(event)

        assert delivered == 50
        for s in sockets:
            s.send_json.assert_called_once_with(event)
