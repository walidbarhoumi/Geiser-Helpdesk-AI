from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional
from database.mongodb import get_database
from core.deps import get_current_user, RoleChecker
from schemas.schemas import (
    UserRole, AnalyticsDashboardOut, AIPredictiveInsights,
    VolumeForecastOut, ResolutionTimePredictionIn, ResolutionTimePredictionOut,
    SLABreachRisksOut, RecurringIssuesResponse, RecurringClusterOut,
    CSATAnalyticsOut
)
from services.analytics_service import AnalyticsService
from services.predictive_analytics_service import PredictiveAnalyticsService
from services.report_export_service import ReportExportService
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime

router = APIRouter()


def _role_value(user):
    value = user.get("role") if isinstance(user, dict) else getattr(user, "role", None)
    return value.value if hasattr(value, "value") else str(value)


@router.get("/dashboard", response_model=AnalyticsDashboardOut)
async def get_analytics_dashboard(
    period_days: int = Query(30, ge=7, le=90),
    priority: Optional[str] = Query(None, description="Filtrer par priorité (URGENT, HIGH, MEDIUM, LOW)"),
    team_id: Optional[str] = Query(None, description="Filtrer par ID d'équipe"),
    start_date: Optional[str] = Query(None, description="Date de début ISO (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Date de fin ISO (YYYY-MM-DD)"),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.AGENT]))
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
        end_date=end_date,
        current_user=current_user
    )


@router.get("/csat", response_model=CSATAnalyticsOut)
async def get_csat_analytics(
    period_days: int = Query(30, ge=1, le=365, description="Nombre de jours d'analyse"),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.AGENT]))
):
    """
    Returns detailed Customer Satisfaction (CSAT) analytics:
    - Total evaluations
    - Average score (1-5)
    - Positive satisfaction rate (% >= 4 stars)
    - 1-5 star distribution
    - Temporal evolution trend
    - Performance breakdown by agent and category
    - Recent customer feedback comments
    """
    service = AnalyticsService(db)
    return await service.get_csat_analytics(period_days=period_days, current_user=current_user)


@router.get("/predictive-insights", response_model=AIPredictiveInsights)
async def get_predictive_insights(
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.AGENT]))
):
    """
    Returns strategic predictive insights, volume forecasts, SLA breach risks, and root-cause issues.
    """
    service = AnalyticsService(db)
    dash = await service.get_dashboard_analytics(period_days=30, current_user=current_user)
    return dash.predictive_insights


@router.get("/predictive/volume-forecast", response_model=VolumeForecastOut)
async def get_volume_forecast(
    forecast_days: int = Query(7, ge=1, le=30, description="Nombre de jours de projection future"),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.AGENT]))
):
    """
    Forecast ticket volume for the next N days with trend analysis and spike risk indicators.
    """
    pred_svc = PredictiveAnalyticsService(db)
    scoped = await AnalyticsService(db).get_scoped_tickets(current_user)
    return await pred_svc.generate_volume_forecast(tickets=scoped, forecast_days=forecast_days)


@router.post("/predictive/resolution-time", response_model=ResolutionTimePredictionOut)
async def predict_resolution_time_post(
    payload: ResolutionTimePredictionIn,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.AGENT]))
):
    """
    Predict resolution time for specific ticket parameters (category, priority, urgency, impact, team).
    """
    pred_svc = PredictiveAnalyticsService(db)
    scoped = await AnalyticsService(db).get_scoped_tickets(current_user)
    if payload.ticket_id and not any(str(t.get("_id") or t.get("id")) == payload.ticket_id for t in scoped):
        raise HTTPException(status_code=404, detail="Ticket not found")
    if payload.assigned_agent_id and _role_value(current_user) == UserRole.AGENT.value:
        visible = await AnalyticsService(db).get_visible_agent_ids(current_user)
        if payload.assigned_agent_id not in visible:
            raise HTTPException(status_code=404, detail="Agent not found")
    if payload.assigned_team_id and _role_value(current_user) == UserRole.AGENT.value:
        await AnalyticsService(db).validate_team_scope(current_user, payload.assigned_team_id)
    return await pred_svc.predict_resolution_time(
        category=payload.category,
        subcategory=payload.subcategory,
        priority=payload.priority,
        impact=payload.impact,
        urgency=payload.urgency,
        team_id=payload.assigned_team_id,
        agent_id=payload.assigned_agent_id,
        ticket_id=payload.ticket_id,
        tickets=scoped
    )


