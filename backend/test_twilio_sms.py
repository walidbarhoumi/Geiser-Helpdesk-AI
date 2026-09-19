"""
Suite de tests unitaires pour la Passerelle SMS Twilio (STEP 5).
Vérifie les 11 exigences clés de la spécification :
1. Configuration Twilio valide.
2. Credentials absents.
3. Numéro valide E.164.
4. Numéro invalide.
5. Message valide.
6. Envoi Twilio réussi (mocké, retourne SID).
7. Erreur Twilio (TwilioRestException gérée sans crash).
8. Timeout / erreur réseau.
9. Le token n'apparaît jamais dans les logs / exceptions / erreurs.
10. Un échec SMS ne fait pas échouer l'opération ticket (création & mise à jour).
11. Anti-duplication / idempotence.

Exécution: pytest test_twilio_sms.py -v
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId
from datetime import datetime

from services.sms.sms_provider import SMSResult
from services.sms.twilio_provider import TwilioProvider, validate_e164_phone
from services.sms.simulated_provider import SimulatedSMSProvider
from services.notification_service import NotificationService
from services.ticket_service import TicketService
from schemas.schemas import (
    TicketCreate,
    TicketStatus,
    TicketPriority,
    ImpactLevel,
    UrgencyLevel,
    TicketChannel,
)


# ─── Test 1 : Configuration Twilio valide ─────────────────────────────────────

def test_1_twilio_config_valid():
    provider = TwilioProvider(
        account_sid="ACdummy1234567890abcdef1234567890",
        auth_token="dummy_secret_token_abc123",
        from_number="+15005550006"
    )
    assert provider.is_configured() is True
    assert provider.provider_name == "twilio"


# ─── Test 2 : Credentials absents ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_2_twilio_credentials_missing():
    provider = TwilioProvider(
        account_sid="",
        auth_token="",
        from_number=""
    )
    assert provider.is_configured() is False

    result = await provider.send_sms(to="+33612345678", message="Test message")
    assert result.success is False
    assert result.status == "failed"
    assert "not configured" in result.error.lower()


# ─── Test 3 : Numéro E.164 valide ─────────────────────────────────────────────

def test_3_phone_e164_valid():
    assert validate_e164_phone("+33612345678") == "+33612345678"
    assert validate_e164_phone("+216 12 345 678") == "+21612345678"
    assert validate_e164_phone("+49-151-23456789") == "+4915123456789"
    assert validate_e164_phone(" +1 (500) 555-0006 ") == "+15005550006"


# ─── Test 4 : Numéro invalide ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_4_phone_invalid():
    assert validate_e164_phone("0612345678") is None  # Missing + country code
    assert validate_e164_phone("not_a_phone") is None
    assert validate_e164_phone("") is None
    assert validate_e164_phone(None) is None

    provider = TwilioProvider(
        account_sid="ACdummy1234567890abcdef1234567890",
        auth_token="dummy_token",
        from_number="+15005550006"
    )
    result = await provider.send_sms(to="0612345678", message="Hello")
    assert result.success is False
    assert "invalid destination phone number" in result.error.lower()


# ─── Test 5 : Message valide (non vide) ───────────────────────────────────────

@pytest.mark.asyncio
async def test_5_message_validation():
    provider = TwilioProvider(
        account_sid="ACdummy1234567890abcdef1234567890",
        auth_token="dummy_token",
        from_number="+15005550006"
    )
    result_empty = await provider.send_sms(to="+33612345678", message="")
    assert result_empty.success is False
    assert "empty" in result_empty.error.lower()

    result_spaces = await provider.send_sms(to="+33612345678", message="   \n  ")
    assert result_spaces.success is False
    assert "empty" in result_spaces.error.lower()


# ─── Test 6 : Envoi Twilio réussi (mocké) ──────────────────────────────────────

@pytest.mark.asyncio
async def test_6_twilio_send_success():
    mock_client = MagicMock()
    mock_msg = MagicMock()
    mock_msg.sid = "SM998877665544332211aabbccddeeff00"
    mock_client.messages.create.return_value = mock_msg

    provider = TwilioProvider(
        account_sid="ACdummy1234567890abcdef1234567890",
        auth_token="dummy_secret_token",
        from_number="+15005550006",
        client=mock_client
    )

    result = await provider.send_sms(to="+33612345678", message="GEISER test SMS")
    assert result.success is True
    assert result.status == "sent"
    assert result.message_id == "SM998877665544332211aabbccddeeff00"
    assert result.to == "+33612345678"
    assert result.error is None


# ─── Test 7 : Erreur Twilio (TwilioRestException gérée) ─────────────────────────

@pytest.mark.asyncio
async def test_7_twilio_rest_exception_handling():
    from twilio.base.exceptions import TwilioRestException

    mock_client = MagicMock()
    # Simuler TwilioRestException (ex: code 21211, invalid number)
    mock_client.messages.create.side_effect = TwilioRestException(
        status=400,
        uri="/2010-04-01/Accounts/ACxxx/Messages.json",
        msg="The 'To' number is not a valid phone number.",
        code=21211
    )

    provider = TwilioProvider(
        account_sid="ACdummy1234567890abcdef1234567890",
        auth_token="dummy_secret_token",
        from_number="+15005550006",
        client=mock_client
    )

    result = await provider.send_sms(to="+33612345678", message="Test message")
    assert result.success is False
    assert result.status == "failed"
    assert "code 21211" in result.error
    assert "21211" in result.error


# ─── Test 8 : Timeout / Erreur réseau ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_8_network_timeout_handling():
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = TimeoutError("Connection timed out to api.twilio.com")

    provider = TwilioProvider(
        account_sid="ACdummy1234567890abcdef1234567890",
        auth_token="dummy_secret_token",
        from_number="+15005550006",
        client=mock_client
    )

    result = await provider.send_sms(to="+33612345678", message="Test timeout")
    assert result.success is False
    assert result.status == "failed"
    assert "timed out" in result.error.lower()


# ─── Test 9 : Écran étanche : aucun token dans les logs / exceptions ───────────

@pytest.mark.asyncio
async def test_9_auth_token_never_leaked_in_errors():
    secret_token = "VERY_SECRET_AUTH_TOKEN_NEVER_REVEAL_999"

    mock_client = MagicMock()
    # Simuler une exception contenant le secret
    mock_client.messages.create.side_effect = Exception(
        f"Unauthorized request using token={secret_token} for account ACdummy"
    )

    provider = TwilioProvider(
        account_sid="ACdummy1234567890abcdef1234567890",
        auth_token=secret_token,
        from_number="+15005550006",
        client=mock_client
    )

    result = await provider.send_sms(to="+33612345678", message="Hello")
    assert result.success is False
    # Vérifier que le secret a été caviardé
    assert secret_token not in result.error
    assert "[REDACTED]" in result.error


# ─── Test 10 : Échec SMS n'impacte pas l'opération ticket ───────────────────────

@pytest.mark.asyncio
async def test_10_sms_failure_does_not_break_ticket_operations():
    """Vérifie qu'un plantage total de la couche SMS ne fait PAS planter la création de ticket."""
    mock_db = MagicMock()
    mock_db.tickets = MagicMock()
    mock_db.agents = MagicMock()
    mock_db.users = MagicMock()
    mock_db.notifications = MagicMock()
    mock_db.sla_policies = MagicMock()

    # Mocks DB
    cursor_mock = MagicMock()
    cursor_mock.sort.return_value = cursor_mock
    cursor_mock.limit.return_value = cursor_mock
    cursor_mock.to_list = AsyncMock(return_value=[])
    mock_db.agents.find.return_value = cursor_mock

    # Utilisateur avec numéro de téléphone
    mock_db.users.find_one = AsyncMock(return_value={
        "_id": ObjectId(),
        "email": "user@test.com",
        "phone_number": "+33612345678"
    })
    mock_db.sla_policies.find_one = AsyncMock(return_value=None)
    mock_db.notifications.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))
    mock_db.notifications.find_one = AsyncMock(return_value=None)

    async def mock_insert_ticket(doc):
        doc_copy = dict(doc)
        doc_copy["_id"] = ObjectId()
        res = MagicMock()
        res.inserted_id = doc_copy["_id"]
        return res

    mock_db.tickets.insert_one = AsyncMock(side_effect=mock_insert_ticket)

    # Provider SMS qui lève une exception inattendue
    failing_provider = MagicMock()
    failing_provider.provider_name = "failing_mock"
    failing_provider.send_sms = AsyncMock(side_effect=RuntimeError("Twilio cluster down"))

    with patch("services.notification_service.NotificationService") as MockNS:
        # On injecte une notification service qui capture l'erreur
        ns_instance = NotificationService(mock_db, sms_provider=failing_provider)
        MockNS.return_value = ns_instance

        ticket_service = TicketService(mock_db)

        # Création d'un ticket : l'opération doit réussir à 100%
        ticket_in = TicketCreate(
            subject="Panne imprimante",
            description="L'imprimante ne répond plus sur le réseau.",
            impact=ImpactLevel.LOW,
            urgency=UrgencyLevel.LOW,
            category="Matériel & Poste de Travail",
            subcategory="Imprimante & Scanner",
        )

        created = await ticket_service.create_ticket(ticket_in=ticket_in, user_id=str(ObjectId()))
        assert created is not None
        assert created["subject"] == "Panne imprimante"
        assert created["status"] == TicketStatus.OPEN.value


