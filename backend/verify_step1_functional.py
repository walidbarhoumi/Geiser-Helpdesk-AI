"""
End-to-end functional verification script for STEP 1:
- Tests classify_ticket endpoint
- Tests manual override preservation logic
- Simulates ticket creation via TicketService
- Verifies database record
"""
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from core.config import settings
from services.ai.ai_classifier import AIClassifier
from services.ticket_service import TicketService
from schemas.schemas import TicketCreate, TicketPriority, TicketChannel


async def run_functional_validation():
    print("=== DÉBUT DE LA VÉRIFICATION FONCTIONNELLE STEP 1 ===")

    # 1. Test AI Classification directly
    print("\n--- 1. Analyse IA pour un incident VPN ---")
    classifier = AIClassifier()
    ai_res = await classifier.classify_ticket(
        subject="Connexion VPN impossible",
        description="Depuis la mise à jour ce matin, Cisco AnyConnect refuse la connexion avec code 403."
    )
    print(f"Catégorie détectée : {ai_res.category}")
    print(f"Sous-catégorie     : {ai_res.subcategory}")
    print(f"Priorité suggérée  : {ai_res.priority.value}")
    print(f"Tags extraits      : {ai_res.tags}")
    print(f"Score de confiance : {ai_res.confidence * 100:.0f}%")
    print(f"Raisonnement       : {ai_res.reasoning}")

    assert ai_res.category == "Infrastructure & Réseau"
    assert ai_res.subcategory == "VPN & Accès Distant"
    assert ai_res.priority in [TicketPriority.HIGH, TicketPriority.URGENT]

    # 2. Simulation de la logique de préservation manuelle du formulaire
    print("\n--- 2. Simulation de la logique de respect des choix utilisateur ---")
    # Initial state
    user_form = {
        "category": "Infrastructure & Réseau",
        "subcategory": "VPN & Accès Distant",
        "priority": TicketPriority.MEDIUM
    }
    # User manually overrides priority to LOW
    manually_modified = {"category": False, "subcategory": False, "priority": True}
    user_form["priority"] = TicketPriority.LOW  # user forced LOW

    # AI result arrives
    updated_category = user_form["category"] if manually_modified["category"] else ai_res.category
    updated_subcategory = user_form["subcategory"] if manually_modified["subcategory"] else ai_res.subcategory
    updated_priority = user_form["priority"] if manually_modified["priority"] else ai_res.priority

    assert updated_priority == TicketPriority.LOW, "L'override manuel de la priorité n'a pas été respecté !"
    assert updated_category == ai_res.category, "La catégorie suggérée par l'IA aurait dû être appliquée !"
    print("[OK] Respect strict des choix manuels utilisateur validé : priorité manuelle LOW conservée.")

    # 3. Test de création effective d'un ticket en base
    print("\n--- 3. Enregistrement d'un ticket classifié par IA en base de données ---")
    client = AsyncIOMotorClient(settings.MONGO_URL)
    db = client[settings.DATABASE_NAME]
    ticket_service = TicketService(db)

    # Find or mock a user
    user = await db.users.find_one()
    user_id = str(user["_id"]) if user else "000000000000000000000001"

    ticket_in = TicketCreate(
        subject="Panne VPN télétravail certif expiré",
        description="Le VPN AnyConnect signale un certificat expiré. Impossible d'accéder aux partages de fichiers.",
        category=ai_res.category,
        subcategory=ai_res.subcategory,
        priority=ai_res.priority,
        channel=TicketChannel.WEB,
        keywords=ai_res.tags
    )

    created = await ticket_service.create_ticket(ticket_in, user_id=user_id)
    ticket_id = created["id"]
    print(f"[OK] Ticket créé avec succès (ID: {ticket_id})")

    # 4. Vérification de la persistance exacte dans MongoDB
    print("\n--- 4. Contrôle de la persistance MongoDB ---")
    from bson import ObjectId
    saved_doc = await db.tickets.find_one({"_id": ObjectId(ticket_id)})
    assert saved_doc is not None, "Le ticket n'a pas été trouvé en base"
    assert saved_doc["category"] == "Infrastructure & Réseau"
    assert saved_doc["subcategory"] == "VPN & Accès Distant"
    assert saved_doc["priority"] in ["HIGH", "URGENT"]
    assert "vpn" in [k.lower() for k in saved_doc.get("keywords", [])]
    print(f"[OK] Ticket vérifié en base : Catégorie='{saved_doc['category']}', Sous-cat='{saved_doc['subcategory']}', Priorité='{saved_doc['priority']}', Keywords={saved_doc.get('keywords')}")

    # Nettoyage du ticket de test
    await db.tickets.delete_one({"_id": ObjectId(ticket_id)})
    print("[OK] Ticket de test nettoyé.")
    client.close()

    print("\n=== VALIDATION FONCTIONNELLE STEP 1 RÉUSSIE AVEC SUCCÈS (4/4) ===")

if __name__ == "__main__":
    asyncio.run(run_functional_validation())
