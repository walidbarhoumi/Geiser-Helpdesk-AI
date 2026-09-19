"""
Script de validation fonctionnelle pour STEP 4 : Matrice ITIL Impact × Urgence.
Exécution: python verify_step4_functional.py
"""
import asyncio
from datetime import datetime
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from core.config import settings
from services.sla_service import SLAService
from services.ticket_service import TicketService
from services.itil_service import calculate_priority_from_impact_urgency
from schemas.schemas import (
    ImpactLevel,
    UrgencyLevel,
    PrioritySource,
    TicketPriority,
    TicketChannel,
    TicketCreate,
)


async def run_functional_verification():
    print("=== DÉBUT DU TEST FONCTIONNEL STEP 4 : MATRICE ITIL IMPACT × URGENCE ===")
    client = AsyncIOMotorClient(settings.MONGO_URL)
    db = client[settings.DATABASE_NAME]

    ticket_service = TicketService(db)
    created_ticket_ids = []

    try:
        # ─────────────────────────────────────────────────────────────────
        # Étape 1 : Création avec Impact HIGH × Urgence HIGH -> URGENT (ITIL Matrix)
        # ─────────────────────────────────────────────────────────────────
        print("\n--- Étape 1 : Ticket avec Impact HIGH et Urgence HIGH ---")
        ticket_1_in = TicketCreate(
            subject="Test STEP4 - Incident Majeur Datacenter",
            description="Perte totale d'alimentation sur la baie principale du datacenter.",
            category="Infrastructure & Réseau",
            subcategory="Serveurs & Cloud",
            impact=ImpactLevel.HIGH,
            urgency=UrgencyLevel.HIGH,
            channel=TicketChannel.WEB
        )
        created_1 = await ticket_service.create_ticket(
            ticket_in=ticket_1_in,
            user_id=str(ObjectId())
        )
        created_ticket_ids.append(created_1["id"])

        print(f"[OK] Ticket 1 créé ID: {created_1['id']}")
        print(f"     Impact: {created_1.get('impact')} | Urgence: {created_1.get('urgency')}")
        print(f"     Priorité finale: {created_1.get('priority')} | Source: {created_1.get('priority_source')}")
        assert created_1["priority"] == TicketPriority.URGENT.value, f"Attendu URGENT, obtenu {created_1['priority']}"
        assert created_1["priority_source"] == PrioritySource.ITIL_MATRIX.value
        assert created_1.get("sla_applied_rule") is not None

        # ─────────────────────────────────────────────────────────────────
        # Étape 2 : Ticket avec Impact LOW × Urgence LOW -> LOW (ITIL Matrix)
        # ─────────────────────────────────────────────────────────────────
        print("\n--- Étape 2 : Ticket avec Impact LOW et Urgence LOW ---")
        ticket_2_in = TicketCreate(
            subject="Test STEP4 - Demande de souris ergonomique",
            description="L'utilisateur souhaite commander une nouvelle souris sans urgence.",
            category="Matériel & Poste de Travail",
            subcategory="Écran & Périphériques",
            impact=ImpactLevel.LOW,
            urgency=UrgencyLevel.LOW,
            channel=TicketChannel.WEB
        )
        created_2 = await ticket_service.create_ticket(
            ticket_in=ticket_2_in,
            user_id=str(ObjectId())
        )
        created_ticket_ids.append(created_2["id"])

        print(f"[OK] Ticket 2 créé ID: {created_2['id']}")
        print(f"     Impact: {created_2.get('impact')} | Urgence: {created_2.get('urgency')}")
        print(f"     Priorité finale: {created_2.get('priority')} | Source: {created_2.get('priority_source')}")
        assert created_2["priority"] == TicketPriority.LOW.value
        assert created_2["priority_source"] == PrioritySource.ITIL_MATRIX.value

        # ─────────────────────────────────────────────────────────────────
        # Étape 3 : Ticket Hérité (Sans Impact ni Urgence) -> Priorité Manuelle
        # ─────────────────────────────────────────────────────────────────
        print("\n--- Étape 3 : Ticket Hérité sans Impact ni Urgence ---")
        ticket_legacy_in = TicketCreate(
            subject="Test STEP4 - Ticket hérité v1",
            description="Créé par un client legacy sans les champs ITIL.",
            category="Support Général",
            subcategory="Assistance Utilisateur",
            priority=TicketPriority.HIGH,
            channel=TicketChannel.EMAIL
        )
        created_legacy = await ticket_service.create_ticket(
            ticket_in=ticket_legacy_in,
            user_id=str(ObjectId())
        )
        created_ticket_ids.append(created_legacy["id"])

        print(f"[OK] Ticket Legacy créé ID: {created_legacy['id']}")
        print(f"     Impact: {created_legacy.get('impact')} | Urgence: {created_legacy.get('urgency')}")
        print(f"     Priorité finale: {created_legacy.get('priority')} | Source: {created_legacy.get('priority_source')}")
        assert created_legacy["priority"] == TicketPriority.HIGH.value
        assert created_legacy["priority_source"] == PrioritySource.MANUAL.value
        assert created_legacy.get("impact") is None
        assert created_legacy.get("urgency") is None

        # ─────────────────────────────────────────────────────────────────
        # Étape 4 : Test de Mise à Jour et Règle de Préservation du SLA
        # ─────────────────────────────────────────────────────────────────
        print("\n--- Étape 4 : Mise à jour avec Urgence modifiée mais priorité finale identique ---")
        # Ticket 1 est en HIGH x HIGH = URGENT.
        # On passe l'urgence à MEDIUM: HIGH x MEDIUM = URGENT (priorité inchangée)
        # Simulation de la route PUT /tickets/{id}
        doc_before = await db.tickets.find_one({"_id": ObjectId(created_1["id"])})
        initial_deadline = doc_before["sla_deadline"]
        active_impact = "HIGH"
        new_urgency = "MEDIUM"
        recalc_prio = calculate_priority_from_impact_urgency(active_impact, new_urgency)
        priority_actually_changed = (recalc_prio.value != doc_before.get("priority"))

        print(f"     Impact HIGH × Urgence MEDIUM -> Priorité recalculée: {recalc_prio.value}")
        print(f"     La priorité a-t-elle réellement changé ? -> {priority_actually_changed}")
        assert priority_actually_changed is False, "La priorité URGENT n'aurait pas dû être marquée comme modifiée !"

        # Mise à jour des champs sans recalculer le SLA
        await db.tickets.update_one(
            {"_id": ObjectId(created_1["id"])},
            {"$set": {"urgency": new_urgency, "priority": recalc_prio.value}}
        )

        doc_after_same = await db.tickets.find_one({"_id": ObjectId(created_1["id"])})
        assert doc_after_same["sla_deadline"] == initial_deadline
        print(f"[OK] SLA Deadline préservée à l'identique ({doc_after_same['sla_deadline']})")

        print("\n--- Étape 5 : Mise à jour avec Priorité finale modifiée (HIGH x LOW = HIGH) ---")
        # Passage à LOW: HIGH x LOW = HIGH (changement réel de priorité !)
        new_urgency_low = "LOW"
        recalc_prio_low = calculate_priority_from_impact_urgency(active_impact, new_urgency_low)
        priority_actually_changed_2 = (recalc_prio_low.value != doc_after_same.get("priority"))

        print(f"     Impact HIGH × Urgence LOW -> Priorité recalculée: {recalc_prio_low.value}")
        print(f"     La priorité a-t-elle réellement changé ? -> {priority_actually_changed_2}")
        assert priority_actually_changed_2 is True, "La priorité devait changer de URGENT à HIGH !"

        # Recalcul du SLA via SLAService
        sla_service = SLAService(db)
        sla_calc = await sla_service.calculate_ticket_sla(
            priority=recalc_prio_low,
            created_at=doc_after_same["created_at"],
            category=doc_after_same["category"],
            subcategory=doc_after_same["subcategory"]
        )
        new_deadline = sla_calc["resolution_deadline"]

        await db.tickets.update_one(
            {"_id": ObjectId(created_1["id"])},
            {"$set": {
                "urgency": new_urgency_low,
                "priority": recalc_prio_low.value,
                "sla_deadline": new_deadline,
                "sla_applied_rule": sla_calc["applied_rule"]
            }}
        )

        doc_after_changed = await db.tickets.find_one({"_id": ObjectId(created_1["id"])})
        assert doc_after_changed["priority"] == TicketPriority.HIGH.value
        assert doc_after_changed["sla_deadline"] != initial_deadline
        print(f"[OK] Priorité mise à jour en HIGH et SLA Deadline correctement recalculée ({doc_after_changed['sla_deadline']})")

        print("\n==================================================================")
        print("TOUTES LES VÉRIFICATIONS FONCTIONNELLES STEP 4 SONT PASSÉES AVEC SUCCÈS !")
        print("==================================================================")

    finally:
        # Nettoyage
        print("\n--- Nettoyage de la base de données ---")
        if created_ticket_ids:
            res_del = await db.tickets.delete_many({"_id": {"$in": [ObjectId(tid) for tid in created_ticket_ids]}})
            print(f"[CLEANUP] {res_del.deleted_count} tickets de test supprimés.")
        client.close()


if __name__ == "__main__":
    asyncio.run(run_functional_verification())
