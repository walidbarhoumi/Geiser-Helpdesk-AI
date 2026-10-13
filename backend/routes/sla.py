from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from typing import List
from database.mongodb import get_database
from core.deps import get_current_user, RoleChecker
from models.base import MongoModel
from schemas.schemas import (
    SLAPolicyOut, SLAPolicyUpdate, SLAAlertOut,
    SLATicketDetailOut, SLAScanResult, SLACalculateRequest, SLACalculateResponse,
    SLARiskConfigOut, SLARiskConfigUpdate, SLARiskOverviewOut, SLARiskEvaluationResult,
    UserRole, TicketPriority,
)
from services.sla_service import SLAService
from services.sla_risk_service import SLARiskService

router = APIRouter()


@router.get("/policies", response_model=List[SLAPolicyOut])
async def list_policies(
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.AGENT])),
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

    # ISO 27001 Security Audit Log
    try:
        from services.audit_service import AuditService
        from schemas.schemas import AuditEventCategory, AuditSeverity
        import asyncio
        asyncio.create_task(
            AuditService(db).log_event(
                event_category=AuditEventCategory.SLA,
                event_type="SLA_POLICY_OVERRIDE",
                severity=AuditSeverity.WARNING,
                target_resource_type="sla_policy",
                target_resource_id=priority.value,
                actor_id=str(current_user.get("id")),
                actor_email=current_user.get("email"),
                actor_role=current_user.get("role", "ADMIN"),
                status="SUCCESS",
                details={
                    "priority": priority.value,
                    "updated_fields": update
                }
            )
        )
    except Exception:
        pass

    return {
        "priority": priority,
        "response_time_hours": policy["response_time_hours"],
        "resolution_time_hours": policy["resolution_time_hours"],
        "at_risk_threshold_pct": policy.get("at_risk_threshold_pct", 0.20),
    }


@router.post("/calculate", response_model=SLACalculateResponse)
async def calculate_sla_preview(
    body: SLACalculateRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Preview or calculate SLA deadlines and applied rule for a given priority, category and subcategory."""
    service = SLAService(db)
    created_at = body.created_at or datetime.utcnow()
    prio_str = body.priority.value if hasattr(body.priority, "value") else str(body.priority)
    res = await service.calculate_ticket_sla(
        priority=prio_str,
        created_at=created_at,
        category=body.category,
        subcategory=body.subcategory
    )
    applied = res.get("applied_rule", {})
    return {
        "priority": body.priority,
        "category": body.category,
        "subcategory": body.subcategory,
        "response_time_hours": res["response_time_hours"],
        "resolution_time_hours": res["resolution_time_hours"],
        "response_deadline": res["response_deadline"],
        "resolution_deadline": res["resolution_deadline"],
        "rule_level": applied.get("rule_level", "unknown"),
        "applied_rule": applied,
    }


@router.get("/alerts", response_model=List[SLAAlertOut])
async def list_alerts(
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.AGENT])),
    db=Depends(get_database),
):
    """List active AT_RISK / BREACHED tickets."""
    alerts = await SLAService(db).get_at_risk_tickets()
    if current_user.get("role") == UserRole.AGENT:
        allowed = await _agent_ticket_ids(db, current_user)
        alerts = [a for a in alerts if a.get("ticket_id") in allowed]
    return alerts


@router.get("/tickets/{ticket_id}/status", response_model=SLATicketDetailOut)
async def get_ticket_sla_status(
    ticket_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Get SLA detail for a specific ticket."""
    try:
        ticket_oid = MongoModel.to_object_id(ticket_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Ticket not found")
    detail = await SLAService(db).get_ticket_sla_detail(ticket_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Ticket not found")
    ticket = await db.tickets.find_one({"_id": ticket_oid})
    await _require_scope(db, ticket, current_user)
    return detail


@router.post("/scan", response_model=SLAScanResult)
async def trigger_sla_scan(
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR])),
    db=Depends(get_database),
):
    """Manually trigger SLA scan (admin/supervisor)."""
    stats = await SLAService(db).scan_tickets_and_alert()
    return stats


