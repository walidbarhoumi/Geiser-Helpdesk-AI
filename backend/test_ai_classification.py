"""
Tests for real-time AI ticket classification (STEP 1).
Run: pytest test_ai_classification.py -v
"""
import pytest
from services.ai.ai_classifier import AIClassifier, GEISER_TAXONOMY
from schemas.schemas import (
    TicketPriority,
    TicketClassificationResponse
)


@pytest.fixture
def classifier():
    return AIClassifier()


@pytest.mark.asyncio
async def test_vpn_incident_classification(classifier):
    subject = "VPN impossible"
    description = "Je ne peux plus me connecter au VPN depuis ce matin, accès distant bloqué."

    result = await classifier.classify_ticket(subject, description)

    assert isinstance(result, TicketClassificationResponse)
    assert result.category == "Infrastructure & Réseau"
    assert result.subcategory in GEISER_TAXONOMY["Infrastructure & Réseau"]
    assert result.subcategory == "VPN & Accès Distant"
    assert result.priority in [TicketPriority.HIGH, TicketPriority.URGENT]
    assert any("vpn" in t.lower() for t in result.tags)
    assert 0.0 <= result.confidence <= 1.0
    assert len(result.reasoning) > 10


@pytest.mark.asyncio
async def test_password_reset_classification(classifier):
    subject = "Mot de passe oublié"
    description = "Je ne peux plus accéder à mon compte session Windows, mon mot de passe a expiré."

    result = await classifier.classify_ticket(subject, description)

    assert isinstance(result, TicketClassificationResponse)
    assert result.category == "Authentification & Accès"
    assert result.subcategory in GEISER_TAXONOMY["Authentification & Accès"]
    assert result.subcategory == "Réinitialisation Mot de passe"
    assert result.priority in [TicketPriority.MEDIUM, TicketPriority.HIGH, TicketPriority.URGENT]
    assert any("mot" in t.lower() or "passe" in t.lower() or "compte" in t.lower() for t in result.tags)
    assert 0.0 <= result.confidence <= 1.0
    assert len(result.reasoning) > 10


@pytest.mark.asyncio
async def test_phishing_security_classification(classifier):
    subject = "Email suspect"
    description = "J'ai reçu un email qui semble être une tentative de phishing me demandant mes identifiants bancaires."

    result = await classifier.classify_ticket(subject, description)

    assert isinstance(result, TicketClassificationResponse)
    assert result.category == "Sécurité IT"
    assert result.subcategory in GEISER_TAXONOMY["Sécurité IT"]
    assert result.subcategory == "Email Suspect / Phishing"
    assert result.priority in [TicketPriority.HIGH, TicketPriority.URGENT]
    assert any("phishing" in t.lower() or "sécurité" in t.lower() or "suspect" in t.lower() for t in result.tags)
    assert 0.0 <= result.confidence <= 1.0
    assert len(result.reasoning) > 10


@pytest.mark.asyncio
async def test_printer_hardware_classification(classifier):
    subject = "Imprimante bloquée"
    description = "L'imprimante réseau du deuxième étage affiche bourrage papier et ne répond plus."

    result = await classifier.classify_ticket(subject, description)

    assert isinstance(result, TicketClassificationResponse)
    assert result.category == "Matériel & Poste de Travail"
    assert result.subcategory in GEISER_TAXONOMY["Matériel & Poste de Travail"]
    assert result.subcategory == "Imprimante & Scanner"
    assert 0.0 <= result.confidence <= 1.0
    assert len(result.reasoning) > 10


@pytest.mark.asyncio
async def test_general_inquiry_fallback(classifier):
    subject = "Question diverse"
    description = "Bonjour, pourriez-vous m'indiquer les horaires d'ouverture du support IT ?"

    result = await classifier.classify_ticket(subject, description)

    assert isinstance(result, TicketClassificationResponse)
    assert result.category == "Support Général"
    assert result.subcategory in GEISER_TAXONOMY["Support Général"]
    assert result.priority == TicketPriority.LOW
    assert 0.0 <= result.confidence <= 1.0
    assert len(result.reasoning) > 10


@pytest.mark.asyncio
async def test_api_endpoint_flow():
    """Test using FastAPI TestClient with mocked authenticated user."""
    from main import app
    from core.deps import get_current_user
    from fastapi.testclient import TestClient

    # Mock authenticated user dependency
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "6aada2aeb3dea0b7bfe54e9a",
        "email": "agent.test@geiser.internal",
        "role": "AGENT"
    }

    client = TestClient(app)
    response = client.post(
        "/api/v1/ai/classify-ticket",
        json={
            "subject": "Coupure VPN totale",
            "description": "Impossible de joindre le concentrateur VPN, toute l'équipe est bloquée."
        }
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "Infrastructure & Réseau"
    assert data["subcategory"] == "VPN & Accès Distant"
    assert data["priority"] in ["HIGH", "URGENT"]
    assert isinstance(data["tags"], list)
    assert 0.0 <= data["confidence"] <= 1.0
    assert len(data["reasoning"]) > 5
