"""Regression tests for ticket update authorization and ticket scope."""

from copy import deepcopy
from datetime import datetime

import pytest
from bson import ObjectId
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

from database.mongodb import get_database
from routes.tickets import router as tickets_router, update_status, update_ticket
from schemas.schemas import StatusUpdateRequest, TicketUpdate, UserRole


class FakeCursor:
    def __init__(self, docs):
        self.docs = docs

    async def to_list(self, length=None):
        return self.docs[:length] if length is not None else self.docs


class FakeCollection:
    def __init__(self, docs=()):
        self.docs = [deepcopy(doc) for doc in docs]

    async def find_one(self, query):
        for doc in self.docs:
            if all(str(doc.get(key)) == str(value) for key, value in query.items()):
                return deepcopy(doc)
        return None

    def find(self, query=None):
        query = query or {}
        found = []
        for doc in self.docs:
            matches = True
            for key, value in query.items():
                doc_value = doc.get(key)
                if isinstance(doc_value, list) and isinstance(value, str):
                    matches = value in doc_value
                else:
                    matches = str(doc_value) == str(value)
                if not matches:
                    break
            if matches:
                found.append(deepcopy(doc))
        return FakeCursor(found)

    async def update_one(self, query, update):
        for doc in self.docs:
            if all(str(doc.get(key)) == str(value) for key, value in query.items()):
                doc.update(deepcopy(update.get("$set", {})))
                return


class FakeDB:
    def __init__(self, ticket):
        self.tickets = FakeCollection([ticket])
        self.agents = FakeCollection()
        self.teams = FakeCollection()
        self.users = FakeCollection()
        self.routing_history = FakeCollection()
        self.sla_policies = FakeCollection()
        self.sla_alerts = FakeCollection()
        self.audit_logs = FakeCollection()


def make_ticket(owner_id, status="OPEN"):
    now = datetime(2026, 10, 11)
    return {
        "_id": ObjectId(),
        "subject": "Cannot connect to VPN",
        "description": "VPN connection fails after login.",
        "category": "Infrastructure & Réseau",
        "subcategory": "VPN & Accès Distant",
        "priority": "MEDIUM",
        "status": status,
        "channel": "WEB",
        "user_id": str(owner_id),
        "assigned_agent_id": None,
        "attachments": [],
        "keywords": [],
        "responses": [],
        "action_history": [],
        "created_at": now,
        "updated_at": now,
    }


def make_setup():
    owner_id, other_id = str(ObjectId()), str(ObjectId())
    ticket = make_ticket(owner_id)
    return FakeDB(ticket), ticket, {
        "id": owner_id, "role": UserRole.USER.value, "email": "owner@example.test"
    }, owner_id, other_id


@pytest.fixture(autouse=True)
def suppress_external_side_effects(monkeypatch):
    """Keep route tests isolated from email, notification, and audit services."""
    monkeypatch.setattr(
        "services.ticket_service.TicketService.record_ticket_action", AsyncMock()
    )
    monkeypatch.setattr(
        "services.notification_service.NotificationService.notify_status_changed",
        AsyncMock(),
    )
    monkeypatch.setattr("services.audit_service.AuditService.log_event", AsyncMock())


