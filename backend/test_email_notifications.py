"""
test_email_notifications.py
===========================
STEP 8 — Outbound Notification Reliability & Worker Test Suite (12 Tests).
Covers:
- Exponential backoff calculation [30s, 120s, 600s, 1800s, 7200s]
- Queueing with Idempotency Key anti-duplication
- Worker dispatch: Success -> SENT / DELIVERED
- Error classification: TEMPORARY -> RETRYING with next_retry_at
- Error classification: PERMANENT -> FAILED / DEAD_LETTER without retry
- Max retries handling -> DEAD_LETTER queue
- Manual admin single retry API
- Bulk admin dead-letter retry API
- Aggregated queue statistics
- Admin RBAC enforcement on notification routes
- Non-blocking notification failure isolation
- Live WebSocket event dispatch
"""

import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from bson import ObjectId
from jose import jwt
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.config import settings
from database.mongodb import get_database
from routes.notifications import router as notifications_router
from schemas.schemas import UserRole
from services.notification_service import NotificationService
from services.notification_worker import (
    NotificationWorker,
    calculate_backoff,
    DEFAULT_BACKOFF_SCHEDULE,
    run_notification_worker,
)


ADMIN_ID = "6abba6e6702d1408c1f39851"
USER_ID = "6abba6e6702d1408c1f39852"


