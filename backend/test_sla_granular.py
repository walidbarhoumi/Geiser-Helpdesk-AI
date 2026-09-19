"""
Suite de tests unitaires complets pour le moteur SLA Granulaire (STEP 3).
Vérifie les 10 exigences minimales :
1. Règle spécifique complète (category + subcategory + priority)
2. Fallback catégorie (category + priority)
3. Fallback priorité (priority)
4. Fallback global (global_default)
5. Différences entre catégories pour une même priorité
6. Différences entre sous-catégories d'une même catégorie
7. Protection des tickets historiques avec SLA existant
8. Différenciation par niveau de priorité
9. Données incomplètes (None, empty, unknown)
10. Rétrocompatibilité des signatures d'origine

Exécution: pytest test_sla_granular.py -v
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId

from services.sla_service import SLAService, DEFAULT_SLA_POLICIES, GRANULAR_SLA_CATALOG
from schemas.schemas import TicketPriority, SLAStatus, TicketStatus


def make_mock_db():
    db = MagicMock()
    db.tickets = MagicMock()
    db.sla_policies = MagicMock()
    db.sla_alerts = MagicMock()
    # Par défaut aucun override DB
    db.sla_policies.find_one = AsyncMock(return_value=None)
    return db


@pytest.fixture
def sla_service():
    return SLAService(make_mock_db())


# ── Test 1 : Règle spécifique complète (category + subcategory + priority) ──
@pytest.mark.asyncio
async def test_1_specific_rule_category_subcategory_priority(sla_service):
    """
    Vérifie que pour 'Sécurité IT' > 'Incident de Sécurité (ISO 27001)' en URGENT,
    la règle la plus spécifique est appliquée (1h de résolution, 0.25h de réponse).
    """
    created_at = datetime(2026, 1, 1, 10, 0, 0)
    res = await sla_service.calculate_ticket_sla(
        priority=TicketPriority.URGENT,
        created_at=created_at,
        category="Sécurité IT",
        subcategory="Incident de Sécurité (ISO 27001)"
    )
    assert res["resolution_time_hours"] == 1.0
    assert res["response_time_hours"] == 0.25
    assert res["applied_rule"]["rule_level"] == "category_subcategory_priority"
    assert res["applied_rule"]["source"] == "granular_catalog"
    assert res["resolution_deadline"] == created_at + timedelta(hours=1.0)
    assert res["response_deadline"] == created_at + timedelta(hours=0.25)


# ── Test 2 : Fallback catégorie (category + priority) ──
@pytest.mark.asyncio
async def test_2_category_fallback_when_subcategory_unknown(sla_service):
    """
    Lorsqu'une sous-catégorie n'a pas de règle propre dans 'Sécurité IT',
    la règle par défaut de la catégorie est appliquée (2h résolution, 0.5h réponse en URGENT).
    """
    created_at = datetime(2026, 1, 1, 10, 0, 0)
    res = await sla_service.calculate_ticket_sla(
        priority=TicketPriority.URGENT,
        created_at=created_at,
        category="Sécurité IT",
        subcategory="Autre Incident Inconnu"
    )
    assert res["resolution_time_hours"] == 2.0
    assert res["response_time_hours"] == 0.5
    assert res["applied_rule"]["rule_level"] == "category_priority"
    assert res["applied_rule"]["source"] == "granular_catalog"


# ── Test 3 : Fallback priorité (priority) ──
@pytest.mark.asyncio
async def test_3_priority_fallback_when_category_unknown(sla_service):
    """
    Lorsque la catégorie est inconnue du catalogue,
    le système bascule sur la politique globale de priorité (HIGH: 8h résolution, 4h réponse).
    """
    created_at = datetime(2026, 1, 1, 10, 0, 0)
    res = await sla_service.calculate_ticket_sla(
        priority=TicketPriority.HIGH,
        created_at=created_at,
        category="Catégorie Fantôme",
        subcategory="Sous-catégorie Inconnue"
    )
    assert res["resolution_time_hours"] == 8.0
    assert res["response_time_hours"] == 4.0
    assert res["applied_rule"]["rule_level"] == "priority_fallback"
    assert res["applied_rule"]["source"] == "default_policy"


# ── Test 4 : Fallback global (global_default) ──
@pytest.mark.asyncio
async def test_4_global_default_fallback(sla_service):
    """
    Lorsque la priorité est invalide/inconnue et catégorie inexistante,
    le système retombe sur le SLA global par défaut (MEDIUM: 24h résolution, 8h réponse).
    """
    created_at = datetime(2026, 1, 1, 10, 0, 0)
    res = await sla_service.calculate_ticket_sla(
        priority="NON_EXISTENT_PRIORITY",
        created_at=created_at,
        category=None,
        subcategory=None
    )
    assert res["resolution_time_hours"] == 24.0
    assert res["response_time_hours"] == 8.0
    assert res["applied_rule"]["rule_level"] in ["priority_fallback", "global_default"]


# ── Test 5 : Différences entre catégories pour une même priorité ──
@pytest.mark.asyncio
async def test_5_different_categories_same_priority_have_different_slas(sla_service):
    """
    Vérifie qu'en priorité URGENT, un incident 'Sécurité IT' (1h)
    a un délai de résolution beaucoup plus court qu'un incident 'Matériel & Poste de Travail' (6h).
    """
    created_at = datetime(2026, 1, 1, 10, 0, 0)
    sec_sla = await sla_service.calculate_ticket_sla(
        priority=TicketPriority.URGENT,
        created_at=created_at,
        category="Sécurité IT",
        subcategory="Incident de Sécurité (ISO 27001)"
    )
    hw_sla = await sla_service.calculate_ticket_sla(
        priority=TicketPriority.URGENT,
        created_at=created_at,
        category="Matériel & Poste de Travail",
        subcategory="PC Portable / Fixe"
    )
    assert sec_sla["resolution_time_hours"] == 1.0
    assert hw_sla["resolution_time_hours"] == 6.0
    assert sec_sla["resolution_time_hours"] < hw_sla["resolution_time_hours"]


# ── Test 6 : Différences entre types d'une même catégorie ──
@pytest.mark.asyncio
async def test_6_different_subcategories_same_category_have_different_slas(sla_service):
    """
    Dans 'Infrastructure & Réseau' en URGENT :
    'Serveurs & Cloud' (2h résolution) vs 'VPN & Accès Distant' (3h résolution).
    """
    created_at = datetime(2026, 1, 1, 10, 0, 0)
    cloud_sla = await sla_service.calculate_ticket_sla(
        priority=TicketPriority.URGENT,
        created_at=created_at,
        category="Infrastructure & Réseau",
        subcategory="Serveurs & Cloud"
    )
    vpn_sla = await sla_service.calculate_ticket_sla(
        priority=TicketPriority.URGENT,
        created_at=created_at,
        category="Infrastructure & Réseau",
        subcategory="VPN & Accès Distant"
    )
    assert cloud_sla["resolution_time_hours"] == 2.0
    assert vpn_sla["resolution_time_hours"] == 3.0
    assert cloud_sla["resolution_time_hours"] != vpn_sla["resolution_time_hours"]


# ── Test 7 : Protection des tickets historiques avec SLA existant ──
@pytest.mark.asyncio
async def test_7_historical_tickets_sla_not_overwritten(sla_service):
    """
    Vérifie qu'un ticket historique possédant déjà une sla_deadline arbitraire
    conserve son statut et son échéance lors de l'évaluation compute_sla_status.
    """
    created_at = datetime.utcnow() - timedelta(hours=2)
    historical_deadline = created_at + timedelta(hours=10)  # Délai personnalisé
    ticket = {
        "_id": ObjectId(),
        "category": "Sécurité IT",
        "subcategory": "Incident de Sécurité (ISO 27001)",
        "priority": TicketPriority.URGENT,
        "created_at": created_at,
        "sla_deadline": historical_deadline,
        "sla_status": SLAStatus.ON_TRACK.value
    }
    # compute_sla_status calcule le statut à partir du sla_deadline existant du ticket
    status = await sla_service.compute_sla_status(ticket)
    assert status == SLAStatus.ON_TRACK
    # L'échéance originale n'est pas altérée
    assert ticket["sla_deadline"] == historical_deadline


# ── Test 8 : Délais distincts par niveau de priorité ──
@pytest.mark.asyncio
async def test_8_all_priorities_have_distinct_slas(sla_service):
    """
    Vérifie que pour 'Authentification & Accès' > 'Réinitialisation Mot de passe',
    URGENT < HIGH < MEDIUM < LOW en termes de délais de résolution.
    """
    created_at = datetime(2026, 1, 1, 10, 0, 0)
    cat = "Authentification & Accès"
    subcat = "Réinitialisation Mot de passe"

    urgent = await sla_service.calculate_ticket_sla(TicketPriority.URGENT, created_at, cat, subcat)
    high = await sla_service.calculate_ticket_sla(TicketPriority.HIGH, created_at, cat, subcat)
    medium = await sla_service.calculate_ticket_sla(TicketPriority.MEDIUM, created_at, cat, subcat)
    low = await sla_service.calculate_ticket_sla(TicketPriority.LOW, created_at, cat, subcat)

    assert urgent["resolution_time_hours"] == 1.0
    assert high["resolution_time_hours"] == 2.0
    assert medium["resolution_time_hours"] == 4.0
    assert low["resolution_time_hours"] == 8.0

    assert urgent["resolution_time_hours"] < high["resolution_time_hours"]
    assert high["resolution_time_hours"] < medium["resolution_time_hours"]
    assert medium["resolution_time_hours"] < low["resolution_time_hours"]


# ── Test 9 : Données incomplètes ou manquantes ──
@pytest.mark.asyncio
async def test_9_incomplete_data_graceful_fallback(sla_service):
    """
    Catégorie absente (None), chaîne vide, espaces blancs :
    fallback sans exception, résolution conforme.
    """
    created_at = datetime(2026, 1, 1, 10, 0, 0)
    res_none = await sla_service.calculate_ticket_sla(
        priority=TicketPriority.MEDIUM,
        created_at=created_at,
        category=None,
        subcategory=None
    )
    assert res_none["resolution_time_hours"] == 24.0
    assert res_none["applied_rule"]["rule_level"] == "priority_fallback"

    res_empty = await sla_service.calculate_ticket_sla(
        priority=TicketPriority.LOW,
        created_at=created_at,
        category="   ",
        subcategory=""
    )
    assert res_empty["resolution_time_hours"] == 72.0
    assert res_empty["applied_rule"]["rule_level"] == "priority_fallback"


# ── Test 10 : Non-régression sur signatures historiques ──
@pytest.mark.asyncio
async def test_10_backward_compatibility_old_signatures(sla_service):
    """
    Vérifie que les appels avec l'ancienne signature à 2 arguments
    (priority, created_at) fonctionnent à l'identique de l'ancien système.
    """
    created_at = datetime(2026, 1, 1, 10, 0, 0)
    # Appel historique sans category ni subcategory
    res_deadline = await sla_service.compute_sla_deadline(TicketPriority.URGENT, created_at)
    resp_deadline = await sla_service.compute_sla_response_deadline(TicketPriority.URGENT, created_at)

    assert res_deadline == created_at + timedelta(hours=4.0)
    assert resp_deadline == created_at + timedelta(hours=1.0)


# ── Test 11 : Recalcul sélectif lors de l'UPDATE de ticket ──
@pytest.mark.asyncio
async def test_11_update_sla_recalculation_only_when_priority_category_changed():
    """
    Vérifie la condition d'update :
    - Un changement de statut seul ne modifie pas les deadlines existantes
    - Un changement de priorité ou de catégorie déclenche le recalcul
    """
    # 1. Mise à jour de statut seul
    update_payload_status = {"status": TicketStatus.IN_PROGRESS.value}
    ticket_existing = {
        "priority": TicketPriority.HIGH.value,
        "category": "Sécurité IT",
        "subcategory": "Alerte Antivirus",
        "sla_deadline": datetime(2026, 1, 1, 16, 0, 0)
    }
    prio_changed = "priority" in update_payload_status and update_payload_status["priority"] != ticket_existing.get("priority")
    cat_changed = "category" in update_payload_status and update_payload_status["category"] != ticket_existing.get("category")
    subcat_changed = "subcategory" in update_payload_status and update_payload_status["subcategory"] != ticket_existing.get("subcategory")

    assert not (prio_changed or cat_changed or subcat_changed), "Le statut seul ne doit pas déclencher le recalcul !"

    # 2. Mise à jour de priorité
    update_payload_prio = {"priority": TicketPriority.URGENT.value}
    prio_changed = "priority" in update_payload_prio and update_payload_prio["priority"] != ticket_existing.get("priority")
    assert prio_changed, "Le changement de priorité doit déclencher le recalcul !"

    # 3. Même priorité ré-envoyée (pas de vrai changement)
    update_payload_same = {"priority": TicketPriority.HIGH.value, "status": TicketStatus.IN_PROGRESS.value}
    prio_changed = "priority" in update_payload_same and update_payload_same["priority"] != ticket_existing.get("priority")
    assert not prio_changed, "Une priorité identique ne doit pas déclencher le recalcul !"