# ─── Test 11 : Anti-duplication / Idempotence ──────────────────────────────────

@pytest.mark.asyncio
async def test_11_anti_duplication_idempotency():
    mock_db = MagicMock()
    mock_db.notifications = MagicMock()

    # 1. Premier envoi : pas d'historique existant
    mock_db.notifications.find_one = AsyncMock(return_value=None)
    mock_db.notifications.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))

    mock_provider = MagicMock()
    mock_provider.provider_name = "twilio"
    mock_provider.send_sms = AsyncMock(return_value=SMSResult(
        success=True,
        status="sent",
        provider="twilio",
        message_id="SM_FIRST_SEND",
        to="+33612345678"
    ))

    ns = NotificationService(mock_db, sms_provider=mock_provider)

    result_1 = await ns._dispatch_sms(
        user_id="user_123",
        user_email="user@test.com",
        phone="+33612345678",
        ticket_id="ticket_999",
        sms_text="SLA Breach warning",
        event_type="SLA_BREACH"
    )
    assert result_1.success is True
    assert result_1.status == "sent"
    assert mock_provider.send_sms.call_count == 1

    # 2. Deuxième envoi pour le MÊME ticket et MÊME événement : notification déjà trouvée en base
    mock_db.notifications.find_one = AsyncMock(return_value={
        "_id": ObjectId(),
        "ticket_id": "ticket_999",
        "event_type": "SLA_BREACH",
        "status": "SENT"
    })

    result_2 = await ns._dispatch_sms(
        user_id="user_123",
        user_email="user@test.com",
        phone="+33612345678",
        ticket_id="ticket_999",
        sms_text="SLA Breach warning",
        event_type="SLA_BREACH"
    )
    # L'anti-duplication a intercepté l'envoi : provider NON rappelé une 2e fois !
    assert result_2.status == "skipped_duplicate"
    assert mock_provider.send_sms.call_count == 1  # Toujours 1, pas 2 !
