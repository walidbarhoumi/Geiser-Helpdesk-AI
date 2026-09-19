from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any

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
