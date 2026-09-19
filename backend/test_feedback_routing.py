"""
Unit and integration tests for Adaptive Routing & Historical Feedback Loop (STEP 2).
Run: pytest test_feedback_routing.py -v
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId

from services.routing_service import RoutingService, DEFAULT_ROUTING_CONFIG
from services.ticket_service import TicketService
from schemas.schemas import TicketPriority, TicketStatus


def make_mock_db():
    db = MagicMock()
    db.tickets = MagicMock()
    db.agents = MagicMock()
    db.teams = MagicMock()
    db.routing_history = MagicMock()
    return db


# ──────────────────────────────────────────────────────────────
# Test 1: No history → Routing works normally with baseline values
# ──────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_1_no_history_baseline():
    db = make_mock_db()
    # Mock empty tickets for this agent
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=[])
    db.tickets.find = MagicMock(return_value=mock_cursor)

    service = RoutingService(db)
    stats = await service._compute_agent_historical_stats(
        agent_id="agent_new",
        category="Infrastructure & Réseau",
        subcategory="VPN & Accès Distant"
    )

    assert stats["assigned_count"] == 0
    assert stats["resolved_count"] == 0
    assert stats["reassigned_count"] == 0
    assert stats["category_experience_score"] == 0.0
    assert stats["reassignment_penalty"] == 0.0
    # Bayesian smoothed score should equal baseline prior (0.80)
    assert stats["bayesian_success_score"] == DEFAULT_ROUTING_CONFIG["bayesian_baseline"]
    assert stats["is_fallback"] is False


# ──────────────────────────────────────────────────────────────
# Test 2: Good historical performance → higher success & experience
# ──────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_2_good_historical_performance():
    db = make_mock_db()
    agent_id = "agent_expert"
    now = datetime.utcnow()

    # 15 tickets assigned to agent_expert, 14 resolved, 0 reassigned
    fake_tickets = []
    for i in range(15):
        is_res = i < 14
        fake_tickets.append({
            "_id": ObjectId(),
            "assigned_agent_id": agent_id,
            "category": "Infrastructure & Réseau",
            "subcategory": "VPN & Accès Distant",
            "status": TicketStatus.RESOLVED.value if is_res else TicketStatus.IN_PROGRESS.value,
            "created_at": now - timedelta(days=10),
            "updated_at": now - timedelta(days=9),
            "reassigned_from_agent_ids": []
        })

    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=fake_tickets)
    db.tickets.find = MagicMock(return_value=mock_cursor)

    service = RoutingService(db)
    stats = await service._compute_agent_historical_stats(
        agent_id=agent_id,
        category="Infrastructure & Réseau",
        subcategory="VPN & Accès Distant"
    )

    assert stats["assigned_count"] == 15
    assert stats["resolved_count"] == 14
    assert stats["reassigned_count"] == 0
    assert stats["bayesian_success_score"] > 0.85  # Boosted above baseline 0.80
    assert stats["category_experience_score"] == 1.0  # Saturated at 10+ tickets
    assert stats["reassignment_penalty"] == 0.0


# ──────────────────────────────────────────────────────────────
# Test 3: Reassignments → moderate penalty applied
# ──────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_3_reassignments_moderate_penalty():
    db = make_mock_db()
    agent_id = "agent_reassigned"
    now = datetime.utcnow()

    # 10 tickets where agent was assigned or reassigned away
    fake_tickets = []
    # 5 resolved
    for i in range(5):
        fake_tickets.append({
            "_id": ObjectId(),
            "assigned_agent_id": agent_id,
            "category": "Infrastructure & Réseau",
            "subcategory": "VPN & Accès Distant",
            "status": TicketStatus.RESOLVED.value,
            "created_at": now - timedelta(days=5),
            "updated_at": now - timedelta(days=4),
            "reassigned_from_agent_ids": []
        })
    # 4 reassigned away from this agent
    for i in range(4):
        fake_tickets.append({
            "_id": ObjectId(),
            "assigned_agent_id": "other_agent",
            "category": "Infrastructure & Réseau",
            "subcategory": "VPN & Accès Distant",
            "status": TicketStatus.IN_PROGRESS.value,
            "created_at": now - timedelta(days=2),
            "updated_at": now - timedelta(days=1),
            "reassigned_from_agent_ids": [agent_id]
        })

    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=fake_tickets)
    db.tickets.find = MagicMock(return_value=mock_cursor)

    service = RoutingService(db)
    stats = await service._compute_agent_historical_stats(
        agent_id=agent_id,
        category="Infrastructure & Réseau",
        subcategory="VPN & Accès Distant"
    )

    assert stats["reassigned_count"] == 4
    assert stats["reassignment_penalty"] > 0.0
    assert stats["reassignment_penalty"] <= DEFAULT_ROUTING_CONFIG["max_reassignment_penalty"]


# ──────────────────────────────────────────────────────────────
# Test 4: Small sample (1 ticket) does not dominate veteran
# ──────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_4_small_sample_does_not_dominate():
    db = make_mock_db()
    now = datetime.utcnow()

    # Agent 1 (Rookie): 1 ticket, 1 resolved (100% raw)
    rookie_tickets = [{
        "_id": ObjectId(),
        "assigned_agent_id": "rookie",
        "category": "Infrastructure & Réseau",
        "subcategory": "VPN & Accès Distant",
        "status": TicketStatus.RESOLVED.value,
        "created_at": now - timedelta(days=2),
        "updated_at": now - timedelta(days=1),
        "reassigned_from_agent_ids": []
    }]

    # Agent 2 (Veteran): 20 tickets, 19 resolved (95% raw)
    veteran_tickets = []
    for i in range(20):
        veteran_tickets.append({
            "_id": ObjectId(),
            "assigned_agent_id": "veteran",
            "category": "Infrastructure & Réseau",
            "subcategory": "VPN & Accès Distant",
            "status": TicketStatus.RESOLVED.value if i < 19 else TicketStatus.IN_PROGRESS.value,
            "created_at": now - timedelta(days=15),
            "updated_at": now - timedelta(days=14),
            "reassigned_from_agent_ids": []
        })

    service = RoutingService(db)

    # Compute Rookie
    mock_cursor_r = MagicMock()
    mock_cursor_r.to_list = AsyncMock(return_value=rookie_tickets)
    db.tickets.find = MagicMock(return_value=mock_cursor_r)
    rookie_stats = await service._compute_agent_historical_stats("rookie", "Infrastructure & Réseau", "VPN & Accès Distant")

    # Compute Veteran
    mock_cursor_v = MagicMock()
    mock_cursor_v.to_list = AsyncMock(return_value=veteran_tickets)
    db.tickets.find = MagicMock(return_value=mock_cursor_v)
    veteran_stats = await service._compute_agent_historical_stats("veteran", "Infrastructure & Réseau", "VPN & Accès Distant")

    # Bayesian smoothed score of veteran (19/20) should be HIGHER than rookie (1/1)
    assert veteran_stats["bayesian_success_score"] > rookie_stats["bayesian_success_score"]
    # Experience score of veteran must be significantly higher
    assert veteran_stats["category_experience_score"] > rookie_stats["category_experience_score"]
    assert veteran_stats["category_experience_score"] == 1.0
    assert rookie_stats["category_experience_score"] == 0.10


# ──────────────────────────────────────────────────────────────
# Test 5: Different category performance does not leak
# ──────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_5_category_isolation():
    db = make_mock_db()
    agent_id = "hardware_pro"
    now = datetime.utcnow()

    # Agent has 20 resolved tickets in "Matériel & Poste de Travail"
    # When routing for "Infrastructure & Réseau", query filters by category="Infrastructure & Réseau"
    # and returns 0 tickets!
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=[])  # no tickets in Infrastructure & Réseau
    db.tickets.find = MagicMock(return_value=mock_cursor)

    service = RoutingService(db)
    stats = await service._compute_agent_historical_stats(
        agent_id=agent_id,
        category="Infrastructure & Réseau",
        subcategory="VPN & Accès Distant"
    )

    # In Infrastructure, the hardware pro has 0 experience and neutral baseline
    assert stats["assigned_count"] == 0
    assert stats["category_experience_score"] == 0.0
    assert stats["bayesian_success_score"] == DEFAULT_ROUTING_CONFIG["bayesian_baseline"]


# ──────────────────────────────────────────────────────────────
# Test 6: New agent remains eligible with neutral baseline
# ──────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_6_new_agent_eligibility():
    db = make_mock_db()
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=[])
    db.tickets.find = MagicMock(return_value=mock_cursor)

    service = RoutingService(db)
    stats = await service._compute_agent_historical_stats("new_hire_id", "Sécurité IT", "Email Suspect / Phishing")

    # New agent is NOT penalized (penalty=0), has baseline prior (0.80), experience=0.0
    assert stats["reassignment_penalty"] == 0.0
    assert stats["bayesian_success_score"] == 0.80
    assert stats["sample_size"] == 0


# ──────────────────────────────────────────────────────────────
# Test 7: Fallback on database error
# ──────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_7_database_error_fallback():
    db = make_mock_db()
    # Simulate database query error
    db.tickets.find = MagicMock(side_effect=Exception("MongoDB connection timeout"))

    service = RoutingService(db)
    stats = await service._compute_agent_historical_stats("any_agent", "Infrastructure & Réseau")

    # Must catch exception and safely return fallback defaults without crashing
    assert stats["is_fallback"] is True
    assert stats["bayesian_success_score"] == DEFAULT_ROUTING_CONFIG["bayesian_baseline"]
    assert stats["category_experience_score"] == 0.0
    assert stats["reassignment_penalty"] == 0.0


# ──────────────────────────────────────────────────────────────
# Test 8: Reassignment idempotency (same agent not duplicated)
# ──────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_8_reassignment_idempotency_no_duplicates():
    db = make_mock_db()
    ticket_oid = ObjectId()
    agent_a_id = str(ObjectId())
    agent_b_id = str(ObjectId())

    current_ticket = {
        "_id": ticket_oid,
        "id": str(ticket_oid),
        "assigned_agent_id": agent_a_id,
        "status": TicketStatus.IN_PROGRESS.value,
        "reassignment_count": 0,
        "reassigned_from_agent_ids": [],
        "reassignment_history": []
    }

    service = TicketService(db)
    service.get_ticket = AsyncMock(return_value=current_ticket)
    db.agents.find_one = AsyncMock(return_value={"_id": ObjectId(agent_a_id), "workload": 2})
    db.tickets.update_one = AsyncMock()
    db.agents.update_one = AsyncMock()

    # Action 1: Assigning to the SAME agent (agent_a)
    await service.assign_agent(str(ticket_oid), agent_a_id)

    # Must NOT record reassignment nor change workload
    assert db.agents.update_one.call_count == 0

    # Action 2: Assigning to a DIFFERENT agent (agent_b)
    db.agents.find_one = AsyncMock(return_value={"_id": ObjectId(agent_b_id), "workload": 1})
    await service.assign_agent(str(ticket_oid), agent_b_id)

    # Must decrement agent_a workload and increment agent_b workload
    assert db.agents.update_one.call_count == 2
    # Verify update_one was called with $inc reassignment_count and $addToSet reassigned_from_agent_ids
    calls = db.tickets.update_one.call_args_list
    assert any("$inc" in c[0][1] and "reassignment_count" in c[0][1]["$inc"] for c in calls)