@router.get("/predictive/resolution-time", response_model=ResolutionTimePredictionOut)
async def predict_resolution_time_get(
    category: Optional[str] = Query(None),
    subcategory: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    impact: Optional[str] = Query(None),
    urgency: Optional[str] = Query(None),
    ticket_id: Optional[str] = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.AGENT]))
):
    """
    Predict resolution time via GET query parameters for quick client evaluation.
    """
    pred_svc = PredictiveAnalyticsService(db)
    scoped = await AnalyticsService(db).get_scoped_tickets(current_user)
    if ticket_id and not any(str(t.get("_id") or t.get("id")) == ticket_id for t in scoped):
        raise HTTPException(status_code=404, detail="Ticket not found")
    return await pred_svc.predict_resolution_time(
        category=category,
        subcategory=subcategory,
        priority=priority,
        impact=impact,
        urgency=urgency,
        ticket_id=ticket_id,
        tickets=scoped
    )


@router.get("/predictive/sla-breach-risks", response_model=SLABreachRisksOut)
async def get_sla_breach_risks(
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.AGENT]))
):
    """
    Identify active tickets that are at risk of breaching their SLA before resolution.
    """
    pred_svc = PredictiveAnalyticsService(db)
    scoped = await AnalyticsService(db).get_scoped_tickets(current_user)
    return await pred_svc.predict_sla_breach_risks(active_tickets=scoped, all_tickets=scoped)


@router.get("/recurring-tickets", response_model=RecurringIssuesResponse)
async def get_recurring_tickets(
    min_similarity: float = Query(40.0, ge=10.0, le=100.0, description="Seuil minimal de similarité en %"),
    min_cluster_size: int = Query(2, ge=2, le=50, description="Taille minimale d'un groupe récurrent"),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.AGENT]))
):
    """
    Detect and group recurring tickets by category, keywords and semantic text similarity.
    """
    pred_svc = PredictiveAnalyticsService(db)
    scoped = await AnalyticsService(db).get_scoped_tickets(current_user)
    return await pred_svc.detect_recurring_tickets(tickets=scoped, min_similarity=min_similarity, min_cluster_size=min_cluster_size)


@router.get("/recurring-tickets/{cluster_id}", response_model=RecurringClusterOut)
async def get_recurring_cluster_by_id(
    cluster_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.AGENT]))
):
    """
    Get detailed information and sample tickets for a specific recurring ticket cluster.
    """
    pred_svc = PredictiveAnalyticsService(db)
    scoped = await AnalyticsService(db).get_scoped_tickets(current_user)
    recurring_resp = await pred_svc.detect_recurring_tickets(tickets=scoped)
    for cl in recurring_resp.clusters:
        if cl.cluster_id == cluster_id:
            return cl
    raise HTTPException(status_code=404, detail="Groupe d'incidents récurrents introuvable.")


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
        end_date=end_date,
        current_user=current_user
    )

    # Fetch tickets matching filters for detailed sheet
    raw_tickets = await service.get_scoped_tickets(current_user, priority=priority, team_id=team_id, start_date=start_date, end_date=end_date, period_days=period_days)
    
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
        end_date=end_date,
        current_user=current_user
    )

    raw_tickets = await service.get_scoped_tickets(current_user, priority=priority, team_id=team_id, start_date=start_date, end_date=end_date, period_days=period_days)

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
