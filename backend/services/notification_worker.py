"""
notification_worker.py
======================
STEP 8 — Reliable Outbound Notification Queue & Worker.
Features:
- MongoDB `notifications` queue processing
- Exponential backoff retry strategy [30s, 120s, 600s, 1800s, 7200s]
- Error classification: TEMPORARY (network timeout, 4xx) vs PERMANENT (5xx, bad syntax, auth failure)
- Dead-Letter Queue (DLQ) for exceeded max retries or permanent failures
- Manual and bulk retry mechanisms for administrators
- Complete non-blocking execution & ISO 27001 audit compliance
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from bson import ObjectId
from pymongo import ReturnDocument
from motor.motor_asyncio import AsyncIOMotorDatabase

from core.config import settings
from database.mongodb import db as mongo_db
from models.base import MongoModel
from services.email_service import EmailService

logger = logging.getLogger(__name__)

# Standard exponential backoff retry intervals in seconds:
# Attempt 1: 30s | Attempt 2: 2m | Attempt 3: 10m | Attempt 4: 30m | Attempt 5: 2h
DEFAULT_BACKOFF_SCHEDULE = [30, 120, 600, 1800, 7200]
DEFAULT_MAX_RETRIES = 5


def calculate_backoff(attempt: int, schedule: Optional[List[int]] = None) -> int:
    """Calculates backoff duration in seconds based on attempt count (1-indexed)."""
    sched = schedule or DEFAULT_BACKOFF_SCHEDULE
    if not sched:
        return 30
    idx = max(0, min(attempt - 1, len(sched) - 1))
    return sched[idx]


class NotificationWorker:
    """
    Asynchronous queue worker for dispatching and retrying outbound notifications.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.notifications = db.notifications

    async def process_single_notification(self, notif_doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes a single notification from the queue:
        - Locks doc by transitioning status to 'PROCESSING'
        - Dispatches via EmailService or SMS provider
        - On success: marks SENT
        - On temporary failure: sets RETRYING with next_retry_at or DEAD_LETTER if max_retries exceeded
        - On permanent failure: immediately marks FAILED or DEAD_LETTER (no wasteful retries)
        """
        raw_id = notif_doc.get("_id")
        oid = MongoModel.to_object_id(raw_id)
        if not oid:
            logger.error(f"[NotificationWorker] Invalid document ID: {raw_id}")
            return notif_doc

        # Atomic lock
        now = datetime.utcnow()
        locked = await self.notifications.find_one_and_update(
            {"_id": oid, "status": {"$in": ["PENDING", "RETRYING"]}},
            {"$set": {"status": "PROCESSING", "updated_at": now}},
            return_document=ReturnDocument.AFTER
        )
        if not locked:
            return notif_doc

        channel = locked.get("channel", "EMAIL").upper()
        recipient = locked.get("recipient") or locked.get("user_email")
        title = locked.get("title", "Notification GEISER")
        html_body = locked.get("html_body") or locked.get("message", "")
        current_attempts = locked.get("attempts", 0)
        max_retries = locked.get("max_retries", getattr(settings, "NOTIFICATION_MAX_RETRIES", DEFAULT_MAX_RETRIES))

        dispatch_result: Dict[str, Any] = {"success": False, "error_type": "TEMPORARY", "error_detail": "Not processed"}

        if channel == "EMAIL":
            dispatch_result = await EmailService.send_email_detailed_async(
                to_email=recipient,
                subject=title,
                html_body=html_body,
                attachments=locked.get("attachments")
            )
        elif channel == "SMS":
            # SMS dispatch through Twilio or Simulated provider
            try:
                from services.notification_service import NotificationService
                ns = NotificationService(self.db)
                sms_res = await ns.sms_provider.send_sms(to=recipient, message=locked.get("message", ""))
                if sms_res.success:
                    dispatch_result = {"success": True, "error_type": None, "error_detail": None}
                else:
                    dispatch_result = {
                        "success": False,
                        "error_type": "PERMANENT" if "invalid" in (sms_res.error or "").lower() else "TEMPORARY",
                        "error_detail": sms_res.error
                    }
            except Exception as sms_err:
                dispatch_result = {"success": False, "error_type": "TEMPORARY", "error_detail": str(sms_err)}
        else:
            # IN_APP or other channels mark success directly
            dispatch_result = {"success": True, "error_type": None, "error_detail": None}

        finish_time = datetime.utcnow()

        if dispatch_result.get("success"):
            new_status = "SENT" if channel == "EMAIL" else "DELIVERED"
            history_entry = {
                "attempt": current_attempts + 1,
                "timestamp": finish_time.isoformat() + "Z",
                "status": new_status,
                "detail": "Delivered successfully"
            }
            updated = await self.notifications.find_one_and_update(
                {"_id": oid},
                {
                    "$set": {
                        "status": new_status,
                        "sent_at": finish_time,
                        "updated_at": finish_time,
                        "error_detail": None,
                        "error_type": None,
                        "next_retry_at": None,
                    },
                    "$inc": {"attempts": 1},
                    "$push": {"retry_history": history_entry}
                },
                return_document=ReturnDocument.AFTER
            )

            # Live WebSocket notification broadcast
            try:
                from websocket.dispatcher import event_dispatcher
                await event_dispatcher.publish_notification(
                    user_id=str(locked.get("user_id", "")),
                    notification={
                        "id": str(oid),
                        "ticket_id": locked.get("ticket_id"),
                        "title": title,
                        "message": locked.get("message", ""),
                        "channel": channel,
                        "status": new_status,
                        "created_at": locked.get("created_at", finish_time).isoformat() + "Z",
                    }
                )
            except Exception as ws_err:
                logger.debug(f"[NotificationWorker] WS broadcast skipped: {ws_err}")

            return updated or locked

        # Handle failure
        err_type = dispatch_result.get("error_type", "TEMPORARY")
        err_detail = dispatch_result.get("error_detail", "Delivery failed")
        new_attempts = current_attempts + 1

        if err_type == "PERMANENT":
            new_status = "FAILED"
            next_retry = None
        else:
            if new_attempts >= max_retries:
                new_status = "DEAD_LETTER"
                next_retry = None
                logger.warning(
                    f"[NotificationWorker] Notification {oid} reached max retries ({max_retries}). Moved to DEAD_LETTER."
                )
            else:
                new_status = "RETRYING"
                backoff_secs = calculate_backoff(new_attempts)
                next_retry = finish_time + timedelta(seconds=backoff_secs)
                logger.info(
                    f"[NotificationWorker] Notification {oid} failed temporarily (attempt {new_attempts}/{max_retries}). "
                    f"Retrying in {backoff_secs}s at {next_retry}."
                )

        history_entry = {
            "attempt": new_attempts,
            "timestamp": finish_time.isoformat() + "Z",
            "status": new_status,
            "error_type": err_type,
            "error_detail": err_detail,
            "next_retry_at": next_retry.isoformat() + "Z" if next_retry else None,
        }

        updated = await self.notifications.find_one_and_update(
            {"_id": oid},
            {
                "$set": {
                    "status": new_status,
                    "error_type": err_type,
                    "error_detail": err_detail,
                    "next_retry_at": next_retry,
                    "updated_at": finish_time,
                },
                "$inc": {"attempts": 1},
                "$push": {"retry_history": history_entry}
            },
            return_document=ReturnDocument.AFTER
        )
        return updated or locked

    async def run_batch(self, batch_size: int = 50) -> Dict[str, int]:
        """Polls MongoDB for PENDING/RETRYING notifications whose next_retry_at is due."""
        now = datetime.utcnow()
        cursor = self.notifications.find({
            "status": {"$in": ["PENDING", "RETRYING"]},
            "$or": [
                {"next_retry_at": {"$lte": now}},
                {"next_retry_at": None},
                {"next_retry_at": {"$exists": False}},
            ]
        }).sort("next_retry_at", 1).limit(batch_size)

        docs = await cursor.to_list(batch_size)
        if not docs:
            return {"processed": 0, "sent": 0, "retrying": 0, "dead_letter": 0, "failed": 0}

        counts = {"processed": len(docs), "sent": 0, "retrying": 0, "dead_letter": 0, "failed": 0}

        for doc in docs:
            try:
                res = await self.process_single_notification(doc)
                st = res.get("status", "").upper()
                if st in ["SENT", "DELIVERED"]:
                    counts["sent"] += 1
                elif st == "RETRYING":
                    counts["retrying"] += 1
                elif st == "DEAD_LETTER":
                    counts["dead_letter"] += 1
                elif st == "FAILED":
                    counts["failed"] += 1
            except Exception as item_err:
                logger.error(f"[NotificationWorker] Error processing notification {doc.get('_id')}: {item_err}")

        return counts

    async def retry_notification(self, notification_id: str) -> Optional[Dict[str, Any]]:
        """Manually resets a DEAD_LETTER, FAILED, or RETRYING notification for immediate dispatch."""
        oid = MongoModel.to_object_id(notification_id)
        if not oid:
            return None

        now = datetime.utcnow()
        history_entry = {
            "attempt": 0,
            "timestamp": now.isoformat() + "Z",
            "status": "PENDING",
            "detail": "Manual admin retry requested"
        }

        updated = await self.notifications.find_one_and_update(
            {"_id": oid},
            {
                "$set": {
                    "status": "PENDING",
                    "next_retry_at": now,
                    "updated_at": now,
                    "error_detail": None,
                    "error_type": None,
                },
                "$push": {"retry_history": history_entry}
            },
            return_document=ReturnDocument.AFTER
        )
        return updated

    async def retry_all_dead_letters(self) -> int:
        """Resets all DEAD_LETTER notifications to PENDING for re-dispatch."""
        now = datetime.utcnow()
        history_entry = {
            "attempt": 0,
            "timestamp": now.isoformat() + "Z",
            "status": "PENDING",
            "detail": "Bulk admin retry requested"
        }
        res = await self.notifications.update_many(
            {"status": "DEAD_LETTER"},
            {
                "$set": {
                    "status": "PENDING",
                    "next_retry_at": now,
                    "updated_at": now,
                    "error_detail": None,
                    "error_type": None,
                },
                "$push": {"retry_history": history_entry}
            }
        )
        return res.modified_count

    async def get_stats(self) -> Dict[str, Any]:
        """Returns aggregate metrics on notification queues."""
        pipeline = [
            {"$group": {"_id": "$status", "count": {"$sum": 1}}}
        ]
        results = await self.notifications.aggregate(pipeline).to_list(100)
        counts = {r["_id"]: r["count"] for r in results if r.get("_id")}

        total = sum(counts.values())
        return {
            "total": total,
            "pending": counts.get("PENDING", 0),
            "retrying": counts.get("RETRYING", 0),
            "sent": counts.get("SENT", 0),
            "delivered": counts.get("DELIVERED", 0),
            "failed": counts.get("FAILED", 0),
            "dead_letter": counts.get("DEAD_LETTER", 0),
            "skipped_duplicate": counts.get("SKIPPED_DUPLICATE", 0),
            "simulated": counts.get("SIMULATED", 0),
        }


async def run_notification_worker(database: Optional[AsyncIOMotorDatabase] = None) -> Dict[str, int]:
    """Background entrypoint invoked periodically by APScheduler."""
    try:
        db_instance = database or mongo_db.db
        if db_instance is None:
            logger.debug("[NotificationWorker] Database not connected, skipping worker run.")
            return {"processed": 0, "sent": 0, "retrying": 0, "dead_letter": 0, "failed": 0}

        worker = NotificationWorker(db_instance)
        stats = await worker.run_batch(batch_size=50)
        if stats.get("processed", 0) > 0:
            logger.info(f"[NotificationWorker] Batch summary: {stats}")
        return stats
    except Exception as e:
        logger.error(f"[NotificationWorker] Execution error: {e}")
        return {"processed": 0, "sent": 0, "retrying": 0, "dead_letter": 0, "failed": 0}
