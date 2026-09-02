"""
Tests for inbound email triage (support request detection).
Run: pytest test_email_ticket.py -v
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.ai.chatbot_service import ChatbotService
from schemas.schemas import ChatMessage


def make_chatbot():
    db = MagicMock()
    return ChatbotService(db)


@pytest.mark.asyncio
async def test_greeting_email_rejected():
    bot = make_chatbot()
    result = await bot.validate_and_synthesize_email("Bonjour", "")
    assert result["is_valid_ticket"] is False


@pytest.mark.asyncio
async def test_hi_how_are_you_rejected():
    bot = make_chatbot()
    result = await bot.validate_and_synthesize_email("Hi", "comment ça va ?")
    assert result["is_valid_ticket"] is False


@pytest.mark.asyncio
async def test_login_problem_accepted_by_heuristic():
    bot = make_chatbot()
    with patch.object(bot.ollama, "generate_json", new_callable=AsyncMock, return_value=None):
        result = await bot.validate_and_synthesize_email(
            "Problème de compte",
            "Je n'arrive plus à me connecter à mon compte, mon mot de passe ne fonctionne plus.",
        )
    assert result["is_valid_ticket"] is True
    assert result["category"] == "Authentification & Accès"


@pytest.mark.asyncio
async def test_computer_wont_start_accepted():
    bot = make_chatbot()
    with patch.object(bot.ollama, "generate_json", new_callable=AsyncMock, return_value=None):
        result = await bot.validate_and_synthesize_email(
            "PC en panne",
            "Mon ordinateur ne démarre plus après la mise à jour Windows.",
        )
    assert result["is_valid_ticket"] is True
    assert "Matériel" in result["category"] or "Support" in result["category"]


@pytest.mark.asyncio
async def test_payment_error_accepted():
    bot = make_chatbot()
    with patch.object(bot.ollama, "generate_json", new_callable=AsyncMock, return_value=None):
        result = await bot.validate_and_synthesize_email(
            "Erreur paiement",
            "Je rencontre une erreur lors du paiement sur le portail client.",
        )
    assert result["is_valid_ticket"] is True
