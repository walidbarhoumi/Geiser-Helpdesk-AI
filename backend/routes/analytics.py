from fastapi import APIRouter, Depends, Query
from database.mongodb import get_database
from core.deps import get_current_user, RoleChecker
from schemas.schemas import UserRole, AnalyticsDashboardOut, AIPredictiveInsights
from services.analytics_service import AnalyticsService
from motor.motor_asyncio import AsyncIOMotorDatabase

router = APIRouter()


@router.get("/dashboard", response_model=AnalyticsDashboardOut)
async def get_analytics_dashboard(
    period_days: int = Query(30, ge=7, le=90),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(get_current_user)
):
    """
    Returns full predictive analytics and dashboard data:
    KPIs, volume trends, agent performances, MTTR matrix, and AI predictive insights.
    """
    service = AnalyticsService(db)
    return await service.get_dashboard_analytics(period_days=period_days)


@router.get("/predictive-insights", response_model=AIPredictiveInsights)
async def get_predictive_insights(
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.AGENT]))
):
    """
    Returns strategic predictive insights, volume forecasts and root-cause issues.
    """
    service = AnalyticsService(db)
    dash = await service.get_dashboard_analytics(period_days=30)
    return dash.predictive_insights