def create_token(role: str, user_id: str = None) -> str:
    uid = user_id or (ADMIN_ID if role == "ADMIN" else USER_ID)
    payload = {
        "sub": uid,
        "role": role,
        "email": f"{role.lower()}@geiser.internal",
        "type": "access",
        "exp": datetime.utcnow() + timedelta(hours=1),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


# 1. Exponential backoff calculation
def test_calculate_backoff_schedule():
    assert calculate_backoff(1) == 30      # 30 seconds
    assert calculate_backoff(2) == 120     # 2 minutes
    assert calculate_backoff(3) == 600     # 10 minutes
    assert calculate_backoff(4) == 1800    # 30 minutes
    assert calculate_backoff(5) == 7200    # 2 hours
    # Capped at last element for attempt > 5
    assert calculate_backoff(6) == 7200
    assert calculate_backoff(10) == 7200


# 2. Queueing with Idempotency Key prevents duplicate entries
@pytest.mark.asyncio
async def test_notification_queue_idempotency():
    db = MagicMock()
    service = NotificationService(db)

    existing_doc = {
        "_id": ObjectId("6abba6e6702d1408c1f39801"),
        "idempotency_key": "UNIQUE_KEY_001",
        "status": "SENT",
        "title": "Existing",
    }
    service.notifications.find_one = AsyncMock(return_value=existing_doc)

    res = await service.queue_notification(
        user_id="user-1",
        user_email="user@test.com",
        ticket_id="ticket-1",
        channel="EMAIL",
        title="Existing",
        message="Hello",
        idempotency_key="UNIQUE_KEY_001",
    )

    assert str(res["_id"]) == "6abba6e6702d1408c1f39801"
    # insert_one should NOT have been called
    service.notifications.insert_one.assert_not_called()


# 3. Worker processes PENDING notification: success transitions to SENT
@pytest.mark.asyncio
async def test_worker_processes_pending_success():
    db = MagicMock()
    worker = NotificationWorker(db)

    notif_id = ObjectId()
    doc = {
        "_id": notif_id,
        "channel": "EMAIL",
        "recipient": "user@test.com",
        "title": "Confirmation Ticket",
        "message": "Votre ticket est pris en charge.",
        "html_body": "<p>Votre ticket est pris en charge.</p>",
        "status": "PENDING",
        "attempts": 0,
        "max_retries": 5,
    }

    worker.notifications.find_one_and_update = AsyncMock(
        side_effect=[
            # First call locks doc -> status PROCESSING
            {**doc, "status": "PROCESSING"},
            # Second call updates doc -> status SENT
            {**doc, "status": "SENT", "attempts": 1},
        ]
    )

    with patch("services.email_service.EmailService.send_email_detailed_async", new_callable=AsyncMock) as mock_send, \
         patch("websocket.dispatcher.event_dispatcher.publish_notification", new_callable=AsyncMock) as mock_ws:
        mock_send.return_value = {"success": True, "error_type": None, "error_detail": None}

        res = await worker.process_single_notification(doc)
        assert res["status"] == "SENT"
        assert res["attempts"] == 1
        mock_send.assert_called_once()


# 4. Worker processes temporary error: transitions to RETRYING
@pytest.mark.asyncio
async def test_worker_handles_temporary_error_retry():
    db = MagicMock()
    worker = NotificationWorker(db)

    notif_id = ObjectId()
    doc = {
        "_id": notif_id,
        "channel": "EMAIL",
        "recipient": "user@test.com",
        "title": "Confirmation Ticket",
        "message": "Body",
        "status": "PENDING",
        "attempts": 0,
        "max_retries": 5,
    }

    worker.notifications.find_one_and_update = AsyncMock(
        side_effect=[
            {**doc, "status": "PROCESSING"},
            {**doc, "status": "RETRYING", "attempts": 1},
        ]
    )

    with patch("services.email_service.EmailService.send_email_detailed_async", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = {
            "success": False,
            "error_type": "TEMPORARY",
            "error_detail": "Connection timed out",
        }

        res = await worker.process_single_notification(doc)
        # Verify second find_one_and_update call set RETRYING and calculated backoff
        update_call = worker.notifications.find_one_and_update.call_args_list[1]
        update_dict = update_call[0][1]
        assert update_dict["$set"]["status"] == "RETRYING"
        assert update_dict["$set"]["error_type"] == "TEMPORARY"
        assert update_dict["$set"]["next_retry_at"] is not None


# 5. Worker processes permanent error: transitions immediately to FAILED without retry
@pytest.mark.asyncio
async def test_worker_handles_permanent_error_no_retry():
    db = MagicMock()
    worker = NotificationWorker(db)

    notif_id = ObjectId()
    doc = {
        "_id": notif_id,
        "channel": "EMAIL",
        "recipient": "bad_syntax_email",
        "title": "Test",
        "message": "Body",
        "status": "PENDING",
        "attempts": 0,
        "max_retries": 5,
    }

    worker.notifications.find_one_and_update = AsyncMock(
        side_effect=[
            {**doc, "status": "PROCESSING"},
            {**doc, "status": "FAILED", "attempts": 1},
        ]
    )

    with patch("services.email_service.EmailService.send_email_detailed_async", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = {
            "success": False,
            "error_type": "PERMANENT",
            "error_detail": "Invalid recipient email syntax",
        }

        res = await worker.process_single_notification(doc)
        update_call = worker.notifications.find_one_and_update.call_args_list[1]
        update_dict = update_call[0][1]
        assert update_dict["$set"]["status"] == "FAILED"
        assert update_dict["$set"]["next_retry_at"] is None


# 6. Max retries reached transitions to DEAD_LETTER
@pytest.mark.asyncio
async def test_worker_moves_to_dead_letter_on_max_retries():
    db = MagicMock()
    worker = NotificationWorker(db)

    notif_id = ObjectId()
    doc = {
        "_id": notif_id,
        "channel": "EMAIL",
        "recipient": "user@test.com",
        "title": "Test",
        "message": "Body",
        "status": "RETRYING",
        "attempts": 4,   # 5th attempt is about to fail
        "max_retries": 5,
    }

    worker.notifications.find_one_and_update = AsyncMock(
        side_effect=[
            {**doc, "status": "PROCESSING"},
            {**doc, "status": "DEAD_LETTER", "attempts": 5},
        ]
    )

    with patch("services.email_service.EmailService.send_email_detailed_async", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = {
            "success": False,
            "error_type": "TEMPORARY",
            "error_detail": "Network down",
        }

        res = await worker.process_single_notification(doc)
        update_call = worker.notifications.find_one_and_update.call_args_list[1]
        update_dict = update_call[0][1]
        assert update_dict["$set"]["status"] == "DEAD_LETTER"
        assert update_dict["$set"]["next_retry_at"] is None


# 7. Manual admin retry resets status to PENDING
@pytest.mark.asyncio
async def test_manual_admin_retry_notification():
    db = MagicMock()
    worker = NotificationWorker(db)

    notif_id = str(ObjectId())
    worker.notifications.find_one_and_update = AsyncMock(
        return_value={"_id": ObjectId(notif_id), "status": "PENDING"}
    )

    updated = await worker.retry_notification(notif_id)
    assert updated is not None
    assert updated["status"] == "PENDING"
    call_args = worker.notifications.find_one_and_update.call_args[0]
    assert call_args[1]["$set"]["status"] == "PENDING"
    assert call_args[1]["$set"]["error_detail"] is None


# 8. Bulk admin retry resets all dead-letter notifications
@pytest.mark.asyncio
async def test_bulk_admin_retry_dead_letters():
    db = MagicMock()
    worker = NotificationWorker(db)

    worker.notifications.update_many = AsyncMock(return_value=MagicMock(modified_count=7))
    count = await worker.retry_all_dead_letters()
    assert count == 7
    call_args = worker.notifications.update_many.call_args[0]
    assert call_args[0] == {"status": "DEAD_LETTER"}
    assert call_args[1]["$set"]["status"] == "PENDING"


# 9. Notification stats aggregation
@pytest.mark.asyncio
async def test_get_notification_stats_aggregation():
    db = MagicMock()
    worker = NotificationWorker(db)

    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=[
        {"_id": "SENT", "count": 42},
        {"_id": "RETRYING", "count": 3},
        {"_id": "DEAD_LETTER", "count": 2},
        {"_id": "PENDING", "count": 5},
    ])
    worker.notifications.aggregate = MagicMock(return_value=mock_cursor)

    stats = await worker.get_stats()
    assert stats["total"] == 52
    assert stats["sent"] == 42
    assert stats["retrying"] == 3
    assert stats["dead_letter"] == 2
    assert stats["pending"] == 5


# 10. Admin RBAC enforcement on notification routes
def test_notification_api_rbac_protection():
    app = FastAPI()
    app.include_router(notifications_router, prefix="/api/v1/notifications")

    mock_db = MagicMock()
    app.dependency_overrides[get_database] = lambda: mock_db

    from core.deps import get_current_user

    client = TestClient(app)

    # Unauthenticated -> 401/403
    assert client.get("/api/v1/notifications").status_code in [401, 403]
    assert client.get("/api/v1/notifications/stats").status_code in [401, 403]

    # Non-admin user -> 403
    user_token = create_token("USER")
    app.dependency_overrides[get_current_user] = lambda: {
        "id": USER_ID, "email": "user@geiser.internal", "role": "USER"
    }
    assert client.get("/api/v1/notifications", headers={"Authorization": f"Bearer {user_token}"}).status_code == 403
    assert client.get("/api/v1/notifications/stats", headers={"Authorization": f"Bearer {user_token}"}).status_code == 403

    # Admin user -> 200
    admin_token = create_token("ADMIN")
    app.dependency_overrides[get_current_user] = lambda: {
        "id": ADMIN_ID, "email": "admin@geiser.internal", "role": "ADMIN"
    }
    with patch("services.notification_worker.NotificationWorker.get_stats", new_callable=AsyncMock) as mock_stats:
        mock_stats.return_value = {"total": 10, "sent": 10}
        res = client.get("/api/v1/notifications/stats", headers={"Authorization": f"Bearer {admin_token}"})
        assert res.status_code == 200
        assert res.json()["total"] == 10


# 11. Non-blocking error isolation: ticket creation succeeds even when email fails
@pytest.mark.asyncio
async def test_non_blocking_notification_isolation():
    db = MagicMock()
    service = NotificationService(db)

    # Mock DB queries
    service.users.find_one = AsyncMock(return_value={"_id": ObjectId(), "email": "user@corp.com", "phone_number": None})
    service.notifications.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))

    # Even if email service throws unexpected exception, notify_ticket_created must NOT raise
    with patch("services.email_service.EmailService.send_email_detailed_async", side_effect=Exception("Severe SMTP network crash")):
        await service.notify_ticket_created({
            "_id": ObjectId("6abba6e6702d1408c1f39822"),
            "user_id": str(ObjectId()),
            "subject": "Crash test",
            "priority": "HIGH"
        })
    # If we reached this line, the exception was safely caught and isolated


# 12. WebSocket notification dispatched
@pytest.mark.asyncio
async def test_websocket_event_dispatched_on_notification():
    db = MagicMock()
    service = NotificationService(db)

    notif_id = ObjectId()
    service.notifications.insert_one = AsyncMock(return_value=MagicMock(inserted_id=notif_id))

    with patch("websocket.dispatcher.event_dispatcher.publish_notification", new_callable=AsyncMock) as mock_ws:
        await service._record_notification(
            user_id="user-123",
            user_email="user@test.com",
            ticket_id="ticket-777",
            channel="EMAIL",
            title="Notification Test",
            message="Contenu",
            status="SENT"
        )
        mock_ws.assert_called_once()
        ws_call = mock_ws.call_args[1]
        assert ws_call["user_id"] == "user-123"
        assert ws_call["notification"]["title"] == "Notification Test"
