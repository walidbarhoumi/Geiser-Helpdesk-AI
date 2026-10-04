"""
test_backup_restore.py
======================
STEP 6 — Backup & Restore API, RBAC and Scheduler Test Suite
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId
from jose import jwt

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.config import settings
from database.mongodb import get_database
from routes.backups import router as backups_router
from backup.backup_models import BackupStatus, BackupType, RetentionClass, VerificationStatus
from backup.backup_scheduler import register_backup_schedule
from backup.backup_utils import resolve_mongodump_path, resolve_mongorestore_path


# ─────────────────────────────────────────────────────────────
# Test App & Auth Helpers
# ─────────────────────────────────────────────────────────────

ADMIN_ID = "6abba6e6702d1408c1f39851"
SUPERVISOR_ID = "6abba6e6702d1408c1f39852"
AGENT_ID = "6abba6e6702d1408c1f39853"
USER_ID = "6abba6e6702d1408c1f39854"

ROLE_TO_ID = {
    "ADMIN": ADMIN_ID,
    "SUPERVISOR": SUPERVISOR_ID,
    "AGENT": AGENT_ID,
    "USER": USER_ID,
}


def create_token(role: str, user_id: str = None, email: str = None) -> str:
    uid = user_id or ROLE_TO_ID.get(role, USER_ID)
    mail = email or f"{role.lower()}@geiser.internal"
    payload = {
        "sub": uid,
        "role": role,
        "email": mail,
        "type": "access",
        "exp": datetime.utcnow() + timedelta(hours=1),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@pytest.fixture
def test_client():
    app = FastAPI()
    app.include_router(backups_router, prefix="/api/v1/backups")

    mock_db = MagicMock()
    mock_collection = MagicMock()

    # Default mock queries
    mock_collection.count_documents = AsyncMock(return_value=5)
    mock_collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id="mock_id"))
    mock_collection.update_one = AsyncMock(return_value=MagicMock(matched_count=1))
    mock_collection.find = MagicMock(return_value=MagicMock(
        sort=MagicMock(return_value=MagicMock(
            skip=MagicMock(return_value=MagicMock(
                limit=MagicMock(return_value=MagicMock(
                    to_list=AsyncMock(return_value=[
                        {
                            "backup_id": "bkp_20260929_120000_abc12345",
                            "database_name": "itsm_helpdesk",
                            "filename": "geiser_itsm_helpdesk_20260929.archive.gz",
                            "filepath": "/backups/geiser_itsm_helpdesk_20260929.archive.gz",
                            "created_at": datetime.utcnow(),
                            "size_bytes": 1048576,
                            "checksum_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                            "status": BackupStatus.SUCCESS.value,
                            "duration_seconds": 2.5,
                            "backup_type": BackupType.SCHEDULED.value,
                            "verification_status": VerificationStatus.VERIFIED.value,
                            "last_verified_at": datetime.utcnow(),
                            "error_message": None,
                            "retention_class": RetentionClass.DAILY.value,
                            "deleted_at": None,
                            "is_protected": False,
                        }
                    ])
                ))
            ))
        ))
    ))
    mock_collection.find_one = AsyncMock(return_value={
        "backup_id": "bkp_20260929_120000_abc12345",
        "database_name": "itsm_helpdesk",
        "filename": "geiser_itsm_helpdesk_20260929.archive.gz",
        "filepath": "/backups/geiser_itsm_helpdesk_20260929.archive.gz",
        "created_at": datetime.utcnow(),
        "size_bytes": 1048576,
        "checksum_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "status": BackupStatus.SUCCESS.value,
        "duration_seconds": 2.5,
        "backup_type": BackupType.SCHEDULED.value,
        "verification_status": VerificationStatus.VERIFIED.value,
        "last_verified_at": datetime.utcnow(),
        "error_message": None,
        "retention_class": RetentionClass.DAILY.value,
        "deleted_at": None,
        "is_protected": False,
    })
    mock_collection.aggregate = MagicMock(return_value=MagicMock(
        to_list=AsyncMock(return_value=[{"_id": None, "total_size": 1048576}])
    ))

    mock_users = {
        ADMIN_ID: {"_id": ObjectId(ADMIN_ID), "is_active": True, "role": "ADMIN", "email": "admin@geiser.internal"},
        SUPERVISOR_ID: {"_id": ObjectId(SUPERVISOR_ID), "is_active": True, "role": "SUPERVISOR", "email": "sup@geiser.internal"},
        AGENT_ID: {"_id": ObjectId(AGENT_ID), "is_active": True, "role": "AGENT", "email": "agent@geiser.internal"},
        USER_ID: {"_id": ObjectId(USER_ID), "is_active": True, "role": "USER", "email": "user@geiser.internal"},
    }

    async def mock_user_find_one(query, *args, **kwargs):
        val = query.get("_id")
        uid = str(val) if val else ""
        return mock_users.get(uid, {"_id": ObjectId(USER_ID), "is_active": True, "role": "USER", "email": "user@geiser.internal"})

    mock_db.backups = mock_collection
    mock_db.audit_logs = MagicMock(insert_one=AsyncMock())
    mock_db.notifications = MagicMock(find_one=AsyncMock(return_value=None), insert_one=AsyncMock())
    mock_db.tickets = MagicMock()
    mock_db.token_blacklist = MagicMock(find_one=AsyncMock(return_value=None))
    mock_db.users = MagicMock(find_one=AsyncMock(side_effect=mock_user_find_one))

    app.dependency_overrides[get_database] = lambda: mock_db
    return TestClient(app)


# ─────────────────────────────────────────────────────────────
# 1. RBAC Authorization Tests
# ─────────────────────────────────────────────────────────────

def test_admin_can_access_list_and_stats(test_client):
    admin_token = create_token(role="ADMIN")
    headers = {"Authorization": f"Bearer {admin_token}"}

    res = test_client.get("/api/v1/backups", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 5
    assert len(data["items"]) == 1

    res_stats = test_client.get("/api/v1/backups/stats", headers=headers)
    assert res_stats.status_code == 200
    stats = res_stats.json()
    assert stats["total_backups"] == 5


def test_supervisor_has_readonly_access(test_client):
    sup_token = create_token(role="SUPERVISOR")
    headers = {"Authorization": f"Bearer {sup_token}"}

    # Allowed read
    res = test_client.get("/api/v1/backups", headers=headers)
    assert res.status_code == 200

    res_stats = test_client.get("/api/v1/backups/stats", headers=headers)
    assert res_stats.status_code == 200

    # Forbidden write/actions
    res_run = test_client.post("/api/v1/backups/run", headers=headers)
    assert res_run.status_code == 403

    res_del = test_client.delete("/api/v1/backups/bkp_123", headers=headers)
    assert res_del.status_code == 403


def test_agent_and_user_completely_forbidden(test_client):
    agent_token = create_token(role="AGENT")
    user_token = create_token(role="USER")

    for token in [agent_token, user_token]:
        headers = {"Authorization": f"Bearer {token}"}
        res_list = test_client.get("/api/v1/backups", headers=headers)
        assert res_list.status_code == 403

        res_stats = test_client.get("/api/v1/backups/stats", headers=headers)
        assert res_stats.status_code == 403

        res_run = test_client.post("/api/v1/backups/run", headers=headers)
        assert res_run.status_code == 403


def test_unauthenticated_request_rejected(test_client):
    res = test_client.get("/api/v1/backups")
    assert res.status_code == 401


# ─────────────────────────────────────────────────────────────
# 2. Scheduler Registration Tests
# ─────────────────────────────────────────────────────────────

def test_register_backup_schedule_adds_job():
    mock_scheduler = MagicMock()
    with patch.object(settings, "BACKUP_ENABLED", True), \
         patch.object(settings, "BACKUP_SCHEDULE_CRON", "0 2 * * *"):
        register_backup_schedule(mock_scheduler)
        mock_scheduler.add_job.assert_called_once()
        args, kwargs = mock_scheduler.add_job.call_args
        assert kwargs.get("id") == "automated_backup"


def test_register_backup_schedule_disabled_flag():
    mock_scheduler = MagicMock()
    with patch.object(settings, "BACKUP_ENABLED", False):
        register_backup_schedule(mock_scheduler)
        mock_scheduler.add_job.assert_not_called()


# ─────────────────────────────────────────────────────────────
# 3. Host Binary Auto-Discovery Test
# ─────────────────────────────────────────────────────────────

def test_resolve_mongodump_path_on_system():
    # Verify that resolve_mongodump_path does not crash and returns a string or None
    dump_path = resolve_mongodump_path()
    restore_path = resolve_mongorestore_path()
    # If installed on Windows, it will resolve the real path
    if dump_path:
        assert "mongodump" in dump_path.lower()
    if restore_path:
        assert "mongorestore" in restore_path.lower()
