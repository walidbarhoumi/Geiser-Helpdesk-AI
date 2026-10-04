"""
rate_limit.py
==============================================================================
Système de Rate Limiting robuste, distribué et sécurisé pour GEISER Support IA.

Fonctionnalités & Garanties de Sécurité :
- Multi-worker / Distribué : persistance dans MongoDB (collection `rate_limits`)
  avec mise à jour atomique ($inc) et index TTL pour auto-nettoyage des fenêtres expirées.
- Fallback In-Memory thread-safe : utilisé pour les tests unitaires ou si MongoDB
  est indisponible.
- Protection anti-spoofing : les en-têtes proxy (`X-Forwarded-For`, `X-Real-IP`)
  ne sont acceptés QUE si la connexion directe provient d'un proxy de confiance
  déclaré dans `settings.TRUSTED_PROXIES`.
- Support double identification : par adresse IP ou par identifiant utilisateur (authentifié).
- Réponse standardisée : code HTTP 429 Too Many Requests, en-tête `Retry-After`,
  et en-têtes informatifs `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`.
- Sécurité des traces : aucun secret (mot de passe, OTP, token) n'est jamais consigné.
"""

import time
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict
from fastapi import Request, HTTPException, status, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from core.config import settings
from database.mongodb import get_database
import logging

logger = logging.getLogger(__name__)

# Fallback local in-memory store: { key: { "count": int, "expires_at": float } }
_memory_store: Dict[str, Dict[str, float]] = {}
_memory_lock = asyncio.Lock()


def get_real_client_ip(request: Request) -> str:
    """Extrait l'adresse IP réelle du client de manière sécurisée.
    Ne fait confiance aux en-têtes X-Forwarded-For / X-Real-IP que si le client direct
    appartient à la liste blanche TRUSTED_PROXIES.
    """
    direct_host = request.client.host if request.client else "127.0.0.1"

    # Vérification si le client direct est un proxy de confiance
    trusted_list = getattr(settings, "TRUSTED_PROXIES", ["127.0.0.1", "::1", "testclient"])
    is_trusted = direct_host in trusted_list or any(direct_host.startswith(p) for p in trusted_list)

    if is_trusted:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Premier IP dans la liste X-Forwarded-For = client d'origine
            client_ip = forwarded.split(",")[0].strip()
            if client_ip:
                return client_ip
        real_ip = request.headers.get("X-Real-IP")
        if real_ip and real_ip.strip():
            return real_ip.strip()

    return direct_host


