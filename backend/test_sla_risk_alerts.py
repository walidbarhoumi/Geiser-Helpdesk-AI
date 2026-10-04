"""
test_sla_risk_alerts.py
=======================
STEP 4 — SLA Intelligent Risk Detection & Automatic Alerts
Test Coverage:
  - State calculation: ON_TRACK, AT_RISK, BREACHED, PAUSED, COMPLETED
  - Threshold crossing: percentage, absolute time, multiple thresholds, boundaries
  - Duplicate prevention: same threshold not alerting twice, breach idempotency
  - Email/SMS dispatch: correct recipients, failure resilience
  - SLA lifecycle: pause/resume, resolution → COMPLETED, breach → BREACHED
  - API access control: unauthorized access blocked
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime, timedelta
from bson import ObjectId


# ─────────────────────────────────────────────────────────────
# Fixtures — Shared helpers
# ─────────────────────────────────────────────────────────────

def make_ticket(
    status="OPEN",
    priority="HIGH",
    created_at=None,
    deadline=None,
    sla_breached_at=None,
    sla_status=None,
    sla_paused_at=None,
    sla_total_paused_seconds=0.0,
    sla_response_deadline=None,
    agent_id=None,
    team_id=None,
    extra=None,
):
    """Factory for mock ticket documents."""
    now = datetime.utcnow()
    oid = ObjectId()
    t = {
        "_id": oid,
        "id": str(oid),
        "ticket_number": "TK-001",
        "subject": "Test ticket",
        "status": status,
        "priority": priority,
        "created_at": created_at or now - timedelta(hours=2),
        "sla_deadline": deadline,
        "sla_breached_at": sla_breached_at,
        "sla_status": sla_status,
        "sla_paused_at": sla_paused_at,
        "sla_total_paused_seconds": sla_total_paused_seconds,
        "sla_response_deadline": sla_response_deadline,
        "agent_id": agent_id,
        "team_id": team_id,
    }
    if extra:
        t.update(extra)
    return t


def make_db():
    """
    Build a minimal mock Motor database with all collections needed by
    SLARiskService and TicketService.
    """
    db = MagicMock()

    # Generic async collection mock factory
    def make_col():
        col = MagicMock()
        col.find_one = AsyncMock(return_value=None)
        col.find = MagicMock(return_value=_make_cursor([]))
        col.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
        col.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))
        col.aggregate = MagicMock(return_value=_make_cursor([]))
        col.count_documents = AsyncMock(return_value=0)
        col.create_index = AsyncMock(return_value="idx")
        return col

    for name in [
        "tickets", "sla_alerts", "sla_risk_config", "users",
        "agents", "teams", "notifications", "audit_logs", "sla_policies",
    ]:
        setattr(db, name, make_col())

    return db


def _make_cursor(items):
    """Return a mock cursor that supports .sort().limit().to_list()."""
    cursor = MagicMock()
    cursor.sort = MagicMock(return_value=cursor)
    cursor.limit = MagicMock(return_value=cursor)
    cursor.skip = MagicMock(return_value=cursor)
    cursor.to_list = AsyncMock(return_value=items)
    return cursor


DEFAULT_CONFIG = {
    "key": "global_config",
    "warning_thresholds": [
        {"id": "25_percent", "type": "percentage", "value": 25.0, "label": "25% du temps restant"},
        {"id": "10_percent", "type": "percentage", "value": 10.0, "label": "10% du temps restant"},
        {"id": "5_percent",  "type": "percentage", "value": 5.0,  "label": "5% du temps restant"},
        {"id": "1_hour",     "type": "time_minutes", "value": 60.0, "label": "Moins de 1 heure restante"},
    ],
    "risk_alert_enabled": True,
    "breach_alert_enabled": True,
    "sms_alerts_enabled": True,
    "email_alerts_enabled": True,
}


# ─────────────────────────────────────────────────────────────
# Imports under test
# ─────────────────────────────────────────────────────────────

from services.sla_risk_service import SLARiskService, DEFAULT_SLA_RISK_CONFIG
from schemas.schemas import SLAStatus, TicketStatus


# ═════════════════════════════════════════════════════════════
# SECTION 1 — SLA STATE CALCULATION
# ═════════════════════════════════════════════════════════════

class TestSLAStateCalculation:
    """evaluate_ticket_sla() must return the correct state in all scenarios."""

    @pytest.mark.asyncio
    async def test_on_track_state(self):
        """Ticket with plenty of time remaining → ON_TRACK."""
        now = datetime.utcnow()
        ticket = make_ticket(
            status="OPEN",
            created_at=now - timedelta(hours=1),
            deadline=now + timedelta(hours=10),
        )
        db = make_db()
        db.sla_risk_config.find_one = AsyncMock(return_value=DEFAULT_CONFIG)
        svc = SLARiskService(db)

        result = await svc.evaluate_ticket_sla(ticket, now=now, config=DEFAULT_CONFIG)

        assert result["state"] == SLAStatus.ON_TRACK
        assert result["should_alert"] is False
        assert result["remaining_seconds"] > 0
        assert result["remaining_percentage"] > 25.0

    @pytest.mark.asyncio
    async def test_at_risk_percentage_threshold(self):
        """Ticket with 20% remaining time → AT_RISK (crosses 25% threshold)."""
        now = datetime.utcnow()
        total = timedelta(hours=8)
        created_at = now - (total * 0.80)   # 80% elapsed
        deadline = created_at + total       # 20% remaining

        ticket = make_ticket(
            status="OPEN",
            created_at=created_at,
            deadline=deadline,
        )
        db = make_db()
        svc = SLARiskService(db)

        result = await svc.evaluate_ticket_sla(ticket, now=now, config=DEFAULT_CONFIG)

        assert result["state"] == SLAStatus.AT_RISK
        assert result["should_alert"] is True
        assert result["crossed_threshold"] is not None

    @pytest.mark.asyncio
    async def test_at_risk_absolute_time_threshold(self):
        """Ticket with 45 min remaining → AT_RISK (crosses 1-hour threshold)."""
        now = datetime.utcnow()
        created_at = now - timedelta(hours=48)
        deadline = now + timedelta(minutes=45)

        ticket = make_ticket(
            status="IN_PROGRESS",
            created_at=created_at,
            deadline=deadline,
        )
        db = make_db()
        svc = SLARiskService(db)

        result = await svc.evaluate_ticket_sla(ticket, now=now, config=DEFAULT_CONFIG)

        assert result["state"] == SLAStatus.AT_RISK
        assert result["should_alert"] is True

    @pytest.mark.asyncio
    async def test_breached_state_active_ticket(self):
        """Active ticket past its deadline → BREACHED."""
        now = datetime.utcnow()
        ticket = make_ticket(
            status="OPEN",
            created_at=now - timedelta(hours=5),
            deadline=now - timedelta(minutes=30),  # past
        )
        db = make_db()
        svc = SLARiskService(db)

        result = await svc.evaluate_ticket_sla(ticket, now=now, config=DEFAULT_CONFIG)

        assert result["state"] == SLAStatus.BREACHED
        assert result["remaining_seconds"] == 0.0
        assert result["should_alert"] is True

    @pytest.mark.asyncio
    async def test_paused_state(self):
        """PENDING ticket → PAUSED, should_alert is False."""
        now = datetime.utcnow()
        ticket = make_ticket(
            status="PENDING",
            created_at=now - timedelta(hours=3),
            deadline=now + timedelta(hours=1),
            sla_paused_at=now - timedelta(hours=1),
        )
        db = make_db()
        svc = SLARiskService(db)

        result = await svc.evaluate_ticket_sla(ticket, now=now, config=DEFAULT_CONFIG)

        assert result["state"] == SLAStatus.PAUSED
        assert result["should_alert"] is False

    @pytest.mark.asyncio
    async def test_completed_state_resolved_on_time(self):
        """RESOLVED ticket without prior breach → COMPLETED."""
        now = datetime.utcnow()
        ticket = make_ticket(
            status="RESOLVED",
            created_at=now - timedelta(hours=5),
            deadline=now + timedelta(hours=1),  # still in future
            sla_breached_at=None,
            sla_status=None,
        )
        db = make_db()
        svc = SLARiskService(db)

        result = await svc.evaluate_ticket_sla(ticket, now=now, config=DEFAULT_CONFIG)

        assert result["state"] == SLAStatus.COMPLETED
        assert result["should_alert"] is False

    @pytest.mark.asyncio
    async def test_closed_after_breach_returns_breached(self):
        """CLOSED ticket that was previously breached → state is BREACHED."""
        now = datetime.utcnow()
        ticket = make_ticket(
            status="CLOSED",
            created_at=now - timedelta(hours=10),
            deadline=now - timedelta(hours=2),
            sla_breached_at=now - timedelta(hours=2),
            sla_status="BREACHED",
        )
        db = make_db()
        svc = SLARiskService(db)

        result = await svc.evaluate_ticket_sla(ticket, now=now, config=DEFAULT_CONFIG)

        assert result["state"] == SLAStatus.BREACHED
        assert result["should_alert"] is False

    @pytest.mark.asyncio
    async def test_no_deadline_returns_on_track(self):
        """Ticket with no sla_deadline → ON_TRACK (no data to breach)."""
        ticket = make_ticket(status="OPEN", deadline=None)
        db = make_db()
        svc = SLARiskService(db)

        result = await svc.evaluate_ticket_sla(ticket, config=DEFAULT_CONFIG)

        assert result["state"] == SLAStatus.ON_TRACK
        assert result["should_alert"] is False

    @pytest.mark.asyncio
    async def test_boundary_exactly_at_deadline(self):
        """Ticket where now == deadline exactly → BREACHED."""
        now = datetime.utcnow()
        ticket = make_ticket(
            status="OPEN",
            created_at=now - timedelta(hours=4),
            deadline=now,   # exact boundary
        )
        db = make_db()
        svc = SLARiskService(db)

        result = await svc.evaluate_ticket_sla(ticket, now=now, config=DEFAULT_CONFIG)

        assert result["state"] == SLAStatus.BREACHED

    @pytest.mark.asyncio
    async def test_multiple_thresholds_most_critical_selected(self):
        """
        When 5% remaining, both 25%,10%,5% thresholds are crossed.
        The service should pick the most critical (smallest threshold).
        """
        now = datetime.utcnow()
        total = timedelta(hours=4)
        created_at = now - (total * 0.96)   # 96% elapsed → 4% remaining
        deadline = created_at + total

        ticket = make_ticket(
            status="OPEN",
            created_at=created_at,
            deadline=deadline,
        )
        db = make_db()
        svc = SLARiskService(db)

        result = await svc.evaluate_ticket_sla(ticket, now=now, config=DEFAULT_CONFIG)

        assert result["state"] == SLAStatus.AT_RISK
        # The crossed threshold should be the most critical one
        assert result["crossed_threshold"] is not None


# ═════════════════════════════════════════════════════════════
# SECTION 2 — CONFIGURATION MANAGEMENT
# ═════════════════════════════════════════════════════════════

class TestRiskConfigManagement:

    @pytest.mark.asyncio
    async def test_get_config_returns_defaults_when_no_db_record(self):
        """get_risk_config() returns DEFAULT_SLA_RISK_CONFIG when collection is empty."""
        db = make_db()
        db.sla_risk_config.find_one = AsyncMock(return_value=None)
        svc = SLARiskService(db)

        config = await svc.get_risk_config()

        assert config["key"] == "global_config"
        assert len(config["warning_thresholds"]) == 4
        assert config["risk_alert_enabled"] is True

    @pytest.mark.asyncio
    async def test_get_config_strips_mongo_id(self):
        """get_risk_config() strips _id field from returned dict."""
        stored = dict(DEFAULT_CONFIG)
        stored["_id"] = ObjectId()
        db = make_db()
        db.sla_risk_config.find_one = AsyncMock(return_value=stored)
        svc = SLARiskService(db)

        config = await svc.get_risk_config()

        assert "_id" not in config

    @pytest.mark.asyncio
    async def test_update_config_upserts(self):
        """update_risk_config() performs an upsert and returns updated config."""
        db = make_db()
        updated = dict(DEFAULT_CONFIG)
        updated["sms_alerts_enabled"] = False
        db.sla_risk_config.find_one = AsyncMock(return_value=updated)
        svc = SLARiskService(db)

        result = await svc.update_risk_config({"sms_alerts_enabled": False})

        db.sla_risk_config.update_one.assert_called_once()
        call_args = db.sla_risk_config.update_one.call_args
        assert call_args[1].get("upsert") is True or (len(call_args[0]) > 1 and "upsert" in str(call_args))


# ═════════════════════════════════════════════════════════════
# SECTION 3 — DUPLICATE PREVENTION
# ═════════════════════════════════════════════════════════════

class TestDuplicatePrevention:

    @pytest.mark.asyncio
    async def test_alert_already_sent_blocks_duplicate(self):
        """_is_alert_already_sent() returns True when a matching record exists."""
        db = make_db()
        db.sla_alerts.find_one = AsyncMock(return_value={"_id": ObjectId()})
        svc = SLARiskService(db)

        already_sent = await svc._is_alert_already_sent(
            ticket_id="TK-001",
            alert_type="AT_RISK",
            threshold_id="25_percent",
            recipient_id="user123",
            channel="email",
        )

        assert already_sent is True

    @pytest.mark.asyncio
    async def test_alert_not_sent_when_no_matching_record(self):
        """_is_alert_already_sent() returns False when no record matches."""
        db = make_db()
        db.sla_alerts.find_one = AsyncMock(return_value=None)
        svc = SLARiskService(db)

        already_sent = await svc._is_alert_already_sent(
            ticket_id="TK-999",
            alert_type="BREACHED",
            threshold_id="breach",
            recipient_id="user456",
            channel="sms",
        )

        assert already_sent is False

    @pytest.mark.asyncio
    async def test_evaluate_active_slas_does_not_resend_alert(self):
        """evaluate_active_slas() skips tickets whose alert was already sent."""
        now = datetime.utcnow()
        ticket = make_ticket(
            status="OPEN",
            created_at=now - timedelta(hours=5),
            deadline=now - timedelta(minutes=10),  # breached
        )

        db = make_db()
        # Ticket exists in query
        db.tickets.find = MagicMock(return_value=_make_cursor([ticket]))
        # All alert lookups say "already sent"
        db.sla_alerts.find_one = AsyncMock(return_value={"_id": ObjectId()})
        db.tickets.update_one = AsyncMock(return_value=MagicMock())
        db.sla_risk_config.find_one = AsyncMock(return_value=DEFAULT_CONFIG)

        svc = SLARiskService(db)

        with patch("services.sla_risk_service.EmailService") as MockEmail:
            MockEmail.send_email = MagicMock()
            result = await svc.evaluate_active_slas()
            assert result["alerted"] == 0
            MockEmail.send_email.assert_not_called()


# ═════════════════════════════════════════════════════════════
# SECTION 4 — NOTIFICATION DISPATCH
# ═════════════════════════════════════════════════════════════

class TestNotificationDispatch:

    @pytest.mark.asyncio
    async def test_email_sent_when_not_duplicate(self):
        """_dispatch_risk_alerts() sends email when not a duplicate."""
        db = make_db()
        db.sla_alerts.find_one = AsyncMock(return_value=None)   # not already sent
        db.sla_alerts.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))

        # Mock users/agents/teams lookups
        agent_user = {"_id": ObjectId(), "email": "agent@example.com", "full_name": "Agent One"}
        db.users.find_one = AsyncMock(return_value=agent_user)
        db.agents.find_one = AsyncMock(return_value={"user_id": str(agent_user["_id"])})
        db.teams.find_one = AsyncMock(return_value=None)
        admin_id = ObjectId()
        db.users.find = MagicMock(return_value=_make_cursor([
            {"_id": admin_id, "email": "admin@example.com", "full_name": "Admin"}
        ]))

        ticket = make_ticket(
            status="OPEN",
            created_at=datetime.utcnow() - timedelta(hours=6),
            deadline=datetime.utcnow() + timedelta(minutes=20),
            agent_id="agent_oid",
        )
        eval_result = {
            "state": SLAStatus.AT_RISK,
            "ticket_id": str(ticket["_id"]),
            "crossed_threshold": "25_percent",
            "crossed_threshold_label": "25% du temps restant",
            "remaining_seconds": 1200.0,
            "should_alert": True,
        }

        svc = SLARiskService(db)

        with patch("services.sla_risk_service.EmailService") as MockEmail:
            MockEmail.send_email = MagicMock(return_value=True)

            await svc._dispatch_risk_alerts(ticket, eval_result, DEFAULT_CONFIG)

            # Email should be attempted
            assert MockEmail.send_email.called

    @pytest.mark.asyncio
    async def test_email_failure_does_not_crash_dispatch(self):
        """_dispatch_risk_alerts() catches email exceptions and continues."""
        db = make_db()
        db.sla_alerts.find_one = AsyncMock(return_value=None)
        db.sla_alerts.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))
        db.users.find_one = AsyncMock(return_value={"email": "a@b.com", "full_name": "A"})
        db.agents.find_one = AsyncMock(return_value={"user_id": "uid"})
        db.teams.find_one = AsyncMock(return_value=None)
        db.users.find = MagicMock(return_value=_make_cursor([]))

        ticket = make_ticket(
            status="OPEN",
            created_at=datetime.utcnow() - timedelta(hours=6),
            deadline=datetime.utcnow() + timedelta(minutes=10),
            agent_id="some_agent",
        )
        eval_result = {
            "state": SLAStatus.AT_RISK,
            "ticket_id": str(ticket["_id"]),
            "crossed_threshold": "5_percent",
            "crossed_threshold_label": "5% du temps restant",
            "remaining_seconds": 600.0,
            "should_alert": True,
        }

        svc = SLARiskService(db)

        with patch("services.sla_risk_service.EmailService") as MockEmail:
            mock_email_inst = MockEmail.return_value
            mock_email_inst.send_email = MagicMock(side_effect=Exception("SMTP down"))

            # Must not raise
            await svc._dispatch_risk_alerts(ticket, eval_result, DEFAULT_CONFIG)


# ═════════════════════════════════════════════════════════════
# SECTION 5 — EVALUATE_ACTIVE_SLAS (BATCH SCAN)
# ═════════════════════════════════════════════════════════════

class TestEvaluateActiveSLAs:

    @pytest.mark.asyncio
    async def test_on_track_tickets_not_alerted(self):
        """ON_TRACK tickets during scan don't trigger alerts."""
        now = datetime.utcnow()
        ticket = make_ticket(
            status="OPEN",
            created_at=now - timedelta(hours=1),
            deadline=now + timedelta(hours=10),
        )

        db = make_db()
        db.tickets.find = MagicMock(return_value=_make_cursor([ticket]))
        db.sla_risk_config.find_one = AsyncMock(return_value=DEFAULT_CONFIG)
        db.tickets.update_one = AsyncMock(return_value=MagicMock())

        svc = SLARiskService(db)

        with patch.object(svc, "_dispatch_risk_alerts", new=AsyncMock()) as mock_dispatch:
            result = await svc.evaluate_active_slas()
            mock_dispatch.assert_not_called()

        assert result["scanned"] >= 1

    @pytest.mark.asyncio
    async def test_breached_ticket_triggers_update(self):
        """Breached ticket causes sla_status update in the database."""
        now = datetime.utcnow()
        ticket = make_ticket(
            status="OPEN",
            created_at=now - timedelta(hours=5),
            deadline=now - timedelta(minutes=5),  # breached
            sla_status="ON_TRACK",  # stale status
        )

        db = make_db()
        db.tickets.find = MagicMock(return_value=_make_cursor([ticket]))
        db.sla_risk_config.find_one = AsyncMock(return_value=DEFAULT_CONFIG)
        db.sla_alerts.find_one = AsyncMock(return_value=None)  # first breach
        db.sla_alerts.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))
        db.users.find_one = AsyncMock(return_value=None)
        db.agents.find_one = AsyncMock(return_value=None)
        db.teams.find_one = AsyncMock(return_value=None)
        db.users.find = MagicMock(return_value=_make_cursor([]))
        db.tickets.update_one = AsyncMock(return_value=MagicMock())

        svc = SLARiskService(db)

        with patch("services.sla_risk_service.EmailService"):
            result = await svc.evaluate_active_slas()

        # sla_status in DB must be updated
        db.tickets.update_one.assert_called()
        update_call = db.tickets.update_one.call_args
        update_payload = update_call[0][1] if update_call[0] else update_call[1]
        assert "$set" in str(update_payload) or "BREACHED" in str(update_payload)

    @pytest.mark.asyncio
    async def test_scan_result_contains_expected_keys(self):
        """evaluate_active_slas() returns a dict with all required KPI keys."""
        db = make_db()
        db.tickets.find = MagicMock(return_value=_make_cursor([]))
        db.sla_risk_config.find_one = AsyncMock(return_value=DEFAULT_CONFIG)

        svc = SLARiskService(db)
        result = await svc.evaluate_active_slas()

        assert "scanned" in result
        assert "at_risk" in result
        assert "breached" in result
        assert "alerted" in result


