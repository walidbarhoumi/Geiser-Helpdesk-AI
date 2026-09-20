from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional
from database.mongodb import get_database
from core.deps import get_current_user, RoleChecker
from schemas.schemas import UserRole, AnalyticsDashboardOut, AIPredictiveInsights
from services.analytics_service import AnalyticsService
from services.report_export_service import ReportExportService
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime

router = APIRouter()


@router.get("/dashboard", response_model=AnalyticsDashboardOut)
async def get_analytics_dashboard(
    period_days: int = Query(30, ge=7, le=90),
    priority: Optional[str] = Query(None, description="Filtrer par priorité (URGENT, HIGH, MEDIUM, LOW)"),
    team_id: Optional[str] = Query(None, description="Filtrer par ID d'équipe"),
    start_date: Optional[str] = Query(None, description="Date de début ISO (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Date de fin ISO (YYYY-MM-DD)"),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(get_current_user)
):
    """
    Returns full predictive analytics and dashboard data for managers and agents:
    KPIs, volume trends, agent performances, MTTR matrix, and AI predictive insights,
    with flexible manager filters (period, priority, team, custom date range).
    """
    service = AnalyticsService(db)
    return await service.get_dashboard_analytics(
        period_days=period_days,
        priority=priority,
        team_id=team_id,
        start_date=start_date,
        end_date=end_date
    )


@router.get("/predictive-insights", response_model=AIPredictiveInsights)
async def get_predictive_insights(
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.AGENT]))
):
    """
    Returns strategic predictive insights, volume forecasts and root-cause issues.
    """
    service = AnalyticsService(db)
    dash = await service.get_dashboard_analytics(period_days=30)
    return dash.predictive_insights


@router.get("/export/excel")
async def export_excel_report(
    period_days: int = Query(30, ge=7, le=90),
    priority: Optional[str] = Query(None),
    team_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR]))
):
    """
    Generates and downloads a custom Excel (.xlsx) report covering:
    - Tickets par agent
    - SLA respectés / non respectés
    - Satisfaction client (CSAT)
    - Temps de réponse moyen et MTTR
    """
    service = AnalyticsService(db)
    dashboard_data = await service.get_dashboard_analytics(
        period_days=period_days,
        priority=priority,
        team_id=team_id,
        start_date=start_date,
        end_date=end_date
    )

    # Fetch tickets matching filters for detailed sheet
    raw_tickets = await db.tickets.find().to_list(1000)
    
    # Enrich team label if provided
    team_name = "Toutes"
    if team_id:
        try:
            from models.base import MongoModel
            t_doc = await db.teams.find_one({"_id": MongoModel.to_object_id(team_id)})
            if t_doc:
                team_name = t_doc.get("name", team_id)
        except Exception:
            pass

    filter_meta = {
        "period": f"{period_days} jours",
        "priority": priority or "Toutes",
        "team": team_name
    }

    report_payload = dashboard_data.dict()
    report_payload["tickets"] = raw_tickets

    # ISO 27001 Security Audit Log
    try:
        from services.audit_service import AuditService
        from schemas.schemas import AuditEventCategory, AuditSeverity
        import asyncio
        asyncio.create_task(
            AuditService(db).log_event(
                event_category=AuditEventCategory.DATA_EXPORT,
                event_type="REPORT_EXPORT_EXCEL",
                severity=AuditSeverity.INFO,
                target_resource_type="report_excel",
                target_resource_id=None,
                actor_id=str(current_user.get("id")),
                actor_email=current_user.get("email"),
                actor_role=current_user.get("role", "SUPERVISOR"),
                status="SUCCESS",
                details=filter_meta
            )
        )
    except Exception:
        pass

    excel_stream = ReportExportService.generate_excel_report(report_payload, filter_meta=filter_meta)
    filename = f"Rapport_GEISER_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"

    return StreamingResponse(
        excel_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/export/pdf")
async def export_pdf_report(
    period_days: int = Query(30, ge=7, le=90),
    priority: Optional[str] = Query(None),
    team_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR]))
):
    """
    Generates and downloads an executive PDF report covering:
    - Tickets par agent
    - SLA respectés / non respectés
    - Satisfaction client (CSAT)
    - Temps de réponse moyen et MTTR
    """
    service = AnalyticsService(db)
    dashboard_data = await service.get_dashboard_analytics(
        period_days=period_days,
        priority=priority,
        team_id=team_id,
        start_date=start_date,
        end_date=end_date
    )

    raw_tickets = await db.tickets.find().to_list(1000)

    team_name = "Toutes"
    if team_id:
        try:
            from models.base import MongoModel
            t_doc = await db.teams.find_one({"_id": MongoModel.to_object_id(team_id)})
            if t_doc:
                team_name = t_doc.get("name", team_id)
        except Exception:
            pass

    filter_meta = {
        "period": f"{period_days} jours",
        "priority": priority or "Toutes",
        "team": team_name
    }

    report_payload = dashboard_data.dict()
    report_payload["tickets"] = raw_tickets

    # ISO 27001 Security Audit Log
    try:
        from services.audit_service import AuditService
        from schemas.schemas import AuditEventCategory, AuditSeverity
        import asyncio
        asyncio.create_task(
            AuditService(db).log_event(
                event_category=AuditEventCategory.DATA_EXPORT,
                event_type="REPORT_EXPORT_PDF",
                severity=AuditSeverity.INFO,
                target_resource_type="report_pdf",
                target_resource_id=None,
                actor_id=str(current_user.get("id")),
                actor_email=current_user.get("email"),
                actor_role=current_user.get("role", "SUPERVISOR"),
                status="SUCCESS",
                details=filter_meta
            )
        )
    except Exception:
        pass

    pdf_stream = ReportExportService.generate_pdf_report(report_payload, filter_meta=filter_meta)
    filename = f"Rapport_GEISER_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"

    return StreamingResponse(
        pdf_stream,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
