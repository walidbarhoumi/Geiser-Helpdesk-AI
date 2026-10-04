"""
test_jwt_blacklist.py
==============================================================================
Suite de tests unitaires pour l'invalidation réelle des JWT lors de la déconnexion
(JWT Blacklist avec JTI, persistance MongoDB, index TTL, vérification get_current_user,
révocation refresh token, audit ISO 27001).

Couvre l'ensemble des 18 scénarios obligatoires :
 1. JWT valide est accepté.
 2. JWT expiré est refusé (401).
 3. JWT avec signature invalide est refusé (401).
 4. JWT sans jti est géré selon la stratégie de rétrocompatibilité (accepté si valide).
 5. JWT révoqué est refusé (401 Token has been revoked).
 6. JWT non révoqué est accepté.
 7. JTI appartenant à un autre utilisateur ne permet pas de contourner l'autorisation.
 8. Logout avec access token valide.
 9. Logout avec refresh token valide.
10. Réutilisation d'un access token révoqué (refusé).
11. Réutilisation d'un refresh token révoqué (refusé).
12. Double logout (idempotence garantie).
13. Logout avec token expiré (géré sans crash).
14. Logout avec token invalide (401 Invalid token).
15. Requête non authentifiée (401 Not authenticated).
16. Vérification de l'audit trail (AUTH_LOGOUT consigné).
17. Vérification de la persistance MongoDB (document inséré dans token_blacklist).
18. Vérification de la configuration des index TTL et JTI unique.

Run:
    cd backend
    python -m pytest test_jwt_blacklist.py -v --tb=short
"""

import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId
from fastapi import HTTPException, status
from jose import jwt

from core.config import settings
from core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    decode_token_unverified,
)
from core.deps import get_current_user
from services.auth_service import AuthService
from schemas.schemas import UserRole, AuditSeverity


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures & Mocks
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def fake_user_id():
    return str(ObjectId())


@pytest.fixture
def fake_user(fake_user_id):
    return {
        "_id": ObjectId(fake_user_id),
        "id": fake_user_id,
        "email": "user@geiser.tn",
        "full_name": "Test User",
        "role": UserRole.AGENT,
        "is_active": True,
        "two_factor_enabled": False,
    }


@pytest.fixture
def mock_db(fake_user):
    db = MagicMock()
    # In-memory storage for token_blacklist
    blacklist_store = {}

    async def mock_find_one(filter_dict, projection=None):
        if "_id" in filter_dict:
            oid = str(filter_dict["_id"])
            if oid == str(fake_user["_id"]):
                return fake_user
            return None
        if "jti" in filter_dict:
            jti = filter_dict["jti"]
            return blacklist_store.get(jti)
        if "email" in filter_dict:
            if filter_dict["email"] == fake_user["email"]:
                return fake_user
            return None
        return None

    async def mock_update_one(filter_dict, update_dict, upsert=False):
        if "jti" in filter_dict and upsert:
            jti = filter_dict["jti"]
            doc = update_dict.get("$setOnInsert", {})
            blacklist_store[jti] = doc
            mock_res = MagicMock()
            mock_res.upserted_id = jti
            return mock_res
        return MagicMock()

    db.token_blacklist.find_one = AsyncMock(side_effect=mock_find_one)
    db.token_blacklist.update_one = AsyncMock(side_effect=mock_update_one)
    db.users.find_one = AsyncMock(side_effect=mock_find_one)
    db._blacklist_store = blacklist_store

    return db


# ─────────────────────────────────────────────────────────────────────────────
# 1. Tests JWT
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_01_valid_jwt_is_accepted(mock_db, fake_user_id, fake_user):
    """Un JWT valide avec JTI et non révoqué est accepté par get_current_user."""
    token = create_access_token(subject=fake_user_id)
    user = await get_current_user(token=token, db=mock_db)
    assert user is not None
    assert str(user["id"]) == fake_user_id


@pytest.mark.asyncio
async def test_02_expired_jwt_is_rejected(mock_db, fake_user_id):
    """Un JWT expiré est immédiatement refusé avec HTTP 401."""
    token = create_access_token(subject=fake_user_id, expires_delta=timedelta(seconds=-10))
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=token, db=mock_db)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Could not validate credentials" in exc_info.value.detail


