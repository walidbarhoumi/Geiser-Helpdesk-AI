"""
Functional verification script for STEP 3 (Granular SLA Engine by Category & Subcategory).
Run: python verify_step3_functional.py
"""
import asyncio
from datetime import datetime, timedelta
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from core.config import settings
from services.sla_service import SLAService
from services.ticket_service import TicketService
from schemas.schemas import TicketPriority, TicketStatus, TicketChannel, TicketCreate


async def run_functional_verification():
    print("=== DÉBUT DU TEST FONCTIONNEL STEP 3 : SLA GRANULAIRE PAR CATÉGORIE / TYPE ===")
    client = AsyncIOMotorClient(settings.MONGO_URL)
    db = client[settings.DATABASE_NAME]

    sla_service = SLAService(db)
    ticket_service = TicketService(db)

    now = datetime.utcnow()
    created_ticket_ids = []
    override_rule_id = None

    try:
        # ─────────────────────────────────────────────────────────────────
        # Étape 1 : Création temporaire d'une surcharge DB spécifique
        # ─────────────────────────────────────────────────────────────────
        print("\n--- Étape 1 : Surcharge DB temporaire dans sla_policies ---")
        override_rule = {
            "category": "CatégorieTestStep3",
            "subcategory": "SousCatégorieTestStep3",
            "priority": TicketPriority.URGENT.value,
            "response_time_hours": 0.1,  # 6 minutes
            "resolution_time_hours": 0.5, # 30 minutes
            "at_risk_threshold_pct": 0.15,
            "created_at": now
        }
        res_db = await db.sla_policies.insert_one(override_rule)
        override_rule_id = res_db.inserted_id
        print(f"[OK] Surcharge DB créée avec ID: {override_rule_id} (0.1h rep / 0.5h res)")

        # ─────────────────────────────────────────────────────────────────
        # Étape 2 : Deux tickets de MÊME priorité mais CATÉGORIES différentes
        # ─────────────────────────────────────────────────────────────────
        print("\n--- Étape 2 : Même priorité (URGENT) mais catégories différentes ---")
        # Ticket A : Sécurité IT (doit être très rapide : 1h)
        # Ticket B : Matériel & Poste de Travail (intervention physique : 6h)
        ticket_a = await ticket_service.create_ticket(
            ticket_in=TicketCreate(
                subject="Test STEP3 - Alerte Phishing Critique",
                description="Email suspect reçu avec pièce jointe frauduleuse.",
                category="Sécurité IT",
                subcategory="Email Suspect / Phishing",
                priority=TicketPriority.URGENT,
                channel=TicketChannel.WEB
            ),
            user_id="user_test_step3_a"
        )
        created_ticket_ids.append(ticket_a["id"])

        ticket_b = await ticket_service.create_ticket(
            ticket_in=TicketCreate(
                subject="Test STEP3 - Panne PC Fixe",
                description="Le PC ne démarre plus du tout au bureau.",
                category="Matériel & Poste de Travail",
                subcategory="PC Portable / Fixe",
                priority=TicketPriority.URGENT,
                channel=TicketChannel.WEB
            ),
            user_id="user_test_step3_b"
        )
        created_ticket_ids.append(ticket_b["id"])

        doc_a = await db.tickets.find_one({"_id": ObjectId(ticket_a["id"])})
        doc_b = await db.tickets.find_one({"_id": ObjectId(ticket_b["id"])})

        deadline_a = doc_a["sla_deadline"]
        deadline_b = doc_b["sla_deadline"]
        duration_a_hours = (deadline_a - doc_a["created_at"]).total_seconds() / 3600.0
        duration_b_hours = (deadline_b - doc_b["created_at"]).total_seconds() / 3600.0

        print(f"Ticket A (Sécurité IT) : délai = {duration_a_hours:.1f}h")
        print(f"Ticket B (Matériel)     : délai = {duration_b_hours:.1f}h")

        assert duration_a_hours < duration_b_hours, "Sécurité IT doit avoir un SLA plus court que Matériel !"
        assert duration_a_hours == 2.0, f"Attendu 2.0h pour Email Suspect URGENT, obtenu {duration_a_hours}"
        assert duration_b_hours == 6.0, f"Attendu 6.0h pour Matériel PC Fixe URGENT, obtenu {duration_b_hours}"
        print("[OK] Délais différents validés pour une même priorité entre catégories distinctes.")

        # ─────────────────────────────────────────────────────────────────
        # Étape 3 : Deux tickets de MÊME catégorie mais SOUS-CATÉGORIES différentes
        # ─────────────────────────────────────────────────────────────────
        print("\n--- Étape 3 : Même catégorie (Infrastructure & Réseau) mais sous-catégories différentes ---")
        # Ticket C : Serveurs & Cloud (2h résolution en URGENT)
        # Ticket D : VPN & Accès Distant (3h résolution en URGENT)
        ticket_c = await ticket_service.create_ticket(
            ticket_in=TicketCreate(
                subject="Test STEP3 - Crash Serveur Cloud",
                description="Le serveur de production ne répond plus.",
                category="Infrastructure & Réseau",
                subcategory="Serveurs & Cloud",
                priority=TicketPriority.URGENT,
                channel=TicketChannel.WEB
            ),
            user_id="user_test_step3_c"
        )
        created_ticket_ids.append(ticket_c["id"])

        ticket_d = await ticket_service.create_ticket(
            ticket_in=TicketCreate(
                subject="Test STEP3 - Panne Accès VPN",
                description="Perte de connexion VPN sur le concentrateur.",
                category="Infrastructure & Réseau",
                subcategory="VPN & Accès Distant",
                priority=TicketPriority.URGENT,
                channel=TicketChannel.WEB
            ),
            user_id="user_test_step3_d"
        )
        created_ticket_ids.append(ticket_d["id"])

        doc_c = await db.tickets.find_one({"_id": ObjectId(ticket_c["id"])})
        doc_d = await db.tickets.find_one({"_id": ObjectId(ticket_d["id"])})

        duration_c_hours = (doc_c["sla_deadline"] - doc_c["created_at"]).total_seconds() / 3600.0
        duration_d_hours = (doc_d["sla_deadline"] - doc_d["created_at"]).total_seconds() / 3600.0

        print(f"Ticket C (Serveurs & Cloud) : délai = {duration_c_hours:.1f}h")
        print(f"Ticket D (VPN & Accès)      : délai = {duration_d_hours:.1f}h")

        assert duration_c_hours != duration_d_hours, "Sous-catégories différentes doivent avoir des SLA différents !"
        assert duration_c_hours == 2.0
        assert duration_d_hours == 3.0
        print("[OK] Règles spécifiques appliquées avec succès entre sous-catégories.")

        # ─────────────────────────────────────────────────────────────────
        # Étape 4 : Test des fallbacks hiérarchiques et de la surcharge DB
        # ─────────────────────────────────────────────────────────────────
        print("\n--- Étape 4 : Test de la surcharge DB et des fallbacks ---")
        # 4a. Surcharge DB
        db_override_sla = await sla_service.calculate_ticket_sla(
            priority=TicketPriority.URGENT,
            created_at=now,
            category="CatégorieTestStep3",
            subcategory="SousCatégorieTestStep3"
        )
        assert db_override_sla["resolution_time_hours"] == 0.5
        assert db_override_sla["applied_rule"]["source"] == "db_override"
        assert db_override_sla["applied_rule"]["rule_level"] == "category_subcategory_priority"
        print("[OK] Surcharge DB appliquée au niveau 1 avec succès (0.5h).")

        # 4b. Fallback Catégorie (sous-catégorie inconnue dans une catégorie connue)
        cat_fallback_sla = await sla_service.calculate_ticket_sla(
            priority=TicketPriority.URGENT,
            created_at=now,
            category="Infrastructure & Réseau",
            subcategory="SousCatégorieInconnue"
        )
        assert cat_fallback_sla["resolution_time_hours"] == 4.0  # _default de Infrastructure & Réseau
        assert cat_fallback_sla["applied_rule"]["rule_level"] == "category_priority"
        print("[OK] Fallback niveau 2 (category_priority) validé avec succès (4.0h).")

        # 4c. Fallback Priorité (catégorie totalement inconnue)
        prio_fallback_sla = await sla_service.calculate_ticket_sla(
            priority=TicketPriority.HIGH,
            created_at=now,
            category="CatégorieTotalementInconnue",
            subcategory=None
        )
        assert prio_fallback_sla["resolution_time_hours"] == 8.0  # DEFAULT_SLA_POLICIES HIGH
        assert prio_fallback_sla["applied_rule"]["rule_level"] == "priority_fallback"
        print("[OK] Fallback niveau 3 (priority_fallback) validé avec succès (8.0h).")

        # ─────────────────────────────────────────────────────────────────
        # Étape 5 : Persistance effective de sla_applied_rule dans MongoDB
        # ─────────────────────────────────────────────────────────────────
        print("\n--- Étape 5 : Vérification de la persistance de sla_applied_rule ---")
        saved_ticket = await db.tickets.find_one({"_id": ObjectId(ticket_a["id"])})
        assert "sla_applied_rule" in saved_ticket, "sla_applied_rule doit être persisté dans MongoDB !"
        rule = saved_ticket["sla_applied_rule"]
        assert rule["rule_level"] == "category_subcategory_priority"
        assert rule["category"] == "Sécurité IT"
        assert rule["subcategory"] == "Email Suspect / Phishing"
        print(f"[OK] sla_applied_rule vérifié en base : {rule}")

    finally:
        # ─────────────────────────────────────────────────────────────────
        # Étape 6 : Nettoyage complet des données de test
        # ─────────────────────────────────────────────────────────────────
        print("\n--- Étape 6 : Nettoyage complet des données de test ---")
        if override_rule_id:
            await db.sla_policies.delete_one({"_id": override_rule_id})
        if created_ticket_ids:
            oids = [ObjectId(tid) for tid in created_ticket_ids]
            await db.tickets.delete_many({"_id": {"$in": oids}})
            await db.sla_alerts.delete_many({"ticket_id": {"$in": created_ticket_ids}})
        client.close()
        print("[OK] Base de données nettoyée sans aucun résidu de test.")

    print("\n=== TOUTES LES VÉRIFICATIONS FONCTIONNELLES STEP 3 RÉUSSIES AVEC SUCCÈS ===")


if __name__ == "__main__":
    asyncio.run(run_functional_verification())
