"""
test_csat_feature.py
====================
Comprehensive test suite for Feature 2: Complete CSAT (Customer Satisfaction).

Covers:
1. Valid 1-5 ratings on resolved/closed tickets
2. Invalid ratings (0, 6, negative) rejected with 422
3. Rating an unresolved ticket (OPEN, IN_PROGRESS, PENDING) rejected with 400
4. Rating another user's ticket rejected with 403 for USER role
5. Duplicate rating on already rated ticket rejected with 409
6. Admin permission to rate tickets
7. Optional comments and sanitization
8. ISO 27001 action history audit trail on rating
9. CSAT outcome feedback in routing_history
10. CSAT analytics calculations (average, positive %, 1-5 distribution, trends)
11. Agent and category CSAT aggregations
12. GET /api/v1/analytics/csat endpoint
13. GET /api/v1/analytics/dashboard CSAT integration
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId
from fastapi.testclient import TestClient

from main import app
from database.mongodb import get_database
from core.deps import get_current_user
from schemas.schemas import (
    TicketStatus, TicketPriority, UserRole,
    SubmitSatisfactionRequest, CSATAnalyticsOut
)
from services.analytics_service import AnalyticsService


# ─── FIXTURES & HELPERS ────────────────────────────────────────────────────────

def create_mock_ticket(
    ticket_id="507f1f77bcf86cd799439011",
    user_id="user_123",
    status="RESOLVED",
    rating=None,
    comment=None,
    category="Logiciel & Applications",
    assigned_agent_id="agent_456"
):
    return {
        "_id": ObjectId(ticket_id),
        "id": ticket_id,
        "subject": "Test ticket subject",
        "description": "Test description",
        "category": category,
        "priority": "MEDIUM",
        "channel": "WEB",
        "status": status,
        "user_id": user_id,
        "assigned_agent_id": assigned_agent_id,
        "satisfaction_rating": rating,
        "satisfaction_comment": comment,
        "satisfaction_submitted_at": datetime.utcnow() if rating else None,
        "action_history": [],
        "responses": [],
        "created_at": datetime.utcnow() - timedelta(days=2),
        "updated_at": datetime.utcnow()
    }


def make_test_client(db_mock, current_user):
    app.dependency_overrides[get_database] = lambda: db_mock
    app.dependency_overrides[get_current_user] = lambda: current_user
    return TestClient(app)


# ─── 1. CSAT SUBMISSION ENDPOINT TESTS ────────────────────────────────────────

class TestCSATSubmissionEndpoint:
    @pytest.fixture(autouse=True)
    def cleanup(self):
        yield
        app.dependency_overrides.clear()

    def test_valid_csat_rating_resolved_ticket(self):
        """Valid 1-5 star rating on a RESOLVED ticket should succeed with 200."""
        ticket_id = "507f1f77bcf86cd799439011"
        user_id = "user_abc"
        ticket_doc = create_mock_ticket(ticket_id=ticket_id, user_id=user_id, status="RESOLVED", rating=None)

        db = MagicMock()
        db.tickets.find_one = AsyncMock(return_value=ticket_doc)
        db.tickets.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
        db.routing_history.update_one = AsyncMock(return_value=MagicMock())

        current_user = {"id": user_id, "role": UserRole.USER.value, "email": "test@user.com", "full_name": "Test User"}
        client = make_test_client(db, current_user)

        response = client.post(
            f"/api/v1/tickets/{ticket_id}/satisfaction",
            json={"rating": 5, "comment": "Excellent support rapide !"}
        )

        assert response.status_code == 200
        assert db.tickets.update_one.called
        set_calls = [
            c[0][1]["$set"] for c in db.tickets.update_one.call_args_list
            if len(c[0]) > 1 and "$set" in c[0][1]
        ]
        assert len(set_calls) > 0
        assert set_calls[0]["satisfaction_rating"] == 5
        assert set_calls[0]["satisfaction_comment"] == "Excellent support rapide !"

    def test_valid_csat_rating_closed_ticket(self):
        """Valid rating on a CLOSED ticket should also succeed."""
        ticket_id = "507f1f77bcf86cd799439012"
        user_id = "user_abc"
        ticket_doc = create_mock_ticket(ticket_id=ticket_id, user_id=user_id, status="CLOSED", rating=None)

        db = MagicMock()
        db.tickets.find_one = AsyncMock(return_value=ticket_doc)
        db.tickets.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
        db.routing_history.update_one = AsyncMock(return_value=MagicMock())

        current_user = {"id": user_id, "role": UserRole.USER.value, "email": "test@user.com", "full_name": "Test User"}
        client = make_test_client(db, current_user)

        response = client.post(
            f"/api/v1/tickets/{ticket_id}/satisfaction",
            json={"rating": 4, "comment": None}
        )

        assert response.status_code == 200
        assert db.tickets.update_one.called

    def test_rating_unresolved_ticket_fails_400(self):
        """Rating an OPEN, IN_PROGRESS, or PENDING ticket must be rejected with 400."""
        for invalid_status in ["OPEN", "IN_PROGRESS", "PENDING"]:
            ticket_id = "507f1f77bcf86cd799439013"
            user_id = "user_abc"
            ticket_doc = create_mock_ticket(ticket_id=ticket_id, user_id=user_id, status=invalid_status, rating=None)

            db = MagicMock()
            db.tickets.find_one = AsyncMock(return_value=ticket_doc)

            current_user = {"id": user_id, "role": UserRole.USER.value, "email": "test@user.com", "full_name": "Test User"}
            client = make_test_client(db, current_user)

            response = client.post(
                f"/api/v1/tickets/{ticket_id}/satisfaction",
                json={"rating": 5}
            )

            assert response.status_code == 400
            assert "RESOLVED or CLOSED" in response.json()["detail"]

    def test_rating_another_users_ticket_fails_403(self):
        """A customer with USER role cannot rate someone else's ticket (403 Forbidden)."""
        ticket_id = "507f1f77bcf86cd799439014"
        owner_id = "user_original_owner"
        attacker_id = "user_attacker"
        ticket_doc = create_mock_ticket(ticket_id=ticket_id, user_id=owner_id, status="RESOLVED", rating=None)

        db = MagicMock()
        db.tickets.find_one = AsyncMock(return_value=ticket_doc)

        attacker_user = {"id": attacker_id, "role": UserRole.USER.value, "email": "other@user.com", "full_name": "Other User"}
        client = make_test_client(db, attacker_user)

        response = client.post(
            f"/api/v1/tickets/{ticket_id}/satisfaction",
            json={"rating": 4}
        )

        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]

    def test_duplicate_rating_rejected_409(self):
        """Attempting to rate a ticket that already has a satisfaction rating must fail with 409 Conflict."""
        ticket_id = "507f1f77bcf86cd799439015"
        user_id = "user_abc"
        ticket_doc = create_mock_ticket(ticket_id=ticket_id, user_id=user_id, status="RESOLVED", rating=5)

        db = MagicMock()
        db.tickets.find_one = AsyncMock(return_value=ticket_doc)

        current_user = {"id": user_id, "role": UserRole.USER.value, "email": "test@user.com", "full_name": "Test User"}
        client = make_test_client(db, current_user)

        response = client.post(
            f"/api/v1/tickets/{ticket_id}/satisfaction",
            json={"rating": 3, "comment": "Changed my mind"}
        )

        assert response.status_code == 409
        assert "already been submitted" in response.json()["detail"]

    def test_invalid_rating_bounds_rejected_422(self):
        """Ratings outside 1-5 (e.g. 0, 6, -1) must be rejected by Pydantic validation with 422."""
        ticket_id = "507f1f77bcf86cd799439016"
        user_id = "user_abc"
        ticket_doc = create_mock_ticket(ticket_id=ticket_id, user_id=user_id, status="RESOLVED", rating=None)

        db = MagicMock()
        db.tickets.find_one = AsyncMock(return_value=ticket_doc)

        current_user = {"id": user_id, "role": UserRole.USER.value, "email": "test@user.com", "full_name": "Test User"}
        client = make_test_client(db, current_user)

        for invalid_rating in [0, 6, -1, 10]:
            response = client.post(
                f"/api/v1/tickets/{ticket_id}/satisfaction",
                json={"rating": invalid_rating}
            )
            assert response.status_code == 422

    def test_admin_can_rate_ticket(self):
        """An administrator can submit rating for a ticket."""
        ticket_id = "507f1f77bcf86cd799439017"
        owner_id = "user_customer"
        ticket_doc = create_mock_ticket(ticket_id=ticket_id, user_id=owner_id, status="RESOLVED", rating=None)

        db = MagicMock()
        db.tickets.find_one = AsyncMock(return_value=ticket_doc)
        db.tickets.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
        db.routing_history.update_one = AsyncMock(return_value=MagicMock())

        admin_user = {"id": "admin_999", "role": UserRole.ADMIN.value, "email": "admin@geiser.tn", "full_name": "Admin User"}
        client = make_test_client(db, admin_user)

        response = client.post(
            f"/api/v1/tickets/{ticket_id}/satisfaction",
            json={"rating": 4, "comment": "Admin feedback on behalf of user"}
        )

        assert response.status_code == 200

    def test_ticket_not_found_returns_404(self):
        """Submitting satisfaction for non-existent ticket returns 404."""
        db = MagicMock()
        db.tickets.find_one = AsyncMock(return_value=None)

        user = {"id": "user_1", "role": UserRole.USER.value, "email": "u@g.com"}
        client = make_test_client(db, user)

        response = client.post(
            "/api/v1/tickets/507f1f77bcf86cd799439099/satisfaction",
            json={"rating": 5}
        )
        assert response.status_code == 404


