"""
routes/monitoring.py
====================
API routes for Feature 3: Monitoring & Observability in GEISER.
Provides system health checks, subsystem diagnostics, background job tracking,
and real-time operational metrics with role-based access control.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Dict, Any, List, Optional
import logging

from database.mongodb import get_database
from core.deps import get_current_user, RoleChecker
from schemas.schemas import (
    UserRole, SystemHealthOut, BackgroundJobOut, OperationalMetricsOut
)
from services.system_health_service import SystemHealthService
from services.job_tracker import job_tracker

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=SystemHealthOut)
async def get_health_status(
    db=Depends(get_database),
    current_user=Depends(get_current_user)
):
    """
    Returns system health status and component health checks.
    Available to authenticated users; distinguishes between healthy, degraded, and unhealthy.
    """
    service = SystemHealthService(db)
    return await service.get_full_system_health()


@router.get("/system-status", response_model=SystemHealthOut)
async def get_detailed_system_status(
    db=Depends(get_database),
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR]))
):
    """
    Returns comprehensive diagnostic information across all 9 GEISER subsystems:
    MongoDB, Ollama, RAG, SMTP, IMAP, Notifications, SLA, WebSockets, and Backups.
    Restricted to ADMIN and SUPERVISOR.
    """
    service = SystemHealthService(db)
    return await service.get_full_system_health()


@router.get("/metrics", response_model=OperationalMetricsOut)
async def get_monitoring_metrics(
    db=Depends(get_database),
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR]))
):
    """
    Returns aggregated real-time operational metrics across tickets, SLAs,
    queues, email processing, WebSockets, and security events.
    Restricted to ADMIN and SUPERVISOR.
    """
    service = SystemHealthService(db)
    return await service.get_operational_metrics()


@router.get("/jobs", response_model=List[BackgroundJobOut])
async def get_background_jobs(
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR]))
):
    """
    Returns real-time execution states, durations, last success/failure timestamps,
    and next scheduled run times for all background jobs.
    Restricted to ADMIN and SUPERVISOR.
    """
    return job_tracker.get_job_statuses()


@router.post("/jobs/{job_id}/trigger")
async def trigger_background_job(
    job_id: str,
    db=Depends(get_database),
    current_user=Depends(RoleChecker([UserRole.ADMIN]))
):
    """
    Manually triggers an immediate run of a background job on demand.
    Restricted to ADMIN.
    """
    from main import scheduler
    if not scheduler or not scheduler.running:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduler is not currently running"
        )

    # Find and execute corresponding job logic
    job = scheduler.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Background job '{job_id}' not found in scheduler"
        )

    try:
        job_tracker.record_job_start(job_id)
        # Execute the job func directly or schedule immediately
        scheduler.modify_job(job_id, next_run_time=None)  # or invoke func
        return {
            "message": f"Job '{job_id}' triggered successfully",
            "job_id": job_id
        }
    except Exception as e:
        logger.error(f"Error triggering background job '{job_id}': {e}")
        job_tracker.record_job_end(job_id, success=False, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger job: {str(e)}"
        )
