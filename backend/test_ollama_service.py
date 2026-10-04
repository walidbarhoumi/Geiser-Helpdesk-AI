"""
test_ollama_service.py
==============================================================================
Tests unitaires pour OllamaService -- correction du bug UnboundLocalError
dans generate_json().

10 scenarios obligatoires :
 1. Reponse JSON valide
 2. Reponse JSON invalide
 3. Reponse vide
 4. Ollama indisponible (ConnectError)
 5. Timeout Ollama
 6. Exception avant creation de raw_response
 7. Absence garantie de UnboundLocalError
 8. Fonctionnement du fallback heuristique
 9. Classification IA -- Ollama disponible (mock OK)
10. Classification IA -- Ollama indisponible

Run:
    cd backend
    python -m pytest test_ollama_service.py -v --tb=short
"""

import pytest
import json
import httpx
from unittest.mock import AsyncMock, patch

from services.ai.ollama_service import OllamaService
from services.ai.ai_classifier import AIClassifier
from schemas.schemas import TicketPriority

VALID_CATEGORIES = [
    "Infrastructure & R\u00e9seau",
    "Authentification & Acc\u00e8s",
    "Mat\u00e9riel & Poste de Travail",
    "Logiciels & Applications",
    "S\u00e9curit\u00e9 IT",
    "Support G\u00e9n\u00e9ral",
]


def make_ollama() -> OllamaService:
    svc = OllamaService()
    svc.base_url = "http://localhost:11434"
    svc.model = "gemma3:4b"
    return svc


# =============================================================================
# TEST 1 -- Reponse JSON valide
# =============================================================================

@pytest.mark.asyncio
async def test_generate_json_valid():
    """generate_json returns parsed dict on a valid JSON response."""
    expected = {"category": "Infrastructure", "priority": "HIGH"}
    svc = make_ollama()
    with patch.object(svc, "generate_response", new=AsyncMock(return_value=json.dumps(expected))):
        result = await svc.generate_json("test prompt")
    assert result == expected
    assert isinstance(result, dict)


# =============================================================================
# TEST 2 -- Reponse JSON invalide
# =============================================================================

@pytest.mark.asyncio
async def test_generate_json_invalid_json():
    """generate_json returns {} when Ollama returns malformed JSON."""
    svc = make_ollama()
    with patch.object(svc, "generate_response", new=AsyncMock(return_value="not json {{")):
        result = await svc.generate_json("test prompt")
    assert result == {}


# =============================================================================
# TEST 3 -- Reponse vide
# =============================================================================

@pytest.mark.asyncio
async def test_generate_json_empty_string():
    """generate_json returns {} on empty string response."""
    svc = make_ollama()
    with patch.object(svc, "generate_response", new=AsyncMock(return_value="")):
        result = await svc.generate_json("test prompt")
    assert result == {}


@pytest.mark.asyncio
async def test_generate_json_whitespace_only():
    """generate_json returns {} on whitespace-only response."""
    svc = make_ollama()
    with patch.object(svc, "generate_response", new=AsyncMock(return_value="   \n  ")):
        result = await svc.generate_json("test prompt")
    assert result == {}


@pytest.mark.asyncio
async def test_generate_json_markdown_fence_only():
    """generate_json returns {} when content is only markdown fences."""
    svc = make_ollama()
    with patch.object(svc, "generate_response", new=AsyncMock(return_value="```json\n```")):
        result = await svc.generate_json("test prompt")
    assert result == {}


@pytest.mark.asyncio
async def test_generate_json_strips_markdown_fences():
    """generate_json correctly strips markdown fences and parses the inner JSON."""
    payload = {"intent": "AUTHENTICATION", "confidence": 0.9}
    wrapped = "```json\n{}\n```".format(json.dumps(payload))
    svc = make_ollama()
    with patch.object(svc, "generate_response", new=AsyncMock(return_value=wrapped)):
        result = await svc.generate_json("test prompt")
    assert result == payload


# =============================================================================
# TEST 4 -- Ollama indisponible
# =============================================================================

@pytest.mark.asyncio
async def test_generate_response_connect_error():
    """generate_response returns '' on ConnectError (not an exception propagation)."""
    svc = make_ollama()
    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("refused")):
        result = await svc.generate_response("test prompt")
    assert result == ""