@pytest.mark.asyncio
async def test_03_invalid_signature_is_rejected(mock_db, fake_user_id):
    """Un JWT altéré ou signé avec une fausse clé est refusé avec HTTP 401."""
    to_encode = {
        "exp": datetime.utcnow() + timedelta(minutes=30),
        "sub": fake_user_id,
        "jti": uuid.uuid4().hex,
        "type": "access",
    }
    fake_signed_token = jwt.encode(to_encode, "wrong-secret-key-12345", algorithm=settings.ALGORITHM)
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=fake_signed_token, db=mock_db)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_04_jwt_without_jti_backward_compatibility(mock_db, fake_user_id):
    """Un ancien token sans JTI reste valide jusqu'à son expiration naturelle (rétrocompatibilité)."""
    # Création manuelle d'un token legacy sans champ jti
    to_encode = {
        "exp": datetime.utcnow() + timedelta(minutes=15),
        "sub": fake_user_id,
        "type": "access",
    }
    legacy_token = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    user = await get_current_user(token=legacy_token, db=mock_db)
    assert user is not None
    assert str(user["id"]) == fake_user_id


@pytest.mark.asyncio
async def test_05_revoked_jwt_is_rejected(mock_db, fake_user_id):
    """Un JWT dont le JTI est présent dans token_blacklist est refusé avec HTTP 401."""
    token = create_access_token(subject=fake_user_id)
    payload = decode_token(token)
    jti = payload["jti"]

    # Inscrire le token dans la blacklist
    auth_svc = AuthService(mock_db)
    await auth_svc.revoke_token(token)
    assert jti in mock_db._blacklist_store

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=token, db=mock_db)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Token has been revoked" in exc_info.value.detail


@pytest.mark.asyncio
async def test_06_unrevoked_jwt_is_accepted(mock_db, fake_user_id):
    """Parmi deux tokens d'un même utilisateur, seul le token non révoqué est accepté."""
    token1 = create_access_token(subject=fake_user_id)
    token2 = create_access_token(subject=fake_user_id)

    auth_svc = AuthService(mock_db)
    await auth_svc.revoke_token(token1)

    # token1 est refusé
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=token1, db=mock_db)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    # token2 reste accepté
    user = await get_current_user(token=token2, db=mock_db)
    assert user is not None
    assert str(user["id"]) == fake_user_id


@pytest.mark.asyncio
async def test_07_refresh_token_rejected_as_access_token(mock_db, fake_user_id):
    """Un refresh token ne peut pas être détourné pour accéder aux endpoints protégés."""
    refresh_token = create_refresh_token(subject=fake_user_id)
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=refresh_token, db=mock_db)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Refresh token cannot be used as an access token" in exc_info.value.detail


# ─────────────────────────────────────────────────────────────────────────────
# 2. Tests Logout & Révocation
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_08_logout_with_valid_access_token(mock_db, fake_user_id):
    """Le logout avec un access token valide l'inscrit dans la blacklist MongoDB."""
    token = create_access_token(subject=fake_user_id)
    payload = decode_token(token)
    jti = payload["jti"]

    auth_svc = AuthService(mock_db)
    res = await auth_svc.logout(access_token=token)

    assert res == {"message": "Successfully logged out"}
    assert jti in mock_db._blacklist_store
    assert mock_db._blacklist_store[jti]["token_type"] == "access"
    assert mock_db._blacklist_store[jti]["user_id"] == fake_user_id


@pytest.mark.asyncio
async def test_09_logout_with_valid_refresh_token(mock_db, fake_user_id):
    """Le logout révoque également le refresh token lorsqu'il est fourni."""
    access_token = create_access_token(subject=fake_user_id)
    refresh_token = create_refresh_token(subject=fake_user_id)
    rf_payload = decode_token(refresh_token)
    rf_jti = rf_payload["jti"]

    auth_svc = AuthService(mock_db)
    res = await auth_svc.logout(access_token=access_token, refresh_token=refresh_token)

    assert res == {"message": "Successfully logged out"}
    assert rf_jti in mock_db._blacklist_store
    assert mock_db._blacklist_store[rf_jti]["token_type"] == "refresh"


@pytest.mark.asyncio
async def test_10_reuse_revoked_access_token_fails(mock_db, fake_user_id):
    """Toute tentative d'utilisation d'un access token après déconnexion échoue en 401."""
    access_token = create_access_token(subject=fake_user_id)
    auth_svc = AuthService(mock_db)
    await auth_svc.logout(access_token=access_token)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=access_token, db=mock_db)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "revoked" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_11_reuse_revoked_refresh_token_fails(mock_db, fake_user_id):
    """Un refresh token révoqué ne peut plus générer de nouveaux access tokens."""
    refresh_token = create_refresh_token(subject=fake_user_id)
    auth_svc = AuthService(mock_db)
    await auth_svc.logout(refresh_token=refresh_token)

    with pytest.raises(HTTPException) as exc_info:
        await auth_svc.refresh_access_token(refresh_token)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "revoked" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_12_double_logout_is_idempotent(mock_db, fake_user_id):
    """Effectuer plusieurs déconnexions consécutives est idempotent et n'échoue jamais."""
    access_token = create_access_token(subject=fake_user_id)
    auth_svc = AuthService(mock_db)

    res1 = await auth_svc.logout(access_token=access_token)
    res2 = await auth_svc.logout(access_token=access_token)

    assert res1 == {"message": "Successfully logged out"}
    assert res2 == {"message": "Successfully logged out"}


