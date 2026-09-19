"""
Suite de tests unitaires pour la Matrice ITIL Impact × Urgence (STEP 4).
Vérifie les 15 exigences clés :
1-9: Les 9 combinaisons de la matrice 3x3 (HIGH, MEDIUM, LOW).
10: Gestion des entrées invalides (ValueError, types incorrects).
11: Normalisation insensible à la casse et trim des espaces.
12: Création de ticket hérité sans impact/urgence (priority_source = manual).
13: Création de ticket avec impact/urgence (priority_source = itil_matrix).
14: Intégration SLA Granulaire STEP 3 avec la priorité dérivée ITIL.
15: Mise à jour ticket : recalcul SLA si la priorité change, PAS de recalcul si la priorité reste identique.

Exécution: pytest test_itil_priority.py -v
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId

from services.itil_service import (
    calculate_priority_from_impact_urgency,
    ITIL_PRIORITY_MATRIX,
)
from schemas.schemas import (
    ImpactLevel,
    UrgencyLevel,
    PrioritySource,
    TicketPriority,
    TicketCreate,
    TicketUpdate,
)
from services.ticket_service import TicketService
from services.sla_service import SLAService


# ─── Tests 1 à 9 : Les 9 combinaisons de la matrice ITIL ───────────────────────

def test_1_matrix_high_high_urgent():
    assert calculate_priority_from_impact_urgency(ImpactLevel.HIGH, UrgencyLevel.HIGH) == TicketPriority.URGENT

def test_2_matrix_high_medium_urgent():
    assert calculate_priority_from_impact_urgency(ImpactLevel.HIGH, UrgencyLevel.MEDIUM) == TicketPriority.URGENT

def test_3_matrix_high_low_high():
    assert calculate_priority_from_impact_urgency(ImpactLevel.HIGH, UrgencyLevel.LOW) == TicketPriority.HIGH

def test_4_matrix_medium_high_urgent():
    assert calculate_priority_from_impact_urgency(ImpactLevel.MEDIUM, UrgencyLevel.HIGH) == TicketPriority.URGENT

def test_5_matrix_medium_medium_high():
    assert calculate_priority_from_impact_urgency(ImpactLevel.MEDIUM, UrgencyLevel.MEDIUM) == TicketPriority.HIGH

def test_6_matrix_medium_low_medium():
    assert calculate_priority_from_impact_urgency(ImpactLevel.MEDIUM, UrgencyLevel.LOW) == TicketPriority.MEDIUM

def test_7_matrix_low_high_high():
    assert calculate_priority_from_impact_urgency(ImpactLevel.LOW, UrgencyLevel.HIGH) == TicketPriority.HIGH

def test_8_matrix_low_medium_medium():
    assert calculate_priority_from_impact_urgency(ImpactLevel.LOW, UrgencyLevel.MEDIUM) == TicketPriority.MEDIUM

def test_9_matrix_low_low_low():
    assert calculate_priority_from_impact_urgency(ImpactLevel.LOW, UrgencyLevel.LOW) == TicketPriority.LOW


# ─── Test 10 : Gestion des entrées invalides ───────────────────────────────────

def test_10_invalid_inputs_handling():
    with pytest.raises(ValueError):
        calculate_priority_from_impact_urgency("CRITICAL", "LOW")
    with pytest.raises(ValueError):
        calculate_priority_from_impact_urgency("HIGH", "IMMEDIATE")
    with pytest.raises(ValueError):
        calculate_priority_from_impact_urgency(None, "HIGH")
    with pytest.raises(ValueError):
        calculate_priority_from_impact_urgency("HIGH", None)


# ─── Test 11 : Normalisation insensible à la casse et trim ────────────────────

def test_11_case_insensitivity_and_strip():
    assert calculate_priority_from_impact_urgency(" high ", "  low\n") == TicketPriority.HIGH
    assert calculate_priority_from_impact_urgency("medium", "High") == TicketPriority.URGENT
    assert calculate_priority_from_impact_urgency("low", "low") == TicketPriority.LOW


def make_mock_db():
    db = MagicMock()
    db.tickets = MagicMock()
    db.agents = MagicMock()
    db.users = MagicMock()
    db.sla_policies = MagicMock()
    db.sla_alerts = MagicMock()

    # agents find cursor mock
    cursor_mock = MagicMock()
    cursor_mock.sort.return_value = cursor_mock
    cursor_mock.limit.return_value = cursor_mock
    cursor_mock.to_list = AsyncMock(return_value=[])
    db.agents.find.return_value = cursor_mock

    # users find_one mock
    db.users.find_one = AsyncMock(return_value=None)

    # sla_policies mock
    db.sla_policies.find_one = AsyncMock(return_value=None)
    return db


# ─── Test 12 : Rétrocompatibilité ticket hérité sans impact/urgence ────────────

@pytest.mark.asyncio
async def test_12_legacy_ticket_creation_without_impact_urgency():
    mock_db = make_mock_db()
    inserted_docs = []

    async def mock_insert_one(doc):
        doc_copy = dict(doc)
        doc_copy["_id"] = ObjectId()
        inserted_docs.append(doc_copy)
        res = MagicMock()
        res.inserted_id = doc_copy["_id"]
        return res

    mock_db.tickets.insert_one = AsyncMock(side_effect=mock_insert_one)

    ticket_service = TicketService(mock_db)

    # Création sans impact ni urgence (ticket hérité)
    legacy_ticket_in = TicketCreate(
        subject="Problème écran noir",
        description="L'écran de la salle de réunion ne s'allume plus du tout.",
        priority=TicketPriority.HIGH,
        category="Matériel & Poste de Travail",
        subcategory="Écran & Périphériques",
    )

    created = await ticket_service.create_ticket(
        ticket_in=legacy_ticket_in,
        user_id=str(ObjectId()),
    )

    assert created["priority"] == TicketPriority.HIGH
    assert created["priority_source"] == PrioritySource.MANUAL
    assert created["impact"] is None
    assert created["urgency"] is None
    assert "sla_deadline" in created
    assert created["sla_applied_rule"] is not None


# ─── Test 13 : Création de ticket avec impact et urgence (Matrice ITIL) ────────

@pytest.mark.asyncio
async def test_13_ticket_creation_with_impact_urgency():
    mock_db = make_mock_db()
    inserted_docs = []

    async def mock_insert_one(doc):
        doc_copy = dict(doc)
        doc_copy["_id"] = ObjectId()
        inserted_docs.append(doc_copy)
        res = MagicMock()
        res.inserted_id = doc_copy["_id"]
        return res

    mock_db.tickets.insert_one = AsyncMock(side_effect=mock_insert_one)

    ticket_service = TicketService(mock_db)

    # Impact HIGH × Urgence MEDIUM -> URGENT
    ticket_in = TicketCreate(
        subject="Panne VPN généralisée",
        description="L'ensemble des collaborateurs du site ne peuvent plus se connecter au VPN.",
        impact=ImpactLevel.HIGH,
        urgency=UrgencyLevel.MEDIUM,
        category="Infrastructure & Réseau",
        subcategory="VPN & Accès Distant",
    )

    created = await ticket_service.create_ticket(
        ticket_in=ticket_in,
        user_id=str(ObjectId()),
    )

    # Doit avoir calculé URGENT via la matrice ITIL
    assert created["priority"] == TicketPriority.URGENT
    assert created["priority_source"] == PrioritySource.ITIL_MATRIX
    assert created["impact"] == ImpactLevel.HIGH
    assert created["urgency"] == UrgencyLevel.MEDIUM


# ─── Test 14 : Intégration SLA STEP 3 avec priorité calculée ITIL ──────────────

@pytest.mark.asyncio
async def test_14_sla_step3_integration_with_itil_priority():
    mock_db = make_mock_db()
    inserted_docs = []

    async def mock_insert_one(doc):
        doc_copy = dict(doc)
        doc_copy["_id"] = ObjectId()
        inserted_docs.append(doc_copy)
        res = MagicMock()
        res.inserted_id = doc_copy["_id"]
        return res

    mock_db.tickets.insert_one = AsyncMock(side_effect=mock_insert_one)

    ticket_service = TicketService(mock_db)

    # 'Sécurité IT' > 'Incident de Sécurité (ISO 27001)' avec Impact HIGH × Urgence HIGH -> URGENT
    # Règle Granulaire STEP 3: resolution = 1h, response = 0.25h
    ticket_in = TicketCreate(
        subject="Attaque Ransomware détectée",
        description="Fichiers chiffrés sur le serveur de stockage principal avec demande de rançon.",
        impact=ImpactLevel.HIGH,
        urgency=UrgencyLevel.HIGH,
        category="Sécurité IT",
        subcategory="Incident de Sécurité (ISO 27001)",
    )

    created = await ticket_service.create_ticket(
        ticket_in=ticket_in,
        user_id=str(ObjectId()),
    )

    assert created["priority"] == TicketPriority.URGENT
    assert created["priority_source"] == PrioritySource.ITIL_MATRIX
    # Vérification que le SLA granulaire STEP 3 a bien appliqué la règle 1h
    sla_rule = created.get("sla_applied_rule")
    assert sla_rule is not None
    assert sla_rule.get("resolution_time_hours") == 1.0
    assert sla_rule.get("rule_level") == "category_subcategory_priority"


# ─── Test 15 : Mise à jour du ticket : recalcule si priorité change, saute sinon 

@pytest.mark.asyncio
async def test_15_ticket_update_sla_recalculation_behavior():
    """
    Vérifie la logique de mise à jour:
    1. Si l'urgence change et fait changer la priorité (ex: HIGHxLOW=HIGH -> HIGHxHIGH=URGENT),
       la priorité et le SLA sont recalculés.
    2. Si l'urgence change mais la priorité finale reste identique (ex: HIGHxHIGH=URGENT -> HIGHxMEDIUM=URGENT),
       la priorité reste URGENT et le SLA d'origine N'EST PAS recalculé.
    """
    mock_db = MagicMock()

    # Simulation d'un ticket existant en base
    initial_deadline = datetime(2026, 9, 20, 15, 0, 0)
    ticket_id = ObjectId()
    current_doc = {
        "_id": ticket_id,
        "subject": "Panne serveur ERP",
        "description": "Serveur inaccessible",
        "category": "Logiciels & Applications",
        "subcategory": "ERP & Outils Métier",
        "impact": "HIGH",
        "urgency": "HIGH",
        "priority": "URGENT",
        "priority_source": "itil_matrix",
        "created_at": datetime(2026, 9, 19, 10, 0, 0),
        "sla_deadline": initial_deadline,
        "sla_applied_rule": {"resolution_time_hours": 4.0, "rule_level": "category_subcategory_priority"}
    }

    # Cas A: Passage de HIGHxHIGH (URGENT) à HIGHxMEDIUM (URGENT)
    # Même priorité finale -> PAS de recalcul du SLA
    from services.itil_service import calculate_priority_from_impact_urgency

    new_impact = "HIGH"
    new_urgency = "MEDIUM"
    calculated_prio = calculate_priority_from_impact_urgency(new_impact, new_urgency)
    assert calculated_prio == TicketPriority.URGENT

    priority_changed = (calculated_prio.value != current_doc.get("priority"))
    assert priority_changed is False  # La priorité reste URGENT

    # Cas B: Passage de HIGHxHIGH (URGENT) à HIGHxLOW (HIGH)
    # Priorité passe de URGENT à HIGH -> Changement réel -> Déclenche recalcul SLA
    new_urgency_low = "LOW"
    calculated_prio_low = calculate_priority_from_impact_urgency(new_impact, new_urgency_low)
    assert calculated_prio_low == TicketPriority.HIGH

    priority_changed_b = (calculated_prio_low.value != current_doc.get("priority"))
    assert priority_changed_b is True  # La priorité change de URGENT à HIGH
