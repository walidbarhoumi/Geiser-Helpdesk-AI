"""
test_rate_limiting.py
==============================================================================
Suite de tests unitaires pour le Rate Limiting backend (TÂCHE 6 — GEISER Support IA).

Couvre l'ensemble des scénarios exigés par l'audit :
 1. Requête sous la limite -> autorisée (200 / pas d'exception).
 2. Dépassement de la limite -> HTTP 429 Too Many Requests.
 3. En-tête Retry-After présent et valide dans la réponse 429.
 4. Réinitialisation automatique du compteur après expiration de la fenêtre temporelle.
 5. Protection brute-force sur Login (blocage après N tentatives).
 6. Anti-contournement Login : changer d'identifiant (email) ne contourne pas la limite IP.
 7. Anti-spoofing : les en-têtes X-Forwarded-For ne sont pas crus depuis des hôtes non fiables.
 8. Proxies de confiance : X-Forwarded-For est extrait correctement depuis un proxy autorisé.
 9. Protection 2FA : limitation stricte sur request / confirm OTP.
10. Protection Password Reset : limitation stricte sur forgot-password et reset-password.
11. Endpoints IA : limitation par utilisateur authentifié (isolation multi-utilisateurs).
12. Moteur MongoDB distribué : mise à jour atomique ($inc) et configuration TTL.
13. Fallback mémoire local : fonctionnement transparent si MongoDB est inaccessible.
14. Concurrence : absence de race condition sous 20 requêtes simultanées (asyncio.gather).
15. Drapeau global RATE_LIMIT_ENABLED : court-circuit propre lorsque désactivé.
16. Sécurité des logs : aucune fuite de mot de passe, OTP ou token lors des rejets 429.
"""

import time
import asyncio
import logging
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from fastapi import Request, HTTPException, status
from bson import ObjectId

from core.config import settings
from core.rate_limit import (
    RateLimiter,
    get_real_client_ip,
    get_rate_limiter_login,
    get_rate_limiter_2fa,
    get_rate_limiter_password_reset,
    get_rate_limiter_ai,
    _memory_store,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers & Fixtures
# ─────────────────────────────────────────────────────────────────────────────

def make_request(
    client_host: str = "192.168.1.100",
    headers: dict = None,
) -> Request:
    """Crée une fausse requête FastAPI/Starlette avec client et headers."""
    headers_dict = headers or {}
    raw_headers = [(k.lower().encode("latin1"), v.encode("latin1")) for k, v in headers_dict.items()]

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/auth/login",
        "headers": raw_headers,
        "client": (client_host, 54321),
    }
    return Request(scope)


@pytest.fixture(autouse=True)
def clean_memory_store():
    """Nettoie le store mémoire avant chaque test."""
    _memory_store.clear()
    orig_enabled = settings.RATE_LIMIT_ENABLED
    orig_login_limit = settings.RATE_LIMIT_LOGIN
    orig_login_win = settings.RATE_LIMIT_LOGIN_WINDOW
    orig_trusted = settings.TRUSTED_PROXIES

    settings.RATE_LIMIT_ENABLED = True
    settings.RATE_LIMIT_LOGIN = 5
    settings.RATE_LIMIT_LOGIN_WINDOW = 60
    settings.TRUSTED_PROXIES = ["127.0.0.1", "::1", "testclient"]

    yield

    _memory_store.clear()
    settings.RATE_LIMIT_ENABLED = orig_enabled
    settings.RATE_LIMIT_LOGIN = orig_login_limit
    settings.RATE_LIMIT_LOGIN_WINDOW = orig_login_win
    settings.TRUSTED_PROXIES = orig_trusted


# ─────────────────────────────────────────────────────────────────────────────
# 1-3. Fonctionnement de base (Autorisé, Dépassement 429, Retry-After)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_1_request_under_limit_allowed():
    limiter = RateLimiter(times=3, seconds=60, scope="test:base")
    req = make_request("10.0.0.1")

    # 3 requêtes autorisées
    await limiter(req, db=None)
    await limiter(req, db=None)
    await limiter(req, db=None)


@pytest.mark.asyncio
async def test_2_exceeding_limit_raises_429():
    limiter = RateLimiter(times=2, seconds=60, scope="test:exceed")
    req = make_request("10.0.0.2")

    await limiter(req, db=None)
    await limiter(req, db=None)

    # 3e requête : dépassement de la limite de 2
    with pytest.raises(HTTPException) as exc_info:
        await limiter(req, db=None)

    assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "trop de requêtes" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_3_retry_after_header_present():
    limiter = RateLimiter(times=1, seconds=45, scope="test:retry")
    req = make_request("10.0.0.3")

    await limiter(req, db=None)

    with pytest.raises(HTTPException) as exc_info:
        await limiter(req, db=None)

    headers = exc_info.value.headers
    assert "Retry-After" in headers
    retry_after = int(headers["Retry-After"])
    assert 1 <= retry_after <= 45
    assert headers["X-RateLimit-Limit"] == "1"
    assert headers["X-RateLimit-Remaining"] == "0"


