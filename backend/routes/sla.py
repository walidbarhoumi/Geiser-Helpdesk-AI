from fastapi import APIRouter, Depends, HTTPException
from typing import List
from database.mongodb import get_database
from core.deps import get_current_user, RoleChecker
from schemas.schemas import (
    SLAPolicyOut, SLAPolicyUpdate, SLAAlertOut,
    SLATicketDetailOut, SLAScanResult, UserRole, TicketPriority,
)
from services.sla_service import SLAService

router = APIRouter()


@router.get("/policies", response_model=List[SLAPolicyOut])
async def list_policies(
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.AGENT])),
    db=Depends(get_database),
):
    """List default + custom SLA policies per priority."""
    return await SLAService(db).get_all_policies()


@router.put("/policies/{priority}", response_model=SLAPolicyOut)
async def update_policy(
    priority: TicketPriority,
    body: SLAPolicyUpdate,
    current_user=Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database),
):
    """Admin override of SLA times for a given priority."""
    service = SLAService(db)
    update = body.dict(exclude_unset=True)
    if not update:
        raise HTTPException(status_code=400, detail="No fields to update")
    policy = await service.update_policy(priority.value, update)
    return {
        "priority": priority,
        "response_time_hours": policy["response_time_hours"],
        "resolution_time_hours": policy["resolution_time_hours"],
        "at_risk_threshold_pct": policy.get("at_risk_threshold_pct", 0.20),
    }


@router.get("/alerts", response_model=List[SLAAlertOut])
async def list_alerts(
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.AGENT])),
    db=Depends(get_database),
):
    """List active AT_RISK / BREACHED tickets."""
    return await SLAService(db).get_at_risk_tickets()


@router.get("/tickets/{ticket_id}/status", response_model=SLATicketDetailOut)
async def get_ticket_sla_status(
    ticket_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Get SLA detail for a specific ticket."""
    detail = await SLAService(db).get_ticket_sla_detail(ticket_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return detail


@router.post("/scan", response_model=SLAScanResult)
async def trigger_sla_scan(
    current_user=Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database),
):
    """Manually trigger SLA scan (admin only)."""
    stats = await SLAService(db).scan_tickets_and_alert()
    return stats
