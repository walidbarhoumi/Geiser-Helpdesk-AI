"""
Tests for SLA deadline calculation, AT_RISK detection, and BREACHED detection.
Run: pytest test_sla_service.py -v
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from services.sla_service import SLAService, DEFAULT_SLA_POLICIES
from schemas.schemas import TicketPriority, SLAStatus


def make_mock_db():
    db = MagicMock()
    db.tickets = MagicMock()
    db.sla_policies = MagicMock()
    db.sla_alerts = MagicMock()
    db.sla_policies.find_one = AsyncMock(return_value=None)
    return db


@pytest.fixture
def sla_service():
    return SLAService(make_mock_db())


@pytest.mark.asyncio
async def test_urgent_deadline_is_4h(sla_service):
    created_at = datetime(2026, 1, 1, 10, 0, 0)
    deadline = await sla_service.compute_sla_deadline(TicketPriority.URGENT, created_at)
    assert deadline == created_at + timedelta(hours=4)


@pytest.mark.asyncio
async def test_high_deadline_is_8h(sla_service):
    created_at = datetime(2026, 1, 1, 10, 0, 0)
    deadline = await sla_service.compute_sla_deadline(TicketPriority.HIGH, created_at)
    assert deadline == created_at + timedelta(hours=8)


@pytest.mark.asyncio
async def test_on_track_status(sla_service):
    created_at = datetime.utcnow() - timedelta(hours=1)
    deadline = created_at + timedelta(hours=4)
    ticket = {
        "priority": TicketPriority.URGENT,
        "created_at": created_at,
        "sla_deadline": deadline,
    }
    status = await sla_service.compute_sla_status(ticket)
    assert status == SLAStatus.ON_TRACK


@pytest.mark.asyncio
async def test_at_risk_status(sla_service):
    """URGENT 4h SLA: at 3h30m elapsed, less than 20% time remains → AT_RISK."""
    created_at = datetime.utcnow() - timedelta(hours=3, minutes=30)
    deadline = created_at + timedelta(hours=4)
    ticket = {
        "priority": TicketPriority.URGENT,
        "created_at": created_at,
        "sla_deadline": deadline,
    }
    status = await sla_service.compute_sla_status(ticket)
    assert status == SLAStatus.AT_RISK


@pytest.mark.asyncio
async def test_breached_status(sla_service):
    """URGENT 4h SLA: at 5h elapsed → BREACHED."""
    created_at = datetime.utcnow() - timedelta(hours=5)
    deadline = created_at + timedelta(hours=4)
    ticket = {
        "priority": TicketPriority.URGENT,
        "created_at": created_at,
        "sla_deadline": deadline,
    }
    status = await sla_service.compute_sla_status(ticket)
    assert status == SLAStatus.BREACHED


@pytest.mark.asyncio
async def test_default_policies_match_spec():
    urgent = DEFAULT_SLA_POLICIES[TicketPriority.URGENT]
    assert urgent["response_time_hours"] == 1.0
    assert urgent["resolution_time_hours"] == 4.0

    low = DEFAULT_SLA_POLICIES[TicketPriority.LOW]
    assert low["response_time_hours"] == 24.0
    assert low["resolution_time_hours"] == 72.0