# ──────────────────────────────────────────────
# Surveillance Intelligente des Risques SLA (STEP 4)
# ──────────────────────────────────────────────

@router.get("/risk", response_model=SLARiskOverviewOut)
async def get_sla_risk_overview(
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.AGENT])),
    db=Depends(get_database),
):
    """
    Vue d'ensemble des risques SLA pour superviseurs et managers :
    - KPIs agrégés (SLA On Track, At Risk, Breached, Paused, % conformité, délai moyen)
    - File d'attente prioritaire des tickets à risque et en dépassement
    - Journal des alertes récentes
    """
    service = SLARiskService(db)
    overview = await service.get_risk_overview()
    if current_user.get("role") == UserRole.AGENT:
        allowed = await _agent_ticket_ids(db, current_user)
        scoped = [t for t in await db.tickets.find({}).to_list(10000) if str(t.get("_id")) in allowed]
        active = [t for t in scoped if t.get("status") in ("OPEN", "IN_PROGRESS", "PENDING")]
        breached = [t for t in active if t.get("sla_status") == "BREACHED"]
        at_risk = [t for t in active if t.get("sla_status") == "AT_RISK"]
        paused = [t for t in active if t.get("sla_status") == "PAUSED"]
        overview["kpis"].update({
            "total_active_slas": len(active), "breached_count": len(breached),
            "at_risk_count": len(at_risk), "paused_count": len(paused),
            "on_track_count": max(0, len(active) - len(breached) - len(at_risk) - len(paused)),
            "compliance_pct": round((len(active) - len(breached)) * 100 / len(active), 1) if active else 0.0
        })
        overview["at_risk_tickets"] = [t for t in overview["at_risk_tickets"] if t.get("ticket_id") in allowed]
        remaining = [t.get("time_remaining_minutes") for t in overview["at_risk_tickets"] if t.get("time_remaining_minutes") is not None]
        overview["kpis"]["avg_remaining_minutes"] = round(sum(remaining) / len(remaining), 1) if remaining else None
        # Alert rows can contain recipient contact details; those are supervisor-only.
        overview["active_alerts"] = []
    return overview


@router.get("/config", response_model=SLARiskConfigOut)
async def get_sla_risk_config(
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR])),
    db=Depends(get_database),
):
    """Récupère la configuration des seuils d'alerte SLA (pourcentage et temps absolu)."""
    service = SLARiskService(db)
    return await service.get_risk_config()


@router.put("/config", response_model=SLARiskConfigOut)
async def update_sla_risk_config(
    body: SLARiskConfigUpdate,
    current_user=Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database),
):
    """Mise à jour des seuils d'alerte et des canaux (Administrateurs uniquement)."""
    service = SLARiskService(db)
    update_data = body.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Aucun champ de configuration fourni")
    return await service.update_risk_config(update_data)


@router.get("/tickets/{ticket_id}/risk", response_model=SLARiskEvaluationResult)
async def evaluate_single_ticket_sla_risk(
    ticket_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Évaluation précise en temps réel de l'état de risque SLA d'un ticket spécifique."""
    try:
        ticket_oid = MongoModel.to_object_id(ticket_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Ticket introuvable")
    ticket = await db.tickets.find_one({"_id": ticket_oid})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket introuvable")
    await _require_scope(db, ticket, current_user)
    service = SLARiskService(db)
    return await service.evaluate_ticket_sla(ticket)


async def _require_scope(db, ticket, user):
    from routes.tickets import _require_ticket_scope
    await _require_ticket_scope(db, ticket, user)


async def _agent_ticket_ids(db, user):
    from routes.tickets import _agent_scope
    agent, team_ids = await _agent_scope(db, user)
    if not agent:
        return set()
    cursor = db.tickets.find({})
    tickets = await cursor.to_list(10000)
    return {str(t.get("_id")) for t in tickets if str(t.get("assigned_agent_id")) == str(agent.get("_id")) or str(t.get("assigned_team_id")) in team_ids}