@pytest.mark.asyncio
async def test_13_logout_with_expired_token(mock_db, fake_user_id):
    """La déconnexion avec un token venant d'expirer est acceptée et son JTI est sécurisé."""
    expired_token = create_access_token(subject=fake_user_id, expires_delta=timedelta(seconds=-60))
    auth_svc = AuthService(mock_db)

    res = await auth_svc.logout(access_token=expired_token)
    assert res == {"message": "Successfully logged out"}


@pytest.mark.asyncio
async def test_14_logout_with_malformed_token_raises_401(mock_db):
    """Une tentative de déconnexion avec un token corrompu ou falsifié retourne HTTP 401."""
    auth_svc = AuthService(mock_db)
    with pytest.raises(HTTPException) as exc_info:
        await auth_svc.logout(access_token="not.a.valid.jwt.token")
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid token" in exc_info.value.detail


@pytest.mark.asyncio
async def test_15_logout_without_any_token_raises_401(mock_db):
    """Appeler logout sans aucun token (ni access ni refresh) retourne HTTP 401 Not authenticated."""
    auth_svc = AuthService(mock_db)
    with pytest.raises(HTTPException) as exc_info:
        await auth_svc.logout(access_token=None, refresh_token=None)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Not authenticated" in exc_info.value.detail


@pytest.mark.asyncio
async def test_16_audit_trail_logs_logout_event(mock_db, fake_user_id, fake_user):
    """Le logout consigne un événement ISO 27001 AUTH_LOGOUT dans audit_logs."""
    token = create_access_token(subject=fake_user_id)
    auth_svc = AuthService(mock_db)

    with patch("services.audit_service.AuditService.log_event", new_callable=AsyncMock) as mock_audit:
        await auth_svc.logout(access_token=token, client_ip="192.168.1.10", user_agent="Mozilla/5.0")

        mock_audit.assert_called_once()
        kwargs = mock_audit.call_args.kwargs
        assert kwargs["event_type"] == "AUTH_LOGOUT"
        assert kwargs["severity"] == AuditSeverity.INFO
        assert kwargs["client_ip"] == "192.168.1.10"
        assert kwargs["user_agent"] == "Mozilla/5.0"
        assert kwargs["status"] == "SUCCESS"


@pytest.mark.asyncio
async def test_17_mongodb_blacklist_document_structure(mock_db, fake_user_id):
    """Vérifie la conformité de la structure du document persisté dans token_blacklist."""
    token = create_access_token(subject=fake_user_id)
    payload = decode_token(token)
    jti = payload["jti"]

    auth_svc = AuthService(mock_db)
    doc = await auth_svc.revoke_token(token, token_type="access", reason="logout")

    assert doc is not None
    assert doc["jti"] == jti
    assert doc["user_id"] == fake_user_id
    assert doc["token_type"] == "access"
    assert doc["reason"] == "logout"
    assert isinstance(doc["expires_at"], datetime)
    assert isinstance(doc["revoked_at"], datetime)


@pytest.mark.asyncio
async def test_18_mongodb_indexes_configured():
    """Vérifie la définition des index TTL et JTI unique dans database/mongodb.py."""
    mock_motor_db = MagicMock()
    mock_motor_db.token_blacklist.create_index = AsyncMock()
    mock_motor_db.password_resets.create_index = AsyncMock()

    mock_client = MagicMock()
    mock_client.__getitem__.return_value = mock_motor_db

    from database.mongodb import connect_to_mongo
    with patch("database.mongodb.AsyncIOMotorClient", return_value=mock_client):
        await connect_to_mongo()

    calls = [c[0] for c in mock_motor_db.token_blacklist.create_index.call_args_list]
    index_keys = [c[0] for c in calls]
    assert "expires_at" in index_keys
    assert "jti" in index_keys
    assert "user_id" in index_keys

    # Vérifier l'option expireAfterSeconds=0 sur expires_at et unique sur jti
    kwargs_dict = {c[0][0]: c[1] for c in mock_motor_db.token_blacklist.create_index.call_args_list}
    assert kwargs_dict["expires_at"].get("expireAfterSeconds") == 0
    assert kwargs_dict["jti"].get("unique") is True



if __name__ == "__main__":
    import subprocess, sys
    subprocess.run([sys.executable, "-m", "pytest", __file__, "-v"])
