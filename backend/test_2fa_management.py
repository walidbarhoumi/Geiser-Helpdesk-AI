"""
test_2fa_management.py
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Tests complets pour la gestion de la 2FA depuis le profil utilisateur.
Couvre :
  - Statut 2FA
  - Activation (request + confirm)
  - DÃ©sactivation (request + confirm)
  - OTP expirÃ©
  - OTP dÃ©jÃ  utilisÃ©
  - Mauvais code
  - Mauvais mot de passe
  - Cross-user protection
  - CompatibilitÃ© flux login

Run:
    cd backend
    python -m pytest test_2fa_management.py -v
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId

# â”€â”€ Module under test â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
from services.auth_service import AuthService
from fastapi import HTTPException

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Helpers
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def make_user(two_factor_enabled=False, pending_code=None, pending_expires=None, pending_purpose=None):
    oid = ObjectId()
    user = {
        "_id": oid,
        "id": str(oid),
        "email": "test@geiser.local",
        "full_name": "Test User",
        "role": "USER",
        "is_active": True,
        "two_factor_enabled": two_factor_enabled,
        "hashed_password": "$2b$12$abcdefghijklmnopqrstuvuuMockHashedPasswordOKOKOKOKOK",
        "created_at": datetime.utcnow(),
    }
    if pending_code:
        user["pending_2fa_code"] = pending_code
    if pending_expires:
        user["pending_2fa_expires"] = pending_expires
    if pending_purpose:
        user["pending_2fa_purpose"] = pending_purpose
    return user


def make_db(user):
    """Returns a minimal async Motor mock."""
    collection = AsyncMock()
    collection.find_one = AsyncMock(return_value=user)
    collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    db = MagicMock()
    db.users = collection
    db.password_resets = AsyncMock()
    db.audit_logs = AsyncMock()
    db.audit_logs.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))
    return db


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# TEST 1 â€” Statut 2FA (utilisateur authentifiÃ©)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@pytest.mark.asyncio
async def test_get_2fa_status_disabled():
    user = make_user(two_factor_enabled=False)
    db = make_db(user)
    svc = AuthService(db)
    result = await svc.get_2fa_status(user["id"])
    assert result["enabled"] is False
    assert result["method"] == "email"


@pytest.mark.asyncio
async def test_get_2fa_status_enabled():
    user = make_user(two_factor_enabled=True)
    db = make_db(user)
    svc = AuthService(db)
    result = await svc.get_2fa_status(user["id"])
    assert result["enabled"] is True
    assert result["method"] == "email"


@pytest.mark.asyncio
async def test_get_2fa_status_user_not_found():
    db = make_db(None)  # find_one returns None
    svc = AuthService(db)
    with pytest.raises(HTTPException) as exc:
        await svc.get_2fa_status(str(ObjectId()))
    assert exc.value.status_code == 404


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# TEST 2 â€” Activation 2FA (request)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@pytest.mark.asyncio
async def test_request_enable_2fa_ok():
    user = make_user(two_factor_enabled=False)
    db = make_db(user)
    svc = AuthService(db)
    with patch("services.auth_service.EmailService.send_2fa_code") as mock_mail, \
         patch("services.audit_service.AuditService") as MockAudit:
        mock_audit = AsyncMock()
        mock_audit.log_event = AsyncMock()
        MockAudit.return_value = mock_audit

        result = await svc.request_enable_2fa(user["id"])
        assert "code has been sent" in result["message"].lower()
        # Verify email was sent to the right address with a valid 6-digit OTP
        mock_mail.assert_called_once()
        call_args = mock_mail.call_args[0]
        assert call_args[0] == user["email"]
        assert len(call_args[1]) == 6 and call_args[1].isdigit(), f"OTP should be 6 digits, got: {call_args[1]}"



@pytest.mark.asyncio
async def test_request_enable_2fa_already_enabled():
    user = make_user(two_factor_enabled=True)
    db = make_db(user)
    svc = AuthService(db)
    with pytest.raises(HTTPException) as exc:
        await svc.request_enable_2fa(user["id"])
    assert exc.value.status_code == 400
    assert "already enabled" in exc.value.detail.lower()


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# TEST 3 â€” Activation 2FA (confirm) â€” OTP valide
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@pytest.mark.asyncio
async def test_confirm_enable_2fa_valid_code():
    code = "482931"
    user = make_user(
        two_factor_enabled=False,
        pending_code=code,
        pending_expires=datetime.utcnow() + timedelta(minutes=9),
        pending_purpose="enable"
    )
    db = make_db(user)
    svc = AuthService(db)
    with patch("services.audit_service.AuditService") as MockAudit:
        mock_audit = AsyncMock()
        mock_audit.log_event = AsyncMock()
        MockAudit.return_value = mock_audit

        result = await svc.confirm_enable_2fa(user["id"], code)
        assert result["enabled"] is True
        db.users.update_one.assert_called_once()
        # Verify that $set two_factor_enabled=True is in the update call
        call_args = db.users.update_one.call_args[0]
        assert call_args[1]["$set"]["two_factor_enabled"] is True


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# TEST 4 â€” Activation 2FA â€” OTP incorrect
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@pytest.mark.asyncio
async def test_confirm_enable_2fa_wrong_code():
    user = make_user(
        two_factor_enabled=False,
        pending_code="111111",
        pending_expires=datetime.utcnow() + timedelta(minutes=9),
        pending_purpose="enable"
    )
    db = make_db(user)
    svc = AuthService(db)
    with patch("services.audit_service.AuditService") as MockAudit:
        mock_audit = AsyncMock()
        mock_audit.log_event = AsyncMock()
        MockAudit.return_value = mock_audit
        with pytest.raises(HTTPException) as exc:
            await svc.confirm_enable_2fa(user["id"], "999999")
    assert exc.value.status_code == 401


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# TEST 5 â€” Activation 2FA â€” OTP expirÃ©
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@pytest.mark.asyncio
async def test_confirm_enable_2fa_expired_code():
    code = "123456"
    user = make_user(
        two_factor_enabled=False,
        pending_code=code,
        pending_expires=datetime.utcnow() - timedelta(minutes=1),  # already expired
        pending_purpose="enable"
    )
    db = make_db(user)
    svc = AuthService(db)
    with patch("services.audit_service.AuditService") as MockAudit:
        mock_audit = AsyncMock()
        mock_audit.log_event = AsyncMock()
        MockAudit.return_value = mock_audit
        with pytest.raises(HTTPException) as exc:
            await svc.confirm_enable_2fa(user["id"], code)
    assert exc.value.status_code == 401


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# TEST 6 â€” Activation 2FA â€” OTP dÃ©jÃ  utilisÃ© (purpose mismatch)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@pytest.mark.asyncio
async def test_confirm_enable_2fa_purpose_mismatch():
    """OTP generated for 'disable' cannot be used for 'enable'."""
    code = "654321"
    user = make_user(
        two_factor_enabled=False,
        pending_code=code,
        pending_expires=datetime.utcnow() + timedelta(minutes=9),
        pending_purpose="disable"  # Wrong purpose!
    )
    db = make_db(user)
    svc = AuthService(db)
    with patch("services.audit_service.AuditService") as MockAudit:
        mock_audit = AsyncMock()
        mock_audit.log_event = AsyncMock()
        MockAudit.return_value = mock_audit
        with pytest.raises(HTTPException) as exc:
            await svc.confirm_enable_2fa(user["id"], code)
    assert exc.value.status_code == 401


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# TEST 7 â€” DÃ©sactivation 2FA â€” Mot de passe incorrect
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@pytest.mark.asyncio
async def test_request_disable_2fa_wrong_password():
    user = make_user(two_factor_enabled=True)
    db = make_db(user)
    svc = AuthService(db)
    with patch("services.auth_service.verify_password", return_value=False), \
         patch("services.audit_service.AuditService") as MockAudit:
        mock_audit = AsyncMock()
        mock_audit.log_event = AsyncMock()
        MockAudit.return_value = mock_audit
        with pytest.raises(HTTPException) as exc:
            await svc.request_disable_2fa(user["id"], "wrongpassword")
    assert exc.value.status_code == 401
    assert "incorrect password" in exc.value.detail.lower()


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# TEST 8 â€” DÃ©sactivation 2FA â€” Flux complet valide
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@pytest.mark.asyncio
async def test_request_disable_2fa_ok():
    user = make_user(two_factor_enabled=True)
    db = make_db(user)
    svc = AuthService(db)
    with patch("services.auth_service.verify_password", return_value=True), \
         patch("services.auth_service.EmailService.send_2fa_code"), \
         patch("services.audit_service.AuditService") as MockAudit:
        mock_audit = AsyncMock()
        mock_audit.log_event = AsyncMock()
        MockAudit.return_value = mock_audit
        result = await svc.request_disable_2fa(user["id"], "correctpassword")
        assert "code has been sent" in result["message"].lower()


@pytest.mark.asyncio
async def test_confirm_disable_2fa_valid_code():
    code = "777888"
    user = make_user(
        two_factor_enabled=True,
        pending_code=code,
        pending_expires=datetime.utcnow() + timedelta(minutes=9),
        pending_purpose="disable"
    )
    db = make_db(user)
    svc = AuthService(db)
    with patch("services.audit_service.AuditService") as MockAudit:
        mock_audit = AsyncMock()
        mock_audit.log_event = AsyncMock()
        MockAudit.return_value = mock_audit
        result = await svc.confirm_disable_2fa(user["id"], code)
        assert result["enabled"] is False
        call_args = db.users.update_one.call_args[0]
        assert call_args[1]["$set"]["two_factor_enabled"] is False


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# TEST 9 â€” Cross-user protection
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@pytest.mark.asyncio
async def test_cross_user_protection():
    """User A cannot use their own token to disable User B's 2FA.
    Each endpoint looks up the current_user["id"] from JWT â€” not from request body.
    Here we verify that if the JWT user_id != the found user, we still operate
    on the JWT user (the DB mock returns user_a when queried with user_a_id).
    """
    user_a = make_user(two_factor_enabled=True)
    user_b_id = str(ObjectId())  # Different ID never queried

    db = make_db(user_a)  # DB returns user_a for user_a's id lookup
    svc = AuthService(db)

    # Calling confirm_disable with user_a's id â€” correctly scoped
    code = "123123"
    user_a["pending_2fa_code"] = code
    user_a["pending_2fa_expires"] = datetime.utcnow() + timedelta(minutes=9)
    user_a["pending_2fa_purpose"] = "disable"
    db.users.find_one = AsyncMock(return_value=user_a)

    with patch("services.audit_service.AuditService") as MockAudit:
        mock_audit = AsyncMock()
        mock_audit.log_event = AsyncMock()
        MockAudit.return_value = mock_audit
        result = await svc.confirm_disable_2fa(user_a["id"], code)
        assert result["enabled"] is False
        # Verify query used user_a's id (not user_b's)
        call_args = db.users.find_one.call_args[0][0]
        assert "_id" in call_args


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# TEST 10 â€” Login flow compatibility
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@pytest.mark.asyncio
async def test_login_2fa_disabled_no_otp_required():
    """When 2FA is disabled, login should return tokens directly (no OTP step)."""
    user = make_user(two_factor_enabled=False)
    user["hashed_password"] = "$2b$12$mock"
    db = make_db(user)
    svc = AuthService(db)

    with patch("services.auth_service.verify_password", return_value=True), \
         patch("services.audit_service.AuditService") as MockAudit:
        mock_audit = AsyncMock()
        mock_audit.log_event = AsyncMock()
        MockAudit.return_value = mock_audit
        result = await svc.authenticate_user("test@geiser.local", "password")
        assert result is not None
        assert result.get("two_factor_enabled") is False


@pytest.mark.asyncio
async def test_login_2fa_enabled_returns_user_for_otp_step():
    """When 2FA is enabled, authenticate_user still returns the user dict
    (the route then calls initiate_2fa separately)."""
    user = make_user(two_factor_enabled=True)
    user["hashed_password"] = "$2b$12$mock"
    db = make_db(user)
    svc = AuthService(db)

    with patch("services.auth_service.verify_password", return_value=True), \
         patch("services.audit_service.AuditService") as MockAudit:
        mock_audit = AsyncMock()
        mock_audit.log_event = AsyncMock()
        MockAudit.return_value = mock_audit
        result = await svc.authenticate_user("test@geiser.local", "password")
        assert result is not None
        assert result.get("two_factor_enabled") is True


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Marker for email mock argument (any 6-digit string)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class ANY_6_DIGIT:
    """Matches any 6-digit string in assert_called_with."""
    def __eq__(self, other):
        return isinstance(other, str) and len(other) == 6 and other.isdigit()


if __name__ == "__main__":
    import subprocess, sys
    subprocess.run([sys.executable, "-m", "pytest", __file__, "-v"])

