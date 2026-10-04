# -*- coding: utf-8 -*-
"""
Comprehensive Test Suite for LDAP / Active Directory Integration.
Tests configuration, authentication, synchronization, role mapping, security controls, and regression.
Run: pytest test_ldap_integration.py -v
"""
import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId

from core.config import Settings
from schemas.schemas import UserRole, UserUpdate, AuditEventCategory, AuditSeverity
from services.ldap_service import LdapService
from services.auth_service import AuthService
from services.user_agent_team_service import UserService


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures & Helpers
# ──────────────────────────────────────────────────────────────────────────────

class MockEntry:
    def __init__(self, dn, sam, mail, display_name, department=None, phone=None, member_of=None):
        self.entry_dn = dn
        self.sAMAccountName = MagicMock(value=sam)
        self.mail = MagicMock(value=mail)
        self.userPrincipalName = MagicMock(value=mail)
        self.displayName = MagicMock(value=display_name)
        self.givenName = MagicMock(value=display_name.split()[0] if display_name else "")
        self.sn = MagicMock(value=display_name.split()[-1] if display_name and len(display_name.split()) > 1 else "")
        self.department = MagicMock(value=department or "")
        self.telephoneNumber = MagicMock(value=phone or "")
        self.mobile = MagicMock(value="")
        self.uid = MagicMock(value=sam)
        self.cn = MagicMock(value=sam)
        if member_of:
            self.memberOf = MagicMock(values=member_of if isinstance(member_of, list) else [member_of])
        else:
            self.memberOf = MagicMock(values=[])


def get_mock_db():
    db = MagicMock()
    db.users = MagicMock()
    db.audit_logs = MagicMock()
    db.password_resets = MagicMock()
    db.token_blacklist = MagicMock()
    return db


# ──────────────────────────────────────────────────────────────────────────────
# 1. Configuration Tests
# ──────────────────────────────────────────────────────────────────────────────

def test_1_ldap_disabled_by_default():
    """LDAP should be disabled by default for safety and zero unwanted network calls."""
    default_settings = Settings()
    svc = LdapService(default_settings)
    assert svc.is_enabled() is False
    assert default_settings.LDAP_ENABLED is False


def test_2_ldap_custom_configuration():
    """Custom settings override correctly instantiates LdapService parameters."""
    custom_cfg = Settings(
        LDAP_ENABLED=True,
        LDAP_SERVER="ldaps://ad.enterprise.com",
        LDAP_PORT=636,
        LDAP_USE_SSL=True,
        LDAP_BASE_DN="dc=enterprise,dc=com",
        LDAP_TIMEOUT=10
    )
    svc = LdapService(custom_cfg)
    assert svc.is_enabled() is True
    server = svc._get_server()
    assert server.port == 636
    assert server.ssl is True


# ──────────────────────────────────────────────────────────────────────────────
# 2. Authentication Flow Tests
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_3_ldap_disabled_returns_disabled_error():
    """Attempting LDAP authentication when LDAP_ENABLED=False immediately returns failure."""
    cfg = Settings(LDAP_ENABLED=False)
    svc = LdapService(cfg)
    success, info, err = await svc.authenticate_user("john.doe", "password123")
    assert success is False
    assert info is None
    assert "disabled" in err.lower()


@pytest.mark.asyncio
async def test_4_ldap_authentication_successful():
    """Valid credentials successfully locate user and bind with directory."""
    cfg = Settings(
        LDAP_ENABLED=True,
        LDAP_SERVER="ldap://localhost:389",
        LDAP_BASE_DN="dc=geiser,dc=internal"
    )
    svc = LdapService(cfg)

    mock_entry = MockEntry(
        dn="CN=John Doe,OU=Users,DC=geiser,DC=internal",
        sam="jdoe",
        mail="john.doe@geiser.internal",
        display_name="John Doe",
        department="IT Operations",
        phone="+33123456789",
        member_of=["CN=Helpdesk-Agents,OU=Groups,DC=geiser,DC=internal"]
    )

    with patch.object(svc, "find_user") as mock_find:
        mock_find.return_value = {
            "dn": "CN=John Doe,OU=Users,DC=geiser,DC=internal",
            "username": "jdoe",
            "email": "john.doe@geiser.internal",
            "full_name": "John Doe",
            "department": "IT Operations",
            "phone_number": "+33123456789",
            "groups": ["Helpdesk-Agents"]
        }
        with patch("services.ldap_service.Connection") as mock_conn_cls:
            mock_conn = MagicMock()
            mock_conn.bind.return_value = True
            mock_conn_cls.return_value = mock_conn

            success, user_info, err = await svc.authenticate_user("jdoe", "SecretPass123!")

            assert success is True
            assert err is None
            assert user_info["email"] == "john.doe@geiser.internal"
            assert user_info["username"] == "jdoe"
            assert "Helpdesk-Agents" in user_info["groups"]
            mock_conn.bind.assert_called_once()
            mock_conn.unbind.assert_called_once()