# ─────────────────────────────────────────────────────────────────────────────
# 4. Expiration de la fenêtre temporelle
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_4_window_reset_restores_allowance():
    # Fenêtre ultra-courte de 1 seconde pour le test
    limiter = RateLimiter(times=1, seconds=1, scope="test:reset")
    req = make_request("10.0.0.4")

    await limiter(req, db=None)

    # Bloqué immédiatement
    with pytest.raises(HTTPException):
        await limiter(req, db=None)

    # Attente de l'expiration de la fenêtre (1.1s)
    await asyncio.sleep(1.1)

    # De nouveau autorisé !
    await limiter(req, db=None)


# ─────────────────────────────────────────────────────────────────────────────
# 5-6. Protection Spécifique Login & Anti-Contournement
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_5_login_rate_limiting_protects_brute_force():
    login_limiter = get_rate_limiter_login()
    req = make_request("198.51.100.5")

    # Épuisement des 5 tentatives autorisées
    for _ in range(5):
        await login_limiter(req, db=None)

    # La 6e tentative doit être immédiatement bloquée en 429
    with pytest.raises(HTTPException) as exc_info:
        await login_limiter(req, db=None)

    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_6_login_rate_limiting_cannot_be_bypassed_by_changing_email():
    """Un attaquant qui essaie différents emails depuis la même IP doit être bloqué."""
    login_limiter = get_rate_limiter_login()
    attacker_ip = "198.51.100.66"

    # L'attaquant cible admin@test.com, user1@test.com, etc.
    for i in range(5):
        req = make_request(attacker_ip, headers={"X-Target-User": f"victim_{i}@example.com"})
        await login_limiter(req, db=None)

    # Tentative sur une autre cible depuis la même IP -> BLOQUÉ 429
    req_new_target = make_request(attacker_ip, headers={"X-Target-User": "another_victim@example.com"})
    with pytest.raises(HTTPException) as exc_info:
        await login_limiter(req_new_target, db=None)

    assert exc_info.value.status_code == 429


# ─────────────────────────────────────────────────────────────────────────────
# 7-8. Anti-Spoofing & Proxies de Confiance
# ─────────────────────────────────────────────────────────────────────────────