class RateLimiter:
    """Dépendance FastAPI appliquant un rate limiting par fenêtre temporelle."""

    def __init__(
        self,
        times: int,
        seconds: int = 60,
        scope: str = "general",
        by_user: bool = False,
    ):
        self.times = times
        self.seconds = seconds
        self.scope = scope
        self.by_user = by_user

    async def _check_mongodb(
        self, key: str, db: AsyncIOMotorDatabase
    ) -> Tuple[bool, int, int]:
        """Vérifie et incrémente le compteur atomiquement dans MongoDB.
        Retourne (is_allowed: bool, current_count: int, retry_after: int).
        """
        now = datetime.utcnow()
        reset_time = now + timedelta(seconds=self.seconds)

        # 1. Tentative d'incrémenter une fenêtre existante non-expirée
        doc = await db.rate_limits.find_one_and_update(
            {"key": key, "expires_at": {"$gt": now}},
            {"$inc": {"count": 1}},
            return_document=ReturnDocument.AFTER,
        )

        if not doc:
            # 2. Fenêtre expirée ou inexistante : initialisation atomique
            doc = await db.rate_limits.find_one_and_update(
                {"key": key},
                {
                    "$set": {
                        "count": 1,
                        "expires_at": reset_time,
                        "window_seconds": self.seconds,
                        "updated_at": now,
                    }
                },
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )

        current_count = doc.get("count", 1)
        expires_at = doc.get("expires_at", reset_time)
        remaining_seconds = max(1, int((expires_at - now).total_seconds()))

        allowed = current_count <= self.times
        return allowed, current_count, remaining_seconds

    async def _check_memory(self, key: str) -> Tuple[bool, int, int]:
        """Vérification atomique en mémoire locale (Fallback ou Mode Test)."""
        async with _memory_lock:
            now_ts = time.time()
            record = _memory_store.get(key)

            if not record or record["expires_at"] <= now_ts:
                # Nouvelle fenêtre
                expires_at = now_ts + self.seconds
                _memory_store[key] = {"count": 1, "expires_at": expires_at}
                return True, 1, self.seconds

            record["count"] += 1
            remaining = max(1, int(record["expires_at"] - now_ts))
            allowed = record["count"] <= self.times
            return allowed, record["count"], remaining

    async def __call__(
        self,
        request: Request,
        db: Optional[AsyncIOMotorDatabase] = Depends(get_database),
    ) -> None:
        # Court-circuit si le rate limiting est désactivé globalement
        if not getattr(settings, "RATE_LIMIT_ENABLED", True):
            return

        client_ip = get_real_client_ip(request)

        # Identification du client : par utilisateur authentifié ou par adresse IP
        client_identifier = f"ip:{client_ip}"
        if self.by_user:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                try:
                    from jose import jwt
                    token = auth_header[7:].strip()
                    payload = jwt.decode(
                        token,
                        settings.SECRET_KEY,
                        algorithms=[settings.ALGORITHM],
                        options={"verify_exp": False},
                    )
                    sub = payload.get("sub")
                    if sub:
                        client_identifier = f"user:{sub}"
                except Exception:
                    pass

        key = f"{self.scope}:{client_identifier}"

        # Évaluation du compteur
        allowed = True
        current_count = 0
        retry_after = self.seconds

        try:
            if db is not None and hasattr(db, "rate_limits"):
                allowed, current_count, retry_after = await self._check_mongodb(key, db)
            else:
                allowed, current_count, retry_after = await self._check_memory(key)
        except Exception as err:
            logger.warning(
                f"[RateLimiter] Erreur lors de l'accès au stockage MongoDB ({err}), bascule en mémoire locale."
            )
            allowed, current_count, retry_after = await self._check_memory(key)

        if not allowed:
            logger.warning(
                f"[SECURITY 429] Rate limit dépassé pour scope='{self.scope}' "
                f"par '{client_identifier}' ({current_count}/{self.times} reqs). "
                f"Retry-After: {retry_after}s"
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Trop de requêtes. Veuillez patienter avant de réessayer.",
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self.times),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time() + retry_after)),
                },
            )


# ─────────────────────────────────────────────────────────────────────────────
# Instances de Rate Limiting Préconfigurées
# ─────────────────────────────────────────────────────────────────────────────

def get_rate_limiter_login():
    """Limite stricte pour l'authentification (brute-force defense)."""
    return RateLimiter(
        times=getattr(settings, "RATE_LIMIT_LOGIN", 5),
        seconds=getattr(settings, "RATE_LIMIT_LOGIN_WINDOW", 60),
        scope="auth:login",
    )


def get_rate_limiter_2fa():
    """Limite stricte pour les requêtes et confirmations 2FA OTP."""
    return RateLimiter(
        times=getattr(settings, "RATE_LIMIT_2FA", 5),
        seconds=getattr(settings, "RATE_LIMIT_2FA_WINDOW", 60),
        scope="auth:2fa",
    )


def get_rate_limiter_password_reset():
    """Limite stricte pour les demandes de réinitialisation de mot de passe."""
    return RateLimiter(
        times=getattr(settings, "RATE_LIMIT_PASSWORD_RESET", 3),
        seconds=getattr(settings, "RATE_LIMIT_PASSWORD_RESET_WINDOW", 60),
        scope="auth:reset",
    )


def get_rate_limiter_ai():
    """Limite adaptée pour les endpoints IA et RAG coûteux."""
    return RateLimiter(
        times=getattr(settings, "RATE_LIMIT_AI", 20),
        seconds=getattr(settings, "RATE_LIMIT_AI_WINDOW", 60),
        scope="ai",
        by_user=True,
    )


def get_rate_limiter_general():
    """Limite générale pour les routes API publiques."""
    return RateLimiter(
        times=getattr(settings, "RATE_LIMIT_GENERAL", 100),
        seconds=getattr(settings, "RATE_LIMIT_GENERAL_WINDOW", 60),
        scope="general",
    )
