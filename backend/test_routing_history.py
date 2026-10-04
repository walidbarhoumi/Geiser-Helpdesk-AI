"""
test_routing_history.py
=======================
STEP 2 — Apprentissage du routage historique
Tests de validation de bout en bout.

Toutes les interactions MongoDB sont simulées via unittest.mock (MagicMock / AsyncMock)
afin que les tests puissent s'exécuter sans base de données active.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime
from bson import ObjectId


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def make_agent(agent_id: str = None, workload: int = 2, skills: list = None):
    oid = ObjectId(agent_id) if agent_id else ObjectId()
    return {
        "_id": oid,
        "user_id": f"agent_{str(oid)[:6]}",
        "skills": skills or ["réseau", "hardware"],
        "workload": workload,
        "is_available": True,
    }


def make_ticket(ticket_id: str = None, category: str = "réseau", status: str = "OPEN",
                assigned_agent_id: str = None, sla_status: str = "ON_TRACK"):
    oid = ObjectId(ticket_id) if ticket_id else ObjectId()
    return {
        "_id": oid,
        "id": str(oid),
        "subject": "Problème réseau",
        "description": "Le réseau ne fonctionne pas",
        "category": category,
        "subcategory": "LAN",
        "priority": "HIGH",
        "impact": "HIGH",
        "urgency": "HIGH",
        "status": status,
        "user_id": str(ObjectId()),
        "assigned_agent_id": assigned_agent_id,
        "sla_status": sla_status,
        "sla_applied_rule": "HIGH_SLA",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }


def make_db_mock():
    """Crée un mock complet de la base de données Motor."""
    db = MagicMock()

    for collection in ["tickets", "agents", "teams", "routing_history",
                        "users", "password_resets", "token_blacklist"]:
        col = MagicMock()
        col.find_one = AsyncMock(return_value=None)
        col.find = MagicMock(return_value=MagicMock(
            to_list=AsyncMock(return_value=[]),
            sort=MagicMock(return_value=MagicMock(
                limit=MagicMock(return_value=MagicMock(
                    to_list=AsyncMock(return_value=[])
                ))
            ))
        ))
        col.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))
        col.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
        col.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))
        col.create_index = AsyncMock()
        setattr(db, collection, col)

    return db


# ─────────────────────────────────────────────────────────────────
# TEST 1 — L'assignation automatique lors de la création de ticket
#           enregistre un document routing_history
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_ticket_auto_assign_writes_routing_history():
    """
    Lors de la création d'un ticket avec assignation automatique,
    _record_routing_history() doit être appelé avec routing_method='automatic'.
    """
    from services.ticket_service import TicketService

    db = make_db_mock()
    agent = make_agent(workload=1, skills=["réseau"])
    ticket_id = ObjectId()

    # L'agent est disponible pour l'assignation automatique
    db.agents.find.return_value = MagicMock(
        sort=MagicMock(return_value=MagicMock(
            limit=MagicMock(return_value=MagicMock(
                to_list=AsyncMock(return_value=[agent])
            ))
        ))
    )
    db.tickets.insert_one.return_value = MagicMock(inserted_id=ticket_id)

    # SLA service mock
    sla_mock = AsyncMock()
    sla_mock.calculate_ticket_sla = AsyncMock(return_value={
        "resolution_deadline": datetime.utcnow(),
        "response_deadline": datetime.utcnow(),
        "applied_rule": "HIGH_SLA"
    })

    service = TicketService(db)
    # Patch SLAService pour éviter les appels DB réels
    with patch("services.ticket_service.SLAService", return_value=sla_mock):
        with patch("services.ticket_service.TicketService._record_routing_history",
                   new_callable=AsyncMock) as mock_record:
            ticket_in = MagicMock()
            ticket_in.dict.return_value = {
                "subject": "Réseau KO",
                "description": "LAN down",
                "category": "réseau",
                "subcategory": "LAN",
                "priority": "HIGH",
                "impact": None,
                "urgency": None,
                "attachments": [],
                "keywords": [],
            }
            ticket_in.category = "réseau"
            ticket_in.priority = MagicMock(value="HIGH")
            ticket_in.impact = None
            ticket_in.urgency = None

            await service.create_ticket(ticket_in, user_id=str(ObjectId()))

            # Vérifie que routing_history a été enregistré
            mock_record.assert_called_once()
            call_kwargs = mock_record.call_args
            assert call_kwargs.kwargs.get("routing_method") == "automatic", \
                f"routing_method attendu 'automatic', obtenu: {call_kwargs.kwargs.get('routing_method')}"


# ─────────────────────────────────────────────────────────────────
# TEST 2 — _record_routing_history() insère le bon document
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_record_routing_history_inserts_correct_document():
    """
    _record_routing_history() doit insérer un document routing_history
    avec tous les champs obligatoires et les valeurs d'initialisation correctes.
    """
    from services.ticket_service import TicketService

    db = make_db_mock()
    service = TicketService(db)

    agent = make_agent(workload=3)
    ticket = make_ticket()
    ticket["id"] = str(ticket["_id"])

    await service._record_routing_history(ticket=ticket, agent=agent, routing_method="automatic")

    db.routing_history.insert_one.assert_called_once()
    inserted = db.routing_history.insert_one.call_args[0][0]

    # Champs obligatoires
    assert inserted["ticket_id"] == ticket["id"]
    assert inserted["assigned_agent_id"] == str(agent["_id"])
    assert inserted["routing_method"] == "automatic"
    assert inserted["category"] == ticket["category"]
    assert inserted["subcategory"] == ticket["subcategory"]
    assert inserted["priority"] == ticket["priority"]
    assert inserted["sla_applied_rule"] == ticket["sla_applied_rule"]
    assert inserted["agent_workload_at_assignment"] == agent["workload"]

    # Champs de résultat initialisés à None / False
    assert inserted["outcome_resolved_at"] is None
    assert inserted["outcome_sla_respected"] is None
    assert inserted["outcome_csat_score"] is None
    assert inserted["outcome_reassigned"] is False
    assert inserted["outcome_reassignment_count"] == 0

    # Pas de données sensibles
    assert "password" not in inserted
    assert "hashed_password" not in inserted
    assert "token" not in inserted
    assert "secret" not in inserted


# ─────────────────────────────────────────────────────────────────
# TEST 3 — assign_agent() écrit routing_history avec routing_method='manual'
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_assign_agent_manual_writes_routing_history():
    """
    La première assignation manuelle d'un agent doit créer un enregistrement
    routing_history avec routing_method='manual'.
    """
    from services.ticket_service import TicketService

    db = make_db_mock()
    service = TicketService(db)

    agent = make_agent()
    ticket = make_ticket(assigned_agent_id=None)
    ticket_id = str(ticket["_id"])
    ticket["id"] = ticket_id

    db.agents.find_one.return_value = agent
    db.tickets.find_one.return_value = ticket

    # get_ticket doit retourner le ticket formaté
    with patch.object(service, "get_ticket", new_callable=AsyncMock, return_value=ticket):
        with patch.object(service, "_record_routing_history", new_callable=AsyncMock) as mock_record:
            with patch.object(service, "record_ticket_action", new_callable=AsyncMock):
                await service.assign_agent(ticket_id=ticket_id, agent_id=str(agent["_id"]))

            mock_record.assert_called_once()
            call_kwargs = mock_record.call_args.kwargs
            assert call_kwargs["routing_method"] == "manual"
            assert call_kwargs["prior_record_id"] is None


# ─────────────────────────────────────────────────────────────────
# TEST 4 — Réassignation : nouveau enregistrement + marquage de l'ancien
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reassignment_marks_prior_record_and_creates_new():
    """
    Lors d'une réassignation (changement d'agent), l'ancien enregistrement
    routing_history doit être marqué outcome_reassigned=True et un nouveau
    enregistrement doit être créé avec routing_method='reassignment'.
    """
    from services.ticket_service import TicketService

    db = make_db_mock()
    service = TicketService(db)

    old_agent = make_agent(workload=5)
    new_agent = make_agent(workload=1)
    ticket = make_ticket(assigned_agent_id=str(old_agent["_id"]))
    ticket_id = str(ticket["_id"])
    ticket["id"] = ticket_id

    db.agents.find_one.return_value = new_agent
    db.tickets.find_one.return_value = ticket

    with patch.object(service, "get_ticket", new_callable=AsyncMock, return_value=ticket):
        with patch.object(service, "_record_routing_history", new_callable=AsyncMock) as mock_record:
            with patch.object(service, "record_ticket_action", new_callable=AsyncMock):
                await service.assign_agent(
                    ticket_id=ticket_id,
                    agent_id=str(new_agent["_id"])
                )

            mock_record.assert_called_once()
            call_kwargs = mock_record.call_args.kwargs
            assert call_kwargs["routing_method"] == "reassignment"
            # prior_record_id doit être le ticket_id pour déclencher le marquage
            assert call_kwargs["prior_record_id"] == ticket_id


@pytest.mark.asyncio
async def test_record_routing_history_marks_prior_record():
    """
    Quand prior_record_id est fourni, _record_routing_history() doit mettre à jour
    l'ancien enregistrement (outcome_reassigned=True, outcome_reassignment_count++).
    """
    from services.ticket_service import TicketService

    db = make_db_mock()
    service = TicketService(db)

    agent = make_agent()
    ticket = make_ticket()
    ticket["id"] = str(ticket["_id"])

    await service._record_routing_history(
        ticket=ticket,
        agent=agent,
        routing_method="reassignment",
        prior_record_id=ticket["id"]
    )

    # update_one doit avoir été appelé pour marquer l'ancien enregistrement
    update_calls = db.routing_history.update_one.call_args_list
    # Premier appel = marquer l'ancien, deuxième appel n'existe pas
    # (insert_one crée le nouveau)
    assert len(update_calls) >= 1
    first_call_filter = update_calls[0][0][0]
    assert first_call_filter.get("outcome_reassigned") is False

    # insert_one crée le nouveau enregistrement
    db.routing_history.insert_one.assert_called_once()
    new_record = db.routing_history.insert_one.call_args[0][0]
    assert new_record["routing_method"] == "reassignment"
    assert new_record["outcome_reassigned"] is False  # le nouveau commence à False


# ─────────────────────────────────────────────────────────────────
# TEST 5 — update_status(RESOLVED) met à jour outcome_resolved_at
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_resolve_ticket_updates_routing_history_outcome():
    """
    Lorsqu'un ticket passe au statut RESOLVED via update_status(),
    routing_history doit être mis à jour avec outcome_resolved_at et
    outcome_sla_respected.
    """
    from services.ticket_service import TicketService
    from schemas.schemas import TicketStatus

    db = make_db_mock()
    service = TicketService(db)

    ticket = make_ticket(status="IN_PROGRESS", sla_status="ON_TRACK")
    ticket_id = str(ticket["_id"])
    ticket["id"] = ticket_id
    db.tickets.find_one.return_value = ticket

    resolved_ticket = {**ticket, "status": "RESOLVED", "sla_status": "ON_TRACK", "id": ticket_id}

    sla_mock = AsyncMock()
    sla_mock.compute_sla_status = AsyncMock(return_value=MagicMock(value="ON_TRACK"))

    with patch("services.ticket_service.SLAService", return_value=sla_mock):
        with patch.object(service, "get_ticket", new_callable=AsyncMock, return_value=resolved_ticket):
            with patch.object(service, "record_ticket_action", new_callable=AsyncMock):
                await service.update_status(ticket_id, TicketStatus.RESOLVED)

    # Vérifie que routing_history.update_one a été appelé avec outcome_resolved_at
    update_calls = db.routing_history.update_one.call_args_list
    assert len(update_calls) >= 1

    last_call = update_calls[-1]
    query_filter = last_call[0][0]
    update_doc = last_call[0][1]

    assert query_filter.get("ticket_id") == ticket_id
    assert query_filter.get("outcome_resolved_at") is None
    assert "outcome_resolved_at" in update_doc["$set"]
    assert "outcome_sla_respected" in update_doc["$set"]
    # SLA non violée → True
    assert update_doc["$set"]["outcome_sla_respected"] is True


@pytest.mark.asyncio
async def test_resolve_ticket_sla_breached_sets_outcome_false():
    """
    Si le SLA est BREACHED au moment de la résolution,
    outcome_sla_respected doit être False dans routing_history.
    """
    from services.ticket_service import TicketService
    from schemas.schemas import TicketStatus

    db = make_db_mock()
    service = TicketService(db)

    ticket = make_ticket(status="IN_PROGRESS", sla_status="BREACHED")
    ticket_id = str(ticket["_id"])
    ticket["id"] = ticket_id
    db.tickets.find_one.return_value = ticket

    breached_ticket = {**ticket, "status": "RESOLVED", "sla_status": "BREACHED", "id": ticket_id}

    sla_mock = AsyncMock()
    sla_mock.compute_sla_status = AsyncMock(return_value=MagicMock(value="BREACHED"))

    with patch("services.ticket_service.SLAService", return_value=sla_mock):
        with patch.object(service, "get_ticket", new_callable=AsyncMock, return_value=breached_ticket):
            with patch.object(service, "record_ticket_action", new_callable=AsyncMock):
                await service.update_status(ticket_id, TicketStatus.RESOLVED)

    update_calls = db.routing_history.update_one.call_args_list
    last_call = update_calls[-1]
    outcome_sla = last_call[0][1]["$set"]["outcome_sla_respected"]
    assert outcome_sla is False


# ─────────────────────────────────────────────────────────────────
# TEST 6 — Démarrage à froid : agent sans historique obtient le score Bayesian
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cold_start_agent_gets_bayesian_baseline():
    """
    Un agent sans historique de tickets doit obtenir le score Bayesian de référence
    (0.80 par défaut) et non zéro — il reste donc éligible au routage.
    """
    from services.routing_service import RoutingService, DEFAULT_ROUTING_CONFIG

    db = make_db_mock()
    db.tickets.find.return_value = MagicMock(to_list=AsyncMock(return_value=[]))

    service = RoutingService(db)
    stats = await service._compute_agent_historical_stats(
        agent_id=str(ObjectId()),
        category="réseau",
        subcategory="LAN"
    )

    baseline = DEFAULT_ROUTING_CONFIG["bayesian_baseline"]
    assert stats["bayesian_success_score"] == baseline, \
        f"Score attendu {baseline}, obtenu {stats['bayesian_success_score']}"
    assert stats["sample_size"] == 0
    assert stats["is_fallback"] is False


# ─────────────────────────────────────────────────────────────────
# TEST 7 — Agent spécialiste obtient un score historique plus élevé
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_specialist_agent_scores_higher_than_baseline():
    """
    Un agent ayant résolu 10/10 tickets dans la catégorie doit obtenir un score
    historique Bayesian supérieur au score de référence (0.80).
    """
    from services.routing_service import RoutingService, DEFAULT_ROUTING_CONFIG

    db = make_db_mock()
    agent_id = str(ObjectId())
    now = datetime.utcnow()

    # 10 tickets résolus par cet agent
    resolved_tickets = [
        {
            "_id": ObjectId(),
            "assigned_agent_id": agent_id,
            "status": "RESOLVED",
            "category": "réseau",
            "subcategory": "LAN",
            "reassigned_from_agent_ids": [],
            "created_at": now,
            "updated_at": now,
        }
        for _ in range(10)
    ]

    db.tickets.find.return_value = MagicMock(to_list=AsyncMock(return_value=resolved_tickets))

    service = RoutingService(db)
    stats = await service._compute_agent_historical_stats(
        agent_id=agent_id,
        category="réseau",
        subcategory="LAN"
    )

    baseline = DEFAULT_ROUTING_CONFIG["bayesian_baseline"]
    assert stats["bayesian_success_score"] > baseline, \
        f"Un spécialiste avec 10/10 résolus devrait dépasser le baseline {baseline}. Obtenu: {stats['bayesian_success_score']}"
    assert stats["sample_size"] == 10
    assert stats["category_experience_score"] == 1.0  # Saturation atteinte (10 tickets)


# ─────────────────────────────────────────────────────────────────
# TEST 8 — Sécurité : routing_history ne contient pas de données sensibles
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_routing_history_no_sensitive_data():
    """
    Les enregistrements routing_history ne doivent contenir aucune donnée sensible :
    mots de passe, tokens JWT, secrets, clés API, etc.
    """
    from services.ticket_service import TicketService

    db = make_db_mock()
    service = TicketService(db)

    agent = make_agent()
    ticket = make_ticket()
    ticket["id"] = str(ticket["_id"])

    await service._record_routing_history(ticket=ticket, agent=agent, routing_method="automatic")

    inserted = db.routing_history.insert_one.call_args[0][0]

    FORBIDDEN_FIELDS = [
        "password", "hashed_password", "token", "access_token", "refresh_token",
        "secret", "api_key", "private_key", "otp_secret", "two_factor_secret",
        "reset_token", "verification_code"
    ]

    for field in FORBIDDEN_FIELDS:
        assert field not in inserted, \
            f"Champ sensible '{field}' trouvé dans routing_history — VIOLATION DE SÉCURITÉ"


# ─────────────────────────────────────────────────────────────────
# TEST 9 — auto_route_ticket() écrit un enregistrement enrichi
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_auto_route_ticket_writes_enriched_history_record():
    """
    auto_route_ticket() doit insérer un document routing_history contenant
    tous les nouveaux champs : routing_method, category, outcome_*, etc.
    """
    from services.routing_service import RoutingService

    db = make_db_mock()
    agent = make_agent(workload=2)
    team_id = ObjectId()
    ticket = make_ticket()
    ticket_id = str(ticket["_id"])

    db.tickets.find_one.return_value = ticket
    db.teams.find.return_value = MagicMock(to_list=AsyncMock(return_value=[{
        "_id": team_id,
        "name": "Équipe Réseau",
        "competencies": ["réseau", "LAN", "hardware"],
        "agent_ids": [str(agent["_id"])]
    }]))
    db.agents.find.return_value = MagicMock(to_list=AsyncMock(return_value=[agent]))
    db.tickets.find.return_value = MagicMock(to_list=AsyncMock(return_value=[]))

    # Simule l'analyse AI
    ai_mock = MagicMock()
    ai_mock.analyze_ticket = AsyncMock(return_value={"keywords": ["réseau", "LAN"]})

    service = RoutingService(db)
    service.ai_client = ai_mock

    with patch.object(service.tickets, "update_one", new_callable=AsyncMock):
        with patch.object(service.agents, "update_one", new_callable=AsyncMock):
            await service.auto_route_ticket(ticket_id)

    db.routing_history.insert_one.assert_called_once()
    record = db.routing_history.insert_one.call_args[0][0]

    # Champs obligatoires
    assert record["ticket_id"] == ticket_id
    assert "routing_method" in record
    assert record["routing_method"] in ("ai", "fallback", "automatic")
    assert record["category"] == ticket.get("category")
    assert record["subcategory"] == ticket.get("subcategory")
    assert record["priority"] == ticket.get("priority")
    assert "outcome_resolved_at" in record
    assert record["outcome_resolved_at"] is None
    assert "outcome_sla_respected" in record
    assert record["outcome_sla_respected"] is None
    assert "outcome_csat_score" in record
    assert record["outcome_csat_score"] is None
    assert "outcome_reassigned" in record
    assert record["outcome_reassigned"] is False
    assert "assigned_agent_id" in record  # standardisé (plus selected_agent)


# ─────────────────────────────────────────────────────────────────
# TEST 10 — Idempotence : pas de double enregistrement si même agent
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_assign_agent_idempotent_no_routing_history_written():
    """
    Si le ticket est déjà assigné au même agent, assign_agent() doit retourner
    le ticket sans écrire dans routing_history.
    """
    from services.ticket_service import TicketService

    db = make_db_mock()
    service = TicketService(db)

    agent = make_agent()
    ticket = make_ticket(assigned_agent_id=str(agent["_id"]))
    ticket["id"] = str(ticket["_id"])

    db.agents.find_one.return_value = agent

    with patch.object(service, "get_ticket", new_callable=AsyncMock, return_value=ticket):
        with patch.object(service, "_record_routing_history", new_callable=AsyncMock) as mock_record:
            result = await service.assign_agent(
                ticket_id=ticket["id"],
                agent_id=str(agent["_id"])
            )

    # Pas de double enregistrement
    mock_record.assert_not_called()
    assert result is not None


# ─────────────────────────────────────────────────────────────────
# Entrée principale
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
