"""
test_analytics_authorization_correctness.py
============================================
Comprehensive test suite verifying:
1. Analytics endpoint authorization (ordinary user scoped vs manager/admin org-wide)
2. Role/team boundary enforcement (USER cannot pass team_id; AGENT cannot view other teams)
3. 401 / 403 status responses without leaking sensitive data
4. Removal of fabricated values: MTTR=None (not 4.2h/4.0h), response_time=None (not 0.4h/0.5h), satisfaction=None (not 4.8)
5. Empty dataset correctness: all unknown metrics are None, not invented defaults
6. Accurate metric computation from real persisted records
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId
from fastapi.testclient import TestClient

from main import app
from database.mongodb import get_database
from core.deps import get_current_user
from schemas.schemas import UserRole, TicketPriority, TicketStatus
from services.analytics_service import AnalyticsService


def make_mock_db(tickets=None, agents=None, teams=None, users=None):
    db = MagicMock()

    def make_cursor(items):
        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=items or [])
        cursor.sort = MagicMock(return_value=cursor)
        cursor.limit = MagicMock(return_value=cursor)
        return cursor

    ticket_list = list(tickets or [])
    agent_list = list(agents or [])
    team_list = list(teams or [])
    user_list = list(users or [])

    db.tickets = MagicMock()
    db.tickets.find = MagicMock(side_effect=lambda *args, **kwargs: make_cursor(ticket_list))
    db.tickets.find_one = AsyncMock(return_value=ticket_list[0] if ticket_list else None)

    db.agents = MagicMock()
    db.agents.find = MagicMock(side_effect=lambda *args, **kwargs: make_cursor(agent_list))
    
    async def mock_agent_find_one(query):
        uid = query.get("user_id")
        for ag in agent_list:
            if str(ag.get("user_id")) == str(uid):
                return ag
        return None
    db.agents.find_one = AsyncMock(side_effect=mock_agent_find_one)

    db.teams = MagicMock()
    def mock_teams_find(query=None):
        query = query or {}
        ag_id = query.get("agent_ids")
        if ag_id:
            matched = [t for t in team_list if ag_id in t.get("agent_ids", [])]
            return make_cursor(matched)
        return make_cursor(team_list)
    db.teams.find = MagicMock(side_effect=mock_teams_find)
    
    async def mock_teams_find_one(query):
        tid = query.get("_id")
        for tm in team_list:
            if tm.get("_id") == tid:
                return tm
        return None
    db.teams.find_one = AsyncMock(side_effect=mock_teams_find_one)

    db.users = MagicMock()
    db.users.find = MagicMock(side_effect=lambda *args, **kwargs: make_cursor(user_list))
    db.users.find_one = AsyncMock(return_value=user_list[0] if user_list else None)

    return db


USER_ID = "650000000000000000000001"
OTHER_USER_ID = "650000000000000000000002"
AGENT_ID = "650000000000000000000010"
OTHER_AGENT_ID = "650000000000000000000011"
AGENT_USER_ID = "650000000000000000000020"
OTHER_AGENT_USER_ID = "650000000000000000000021"
TEAM_ID = "650000000000000000000100"
OTHER_TEAM_ID = "650000000000000000000101"

MOCK_USER = {"id": USER_ID, "email": "user@example.com", "role": UserRole.USER, "is_active": True}
MOCK_AGENT = {"id": AGENT_USER_ID, "email": "agent@example.com", "role": UserRole.AGENT, "is_active": True}
MOCK_SUPERVISOR = {"id": "650000000000000000000098", "email": "sup@example.com", "role": UserRole.SUPERVISOR, "is_active": True}
MOCK_ADMIN = {"id": "650000000000000000000099", "email": "admin@example.com", "role": UserRole.ADMIN, "is_active": True}

MOCK_AGENT_DOC = {
    "_id": ObjectId(AGENT_ID),
    "user_id": AGENT_USER_ID,
    "name": "Test Agent",
    "email": "agent@example.com"
}
MOCK_TEAM_DOC = {
    "_id": ObjectId(TEAM_ID),
    "name": "Support N1",
    "agent_ids": [AGENT_ID]
}


class TestAnalyticsAuthorization:
    """Test role-based access control on analytics endpoints."""

    def test_unauthenticated_dashboard_returns_401(self):
        client = TestClient(app)
        app.dependency_overrides.clear()
        res = client.get("/api/v1/analytics/dashboard")
        assert res.status_code == 401

    def test_unauthenticated_csat_returns_401(self):
        client = TestClient(app)
        app.dependency_overrides.clear()
        res = client.get("/api/v1/analytics/csat")
        assert res.status_code == 401

    def test_unauthenticated_predictive_insights_returns_401(self):
        client = TestClient(app)
        app.dependency_overrides.clear()
        res = client.get("/api/v1/analytics/predictive-insights")
        assert res.status_code == 401

    def test_ordinary_user_cannot_access_analytics_dashboard(self):
        """The existing role policy grants analytics only to agents and managers."""
        now = datetime.utcnow()
        user_ticket = {
            "_id": ObjectId("650000000000000000000005"),
            "user_id": USER_ID,
            "title": "Mon problème",
            "category": "Logiciel",
            "priority": "LOW",
            "status": "OPEN",
            "created_at": now - timedelta(hours=2),
            "updated_at": now - timedelta(hours=1),
        }
        other_ticket = {
            "_id": ObjectId("650000000000000000000006"),
            "user_id": OTHER_USER_ID,
            "title": "Autre problème",
            "category": "Matériel",
            "priority": "HIGH",
            "status": "OPEN",
            "created_at": now - timedelta(hours=3),
            "updated_at": now - timedelta(hours=1),
        }
        mock_db = make_mock_db(tickets=[user_ticket, other_ticket])

        app.dependency_overrides[get_database] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: MOCK_USER

        try:
            client = TestClient(app)
            res = client.get("/api/v1/analytics/dashboard")
            assert res.status_code == 403
        finally:
            app.dependency_overrides.clear()

    def test_ordinary_user_passing_team_filter_returns_403(self):
        """USER role cannot pass team_id filter to view other teams."""
        mock_db = make_mock_db()
        app.dependency_overrides[get_database] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: MOCK_USER

        try:
            client = TestClient(app)
            res = client.get(f"/api/v1/analytics/dashboard?team_id={TEAM_ID}")
            assert res.status_code == 403
        finally:
            app.dependency_overrides.clear()

    def test_ordinary_user_cannot_access_staff_only_predictive_insights(self):
        """USER role cannot access /analytics/predictive-insights."""
        mock_db = make_mock_db()
        app.dependency_overrides[get_database] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: MOCK_USER

        try:
            client = TestClient(app)
            res = client.get("/api/v1/analytics/predictive-insights")
            assert res.status_code == 403
        finally:
            app.dependency_overrides.clear()

    def test_ordinary_user_cannot_export_excel_or_pdf(self):
        """USER role cannot access export endpoints."""
        mock_db = make_mock_db()
        app.dependency_overrides[get_database] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: MOCK_USER

        try:
            client = TestClient(app)
            res_excel = client.get("/api/v1/analytics/export/excel")
            assert res_excel.status_code == 403
            res_pdf = client.get("/api/v1/analytics/export/pdf")
            assert res_pdf.status_code == 403
        finally:
            app.dependency_overrides.clear()

    def test_agent_cannot_access_unassigned_team_analytics(self):
        """AGENT role cannot pass a team_id they do not belong to."""
        mock_db = make_mock_db(
            agents=[MOCK_AGENT_DOC],
            teams=[MOCK_TEAM_DOC]
        )
        app.dependency_overrides[get_database] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: MOCK_AGENT

        try:
            client = TestClient(app)
            res = client.get(f"/api/v1/analytics/dashboard?team_id={OTHER_TEAM_ID}")
            assert res.status_code == 404
        finally:
            app.dependency_overrides.clear()

    def test_agent_cannot_export_reports(self):
        app.dependency_overrides[get_database] = lambda: make_mock_db()
        app.dependency_overrides[get_current_user] = lambda: MOCK_AGENT
        try:
            client = TestClient(app)
            assert client.get("/api/v1/analytics/export/excel").status_code == 403
            assert client.get("/api/v1/analytics/export/pdf").status_code == 403
        finally:
            app.dependency_overrides.clear()

    def test_admin_can_access_full_dashboard(self):
        """ADMIN has full organization-wide visibility."""
        now = datetime.utcnow()
        t1 = {
            "_id": ObjectId("650000000000000000000001"),
            "user_id": USER_ID,
            "title": "T1",
            "category": "Logiciel",
            "priority": "LOW",
            "status": "RESOLVED",
            "created_at": now - timedelta(hours=5),
            "updated_at": now - timedelta(hours=1),
            "resolved_at": now - timedelta(hours=1),
        }
        t2 = {
            "_id": ObjectId("650000000000000000000002"),
            "user_id": OTHER_USER_ID,
            "title": "T2",
            "category": "Réseau",
            "priority": "HIGH",
            "status": "RESOLVED",
            "created_at": now - timedelta(hours=4),
            "updated_at": now - timedelta(hours=2),
            "resolved_at": now - timedelta(hours=2),
        }
        mock_db = make_mock_db(tickets=[t1, t2])
        app.dependency_overrides[get_database] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: MOCK_ADMIN

        try:
            client = TestClient(app)
            res = client.get("/api/v1/analytics/dashboard")
            assert res.status_code == 200
            data = res.json()
            assert data["kpis"]["total_tickets"] == 2
        finally:
            app.dependency_overrides.clear()

    def test_agent_dashboard_is_limited_to_assigned_team(self):
        now = datetime.utcnow()
        visible = {"_id": ObjectId("650000000000000000000040"), "assigned_team_id": TEAM_ID,
                   "assigned_agent_id": AGENT_ID, "priority": "LOW", "status": "OPEN", "created_at": now}
        hidden = {"_id": ObjectId("650000000000000000000041"), "assigned_team_id": OTHER_TEAM_ID,
                  "assigned_agent_id": OTHER_AGENT_ID, "priority": "HIGH", "status": "OPEN", "created_at": now}
        mock_db = make_mock_db(tickets=[visible, hidden], agents=[MOCK_AGENT_DOC], teams=[MOCK_TEAM_DOC])
        svc = AnalyticsService(mock_db)

        import asyncio
        result = asyncio.run(svc.get_scoped_tickets(MOCK_AGENT))
        assert result == [visible]

    def test_service_rejects_user_without_analytics_permission(self):
        import asyncio
        svc = AnalyticsService(make_mock_db())
        with pytest.raises(Exception) as exc:
            asyncio.run(svc.get_scoped_tickets(MOCK_USER))
        assert getattr(exc.value, "status_code", None) == 403

    def test_supervisor_may_filter_organization_data_by_team(self):
        now = datetime.utcnow()
        team_ticket = {"_id": ObjectId("650000000000000000000042"), "assigned_team_id": TEAM_ID,
                       "priority": "LOW", "created_at": now}
        other_ticket = {"_id": ObjectId("650000000000000000000043"), "assigned_team_id": OTHER_TEAM_ID,
                        "priority": "LOW", "created_at": now}
        mock_db = make_mock_db(tickets=[team_ticket, other_ticket], teams=[MOCK_TEAM_DOC])
        svc = AnalyticsService(mock_db)
        import asyncio
        result = asyncio.run(svc.get_scoped_tickets(MOCK_SUPERVISOR, team_id=TEAM_ID))
        assert result == [team_ticket]

    @pytest.mark.asyncio
    async def test_agent_sla_alerts_and_risk_summary_are_scoped(self, monkeypatch):
        from routes import sla as sla_routes

        visible = {"_id": ObjectId("650000000000000000000060"), "assigned_agent_id": AGENT_ID,
                   "assigned_team_id": TEAM_ID, "status": "OPEN", "sla_status": "AT_RISK"}
        hidden = {"_id": ObjectId("650000000000000000000061"), "assigned_agent_id": OTHER_AGENT_ID,
                  "assigned_team_id": OTHER_TEAM_ID, "status": "OPEN", "sla_status": "BREACHED"}
        db = make_mock_db(tickets=[visible, hidden], agents=[MOCK_AGENT_DOC], teams=[MOCK_TEAM_DOC])

        class FakeSLAService:
            def __init__(self, _db): pass
            async def get_at_risk_tickets(self):
                return [{"ticket_id": str(visible["_id"]), "subject": "visible"},
                        {"ticket_id": str(hidden["_id"]), "subject": "hidden"}]

        class FakeRiskService:
            def __init__(self, _db): pass
            async def get_risk_overview(self):
                return {"kpis": {"total_active_slas": 2, "on_track_count": 0, "at_risk_count": 1,
                                  "breached_count": 1, "paused_count": 0, "compliance_pct": 50.0,
                                  "avg_remaining_minutes": 10.0},
                        "at_risk_tickets": [{"ticket_id": str(visible["_id"])}],
                        "active_alerts": [{"ticket_id": str(hidden["_id"]), "recipient_email": "private@example.com"}]}

        monkeypatch.setattr(sla_routes, "SLAService", FakeSLAService)
        monkeypatch.setattr(sla_routes, "SLARiskService", FakeRiskService)
        alerts = await sla_routes.list_alerts(current_user=MOCK_AGENT, db=db)
        assert [row["ticket_id"] for row in alerts] == [str(visible["_id"])]

        overview = await sla_routes.get_sla_risk_overview(current_user=MOCK_AGENT, db=db)
        assert overview["kpis"]["total_active_slas"] == 1
        assert overview["kpis"]["at_risk_count"] == 1
        assert overview["kpis"]["breached_count"] == 0
        assert overview["active_alerts"] == []

    @pytest.mark.asyncio
    async def test_agent_cannot_read_sla_status_for_out_of_scope_ticket(self, monkeypatch):
        from routes import sla as sla_routes
        hidden = {"_id": ObjectId("650000000000000000000062"), "assigned_agent_id": OTHER_AGENT_ID,
                  "assigned_team_id": OTHER_TEAM_ID, "status": "OPEN"}
        db = make_mock_db(tickets=[hidden], agents=[MOCK_AGENT_DOC], teams=[MOCK_TEAM_DOC])

        class FakeSLAService:
            def __init__(self, _db): pass
            async def get_ticket_sla_detail(self, _ticket_id): return {"ticket_id": str(hidden["_id"])}

        monkeypatch.setattr(sla_routes, "SLAService", FakeSLAService)
        with pytest.raises(Exception) as exc:
            await sla_routes.get_ticket_sla_status(str(hidden["_id"]), current_user=MOCK_AGENT, db=db)
        assert getattr(exc.value, "status_code", None) == 404

    @pytest.mark.asyncio
    async def test_agent_directory_routes_only_return_team_scope(self):
        from routes.agents import list_agents
        from routes.teams import list_teams
        other_agent = {"_id": ObjectId(OTHER_AGENT_ID), "user_id": OTHER_AGENT_USER_ID,
                       "name": "Outside Agent", "email": "outside@example.com"}
        db = make_mock_db(agents=[MOCK_AGENT_DOC, other_agent], teams=[MOCK_TEAM_DOC])
        agents = await list_agents(current_user=MOCK_AGENT, db=db)
        teams = await list_teams(current_user=MOCK_AGENT, db=db)
        assert [entry["id"] for entry in agents] == [AGENT_ID]
        assert [entry["id"] for entry in teams] == [TEAM_ID]


class TestAnalyticsMetricCorrectness:
    """Test metric calculations without fabricated values."""

    @pytest.mark.asyncio
    async def test_empty_dataset_returns_none_for_unknown_metrics(self):
        """When database is empty, MTTR, response time, and CSAT must be None, NOT fabricated."""
        mock_db = make_mock_db(tickets=[])
        svc = AnalyticsService(mock_db)

        dash = await svc.get_dashboard_analytics(period_days=30, current_user=MOCK_ADMIN)
        kpis = dash.kpis

        # Crucial checks: No fabricated fallbacks!
        assert kpis.overall_mttr_hours is None, "MTTR must be None when no tickets resolved, not 4.2h"
        assert kpis.avg_response_hours is None, "avg_response_hours must be None, not 0.4h or 0.5h"
        assert kpis.satisfaction_avg is None, "satisfaction_avg must be None, not 4.8"
        assert kpis.total_tickets == 0
        assert kpis.resolved_tickets == 0

        # MTTR metrics must also be None
        assert dash.mttr_metrics.overall_avg_hours is None
        for p in dash.mttr_metrics.by_priority:
            assert p.avg_resolution_hours is None, f"Priority {p.priority} MTTR must be None, not target_h * 0.75"
            assert p.is_within_sla is None, f"Priority {p.priority} is_within_sla must be None when no data"

        # Strategic issues must be empty list, NOT the hardcoded VPN issue
        assert len(dash.predictive_insights.strategic_issues) == 0, "No hardcoded VPN issues should be fabricated"
        assert dash.predictive_insights.predicted_volume_next_week is None
        assert dash.predictive_insights.volume_forecast.daily_forecasts == []
        assert dash.predictive_insights.volume_forecast.confidence_level == "UNAVAILABLE"

    @pytest.mark.asyncio
    async def test_resolved_tickets_calculate_exact_mttr(self):
        """When resolved tickets exist, MTTR is computed from real (resolved_at - created_at) durations."""
        now = datetime.utcnow()
        # Ticket resolved in exactly 2 hours (120 mins)
        t1 = {
            "_id": ObjectId("650000000000000000000010"),
            "user_id": USER_ID,
            "title": "T1",
            "category": "Matériel",
            "priority": "MEDIUM",
            "status": "RESOLVED",
            "created_at": now - timedelta(hours=2),
            "updated_at": now,
            "resolved_at": now,
        }
        # Ticket resolved in exactly 4 hours (240 mins)
        t2 = {
            "_id": ObjectId("650000000000000000000011"),
            "user_id": USER_ID,
            "title": "T2",
            "category": "Matériel",
            "priority": "MEDIUM",
            "status": "RESOLVED",
            "created_at": now - timedelta(hours=4),
            "updated_at": now,
            "resolved_at": now,
        }
        mock_db = make_mock_db(tickets=[t1, t2])
        svc = AnalyticsService(mock_db)

        dash = await svc.get_dashboard_analytics(period_days=30, current_user=MOCK_ADMIN)
        # Average of 2.0h and 4.0h = 3.0h (NOT 4.2h)
        assert dash.kpis.overall_mttr_hours == 3.0
        assert dash.mttr_metrics.overall_avg_hours == 3.0

    @pytest.mark.asyncio
    async def test_csat_without_ratings_returns_none(self):
        """When no tickets have satisfaction ratings, satisfaction_avg is None, NOT 4.8."""
        now = datetime.utcnow()
        ticket = {
            "_id": ObjectId("650000000000000000000020"),
            "user_id": USER_ID,
            "title": "No CSAT Ticket",
            "category": "Réseau",
            "priority": "LOW",
            "status": "RESOLVED",
            "created_at": now - timedelta(hours=1),
            "updated_at": now,
            "resolved_at": now,
            "satisfaction_rating": None,
        }
        mock_db = make_mock_db(tickets=[ticket])
        svc = AnalyticsService(mock_db)

        csat = await svc.get_csat_analytics(period_days=30, current_user=MOCK_ADMIN)
        assert csat.total_ratings == 0
        assert csat.avg_rating is None
        assert csat.satisfaction_rate_pct is None

        dash = await svc.get_dashboard_analytics(period_days=30, current_user=MOCK_ADMIN)
        assert dash.kpis.satisfaction_avg is None

    @pytest.mark.asyncio
    async def test_csat_computes_exact_average(self):
        """When satisfaction ratings are present, exact math is applied."""
        now = datetime.utcnow()
        t1 = {
            "_id": ObjectId("650000000000000000000030"),
            "user_id": USER_ID,
            "title": "Rated 5",
            "status": "RESOLVED",
            "satisfaction_rating": 5,
            "satisfaction_submitted_at": now,
            "created_at": now - timedelta(days=1),
        }
        t2 = {
            "_id": ObjectId("650000000000000000000031"),
            "user_id": USER_ID,
            "title": "Rated 3",
            "status": "RESOLVED",
            "satisfaction_rating": 3,
            "satisfaction_submitted_at": now,
            "created_at": now - timedelta(days=1),
        }
        mock_db = make_mock_db(tickets=[t1, t2])
        svc = AnalyticsService(mock_db)

        csat = await svc.get_csat_analytics(period_days=30, current_user=MOCK_ADMIN)
        assert csat.total_ratings == 2
        # (5 + 3) / 2 = 4.0 (NOT 4.8)
        assert csat.avg_rating == 4.0
        # 1 rating >= 4 out of 2 = 50.0%
        assert csat.satisfaction_rate_pct == 50.0

    @pytest.mark.asyncio
    async def test_agent_csat_is_limited_to_its_team_scope(self):
        now = datetime.utcnow()
        visible = {"_id": ObjectId("650000000000000000000050"), "assigned_agent_id": AGENT_ID,
                   "assigned_team_id": TEAM_ID, "satisfaction_rating": 5,
                   "satisfaction_comment": "visible", "satisfaction_submitted_at": now, "created_at": now}
        hidden = {"_id": ObjectId("650000000000000000000051"), "assigned_agent_id": OTHER_AGENT_ID,
                  "assigned_team_id": OTHER_TEAM_ID, "satisfaction_rating": 1,
                  "satisfaction_comment": "private", "satisfaction_submitted_at": now, "created_at": now}
        db = make_mock_db(tickets=[visible, hidden], agents=[MOCK_AGENT_DOC], teams=[MOCK_TEAM_DOC])
        result = await AnalyticsService(db).get_csat_analytics(current_user=MOCK_AGENT)
        assert result.total_ratings == 1
        assert result.avg_rating == 5.0
        assert [entry.comment for entry in result.recent_feedback] == ["visible"]