@pytest.mark.asyncio
async def test_5_ldap_invalid_credentials():
    """User exists in directory but supplied incorrect password -> bind fails."""
    cfg = Settings(LDAP_ENABLED=True)
    svc = LdapService(cfg)

    with patch.object(svc, "find_user") as mock_find:
        mock_find.return_value = {
            "dn": "CN=John Doe,OU=Users,DC=geiser,DC=internal",
            "username": "jdoe",
            "email": "john.doe@geiser.internal"
        }
        with patch("services.ldap_service.Connection") as mock_conn_cls:
            mock_conn = MagicMock()
            mock_conn.bind.return_value = False
            mock_conn_cls.return_value = mock_conn

            success, user_info, err = await svc.authenticate_user("jdoe", "WrongPassword!")

            assert success is False
            assert user_info is None
            assert err == "Invalid credentials"


@pytest.mark.asyncio
async def test_6_ldap_user_not_found():
    """Non-existent user in directory returns cleanly without crashing."""
    cfg = Settings(LDAP_ENABLED=True)
    svc = LdapService(cfg)

    with patch.object(svc, "find_user", return_value=None):
        success, user_info, err = await svc.authenticate_user("ghost_user", "password")
        assert success is False
        assert user_info is None
        assert err == "User not found in directory"


@pytest.mark.asyncio
async def test_7_ldap_server_connection_timeout():
    """Network connection timeout is caught and handled safely without exposing internal trace."""
    from ldap3.core.exceptions import LDAPSocketOpenError
    cfg = Settings(LDAP_ENABLED=True, LDAP_TIMEOUT=2)
    svc = LdapService(cfg)

    with patch.object(svc, "_get_service_connection", return_value=None):
        success, user_info, err = await svc.authenticate_user("jdoe", "pass")
        assert success is False
        assert "not found" in err.lower() or "connection" in err.lower()


# ──────────────────────────────────────────────────────────────────────────────
# 3. Role Mapping Tests
# ──────────────────────────────────────────────────────────────────────────────

def test_8_role_mapping_hierarchy():
    """Tests group-to-role mappings: Admin > Supervisor > Agent > Default."""
    cfg = Settings(
        LDAP_ROLE_GROUP_ADMIN="Helpdesk-Admins,Domain Admins",
        LDAP_ROLE_GROUP_SUPERVISOR="Helpdesk-Supervisors",
        LDAP_ROLE_GROUP_AGENT="Helpdesk-Agents,IT-Support",
        LDAP_DEFAULT_ROLE="USER"
    )
    svc = LdapService(cfg)

    # Admin group
    assert svc.get_role_from_groups(["Domain Admins", "Developers"]) == UserRole.ADMIN
    assert svc.get_role_from_groups(["Helpdesk-Admins"]) == UserRole.ADMIN

    # Supervisor group
    assert svc.get_role_from_groups(["Helpdesk-Supervisors"]) == UserRole.SUPERVISOR

    # Agent group
    assert svc.get_role_from_groups(["IT-Support", "Staff"]) == UserRole.AGENT

    # Default role
    assert svc.get_role_from_groups(["Standard-Users", "Accounting"]) == UserRole.USER
    assert svc.get_role_from_groups([]) == UserRole.USER