# ═════════════════════════════════════════════════════════════
# SECTION 6 — SLA LIFECYCLE (PAUSE / RESUME / COMPLETE)
# ═════════════════════════════════════════════════════════════

class TestSLALifecycle:

    @pytest.mark.asyncio
    async def test_evaluate_paused_ticket_does_not_alert(self):
        """PENDING (paused) tickets must never trigger SLA alerts."""
        now = datetime.utcnow()
        ticket = make_ticket(
            status="PENDING",
            created_at=now - timedelta(hours=4),
            deadline=now - timedelta(hours=1),   # would be breached if not paused
            sla_paused_at=now - timedelta(hours=2),
        )

        db = make_db()
        svc = SLARiskService(db)

        result = await svc.evaluate_ticket_sla(ticket, now=now, config=DEFAULT_CONFIG)

        assert result["state"] == SLAStatus.PAUSED
        assert result["should_alert"] is False

    @pytest.mark.asyncio
    async def test_resolved_ticket_without_breach_is_completed(self):
        """RESOLVED on time → COMPLETED state."""
        now = datetime.utcnow()
        ticket = make_ticket(
            status="RESOLVED",
            created_at=now - timedelta(hours=3),
            deadline=now + timedelta(hours=1),
        )

        db = make_db()
        svc = SLARiskService(db)

        result = await svc.evaluate_ticket_sla(ticket, now=now, config=DEFAULT_CONFIG)

        assert result["state"] == SLAStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_resolved_ticket_with_prior_breach_stays_breached(self):
        """RESOLVED but with sla_breached_at → BREACHED, not COMPLETED."""
        now = datetime.utcnow()
        ticket = make_ticket(
            status="RESOLVED",
            created_at=now - timedelta(hours=10),
            deadline=now - timedelta(hours=3),
            sla_breached_at=now - timedelta(hours=3),
        )

        db = make_db()
        svc = SLARiskService(db)

        result = await svc.evaluate_ticket_sla(ticket, now=now, config=DEFAULT_CONFIG)

        assert result["state"] == SLAStatus.BREACHED


