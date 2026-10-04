from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any, Optional

from database.mongodb import get_database
from core.deps import RoleChecker, get_current_user
from schemas.schemas import (
    UserRole,
    UserOut,
    NotificationOut,
    SMSTestRequest,
    SMSTestResponse,
)
from services.notification_service import NotificationService
from services.sms.twilio_provider import TwilioProvider

router = APIRouter()


@router.get("/status")
async def get_sms_gateway_status(
    current_user: UserOut = Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database),
) -> Dict[str, Any]:
    """
    Returns SMS Gateway status and active provider.
    Never exposes auth tokens or sensitive credentials.
    """
    twilio = TwilioProvider()
    is_configured = twilio.is_configured()

    masked_from = None
    if twilio._from_number:
        # Mask phone number (e.g. +123****789)
        raw = twilio._from_number
        if len(raw) > 6:
            masked_from = raw[:4] + "****" + raw[-3:]
        else:
            masked_from = "****"

    return {
        "sms_enabled": True,
        "active_provider": "twilio" if is_configured else "simulated",
        "twilio_configured": is_configured,
        "from_number_configured": bool(twilio._from_number),
        "from_number_masked": masked_from,
    }


@router.post("/sms/test", response_model=SMSTestResponse)
async def send_test_sms(
    payload: SMSTestRequest,
    current_user: UserOut = Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database),
):
    """
    Admin-only diagnostic endpoint to test SMS sending via active provider (Twilio or simulated).
    Returns delivery status and message SID without exposing credentials.
    """
    notification_service = NotificationService(db)
    result = await notification_service.send_direct_sms(
        to=payload.to,
        message=payload.message,
        user_id=current_user.id,
        user_email=current_user.email,
        event_type="MANUAL_ADMIN_TEST"
    )

    return SMSTestResponse(
        success=result.success,
        status=result.status,
        provider=result.provider,
        message_id=result.message_id,
        to=result.to or payload.to,
        error=result.error
    )


@router.get("", response_model=List[NotificationOut])
async def list_notifications(
    limit: int = 50,
    status: Optional[str] = None,
    channel: Optional[str] = None,
    current_user: UserOut = Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database),
):
    """
    List notifications with optional filtering by status and channel (admin only).
    """
    notification_service = NotificationService(db)
    return await notification_service.get_recent_notifications(
        limit=limit, status=status, channel=channel
    )


@router.get("/history", response_model=List[NotificationOut])
async def get_notifications_history(
    limit: int = 50,
    current_user: UserOut = Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database),
):
    """
    Returns recent notification audit trail records (admin only).
    """
    notification_service = NotificationService(db)
    return await notification_service.get_recent_notifications(limit=limit)


@router.get("/stats")
async def get_notifications_stats(
    current_user: UserOut = Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database),
) -> Dict[str, Any]:
    """
    Returns aggregate statistics across all notification queues (admin only).
    """
    from services.notification_worker import NotificationWorker
    worker = NotificationWorker(db)
    return await worker.get_stats()


@router.post("/{notification_id}/retry", response_model=NotificationOut)
async def retry_notification_endpoint(
    notification_id: str,
    current_user: UserOut = Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database),
):
    """
    Manually retries a DEAD_LETTER, FAILED, or RETRYING notification immediately (admin only).
    """
    from services.notification_worker import NotificationWorker
    worker = NotificationWorker(db)
    updated = await worker.retry_notification(notification_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Notification not found")

    return NotificationOut(
        id=str(updated["_id"]),
        user_id=str(updated.get("user_id", "")),
        user_email=updated.get("user_email"),
        ticket_id=updated.get("ticket_id"),
        channel=updated.get("channel", "EMAIL"),
        title=updated.get("title", ""),
        message=updated.get("message", ""),
        status=updated.get("status", "PENDING"),
        provider=updated.get("provider"),
        provider_message_id=updated.get("provider_message_id"),
        event_type=updated.get("event_type"),
        error_detail=updated.get("error_detail"),
        recipient=updated.get("recipient"),
        attempts=updated.get("attempts", 0),
        max_retries=updated.get("max_retries", 5),
        next_retry_at=updated.get("next_retry_at"),
        error_type=updated.get("error_type"),
        idempotency_key=updated.get("idempotency_key"),
        retry_history=updated.get("retry_history"),
        created_at=updated.get("created_at", datetime.utcnow())
    )


@router.post("/dead-letter/retry-all")
async def retry_all_dead_letters_endpoint(
    current_user: UserOut = Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database),
):
    """
    Bulk resets all DEAD_LETTER notifications to PENDING for re-dispatch (admin only).
    """
    from services.notification_worker import NotificationWorker
    worker = NotificationWorker(db)
    count = await worker.retry_all_dead_letters()
    return {"message": f"Successfully reset {count} dead-letter notifications to PENDING", "count": count}