# ──────────────────────────────────────────────────────────────────────────────
# 4. Synchronization into MongoDB Tests
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_9_sync_new_ldap_user():
    """First-time LDAP login creates local user with auth_provider='ldap' and no local password."""
    cfg = Settings(LDAP_ROLE_GROUP_AGENT="Helpdesk-Agents")
    svc = LdapService(cfg)
    db = get_mock_db()

    # User does not exist locally
    db.users.find_one = AsyncMock(return_value=None)
    fake_id = ObjectId()
    mock_insert = MagicMock(inserted_id=fake_id)
    db.users.insert_one = AsyncMock(return_value=mock_insert)

    ldap_info = {
        "dn": "CN=Alice Smith,OU=Users,DC=geiser,DC=internal",
        "username": "asmith",
        "email": "alice.smith@geiser.internal",
        "full_name": "Alice Smith",
        "department": "Engineering",
        "phone_number": "+33612345678",
        "groups": ["Helpdesk-Agents"]
    }

    synced_user = await svc.sync_user_to_db(ldap_info, db)

    assert synced_user["email"] == "alice.smith@geiser.internal"
    assert synced_user["auth_provider"] == "ldap"
    assert synced_user["role"] == UserRole.AGENT.value
    assert synced_user["department"] == "Engineering"

    # Verify insertion call
    db.users.insert_one.assert_called_once()
    inserted_doc = db.users.insert_one.call_args[0][0]
    assert inserted_doc["auth_provider"] == "ldap"
    assert inserted_doc["hashed_password"] == "!LDAP_NO_LOCAL_PASSWORD!"


@pytest.mark.asyncio
async def test_10_sync_existing_ldap_user_updates_profile():
    """Subsequent logins update existing user record without creating duplicate."""
    svc = LdapService(Settings())
    db = get_mock_db()

    existing_id = ObjectId()
    existing_user = {
        "_id": existing_id,
        "email": "alice.smith@geiser.internal",
        "full_name": "Alice OldName",
        "department": "Old Department",
        "auth_provider": "ldap",
        "role": UserRole.AGENT.value,
        "is_active": True,
        "two_factor_enabled": True  # User activated 2FA previously
    }
    db.users.find_one = AsyncMock(side_effect=[existing_user, {**existing_user, "department": "New Dept"}])
    db.users.update_one = AsyncMock()

    ldap_info = {
        "dn": "CN=Alice Smith,OU=Users,DC=geiser,DC=internal",
        "username": "asmith",
        "email": "alice.smith@geiser.internal",
        "full_name": "Alice Smith",
        "department": "New Dept",
        "groups": []
    }

    synced_user = await svc.sync_user_to_db(ldap_info, db)

    # Verify update rather than insert
    db.users.update_one.assert_called_once()
    update_args = db.users.update_one.call_args[0][1]["$set"]
    assert update_args["department"] == "New Dept"
    assert update_args["auth_provider"] == "ldap"


# ──────────────────────────────────────────────────────────────────────────────
# 5. Full Authentication Service Integration & Security Fallback
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_11_auth_service_ldap_login_success(monkeypatch):
    """AuthService.authenticate_user successfully coordinates LDAP login and audit logging."""
    from core.config import settings
    monkeypatch.setattr(settings, "LDAP_ENABLED", True)

    db = get_mock_db()
    fake_user = {
        "_id": ObjectId(),
        "id": "60a123456789abcdef123456",
        "email": "bob.ad@geiser.internal",
        "full_name": "Bob Enterprise",
        "role": UserRole.USER.value,
        "is_active": True,
        "auth_provider": "ldap",
        "two_factor_enabled": False
    }

    db.audit_logs.insert_one = AsyncMock()

    auth_svc = AuthService(db)

    with patch("services.ldap_service.LdapService.authenticate_user", new_callable=AsyncMock) as mock_ldap_auth, \
         patch("services.ldap_service.LdapService.sync_user_to_db", new_callable=AsyncMock) as mock_sync:

        mock_ldap_auth.return_value = (True, {"username": "bob", "email": "bob.ad@geiser.internal"}, None)
        mock_sync.return_value = fake_user

        user = await auth_svc.authenticate_user("bob.ad@geiser.internal", "Password123!")

        assert user is not None
        assert user["email"] == "bob.ad@geiser.internal"
        assert user["auth_provider"] == "ldap"

        # Verify audit log event
        db.audit_logs.insert_one.assert_called_once()
        audit_call = db.audit_logs.insert_one.call_args[0][0]
        assert audit_call["event_type"] == "LDAP_LOGIN_SUCCESS"
        assert audit_call["actor_email"] == "bob.ad@geiser.internal"
        assert audit_call["status"] == "SUCCESS"