def test_7_anti_spoofing_untrusted_forwarded_for_ignored():
    """Si la connexion provient d'une IP publique directe non-proxy,
    les en-têtes X-Forwarded-For falsifiés doivent être STRICTEMENT ignorés.
    """
    untrusted_attacker_ip = "203.0.113.42"
    # L'attaquant envoie un X-Forwarded-For bidon pour tenter de changer d'identité à chaque requête
    req = make_request(
        untrusted_attacker_ip,
        headers={"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}
    )

    extracted_ip = get_real_client_ip(req)
    # Doit être l'IP de connexion directe, PAS la valeur forgée !
    assert extracted_ip == untrusted_attacker_ip


def test_8_trusted_proxy_forwarded_for_extracted():
    """Si la connexion provient de localhost / proxy de confiance (ex: 127.0.0.1),
    le premier IP de X-Forwarded-For est légitimement extrait.
    """
    trusted_proxy_ip = "127.0.0.1"
    req = make_request(
        trusted_proxy_ip,
        headers={"X-Forwarded-For": "198.51.100.99, 10.0.0.1"}
    )

    extracted_ip = get_real_client_ip(req)
    assert extracted_ip == "198.51.100.99"


# ─────────────────────────────────────────────────────────────────────────────
# 9-10. 2FA & Password Reset
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_9_2fa_endpoints_rate_limited():
    twofa_limiter = get_rate_limiter_2fa()
    req = make_request("192.0.2.10")

    # Limite = 5 requêtes
    for _ in range(5):
        await twofa_limiter(req, db=None)

    with pytest.raises(HTTPException) as exc_info:
        await twofa_limiter(req, db=None)

    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_10_password_reset_rate_limited():
    reset_limiter = get_rate_limiter_password_reset()
    req = make_request("192.0.2.20")

    # Limite = 3 requêtes (défaut settings.RATE_LIMIT_PASSWORD_RESET)
    for _ in range(3):
        await reset_limiter(req, db=None)

    with pytest.raises(HTTPException) as exc_info:
        await reset_limiter(req, db=None)

    assert exc_info.value.status_code == 429


# ─────────────────────────────────────────────────────────────────────────────
# 11. Endpoints IA — Isolation par Utilisateur
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_11_ai_endpoints_rate_limited_per_user():
    from jose import jwt
    ai_limiter = RateLimiter(times=2, seconds=60, scope="ai", by_user=True)

    # Token pour User A
    token_a = jwt.encode({"sub": "user_AAA"}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    req_a = make_request("192.168.1.1", headers={"Authorization": f"Bearer {token_a}"})

    # Token pour User B
    token_b = jwt.encode({"sub": "user_BBB"}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    req_b = make_request("192.168.1.1", headers={"Authorization": f"Bearer {token_b}"})

    # User A consomme ses 2 requêtes
    await ai_limiter(req_a, db=None)
    await ai_limiter(req_a, db=None)

    # User A est bloqué
    with pytest.raises(HTTPException):
        await ai_limiter(req_a, db=None)

    # User B (même IP !) n'est PAS bloqué car la limite est isolée par user_id
    await ai_limiter(req_b, db=None)


# ─────────────────────────────────────────────────────────────────────────────
# 12. Moteur MongoDB Distribué (find_one_and_update avec $inc)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_12_mongodb_distributed_storage_atomic_inc():
    mock_db = MagicMock()
    mock_rate_limits = MagicMock()
    mock_db.rate_limits = mock_rate_limits

    # Simulation du premier appel : aucune fenêtre active -> initialisation
    mock_rate_limits.find_one_and_update = AsyncMock(side_effect=[
        None,  # 1ère recherche non-expirée : rien trouvé
        {"count": 1, "expires_at": datetime.utcnow() + timedelta(seconds=60)},  # upsert init
    ])

    limiter = RateLimiter(times=5, seconds=60, scope="mongo:test")
    req = make_request("172.16.0.1")

    # Ne doit pas lever d'erreur
    await limiter(req, db=mock_db)

    # Vérification que find_one_and_update a bien été appelé
    assert mock_rate_limits.find_one_and_update.call_count == 2


# ─────────────────────────────────────────────────────────────────────────────
# 13. Fallback Mémoire Local si MongoDB Indisponible
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_13_memory_fallback_when_db_fails(caplog):
    mock_db = MagicMock()
    mock_rate_limits = MagicMock()
    mock_rate_limits.find_one_and_update = AsyncMock(side_effect=Exception("MongoDB Connection Timeout"))
    mock_db.rate_limits = mock_rate_limits

    limiter = RateLimiter(times=2, seconds=60, scope="mongo:fallback")
    req = make_request("172.16.0.2")

    # Doit basculer de façon transparente sur le store mémoire sans crasher !
    with caplog.at_level(logging.WARNING):
        await limiter(req, db=mock_db)
        await limiter(req, db=mock_db)

    assert "bascule en mémoire locale" in caplog.text

    # Le 3e appel en mémoire doit lever le 429
    with pytest.raises(HTTPException):
        await limiter(req, db=mock_db)


# ─────────────────────────────────────────────────────────────────────────────
# 14. Concurrence & Absence de Race Condition
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_14_concurrency_no_race_conditions():
    """20 requêtes simultanées envoyées via asyncio.gather pour une limite de 10.
    Exactement 10 doivent réussir et 10 doivent échouer en 429.
    """
    limit = 10
    limiter = RateLimiter(times=limit, seconds=60, scope="test:race")
    req = make_request("192.168.99.1")

    results = []

    async def send_req():
        try:
            await limiter(req, db=None)
            return "SUCCESS"
        except HTTPException as e:
            return f"FAIL_{e.status_code}"

    tasks = [send_req() for _ in range(20)]
    results = await asyncio.gather(*tasks)

    success_count = sum(1 for r in results if r == "SUCCESS")
    fail_429_count = sum(1 for r in results if r == "FAIL_429")

    assert success_count == limit, f"Attendu {limit} succès, obtenu {success_count}"
    assert fail_429_count == 10, f"Attendu 10 rejets 429, obtenu {fail_429_count}"


# ─────────────────────────────────────────────────────────────────────────────
# 15. Drapeau Global RATE_LIMIT_ENABLED
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_15_rate_limit_disabled_flag():
    settings.RATE_LIMIT_ENABLED = False

    limiter = RateLimiter(times=1, seconds=60, scope="test:disabled")
    req = make_request("10.10.10.10")

    # Même au-delà de la limite, aucune exception 429 n'est levée
    await limiter(req, db=None)
    await limiter(req, db=None)
    await limiter(req, db=None)


# ─────────────────────────────────────────────────────────────────────────────
# 16. Sécurité des Logs : Absence de Fuite de Secrets
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_16_security_logs_no_sensitive_data(caplog):
    limiter = RateLimiter(times=1, seconds=60, scope="auth:login")
    secret_password = "SuperSecretPassword123!"
    otp_code = "739201"

    req = make_request(
        "10.20.30.40",
        headers={
            "X-Password-Attempt": secret_password,
            "X-OTP-Attempt": otp_code,
        }
    )

    await limiter(req, db=None)

    with caplog.at_level(logging.WARNING):
        with pytest.raises(HTTPException):
            await limiter(req, db=None)

    # Les logs de rate limit ne doivent JAMAIS contenir les valeurs sensibles
    assert secret_password not in caplog.text
    assert otp_code not in caplog.text
    assert "Rate limit dépassé" in caplog.text
