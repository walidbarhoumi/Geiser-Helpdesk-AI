"""
Functional verification script for STEP 2 (Adaptive Routing Feedback Loop).
Run: python verify_step2_functional.py
"""
import asyncio
from datetime import datetime, timedelta
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from core.config import settings
from services.routing_service import RoutingService
from schemas.schemas import TicketStatus, TicketPriority


async def run_functional_verification():
    print("=== DÉBUT DU TEST FONCTIONNEL STEP 2 : ADAPTIVE ROUTING FEEDBACK LOOP ===")
    client = AsyncIOMotorClient(settings.MONGO_URL)
    db = client[settings.DATABASE_NAME]

    service = RoutingService(db)

    # Generated test IDs
    team_id = ObjectId()
    agent_a_id = ObjectId()
    agent_b_id = ObjectId()
    ticket_id = ObjectId()
    ticket_2_id = None

    now = datetime.utcnow()
    unique_keyword = "AlphaBetaSpecialistSkill"
    test_category = "SpecialistCategory"
    test_subcategory = "SpecialistSubcategory"

    try:
        # 1. Setup Test Team and two Agents with identical skills and workload
        print("\n--- Étape 1 : Création de l'équipe et de deux agents équivalents ---")
        await db.teams.insert_one({
            "_id": team_id,
            "name": "Équipe Test Step2",
            "competencies": [unique_keyword, test_category, test_subcategory],
            "agent_ids": [str(agent_a_id), str(agent_b_id)]
        })

        await db.agents.insert_one({
            "_id": agent_a_id,
            "user_id": "agent_alpha_step2",
            "skills": [unique_keyword, test_category, test_subcategory],
            "is_available": True,
            "workload": 3,
            "created_at": now
        })

        await db.agents.insert_one({
            "_id": agent_b_id,
            "user_id": "agent_beta_step2",
            "skills": [unique_keyword, test_category, test_subcategory],
            "is_available": True,
            "workload": 3,
            "created_at": now
        })
        print(f"[OK] Équipe créée avec Agent Alpha ({agent_a_id}) et Agent Beta ({agent_b_id})")

        # 2. Simulation initiale : Agent Alpha a 12 tickets résolus avec succès
        # Agent Beta a 0 historique dans cette catégorie
        print("\n--- Étape 2 : Simulation d'un historique d'excellence pour Agent Alpha ---")
        alpha_tickets = []
        for i in range(12):
            alpha_tickets.append({
                "_id": ObjectId(),
                "subject": f"Test {unique_keyword} résolu #{i}",
                "category": test_category,
                "subcategory": test_subcategory,
                "assigned_agent_id": str(agent_a_id),
                "status": TicketStatus.RESOLVED.value,
                "created_at": now - timedelta(days=5),
                "updated_at": now - timedelta(days=4),
                "reassigned_from_agent_ids": []
            })
        await db.tickets.insert_many(alpha_tickets)
        print(f"[OK] 12 tickets résolus insérés pour Agent Alpha sur '{test_category} > {test_subcategory}'")

        # 3. Création d'un nouveau ticket à router
        await db.tickets.insert_one({
            "_id": ticket_id,
            "subject": f"Demande urgente {unique_keyword}",
            "description": f"Impossible d'utiliser le module {unique_keyword}.",
            "category": test_category,
            "subcategory": test_subcategory,
            "priority": TicketPriority.HIGH.value,
            "status": TicketStatus.OPEN.value,
            "created_at": now
        })

        # 4. Premier routage automatique
        print("\n--- Étape 3 : Premier routage automatique ---")
        routing_res_1 = await service.auto_route_ticket(str(ticket_id))
        print(f"Agent sélectionné : {routing_res_1['agent_name']} (ID: {routing_res_1['selected_agent']})")
        print(f"Raison : {routing_res_1['routing_reason']}")
        print(f"Détails du score : {routing_res_1.get('scoring_details')}")

        assert routing_res_1["selected_agent"] == str(agent_a_id), "Agent Alpha aurait dû être sélectionné grâce à son historique !"
        alpha_first_score = routing_res_1["scoring_details"]["final_score"]
        print("[OK] Agent Alpha sélectionné avec succès grâce à son feedback historique positif.")

        # 5. Modification dynamique de l'historique :
        # On simule qu'Agent Alpha commence à avoir 8 réassignations récentes
        # et Agent Beta accumule 15 résolutions impeccables
        print("\n--- Étape 4 : Évolution de l'historique (feedback négatif pour Alpha, succès pour Beta) ---")
        # Ajout de 8 réassignations pour Alpha (réassignés vers un agent de niveau 3)
        tier3_agent_id = str(ObjectId())
        reassigned_tickets = []
        for j in range(8):
            reassigned_tickets.append({
                "_id": ObjectId(),
                "subject": f"Ticket {unique_keyword} réassigné #{j}",
                "category": test_category,
                "subcategory": test_subcategory,
                "assigned_agent_id": tier3_agent_id,
                "status": TicketStatus.RESOLVED.value,
                "created_at": now - timedelta(days=2),
                "updated_at": now - timedelta(days=1),
                "reassigned_from_agent_ids": [str(agent_a_id)]
            })
        await db.tickets.insert_many(reassigned_tickets)

        # Ajout de 15 résolutions pour Beta
        beta_tickets = []
        for k in range(15):
            beta_tickets.append({
                "_id": ObjectId(),
                "subject": f"Test {unique_keyword} Beta résolu #{k}",
                "category": test_category,
                "subcategory": test_subcategory,
                "assigned_agent_id": str(agent_b_id),
                "status": TicketStatus.RESOLVED.value,
                "created_at": now - timedelta(days=3),
                "updated_at": now - timedelta(days=2),
                "reassigned_from_agent_ids": []
            })
        await db.tickets.insert_many(beta_tickets)
        print("[OK] Historique mis à jour : 8 réassignations pour Alpha, 15 résolutions pour Beta")

        # 6. Deuxième routage automatique pour un nouveau ticket similaire
        ticket_2_id = ObjectId()
        await db.tickets.insert_one({
            "_id": ticket_2_id,
            "subject": f"Nouvelle demande {unique_keyword}",
            "description": f"Problème d'accès au module {unique_keyword} sécurisé.",
            "category": test_category,
            "subcategory": test_subcategory,
            "priority": TicketPriority.HIGH.value,
            "status": TicketStatus.OPEN.value,
            "created_at": now
        })

        print("\n--- Étape 5 : Deuxième routage automatique (adaptation des scores) ---")
        routing_res_2 = await service.auto_route_ticket(str(ticket_2_id))
        print(f"Nouvel Agent sélectionné : {routing_res_2['agent_name']} (ID: {routing_res_2['selected_agent']})")
        print(f"Raison : {routing_res_2['routing_reason']}")
        print(f"Détails du score : {routing_res_2.get('scoring_details')}")

        assert routing_res_2["selected_agent"] == str(agent_b_id), "Agent Beta aurait dû être sélectionné suite à la boucle de feedback !"
        print("[OK] Agent Beta sélectionné suite à l'adaptation dynamique du modèle de feedback.")

        # 7. Contrôle de l'historique d'audit routing_history
        print("\n--- Étape 6 : Vérification de la persistance dans routing_history ---")
        history_entry = await db.routing_history.find_one({"ticket_id": str(ticket_2_id)})
        assert history_entry is not None, "Entrée manquante dans routing_history"
        assert "scoring_details" in history_entry, "scoring_details manquant dans routing_history"
        assert history_entry["scoring_details"]["historical_success_score"] > 0
        print("[OK] Entrée routing_history vérifiée avec scoring_details complet et explicabilité.")

    finally:
        # Nettoyage complet des données temporaires de test
        print("\n--- Nettoyage des données temporaires de test ---")
        await db.teams.delete_one({"_id": team_id})
        await db.agents.delete_many({"_id": {"$in": [agent_a_id, agent_b_id]}})
        await db.tickets.delete_many({"category": test_category})
        clean_ticket_ids = [str(ticket_id)] + ([str(ticket_2_id)] if ticket_2_id else [])
        await db.routing_history.delete_many({"ticket_id": {"$in": clean_ticket_ids}})
        client.close()
        print("[OK] Base de données nettoyée sans laisser de résidus de test.")

    print("\n=== TOUTES LES VÉRIFICATIONS FONCTIONNELLES STEP 2 RÉUSSIES AVEC SUCCÈS ===")


if __name__ == "__main__":
    asyncio.run(run_functional_verification())