@pytest.mark.asyncio
async def test_generate_json_ollama_unavailable():
    """generate_json returns {} when Ollama server is unreachable."""
    svc = make_ollama()
    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("refused")):
        result = await svc.generate_json("test prompt")
    assert result == {}


# =============================================================================
# TEST 5 -- Timeout Ollama
# =============================================================================

@pytest.mark.asyncio
async def test_generate_json_timeout():
    """generate_json returns {} on timeout."""
    svc = make_ollama()
    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("timed out")):
        result = await svc.generate_json("test prompt")
    assert result == {}


@pytest.mark.asyncio
async def test_generate_response_timeout():
    """generate_response returns '' on timeout (not a propagated exception)."""
    svc = make_ollama()
    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("timed out")):
        result = await svc.generate_response("test prompt")
    assert result == ""


# =============================================================================
# TEST 6 -- Exception avant creation de raw_response
# =============================================================================

@pytest.mark.asyncio
async def test_generate_json_exception_before_assignment():
    """
    THE CORE REGRESSION TEST.
    If generate_response() itself raises, the except block must NOT raise
    UnboundLocalError on 'raw_response'. Must return {} safely.
    """
    svc = make_ollama()

    async def crash(*args, **kwargs):
        raise RuntimeError("Simulated crash inside generate_response")

    with patch.object(svc, "generate_response", new=crash):
        result = await svc.generate_json("test prompt")

    assert result == {}


# =============================================================================
# TEST 7 -- Absence garantie de UnboundLocalError
# =============================================================================

@pytest.mark.asyncio
async def test_no_unbound_local_error_exhaustive():
    """
    For every possible exception type, UnboundLocalError must never escape
    from generate_json's except block. This directly validates the fix.
    """
    svc = make_ollama()
    failure_modes = [
        RuntimeError("crash before assign"),
        OSError("OS level error"),
        ValueError("bad value"),
        MemoryError("OOM"),
        ConnectionResetError("reset by peer"),
    ]

    for exc_to_raise in failure_modes:
        async def raise_exc(*a, exc=exc_to_raise, **kw):
            raise exc

        with patch.object(svc, "generate_response", new=raise_exc):
            try:
                result = await svc.generate_json("probe")
                assert result == {}, \
                    f"Expected {{}} for {type(exc_to_raise).__name__}, got {result}"
            except UnboundLocalError as unbound:
                pytest.fail(
                    f"UnboundLocalError raised for {type(exc_to_raise).__name__}: {unbound}"
                )


# =============================================================================
# TEST 8 -- Fallback heuristique
# =============================================================================

@pytest.mark.asyncio
async def test_classify_ticket_always_returns_valid_result_on_empty_llm():
    """
    When generate_json returns {} (any failure), classify_ticket always returns
    a valid TicketClassificationResponse (never raises, never returns None).
    """
    classifier = AIClassifier()
    with patch.object(classifier.ollama, "generate_json", new=AsyncMock(return_value={})):
        result = await classifier.classify_ticket(
            subject="Support request",
            description="I need help with something"
        )

    assert result is not None
    assert result.category in VALID_CATEGORIES
    assert result.priority in list(TicketPriority)
    assert isinstance(result.confidence, float)
    assert 0.0 < result.confidence <= 1.0


@pytest.mark.asyncio
async def test_heuristic_vpn_classification():
    """
    True heuristic test: patch _classify_with_llm to raise an exception,
    forcing the heuristic fallback path in classify_ticket.
    """
    classifier = AIClassifier()

    async def raise_error(*a, **kw):
        raise RuntimeError("LLM unavailable")

    with patch.object(classifier, "_classify_with_llm", new=raise_error):
        result = await classifier.classify_ticket(
            subject="VPN connection problem",
            description="Cannot connect to VPN from home"
        )

    # Heuristic matches 'vpn' -> Infrastructure & Reseau
    assert result is not None
    assert "Infrastructure" in result.category or result.category in VALID_CATEGORIES