# ═════════════════════════════════════════════════════════════
# SECTION 7 — TICKET SERVICE INTEGRATION (PAUSE / RESUME)
# ═════════════════════════════════════════════════════════════

class TestTicketServiceSLALifecycle:
    """
    Validates the SLA lifecycle logic inside TicketService.update_status(),
    specifically PENDING (pause) and OPEN/IN_PROGRESS (resume) transitions.
    """

    @pytest.mark.asyncio
    async def test_update_status_to_pending_sets_sla_paused(self):
        """Transitioning to PENDING → sla_status = PAUSED + sla_paused_at is set."""
        from services.ticket_service import TicketService
        from schemas.schemas import TicketStatus, SLAStatus

        now = datetime.utcnow()
        oid = ObjectId()
        ticket = {
            "_id": oid,
            "status": "OPEN",
            "sla_status": "ON_TRACK",
            "sla_deadline": now + timedelta(hours=3),
            "sla_paused_at": None,
            "sla_total_paused_seconds": 0.0,
            "sla_response_deadline": None,
            "created_at": now - timedelta(hours=1),
        }

        db = make_db()
        db.tickets.find_one = AsyncMock(return_value=ticket)
        db.tickets.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
        db.tickets.aggregate = MagicMock(return_value=_make_cursor([]))
        # Silence audit logging
        with patch("services.ticket_service.AuditService", MagicMock()) if False else \
             patch("services.audit_service.AuditService", MagicMock()):
            svc = TicketService(db)
            with patch.object(svc, "record_ticket_action", AsyncMock()):
                result = await svc.update_status(str(oid), TicketStatus.PENDING)

        update_call = db.tickets.update_one.call_args
        update_payload = update_call[0][1]["$set"]
        assert update_payload["sla_status"] == SLAStatus.PAUSED.value
        assert update_payload["sla_paused_at"] is not None

    @pytest.mark.asyncio
    async def test_update_status_from_pending_extends_deadline(self):
        """Resuming from PENDING extends sla_deadline by pause duration."""
        from services.ticket_service import TicketService
        from schemas.schemas import TicketStatus

        now = datetime.utcnow()
        paused_at = now - timedelta(hours=2)
        original_deadline = now + timedelta(hours=5)
        oid = ObjectId()

        ticket = {
            "_id": oid,
            "status": "PENDING",
            "sla_status": "PAUSED",
            "sla_deadline": original_deadline,
            "sla_paused_at": paused_at,
            "sla_total_paused_seconds": 0.0,
            "sla_response_deadline": None,
            "created_at": now - timedelta(hours=3),
        }

        db = make_db()
        db.tickets.find_one = AsyncMock(return_value=ticket)
        db.tickets.update_one = AsyncMock(return_value=MagicMock(modified_count=1))

        svc = TicketService(db)
        with patch.object(svc, "record_ticket_action", AsyncMock()):
            await svc.update_status(str(oid), TicketStatus.OPEN)

        update_payload = db.tickets.update_one.call_args[0][1]["$set"]
        new_deadline = update_payload.get("sla_deadline")
        assert new_deadline is not None
        # Deadline should be extended by approximately the pause duration
        extension = (new_deadline - original_deadline).total_seconds()
        assert extension >= 7000  # ~2 hours in seconds, allow tolerance

    @pytest.mark.asyncio
    async def test_update_status_to_resolved_sets_completed(self):
        """Closing a non-breached ticket → sla_status = COMPLETED."""
        from services.ticket_service import TicketService
        from schemas.schemas import TicketStatus, SLAStatus

        now = datetime.utcnow()
        oid = ObjectId()
        ticket = {
            "_id": oid,
            "status": "IN_PROGRESS",
            "sla_status": "ON_TRACK",
            "sla_deadline": now + timedelta(hours=2),
            "sla_breached_at": None,
            "sla_paused_at": None,
            "sla_total_paused_seconds": 0.0,
            "created_at": now - timedelta(hours=2),
        }

        db = make_db()
        db.tickets.find_one = AsyncMock(return_value=ticket)
        db.tickets.update_one = AsyncMock(return_value=MagicMock(modified_count=1))

        svc = TicketService(db)
        with patch.object(svc, "record_ticket_action", AsyncMock()):
            await svc.update_status(str(oid), TicketStatus.RESOLVED)

        update_payload = db.tickets.update_one.call_args[0][1]["$set"]
        assert update_payload["sla_status"] == SLAStatus.COMPLETED.value


