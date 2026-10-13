import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock
from bson import ObjectId
from fastapi.testclient import TestClient

from main import app
from database.mongodb import get_database
from core.deps import get_current_user
from schemas.schemas import UserRole, UserOut


def test_list_users_with_local_and_standard_emails():
    """Ensure GET /api/v1/users/ serializes both standard and enterprise/local domain emails without error."""
    mock_users = [
        {
            "_id": ObjectId("69fbaf3db5574840b80319fb"),
            "email": "bwalid819@gmail.com",
            "full_name": "walidbarhoumi",
            "role": "ADMIN",
            "is_active": True,
            "created_at": datetime.utcnow(),
            "two_factor_enabled": True,
            "hashed_password": "supersecretpasswordhash"
        },
        {
            "_id": ObjectId("6ac2acb158ab597edcac1a64"),
            "email": "logintest@geiser.local",
            "full_name": "Login Test User",
            "role": "USER",
            "is_active": True,
            "created_at": datetime.utcnow(),
            "two_factor_enabled": False,
            "hashed_password": "supersecretpasswordhash"
        }
    ]

    mock_db = MagicMock()
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=mock_users)
    mock_db.users.find = MagicMock(return_value=cursor)
    mock_db.users.find_one = AsyncMock(return_value=mock_users[0])

    admin_caller = {
        "id": "69fbaf3db5574840b80319fb",
        "email": "bwalid819@gmail.com",
        "role": UserRole.ADMIN,
        "is_active": True
    }

    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: admin_caller

    try:
        client = TestClient(app)
        res = client.get("/api/v1/users/")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 2
        emails = [u["email"] for u in data]
        assert "bwalid819@gmail.com" in emails
        assert "logintest@geiser.local" in emails

        # Sensitive field check: password hashes must never be exposed
        for u in data:
            assert "hashed_password" not in u
            assert "password" not in u
    finally:
        app.dependency_overrides.clear()


def test_list_users_non_admin_forbidden():
    """Non-admin callers must be rejected with 403."""
    mock_db = MagicMock()
    user_caller = {
        "id": "6ac2acb158ab597edcac1a64",
        "email": "logintest@geiser.local",
        "role": UserRole.USER,
        "is_active": True
    }

    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: user_caller

    try:
        client = TestClient(app)
        res = client.get("/api/v1/users/")
        assert res.status_code == 403
    finally:
        app.dependency_overrides.clear()