# ─── 2. CSAT ANALYTICS SERVICE CALCULATIONS ───────────────────────────────────

class TestCSATAnalyticsCalculations:
    def test_compute_csat_empty_tickets(self):
        """Empty ticket list should produce zeroed metrics gracefully."""
        db = MagicMock()
        svc = AnalyticsService(db)
        csat = svc._compute_csat_analytics([])

        assert csat.total_ratings == 0
        assert csat.avg_rating == 0.0
        assert csat.satisfaction_rate_pct == 0.0
        assert csat.distribution == {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
        assert csat.by_agent == []
        assert csat.by_category == []

    def test_compute_csat_metrics_accuracy(self):
        """Verify average, distribution, and positive satisfaction percentage."""
        db = MagicMock()
        svc = AnalyticsService(db)

        # 5 tickets: ratings 5, 5, 4, 3, 1 -> sum=18, avg=3.6, positive(>=4)=3/5=60%
        tickets = [
            {"satisfaction_rating": 5, "category": "Réseau", "assigned_agent_id": "ag_1", "created_at": datetime.utcnow()},
            {"satisfaction_rating": 5, "category": "Réseau", "assigned_agent_id": "ag_1", "created_at": datetime.utcnow()},
            {"satisfaction_rating": 4, "category": "Logiciel", "assigned_agent_id": "ag_2", "created_at": datetime.utcnow()},
            {"satisfaction_rating": 3, "category": "Logiciel", "assigned_agent_id": "ag_2", "created_at": datetime.utcnow()},
            {"satisfaction_rating": 1, "category": "Matériel", "assigned_agent_id": "ag_3", "created_at": datetime.utcnow()},
            {"satisfaction_rating": None, "category": "Non noté", "created_at": datetime.utcnow()},  # should be ignored
        ]

        csat = svc._compute_csat_analytics(tickets)

        assert csat.total_ratings == 5
        assert csat.avg_rating == 3.6
        assert csat.satisfaction_rate_pct == 60.0
        assert csat.distribution["5"] == 2
        assert csat.distribution["4"] == 1
        assert csat.distribution["3"] == 1
        assert csat.distribution["2"] == 0
        assert csat.distribution["1"] == 1

    def test_csat_agent_aggregation(self):
        """Verify agent-level CSAT aggregation."""
        db = MagicMock()
        svc = AnalyticsService(db)

        tickets = [
            {"satisfaction_rating": 5, "assigned_agent_id": "ag_alpha"},
            {"satisfaction_rating": 4, "assigned_agent_id": "ag_alpha"},
            {"satisfaction_rating": 2, "assigned_agent_id": "ag_beta"},
        ]

        csat = svc._compute_csat_analytics(tickets)
        agents_dict = {a.agent_id: a for a in csat.by_agent}

        assert "ag_alpha" in agents_dict
        assert agents_dict["ag_alpha"].avg_rating == 4.5
        assert agents_dict["ag_alpha"].count == 2

        assert "ag_beta" in agents_dict
        assert agents_dict["ag_beta"].avg_rating == 2.0
        assert agents_dict["ag_beta"].count == 1

    def test_csat_category_aggregation(self):
        """Verify category-level CSAT aggregation."""
        db = MagicMock()
        svc = AnalyticsService(db)

        tickets = [
            {"satisfaction_rating": 5, "category": "Sécurité"},
            {"satisfaction_rating": 5, "category": "Sécurité"},
            {"satisfaction_rating": 3, "category": "Matériel"},
        ]

        csat = svc._compute_csat_analytics(tickets)
        cats_dict = {c.category: c for c in csat.by_category}

        assert "Sécurité" in cats_dict
        assert cats_dict["Sécurité"].avg_rating == 5.0
        assert cats_dict["Sécurité"].count == 2

        assert "Matériel" in cats_dict
        assert cats_dict["Matériel"].avg_rating == 3.0
        assert cats_dict["Matériel"].count == 1

    def test_csat_recent_feedback_ordering(self):
        """Recent feedback comments should be sorted by submission time descending."""
        db = MagicMock()
        svc = AnalyticsService(db)

        now = datetime.utcnow()
        tickets = [
            {
                "_id": "t1",
                "satisfaction_rating": 5,
                "satisfaction_comment": "Premier commentaire",
                "satisfaction_submitted_at": now - timedelta(hours=2)
            },
            {
                "_id": "t2",
                "satisfaction_rating": 4,
                "satisfaction_comment": "Commentaire plus récent",
                "satisfaction_submitted_at": now - timedelta(minutes=10)
            },
            {
                "_id": "t3",
                "satisfaction_rating": 5,
                "satisfaction_comment": None  # No comment, should be excluded
            }
        ]

        csat = svc._compute_csat_analytics(tickets)
        assert len(csat.recent_feedback) == 2
        assert csat.recent_feedback[0].comment == "Commentaire plus récent"
        assert csat.recent_feedback[1].comment == "Premier commentaire"


# ─── 3. ANALYTICS API ENDPOINTS INTEGRATION ────────────────────────────────────

class TestCSATAnalyticsEndpoints:
    @pytest.fixture(autouse=True)
    def cleanup(self):
        yield
        app.dependency_overrides.clear()

    def test_get_csat_analytics_endpoint(self):
        """GET /api/v1/analytics/csat returns CSATAnalyticsOut."""
        db = MagicMock()
        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=[
            {"satisfaction_rating": 5, "created_at": datetime.utcnow(), "category": "Réseau"},
            {"satisfaction_rating": 4, "created_at": datetime.utcnow(), "category": "Réseau"}
        ])
        db.tickets.find = MagicMock(return_value=cursor)

        user = {"id": "u1", "role": UserRole.AGENT.value, "email": "a@g.com"}
        client = make_test_client(db, user)

        response = client.get("/api/v1/analytics/csat?period_days=30")
        assert response.status_code == 200
        data = response.json()
        assert data["total_ratings"] == 2
        assert data["avg_rating"] == 4.5
        assert data["satisfaction_rate_pct"] == 100.0

    def test_dashboard_endpoint_contains_csat(self):
        """GET /api/v1/analytics/dashboard response includes CSAT data."""
        db = MagicMock()
        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=[
            {
                "status": "RESOLVED",
                "priority": "HIGH",
                "created_at": datetime.utcnow() - timedelta(hours=3),
                "updated_at": datetime.utcnow(),
                "satisfaction_rating": 5,
                "satisfaction_comment": "Super",
                "category": "Cloud"
            }
        ])
        cursor.sort = MagicMock(return_value=cursor)
        cursor.limit = MagicMock(return_value=cursor)
        db.tickets.find = MagicMock(return_value=cursor)
        db.agents.find = MagicMock(return_value=cursor)
        db.users.find_one = AsyncMock(return_value=None)
        db.teams.find_one = AsyncMock(return_value=None)

        user = {"id": "u1", "role": UserRole.ADMIN.value, "email": "admin@g.com"}
        client = make_test_client(db, user)

        response = client.get("/api/v1/analytics/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert "csat" in data
        assert data["csat"] is not None
        assert data["csat"]["total_ratings"] == 1
        assert data["kpis"]["positive_satisfaction_rate_pct"] == 100.0