@pytest.mark.asyncio
async def test_12_auth_service_ldap_user_cannot_use_local_password(monkeypatch):
    """An LDAP-managed user cannot log in with a local password even if one exists."""
    from core.config import settings
    monkeypatch.setattr(settings, "LDAP_ENABLED", True)

    db = get_mock_db()
    ldap_user = {
        "_id": ObjectId(),
        "email": "managed.ldap@geiser.internal",
        "auth_provider": "ldap",
        "hashed_password": "!LDAP_NO_LOCAL_PASSWORD!",
        "role": "USER",
        "is_active": True
    }
    db.users.find_one = AsyncMock(return_value=ldap_user)
    db.audit_logs.insert_one = AsyncMock()

    auth_svc = AuthService(db)

    with patch("services.ldap_service.LdapService.authenticate_user", new_callable=AsyncMock) as mock_ldap_auth:
        # LDAP credentials failed
        mock_ldap_auth.return_value = (False, None, "Invalid credentials")

        user = await auth_svc.authenticate_user("managed.ldap@geiser.internal", "bad_pass")
        assert user is None


@pytest.mark.asyncio
async def test_13_auth_service_local_user_works_when_ldap_enabled(monkeypatch):
    """A purely local account (e.g., local break-glass admin) authenticates locally when LDAP enabled."""
    from core.config import settings
    from core.security import get_password_hash
    monkeypatch.setattr(settings, "LDAP_ENABLED", True)

    db = get_mock_db()
    local_admin = {
        "_id": ObjectId(),
        "email": "local.admin@geiser.internal",
        "hashed_password": get_password_hash("LocalEmergencyPass!"),
        "role": UserRole.ADMIN.value,
        "auth_provider": "local",
        "is_active": True,
        "two_factor_enabled": False
    }
    db.users.find_one = AsyncMock(return_value=local_admin)
    db.audit_logs.insert_one = AsyncMock()

    auth_svc = AuthService(db)

    with patch("services.ldap_service.LdapService.authenticate_user", new_callable=AsyncMock) as mock_ldap_auth:
        # Not found in directory -> falls back to local user store
        mock_ldap_auth.return_value = (False, None, "User not found in directory")

        user = await auth_svc.authenticate_user("local.admin@geiser.internal", "LocalEmergencyPass!")
        assert user is not None
        assert user["email"] == "local.admin@geiser.internal"
        assert user["role"] == UserRole.ADMIN.value


# ──────────────────────────────────────────────────────────────────────────────
# 6. Password Reset Protection for LDAP Users
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_14_password_reset_blocked_for_ldap_users():
    """Password reset token generation is quietly ignored for LDAP accounts (anti-enumeration)."""
    db = get_mock_db()
    ldap_user = {
        "_id": ObjectId(),
        "email": "ldap.user@geiser.internal",
        "auth_provider": "ldap"
    }
    db.users.find_one = AsyncMock(return_value=ldap_user)
    db.password_resets.insert_one = AsyncMock()

    auth_svc = AuthService(db)
    await auth_svc.request_password_reset("ldap.user@geiser.internal")

    # No password reset token should be inserted
    db.password_resets.insert_one.assert_not_called()


@pytest.mark.asyncio
async def test_15_admin_cannot_update_ldap_password():
    """Admin updating an LDAP user cannot supply a local password."""
    from fastapi import HTTPException
    db = get_mock_db()
    ldap_user = {
        "_id": ObjectId(),
        "id": "60a123456789abcdef123456",
        "email": "ldap.user@geiser.internal",
        "auth_provider": "ldap"
    }
    user_svc = UserService(db)

    with patch.object(user_svc, "get_user_by_id", return_value=ldap_user):
        update_in = UserUpdate(full_name="New Name")
        # Add password into dict manually to simulate password update
        update_in_with_pwd = MagicMock()
        update_in_with_pwd.dict.return_value = {"password": "NewSecretPassword!"}

        with pytest.raises(HTTPException) as exc_info:
            await user_svc.update_user("60a123456789abcdef123456", update_in_with_pwd)

        assert exc_info.value.status_code == 400
        assert "Active Directory / LDAP" in exc_info.value.detail