def test_missing_bearer_token_is_unauthorized():
    app = FastAPI()
    app.include_router(tickets_router, prefix="/tickets")
    app.dependency_overrides[get_database] = lambda: FakeDB(make_ticket(str(ObjectId())))

    with TestClient(app) as client:
        response = client.put(f"/tickets/{ObjectId()}", json={"subject": "Changed"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_user_can_update_own_subject_and_description():
    db, ticket, user, *_ = make_setup()
    result = await update_ticket(str(ticket["_id"]), TicketUpdate(
        subject="VPN access restored", description="Only my laptop is affected."
    ), user, db)
    assert result["subject"] == "VPN access restored"
    assert result["description"] == "Only my laptop is affected."


@pytest.mark.asyncio
async def test_user_cannot_update_another_users_ticket():
    db, ticket, user, _, other_id = make_setup()
    db.tickets.docs[0]["user_id"] = other_id
    with pytest.raises(HTTPException) as exc:
        await update_ticket(str(ticket["_id"]), TicketUpdate(subject="Changed"), user, db)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Ticket not found"


@pytest.mark.parametrize("payload", [
    {"status": "RESOLVED"},
    {"priority": "URGENT"},
    {"assigned_agent_id": str(ObjectId())},
    {"category": "Sécurité IT"},
    {"resolution_note": "Internal note"},
])
@pytest.mark.asyncio
async def test_user_cannot_escalate_ticket_fields(payload):
    db, ticket, user, *_ = make_setup()
    original = deepcopy(db.tickets.docs[0])
    with pytest.raises(HTTPException) as exc:
        await update_ticket(str(ticket["_id"]), TicketUpdate(**payload), user, db)
    assert exc.value.status_code == 403
    assert db.tickets.docs[0] == original


@pytest.mark.asyncio
async def test_agent_cannot_update_ticket_outside_assignment_scope():
    db, ticket, *_ = make_setup()
    agent_user_id = str(ObjectId())
    db.agents = FakeCollection([{"_id": ObjectId(), "user_id": agent_user_id}])
    agent = {"id": agent_user_id, "role": UserRole.AGENT.value}
    with pytest.raises(HTTPException) as exc:
        await update_ticket(str(ticket["_id"]), TicketUpdate(subject="Changed"), agent, db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_assigned_agent_can_update_ticket_in_scope():
    db, ticket, *_ = make_setup()
    agent_user_id, agent_id = str(ObjectId()), ObjectId()
    db.agents = FakeCollection([{"_id": agent_id, "user_id": agent_user_id}])
    db.tickets.docs[0]["assigned_agent_id"] = str(agent_id)
    agent = {"id": agent_user_id, "role": UserRole.AGENT.value}
    result = await update_ticket(str(ticket["_id"]), TicketUpdate(status="IN_PROGRESS"), agent, db)
    assert result["status"] == "IN_PROGRESS"


@pytest.mark.asyncio
async def test_team_agent_can_update_ticket_in_team_scope():
    db, ticket, *_ = make_setup()
    agent_user_id, agent_id, team_id = str(ObjectId()), ObjectId(), ObjectId()
    db.agents = FakeCollection([{"_id": agent_id, "user_id": agent_user_id}])
    db.teams = FakeCollection([{"_id": team_id, "agent_ids": [str(agent_id)]}])
    db.tickets.docs[0]["assigned_team_id"] = str(team_id)
    agent = {"id": agent_user_id, "role": UserRole.AGENT.value}

    result = await update_ticket(
        str(ticket["_id"]), TicketUpdate(subject="Team scoped update"), agent, db
    )

    assert result["subject"] == "Team scoped update"


@pytest.mark.parametrize("payload", [
    {"priority": "URGENT"},
    {"impact": "HIGH"},
    {"urgency": "HIGH"},
])
@pytest.mark.asyncio
async def test_agent_cannot_override_priority_inputs(payload):
    db, ticket, *_ = make_setup()
    agent_user_id, agent_id = str(ObjectId()), ObjectId()
    db.agents = FakeCollection([{"_id": agent_id, "user_id": agent_user_id}])
    db.tickets.docs[0]["assigned_agent_id"] = str(agent_id)
    agent = {"id": agent_user_id, "role": UserRole.AGENT.value}
    original = deepcopy(db.tickets.docs[0])

    with pytest.raises(HTTPException) as exc:
        await update_ticket(str(ticket["_id"]), TicketUpdate(**payload), agent, db)

    assert exc.value.status_code == 403
    assert db.tickets.docs[0] == original


@pytest.mark.asyncio
async def test_agent_cannot_close_ticket():
    db, ticket, *_ = make_setup()
    agent_user_id, agent_id = str(ObjectId()), ObjectId()
    db.agents = FakeCollection([{"_id": agent_id, "user_id": agent_user_id}])
    db.tickets.docs[0]["assigned_agent_id"] = str(agent_id)
    db.tickets.docs[0]["status"] = "RESOLVED"
    agent = {"id": agent_user_id, "role": UserRole.AGENT.value}

    with pytest.raises(HTTPException) as exc:
        await update_ticket(str(ticket["_id"]), TicketUpdate(status="CLOSED"), agent, db)

    assert exc.value.status_code == 403
    assert db.tickets.docs[0]["status"] == "RESOLVED"


@pytest.mark.asyncio
async def test_agent_cannot_close_ticket_through_status_endpoint():
    db, ticket, *_ = make_setup()
    agent_user_id, agent_id = str(ObjectId()), ObjectId()
    db.agents = FakeCollection([{"_id": agent_id, "user_id": agent_user_id}])
    db.tickets.docs[0]["assigned_agent_id"] = str(agent_id)
    db.tickets.docs[0]["status"] = "RESOLVED"
    agent = {"id": agent_user_id, "role": UserRole.AGENT.value}

    with pytest.raises(HTTPException) as exc:
        await update_status(
            str(ticket["_id"]), StatusUpdateRequest(status="CLOSED"), agent, db
        )

    assert exc.value.status_code == 403
    assert db.tickets.docs[0]["status"] == "RESOLVED"


@pytest.mark.parametrize("role", [UserRole.SUPERVISOR, UserRole.ADMIN])
@pytest.mark.asyncio
async def test_supervisor_and_admin_can_update_privileged_fields(role):
    db, ticket, *_ = make_setup()
    user = {"id": str(ObjectId()), "role": role.value}
    result = await update_ticket(str(ticket["_id"]), TicketUpdate(routing_reason="Reviewed"), user, db)
    assert result["routing_reason"] == "Reviewed"


@pytest.mark.parametrize("role", [UserRole.SUPERVISOR, UserRole.ADMIN])
@pytest.mark.asyncio
async def test_supervisor_and_admin_can_close_resolved_ticket(role):
    db, ticket, *_ = make_setup()
    db.tickets.docs[0]["status"] = "RESOLVED"
    user = {"id": str(ObjectId()), "role": role.value}

    result = await update_ticket(
        str(ticket["_id"]), TicketUpdate(status="CLOSED"), user, db
    )

    assert result["status"] == "CLOSED"


@pytest.mark.asyncio
async def test_invalid_status_transition_is_rejected():
    db, ticket, *_ = make_setup()
    supervisor = {"id": str(ObjectId()), "role": UserRole.SUPERVISOR.value}
    with pytest.raises(HTTPException) as exc:
        await update_ticket(str(ticket["_id"]), TicketUpdate(status="CLOSED"), supervisor, db)
    assert exc.value.status_code == 400
    assert db.tickets.docs[0]["status"] == "OPEN"


@pytest.mark.asyncio
async def test_unknown_ticket_id_returns_404():
    db, _, user, *_ = make_setup()
    with pytest.raises(HTTPException) as exc:
        await update_ticket(str(ObjectId()), TicketUpdate(subject="Changed"), user, db)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Ticket not found"


@pytest.mark.asyncio
async def test_assignment_is_not_available_through_general_update():
    db, ticket, *_ = make_setup()
    supervisor = {"id": str(ObjectId()), "role": UserRole.SUPERVISOR.value}
    with pytest.raises(HTTPException) as exc:
        await update_ticket(str(ticket["_id"]), TicketUpdate(assigned_agent_id=str(ObjectId())), supervisor, db)
    assert exc.value.status_code == 403