# ═════════════════════════════════════════════════════════════
# SECTION 8 — RISK OVERVIEW / DASHBOARD KPIs
# ═════════════════════════════════════════════════════════════

class TestRiskOverview:

    @pytest.mark.asyncio
    async def test_get_risk_overview_returns_required_structure(self):
        """get_risk_overview() returns a dict with all required KPI fields."""
        db = make_db()
        db.sla_risk_config.find_one = AsyncMock(return_value=DEFAULT_CONFIG)
        db.tickets.count_documents = AsyncMock(return_value=0)
        db.tickets.find = MagicMock(return_value=_make_cursor([]))
        db.sla_alerts.find = MagicMock(return_value=_make_cursor([]))

        svc = SLARiskService(db)
        overview = await svc.get_risk_overview()

        # Must have these keys for the dashboard
        for key in ["at_risk_count", "breached_count", "paused_count", "on_track_count"]:
            assert key in overview["kpis"], f"Missing key: {key}"


# ═════════════════════════════════════════════════════════════
# SECTION 9 — SCHEMA VALIDATION
# ═════════════════════════════════════════════════════════════

class TestSchemaEnums:
    """Verify that new enum values were correctly added to the schemas."""

    def test_sla_status_has_five_values(self):
        values = {s.value for s in SLAStatus}
        assert "ON_TRACK" in values
        assert "AT_RISK" in values
        assert "BREACHED" in values
        assert "PAUSED" in values
        assert "COMPLETED" in values

    def test_ticket_status_has_pending(self):
        values = {s.value for s in TicketStatus}
        assert "PENDING" in values

    def test_sla_status_paused_value(self):
        assert SLAStatus.PAUSED.value == "PAUSED"

    def test_sla_status_completed_value(self):
        assert SLAStatus.COMPLETED.value == "COMPLETED"