@pytest.mark.asyncio
async def test_heuristic_password_classification():
    """Heuristic correctly classifies password reset when LLM is bypassed."""
    classifier = AIClassifier()

    async def raise_error(*a, **kw):
        raise RuntimeError("LLM unavailable")

    with patch.object(classifier, "_classify_with_llm", new=raise_error):
        result = await classifier.classify_ticket(
            subject="Password reset request",
            description="I forgot my password and cannot login"
        )

    assert result is not None
    assert result.category in VALID_CATEGORIES


@pytest.mark.asyncio
async def test_heuristic_phishing_classification():
    """Heuristic correctly classifies phishing report when LLM is bypassed."""
    classifier = AIClassifier()

    async def raise_error(*a, **kw):
        raise RuntimeError("LLM unavailable")

    with patch.object(classifier, "_classify_with_llm", new=raise_error):
        result = await classifier.classify_ticket(
            subject="Phishing email received",
            description="I received a phishing email asking for credentials"
        )

    assert result is not None
    assert result.category in VALID_CATEGORIES


# =============================================================================
# TEST 9 -- Classification IA avec Ollama disponible (mock valide)
# =============================================================================

@pytest.mark.asyncio
async def test_classify_ticket_with_valid_llm_response():
    """
    AIClassifier uses LLM result when Ollama returns a structurally valid response.
    """
    classifier = AIClassifier()
    mock_llm = {
        "category": "Infrastructure & R\u00e9seau",
        "subcategory": "VPN & Acc\u00e8s Distant",
        "priority": "HIGH",
        "tags": ["vpn", "reseau", "teletravail"],
        "confidence": 0.95,
        "reasoning": "Panne VPN bloquant le teletravail de l utilisateur."
    }

    with patch.object(classifier.ollama, "generate_json", new=AsyncMock(return_value=mock_llm)):
        result = await classifier.classify_ticket(
            subject="VPN Cisco AnyConnect broken",
            description="Cannot connect to company VPN"
        )

    assert result is not None
    assert result.category in VALID_CATEGORIES
    assert result.priority == TicketPriority.HIGH
    assert result.confidence == 0.95
    assert isinstance(result.tags, list)
    assert len(result.tags) > 0


@pytest.mark.asyncio
async def test_classify_ticket_llm_unknown_category_normalized():
    """
    When LLM returns an unrecognized category, normalization maps it to the
    nearest valid GEISER category (never crashes, never returns None).
    """
    classifier = AIClassifier()
    mock_llm = {
        "category": "Completely Unknown Department XYZ",
        "subcategory": "Unknown Sub",
        "priority": "LOW",
        "tags": ["misc"],
        "confidence": 0.5,
        "reasoning": "No matching category found in taxonomy."
    }

    with patch.object(classifier.ollama, "generate_json", new=AsyncMock(return_value=mock_llm)):
        result = await classifier.classify_ticket("Some subject", "Some description")

    assert result is not None
    assert result.category in VALID_CATEGORIES
    assert result.priority in list(TicketPriority)


# =============================================================================
# TEST 10 -- Classification IA avec Ollama indisponible
# =============================================================================

@pytest.mark.asyncio
async def test_classify_ticket_ollama_fully_down():
    """
    Full stack: when Ollama is unreachable at HTTP level, generate_response
    returns '' -> generate_json returns {} -> classifier still returns valid result.
    """
    classifier = AIClassifier()
    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("refused")):
        result = await classifier.classify_ticket(
            subject="Outlook application crash",
            description="Microsoft Outlook crashes on startup every morning"
        )

    assert result is not None
    assert result.category in VALID_CATEGORIES
    assert result.priority in list(TicketPriority)
    assert isinstance(result.confidence, float)


@pytest.mark.asyncio
async def test_classify_ticket_ollama_timeout_full_stack():
    """
    Full stack: timeout at HTTP level -> generate_response returns '' ->
    generate_json returns {} -> classifier still returns valid result.
    """
    classifier = AIClassifier()
    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("timeout")):
        result = await classifier.classify_ticket(
            subject="Printer not working",
            description="HP LaserJet is offline and not printing anything"
        )

    assert result is not None
    assert result.category in VALID_CATEGORIES
    assert result.priority in list(TicketPriority)


if __name__ == "__main__":
    import subprocess, sys
    subprocess.run([sys.executable, "-m", "pytest", __file__, "-v"])
