from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from database.mongodb import get_database
from core.deps import RoleChecker
from schemas.schemas import UserRole
from services.email_ticket_service import EmailTicketService
from services.imap_service import is_imap_configured
from core.config import settings

router = APIRouter()


class EmailSimulateRequest(BaseModel):
    """Simulate an inbound email for testing (no IMAP required)."""
    sender_email: EmailStr
    sender_name: str = ""
    subject: str
    body: str


@router.get("/status")
async def email_channel_status(
    current_user=Depends(RoleChecker([UserRole.ADMIN])),
):
    """Check if inbound email channel is configured."""
    return {
        "imap_enabled": settings.IMAP_ENABLED,
        "imap_configured": is_imap_configured(),
        "imap_host": settings.IMAP_HOST,
        "imap_folder": settings.IMAP_FOLDER,
        "poll_interval_minutes": settings.EMAIL_POLL_INTERVAL_MINUTES,
        "auto_provision_users": settings.EMAIL_AUTO_PROVISION_USERS,
    }


@router.post("/poll")
async def trigger_email_poll(
    current_user=Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database),
):
    """Manually poll the inbox and process new support emails (admin only)."""
    stats = await EmailTicketService(db).poll_and_process()
    return stats


@router.post("/simulate")
async def simulate_inbound_email(
    payload: EmailSimulateRequest,
    current_user=Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database),
):
    """
    Simulate processing an inbound email without IMAP (admin testing).
    Useful to verify AI triage and ticket creation logic.
    """
    from services.imap_service import InboundEmail
    import uuid

    inbound = InboundEmail(
        message_id=f"simulate-{uuid.uuid4().hex}",
        sender_email=str(payload.sender_email),
        sender_name=payload.sender_name,
        subject=payload.subject,
        body=payload.body,
    )
    result = await EmailTicketService(db).process_inbound_email(inbound)
    return result