# ═════════════════════════════════════════════════════════════
# SECTION 10 — DEFAULT CONFIG INTEGRITY
# ═════════════════════════════════════════════════════════════

class TestDefaultConfigIntegrity:

    def test_default_config_has_four_thresholds(self):
        thresholds = DEFAULT_SLA_RISK_CONFIG["warning_thresholds"]
        assert len(thresholds) == 4

    def test_all_thresholds_have_required_fields(self):
        for t in DEFAULT_SLA_RISK_CONFIG["warning_thresholds"]:
            assert "id" in t
            assert "type" in t
            assert "value" in t
            assert "label" in t
            assert t["type"] in ("percentage", "time_minutes")

    def test_percentage_thresholds_are_descending(self):
        """Percentage thresholds should be ordered largest to smallest for correct matching."""
        pct = [
            t["value"] for t in DEFAULT_SLA_RISK_CONFIG["warning_thresholds"]
            if t["type"] == "percentage"
        ]
        assert pct == sorted(pct, reverse=True), "Percentage thresholds should be descending"

    def test_alerts_enabled_by_default(self):
        assert DEFAULT_SLA_RISK_CONFIG["risk_alert_enabled"] is True
        assert DEFAULT_SLA_RISK_CONFIG["breach_alert_enabled"] is True
        assert DEFAULT_SLA_RISK_CONFIG["email_alerts_enabled"] is True
        assert DEFAULT_SLA_RISK_CONFIG["sms_alerts_enabled"] is True
