from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from database.mongodb import get_database
from core.deps import RoleChecker, get_current_user
from schemas.schemas import (
    UserRole, SecurityAuditLogOut, AuditStatsOut,
    AuditEventCategory, AuditSeverity
)
from services.audit_service import AuditService

router = APIRouter()


@router.get("/logs", response_model=List[SecurityAuditLogOut])
async def list_audit_logs(
    category: Optional[AuditEventCategory] = Query(None, description="Filtrer par catégorie d'audit"),
    severity: Optional[AuditSeverity] = Query(None, description="Filtrer par sévérité (INFO, WARNING, CRITICAL)"),
    actor_id: Optional[str] = Query(None, description="Filtrer par identifiant d'acteur"),
    actor_email: Optional[str] = Query(None, description="Filtrer par email d'acteur"),
    actor_role: Optional[str] = Query(None, description="Filtrer par rôle (ADMIN, SUPERVISOR, AGENT, USER)"),
    target_resource_type: Optional[str] = Query(None, description="Filtrer par ressource cible (ticket, user, agent, team...)"),
    target_resource_id: Optional[str] = Query(None, description="Filtrer par ID de ressource cible"),
    status: Optional[str] = Query(None, description="Filtrer par statut (SUCCESS, FAILURE, DENIED)"),
    event_type: Optional[str] = Query(None, description="Recherche par type d'événement"),
    search: Optional[str] = Query(None, description="Recherche globale (mot-clé, email, détails...)"),
    start_date: Optional[datetime] = Query(None, description="Date de début (ISO)"),
    end_date: Optional[datetime] = Query(None, description="Date de fin (ISO)"),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR])),
    db=Depends(get_database),
):
    """
    ISO/IEC 27001:2013 Annex A.12.4 Audit Logs query endpoint with multi-criteria filtering.
    Accessible strictly to Administrators and Supervisors.
    """
    service = AuditService(db)
    category_val = category.value if category else None
    severity_val = severity.value if severity else None

    return await service.get_audit_logs(
        category=category_val,
        severity=severity_val,
        actor_id=actor_id,
        actor_email=actor_email,
        actor_role=actor_role,
        target_resource_type=target_resource_type,
        target_resource_id=target_resource_id,
        status=status,
        event_type=event_type,
        search=search,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        skip=skip,
    )


@router.get("/stats", response_model=AuditStatsOut)
async def get_audit_statistics(
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR])),
    db=Depends(get_database),
):
    """
    Returns aggregated security metrics for monitoring and compliance dashboards.
    """
    service = AuditService(db)
    return await service.get_security_stats()


@router.get("/export")
async def export_audit_trail_csv(
    category: Optional[AuditEventCategory] = Query(None, description="Filtrer par catégorie"),
    severity: Optional[AuditSeverity] = Query(None, description="Filtrer par sévérité"),
    actor_email: Optional[str] = Query(None, description="Filtrer par email"),
    actor_role: Optional[str] = Query(None, description="Filtrer par rôle"),
    target_resource_type: Optional[str] = Query(None, description="Filtrer par type de ressource"),
    status: Optional[str] = Query(None, description="Filtrer par statut"),
    search: Optional[str] = Query(None, description="Recherche globale"),
    limit: int = Query(2000, ge=10, le=10000),
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR])),
    db=Depends(get_database),
):
    """
    Downloads an ISO 27001 compliant CSV export of the filtered immutable audit trail.
    """
    service = AuditService(db)
    category_val = category.value if category else None
    severity_val = severity.value if severity else None

    csv_stream = await service.export_audit_logs_csv(
        category=category_val,
        severity=severity_val,
        actor_email=actor_email,
        actor_role=actor_role,
        target_resource_type=target_resource_type,
        status=status,
        search=search,
        limit=limit,
    )
    filename = f"GEISER_Audit_ISO27001_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"

    # Also log the export itself as an audit event
    await service.log_event(
        event_category=AuditEventCategory.DATA_EXPORT,
        event_type="AUDIT_TRAIL_EXPORTED",
        severity=AuditSeverity.INFO,
        target_resource_type="audit_logs",
        actor_id=str(current_user.get("id")),
        actor_email=current_user.get("email"),
        actor_role=current_user.get("role"),
        status="SUCCESS",
        details={"record_count_limit": limit, "filter_category": category_val, "filter_severity": severity_val}
    )

    return StreamingResponse(
        csv_stream,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
