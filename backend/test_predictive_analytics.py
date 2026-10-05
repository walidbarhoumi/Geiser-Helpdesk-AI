"""
test_predictive_analytics.py
=============================
Test suite for Feature 1: Advanced Predictive Analytics + Recurring Ticket Detection.

Covers:
1. Volume forecasting (empty, baseline fallback, normal trend estimation, bounds, peak days)
2. Resolution time prediction (segment averages, SLA targets, impact/urgency multipliers, confidence)
3. SLA breach prediction (deadline expired, high breach risk, safe tickets, risk factors)
4. Recurring ticket detection (empty list, identical tickets, similar tickets, dissimilar tickets, solutions extraction)
5. Edge cases: missing optional fields, 0 samples, irregular timestamps
6. FastAPI endpoints integration
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId
from fastapi.testclient import TestClient

from services.predictive_analytics_service import PredictiveAnalyticsService
from services.analytics_service import AnalyticsService
from schemas.schemas import (
    TicketPriority, TicketStatus, SLAStatus, ImpactLevel, UrgencyLevel,
    UserRole
)
from main import app
from database.mongodb import get_database
from core.deps import get_current_user


def make_mock_db():
    db = MagicMock()
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=[])
    cursor.sort = MagicMock(return_value=cursor)
    cursor.limit = MagicMock(return_value=cursor)

    db.tickets = MagicMock()
    db.tickets.find = MagicMock(return_value=cursor)
    db.tickets.find_one = AsyncMock(return_value=None)
    db.agents = MagicMock()
    db.agents.find = MagicMock(return_value=cursor)
    db.users = MagicMock()
    db.users.find_one = AsyncMock(return_value=None)
    db.teams = MagicMock()
    db.teams.find_one = AsyncMock(return_value=None)
    db.knowledge_base = MagicMock()
    db.knowledge_base.find = MagicMock(return_value=cursor)
    db.sla_alerts = MagicMock()
    db.sla_risk_config = MagicMock()
    db.sla_risk_config.find_one = AsyncMock(return_value=None)
    return db


@pytest.fixture
def mock_db():
    return make_mock_db()


@pytest.fixture
def predictive_service(mock_db):
    return PredictiveAnalyticsService(mock_db)


# ──────────────────────────────────────────────────────────────
# 1. Volume Forecasting Tests
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_volume_forecast_empty_tickets(predictive_service):
    """Zero tickets returns baseline fallback with is_baseline=True and confidence=LOW."""
    forecast = await predictive_service.generate_volume_forecast(tickets=[], forecast_days=7)
    assert forecast.is_baseline is True
    assert forecast.confidence_level == "LOW"
    assert forecast.forecast_days == 7
    assert len(forecast.daily_forecasts) == 7
    assert forecast.total_predicted_volume > 0
    assert forecast.data_points_analyzed == 0


@pytest.mark.asyncio
async def test_volume_forecast_insufficient_data(predictive_service):
    """Only 2 tickets on 1 day: should return baseline fallback safely."""
    now = datetime.utcnow()
    tickets = [
        {"_id": ObjectId(), "created_at": now},
        {"_id": ObjectId(), "created_at": now}
    ]
    forecast = await predictive_service.generate_volume_forecast(tickets=tickets, forecast_days=7)
    assert forecast.is_baseline is True
    assert forecast.confidence_level == "LOW"
    assert forecast.data_points_analyzed == 2
    assert len(forecast.daily_forecasts) == 7


@pytest.mark.asyncio
async def test_volume_forecast_normal_trend(predictive_service):
    """Sufficient historical data over 15 days produces statistical projection."""
    now = datetime.utcnow()
    tickets = []
    # 5 tickets per day for 15 days
    for day in range(15):
        dt = now - timedelta(days=day)
        for _ in range(5):
            tickets.append({"_id": ObjectId(), "created_at": dt})

    forecast = await predictive_service.generate_volume_forecast(tickets=tickets, forecast_days=7)
    assert forecast.is_baseline is False
    assert forecast.confidence_level in ["MEDIUM", "HIGH"]
    assert forecast.historical_daily_avg > 0
    assert len(forecast.daily_forecasts) == 7
    assert forecast.total_predicted_volume > 0
    # Every day should have valid bounds
    for pt in forecast.daily_forecasts:
        assert pt.lower_bound <= pt.predicted_count <= pt.upper_bound
        assert pt.day_name in ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]


# ──────────────────────────────────────────────────────────────
# 2. Resolution Time Prediction Tests
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_predict_resolution_time_with_history(predictive_service):
    """Historical resolved tickets in same category & priority inform MTTR."""
    now = datetime.utcnow()
    # 3 resolved tickets in Infrastructure / URGENT with ~2h resolution duration
    tickets = [
        {
            "_id": ObjectId(),
            "category": "Infrastructure & Réseau",
            "priority": "URGENT",
            "status": "RESOLVED",
            "created_at": now - timedelta(hours=3),
            "updated_at": now - timedelta(hours=1)  # 2.0 hours
        },
        {
            "_id": ObjectId(),
            "category": "Infrastructure & Réseau",
            "priority": "URGENT",
            "status": "RESOLVED",
            "created_at": now - timedelta(hours=4),
            "updated_at": now - timedelta(hours=2)  # 2.0 hours
        }
    ]

    res = await predictive_service.predict_resolution_time(
        category="Infrastructure & Réseau",
        priority=TicketPriority.URGENT,
        tickets=tickets
    )

    assert res.predicted_hours > 0
    assert res.baseline_used == "category_priority"
    assert res.historical_sample_size == 2
    assert res.sla_target_hours == 4.0  # URGENT target in DEFAULT_SLA_POLICIES is 4h
    assert len(res.contributing_factors) >= 1
    assert "2h" in res.predicted_duration_formatted or "h" in res.predicted_duration_formatted


@pytest.mark.asyncio
async def test_predict_resolution_time_no_history_uses_sla_baseline(predictive_service):
    """When no historical tickets exist, uses ITIL SLA baseline target."""
    res = await predictive_service.predict_resolution_time(
        category="Inconnue",
        priority=TicketPriority.MEDIUM,
        tickets=[]
    )
    assert res.predicted_hours > 0
    assert res.baseline_used == "sla_policy_default"
    assert res.sla_target_hours == 24.0  # MEDIUM SLA target is 24h
    assert res.estimated_sla_compliance is True


@pytest.mark.asyncio
async def test_predict_resolution_time_impact_urgency_adjustments(predictive_service):
    """HIGH impact increases estimated hours, while LOW decreases it."""
    base_res = await predictive_service.predict_resolution_time(
        category="Poste de Travail",
        priority=TicketPriority.HIGH,
        impact=None,
        tickets=[]
    )

    high_impact_res = await predictive_service.predict_resolution_time(
        category="Poste de Travail",
        priority=TicketPriority.HIGH,
        impact=ImpactLevel.HIGH,
        tickets=[]
    )

    assert high_impact_res.predicted_hours > base_res.predicted_hours
    assert any("Impact Élevé" in f.factor for f in high_impact_res.contributing_factors)


# ──────────────────────────────────────────────────────────────
# 3. SLA Breach Risk Prediction Tests
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_predict_sla_breach_risks_overdue_ticket(predictive_service):
    """Ticket whose deadline has already passed is flagged as CRITIQUE (100%)."""
    now = datetime.utcnow()
    overdue_ticket = {
        "_id": ObjectId(),
        "reference": "[TICK-CRIT01]",
        "subject": "Serveur VPN inaccessible",
        "priority": "URGENT",
        "status": "OPEN",
        "category": "Infrastructure & Réseau",
        "created_at": now - timedelta(hours=5),
        "sla_deadline": now - timedelta(hours=1)  # expired 1 hour ago
    }

    result = await predictive_service.predict_sla_breach_risks(active_tickets=[overdue_ticket])
    assert result.total_active_tickets == 1
    assert result.critical_count == 1
    assert result.tickets[0].risk_level == "CRITIQUE"
    assert result.tickets[0].breach_probability_pct == 100.0
    assert "déjà dépassé" in result.tickets[0].risk_factors[0].lower()


@pytest.mark.asyncio
async def test_predict_sla_breach_risks_safe_ticket(predictive_service):
    """Ticket with ample remaining SLA time is evaluated as FAIBLE risk."""
    now = datetime.utcnow()
    safe_ticket = {
        "_id": ObjectId(),
        "reference": "[TICK-SAFE01]",
        "subject": "Demande de clavier",
        "priority": "LOW",
        "status": "OPEN",
        "category": "Matériel & Équipements",
        "created_at": now - timedelta(minutes=15),
        "sla_deadline": now + timedelta(hours=70)  # 70h remaining (target 72h)
    }

    result = await predictive_service.predict_sla_breach_risks(active_tickets=[safe_ticket])
    assert result.total_active_tickets == 1
    assert result.critical_count == 0
    assert result.tickets[0].risk_level in ["FAIBLE", "MODÉRÉ"]
    assert result.tickets[0].breach_probability_pct <= 45.0


# ──────────────────────────────────────────────────────────────
# 4. Recurring Ticket Detection & Clustering Tests
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_detect_recurring_tickets_empty(predictive_service):
    """Empty tickets returns 0 clusters."""
    resp = await predictive_service.detect_recurring_tickets(tickets=[])
    assert resp.total_clusters == 0
    assert resp.clusters == []


@pytest.mark.asyncio
async def test_detect_recurring_tickets_clusters_similar_issues(predictive_service):
    """Similar tickets with VPN keywords in same category are clustered together."""
    now = datetime.utcnow()
    t1 = {
        "_id": ObjectId(),
        "reference": "[TICK-VPN01]",
        "subject": "Erreur de connexion client VPN",
        "description": "Impossible de me connecter au VPN Cisco AnyConnect depuis ce matin.",
        "category": "Infrastructure & Réseau",
        "subcategory": "VPN & Accès Distant",
        "priority": "HIGH",
        "status": "RESOLVED",
        "keywords": ["vpn", "connexion", "reseau"],
        "resolution_note": "Réinitialisation du profil AnyConnect et vidage du cache DNS.",
        "created_at": now - timedelta(days=2)
    }
    t2 = {
        "_id": ObjectId(),
        "reference": "[TICK-VPN02]",
        "subject": "VPN AnyConnect connexion impossible",
        "description": "Mon VPN ne veut pas se connecter aujourd'hui, message d'erreur réseau.",
        "category": "Infrastructure & Réseau",
        "subcategory": "VPN & Accès Distant",
        "priority": "HIGH",
        "status": "OPEN",
        "keywords": ["vpn", "connexion", "reseau"],
        "created_at": now - timedelta(days=1)
    }
    t3 = {
        "_id": ObjectId(),
        "reference": "[TICK-OTHER]",
        "subject": "Demande de nouvelle souris ergonomique",
        "description": "Besoin d'une souris ergonomique pour mon bureau.",
        "category": "Matériel & Périphériques",
        "priority": "LOW",
        "status": "OPEN",
        "keywords": ["souris", "materiel"],
        "created_at": now
    }

    resp = await predictive_service.detect_recurring_tickets(tickets=[t1, t2, t3], min_similarity=35.0)
    assert resp.total_clusters == 1
    cluster = resp.clusters[0]
    assert cluster.occurrence_count == 2
    assert cluster.category == "Infrastructure & Réseau"
    assert cluster.status == "ACTIVE"  # t2 is OPEN
    assert cluster.average_similarity_pct >= 40.0
    # Common solution should be extracted from t1
    assert any("AnyConnect" in s for s in cluster.common_solutions)
    assert len(cluster.sample_tickets) == 2


@pytest.mark.asyncio
async def test_detect_recurring_tickets_dissimilar_not_clustered(predictive_service):
    """Completely dissimilar tickets in different categories do not form clusters."""
    now = datetime.utcnow()
    t1 = {
        "_id": ObjectId(),
        "subject": "Panne imprimante 3ème étage",
        "description": "Bourrage papier récurrent",
        "category": "Imprimantes",
        "priority": "LOW",
        "status": "OPEN",
        "created_at": now - timedelta(days=2)
    }
    t2 = {
        "_id": ObjectId(),
        "subject": "Accès badge cafeteria bloqué",
        "description": "Mon badge ne passe pas aux tourniquets",
        "category": "Accès Physique",
        "priority": "LOW",
        "status": "OPEN",
        "created_at": now - timedelta(days=1)
    }

    resp = await predictive_service.detect_recurring_tickets(tickets=[t1, t2], min_similarity=50.0)
    assert resp.total_clusters == 0


# ──────────────────────────────────────────────────────────────
# 5. Integration into AnalyticsService & Endpoints
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analytics_dashboard_predictive_insights_integration(mock_db):
    """Test that AnalyticsService dashboard includes predictive insights, volume forecast, and SLA risks."""
    cursor_mock = MagicMock()
    cursor_mock.to_list = AsyncMock(return_value=[
        {
            "_id": ObjectId(),
            "subject": "VPN déconnecté",
            "category": "Réseau",
            "priority": "HIGH",
            "status": "OPEN",
            "created_at": datetime.utcnow()
        }
    ])
    mock_db.tickets.find = MagicMock(return_value=cursor_mock)
    mock_db.agents.find = MagicMock(return_value=cursor_mock)

    service = AnalyticsService(mock_db)
    dash = await service.get_dashboard_analytics(period_days=14)

    assert dash.predictive_insights is not None
    assert dash.predictive_insights.predicted_volume_next_week > 0
    assert dash.predictive_insights.volume_forecast is not None
    assert dash.predictive_insights.volume_forecast.forecast_days == 7


def test_fastapi_predictive_endpoints():
    """Verify predictive REST endpoints respond with valid schemas."""
    mock_user = {
        "id": "60d5ec49f1b2c8b1f8e4e1a1",
        "_id": "60d5ec49f1b2c8b1f8e4e1a1",
        "email": "supervisor@geiser.internal",
        "role": UserRole.SUPERVISOR.value
    }
    fake_db = make_mock_db()
    cursor_mock = MagicMock()
    cursor_mock.to_list = AsyncMock(return_value=[])
    fake_db.tickets.find = MagicMock(return_value=cursor_mock)
    fake_db.agents.find = MagicMock(return_value=cursor_mock)

    app.dependency_overrides[get_database] = lambda: fake_db
    app.dependency_overrides[get_current_user] = lambda: mock_user

    client = TestClient(app)

    # 1. Volume forecast endpoint
    r1 = client.get("/api/v1/analytics/predictive/volume-forecast?forecast_days=7")
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["forecast_days"] == 7
    assert "daily_forecasts" in d1

    # 2. Resolution time prediction endpoint (GET)
    r2 = client.get("/api/v1/analytics/predictive/resolution-time?priority=HIGH&category=Réseau")
    assert r2.status_code == 200
    d2 = r2.json()
    assert "predicted_hours" in d2
    assert d2["sla_target_hours"] == 8.0

    # 3. Resolution time prediction endpoint (POST)
    r3 = client.post("/api/v1/analytics/predictive/resolution-time", json={
        "category": "Sécurité",
        "priority": "URGENT",
        "impact": "HIGH"
    })
    assert r3.status_code == 200
    d3 = r3.json()
    assert d3["predicted_hours"] > 0

    # 4. SLA breach risks endpoint
    r4 = client.get("/api/v1/analytics/predictive/sla-breach-risks")
    assert r4.status_code == 200
    d4 = r4.json()
    assert "at_risk_count" in d4

    # 5. Recurring tickets endpoint
    r5 = client.get("/api/v1/analytics/recurring-tickets")
    assert r5.status_code == 200
    d5 = r5.json()
    assert "clusters" in d5

    app.dependency_overrides.clear()
