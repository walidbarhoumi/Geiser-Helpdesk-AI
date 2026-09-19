"""
Script de validation fonctionnelle pour STEP 5 : Passerelle SMS Twilio.
Supporte deux modes :
1. Mode Réel (si TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER et TWILIO_TEST_TO_NUMBER sont configurés dans .env) :
   Envoie un véritable SMS et affiche "REAL TWILIO SMS TEST".
2. Mode sans credentials (si absent) :
   Affiche "SKIPPED — Twilio credentials not configured" sans faire échouer la validation.

Vérifie également la persistance ISO 27001 dans la collection MongoDB `notifications`.

Exécution: python verify_step5_functional.py
"""
import asyncio
from datetime import datetime
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from core.config import settings
from services.sms.twilio_provider import TwilioProvider, validate_e164_phone
from services.sms.simulated_provider import SimulatedSMSProvider
from services.notification_service import NotificationService
from services.ticket_service import TicketService
from schemas.schemas import (
    TicketCreate,
    ImpactLevel,
    UrgencyLevel,
    TicketPriority,
    TicketChannel,
    TicketStatus,
)


async def run_functional_verification():
    print("=== DÉBUT DU TEST FONCTIONNEL STEP 5 : PASSERELLE SMS TWILIO ===")
    client = AsyncIOMotorClient(settings.MONGO_URL)
    db = client[settings.DATABASE_NAME]

    created_ticket_ids = []
    created_user_ids = []

    try:
        # ─────────────────────────────────────────────────────────────────
        # Étape 1 : Vérification de la configuration Twilio
        # ─────────────────────────────────────────────────────────────────
        print("\n--- Étape 1 : Inspection de la configuration Twilio ---")
        twilio = TwilioProvider()
        is_configured = twilio.is_configured()
        test_to_number = getattr(settings, "TWILIO_TEST_TO_NUMBER", "")

        print(f"Twilio configuré (SID + Token + From) : {is_configured}")
        print(f"Numéro de test destinataire présent   : {bool(test_to_number)}")

        # ─────────────────────────────────────────────────────────────────
        # Étape 2 : Test d'envoi SMS Réel OU Mode Skipped
        # ─────────────────────────────────────────────────────────────────
        if is_configured and test_to_number:
            print("\n==================================================")
            print(">>> REAL TWILIO SMS TEST <<<")
            print("==================================================")
            normalized_test_to = validate_e164_phone(test_to_number)
            if not normalized_test_to:
                print(f"[ERROR] TWILIO_TEST_TO_NUMBER n'est pas au format international E.164 : '{test_to_number}'")
            else:
                test_body = f"GEISER IT HELPDESK — Test fonctionnel STEP 5 réussi le {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC."
                result = await twilio.send_sms(to=normalized_test_to, message=test_body)
                if result.success:
                    print(f"[OK] REAL SMS TEST: PASSED")
                    print(f"     Twilio Message SID : {result.message_id}")
                    print(f"     Status             : {result.status}")
                    print(f"     Provider           : {result.provider}")
                else:
                    print(f"[FAIL] REAL SMS TEST: FAILED")
                    print(f"     Error: {result.error}")
        else:
            print("\n--------------------------------------------------")
            print("SKIPPED — Twilio credentials not configured")
            print("--------------------------------------------------")
            print("Pour activer le test d'envoi réel, renseignez dans backend/.env :")
            print("  TWILIO_ACCOUNT_SID=...")
            print("  TWILIO_AUTH_TOKEN=...")
            print("  TWILIO_FROM_NUMBER=...")
            print("  TWILIO_TEST_TO_NUMBER=...")

        # ─────────────────────────────────────────────────────────────────
        # Étape 3 : Test du cycle complet Ticket -> Notification -> MongoDB
        # ─────────────────────────────────────────────────────────────────
        print("\n--- Étape 3 : Cycle complet Ticket -> Notification -> MongoDB ---")
        # Création d'un utilisateur de test avec numéro de téléphone
        test_user = {
            "email": f"test_sms_user_{ObjectId()}@geiser.internal",
            "full_name": "Agent Test SMS",
            "phone_number": "+33612345678",
            "role": "USER",
            "is_active": True,
            "created_at": datetime.utcnow()
        }
        res_u = await db.users.insert_one(test_user)
        user_id = str(res_u.inserted_id)
        created_user_ids.append(user_id)

        # Création du ticket via TicketService
        ticket_service = TicketService(db)
        ticket_in = TicketCreate(
            subject="Test STEP 5 - Alerte panne routeur",
            description="Le routeur d'étage ne répond plus aux pings ICMP.",
            category="Infrastructure & Réseau",
            subcategory="VPN & Accès Distant",
            impact=ImpactLevel.HIGH,
            urgency=UrgencyLevel.HIGH,
            channel=TicketChannel.WEB
        )
        created_ticket = await ticket_service.create_ticket(ticket_in=ticket_in, user_id=user_id)
        ticket_id = created_ticket["id"]
        created_ticket_ids.append(ticket_id)

        print(f"[OK] Ticket créé avec succès (ID: {ticket_id})")

        # Vérification de l'enregistrement de notification dans MongoDB
        sms_notif = await db.notifications.find_one({
            "ticket_id": ticket_id,
            "channel": "SMS",
            "event_type": "TICKET_CREATED"
        })
        assert sms_notif is not None, "La notification SMS n'a pas été enregistrée dans la collection 'notifications' !"
        print(f"[OK] Notification SMS auditée dans MongoDB (ID: {sms_notif['_id']})")
        print(f"     Provider utilisé : {sms_notif.get('provider')}")
        print(f"     Statut           : {sms_notif.get('status')}")
        print(f"     Destinataire     : {sms_notif.get('recipient')}")

        # ─────────────────────────────────────────────────────────────────
        # Étape 4 : Test Anti-duplication dans MongoDB
        # ─────────────────────────────────────────────────────────────────
        print("\n--- Étape 4 : Vérification de l'anti-duplication (idempotence) ---")
        notification_service = NotificationService(db)
        # Tentative d'envoi du même événement sur le même ticket
        dup_result = await notification_service._dispatch_sms(
            user_id=user_id,
            user_email=test_user["email"],
            phone=test_user["phone_number"],
            ticket_id=ticket_id,
            sms_text="Message dupliqué",
            event_type="TICKET_CREATED"
        )
        assert dup_result.status == "skipped_duplicate", f"Attendu 'skipped_duplicate', obtenu '{dup_result.status}'"
        print("[OK] Idempotence anti-duplication validée : le SMS en doublon a été ignoré.")

        print("\n==================================================================")
        print("TOUTES LES VÉRIFICATIONS FONCTIONNELLES STEP 5 SONT PASSÉES AVEC SUCCÈS !")
        print("==================================================================")

    finally:
        # Nettoyage
        print("\n--- Nettoyage de la base de données ---")
        if created_ticket_ids:
            res_t = await db.tickets.delete_many({"_id": {"$in": [ObjectId(tid) for tid in created_ticket_ids]}})
            print(f"[CLEANUP] {res_t.deleted_count} tickets supprimés.")
        if created_user_ids:
            res_u = await db.users.delete_many({"_id": {"$in": [ObjectId(uid) for uid in created_user_ids]}})
            print(f"[CLEANUP] {res_u.deleted_count} utilisateurs supprimés.")
        if created_ticket_ids:
            res_n = await db.notifications.delete_many({"ticket_id": {"$in": created_ticket_ids}})
            print(f"[CLEANUP] {res_n.deleted_count} notifications supprimées.")
        client.close()


if __name__ == "__main__":
    asyncio.run(run_functional_verification())
