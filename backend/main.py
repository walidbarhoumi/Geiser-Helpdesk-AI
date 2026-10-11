import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from database.mongodb import connect_to_mongo, close_mongo_connection
from routes.api import api_router
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os
import logging

# Logging: stdout always; file only when LOG_FILE is set (avoids permission
# issues and log noise in Docker containers that capture stdout).
import os as _os

_log_handlers = [logging.StreamHandler()]
_log_file = _os.getenv("LOG_FILE", "app.log")
if _log_file:
    try:
        _log_handlers.append(logging.FileHandler(_log_file))
    except OSError:
        pass  # Non-fatal: container may not have write access at startup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=_log_handlers,
)
logger = logging.getLogger(__name__)


scheduler = AsyncIOScheduler()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.on_event("startup")
async def startup_db_client():
    # Ensure upload directory exists
    if not os.path.exists(settings.UPLOAD_DIR):
        os.makedirs(settings.UPLOAD_DIR)
    await connect_to_mongo()
    
    # Check AI Engine
    from ai.ollama_client import OllamaClient
    ai_client = OllamaClient()
    ai_status = await ai_client.check_health()
    if ai_status["status"] == "healthy":
        logger.info(f"AI Engine started: Model '{settings.OLLAMA_MODEL}' is ready.")
    else:
        logger.warning(f"AI Engine warning: {ai_status.get('status')} - {ai_status.get('error', 'Model not found')}")

    # SLA monitoring — periodic scan and risk evaluator
    from sla_monitor import run_sla_scan
    scheduler.add_job(
        run_sla_scan,
        "interval",
        minutes=settings.SLA_SCAN_INTERVAL_MINUTES,
        id="sla_scan",
        replace_existing=True
    )

    # Inbound email polling
    from email_monitor import run_email_poll
    from services.imap_service import is_imap_configured
    if is_imap_configured():
        poll_interval = getattr(settings, "EMAIL_POLL_INTERVAL_SECONDS", 60)
        scheduler.add_job(
            run_email_poll, "interval",
            seconds=poll_interval,
            id="email_poll", replace_existing=True,
        )
        logger.info(f"Email monitor scheduled (every {poll_interval} seconds)")
    else:
        logger.info("Email monitor not scheduled — IMAP not configured (set IMAP_ENABLED=true)")

    # Automated Backups & Disaster Recovery (STEP 6)
    from backup.backup_scheduler import register_backup_schedule
    register_backup_schedule(scheduler)

    # Notification reliability worker (STEP 8)
    from services.notification_worker import run_notification_worker
    worker_interval = getattr(settings, "NOTIFICATION_WORKER_INTERVAL_SECONDS", 30)
    scheduler.add_job(
        run_notification_worker,
        "interval",
        seconds=worker_interval,
        id="notification_worker",
        replace_existing=True,
    )
    logger.info(f"Notification reliability worker scheduled (every {worker_interval} seconds)")

    scheduler.start()
    logger.info("SLA monitor scheduled (every 15 minutes)")

    # Monitoring & Observability: Track background jobs
    from services.job_tracker import job_tracker
    job_tracker.attach_scheduler(scheduler)

@app.on_event("shutdown")
async def shutdown_db_client():
    if scheduler.running:
        scheduler.shutdown(wait=False)
    await close_mongo_connection()

@app.get("/")
async def root():
    return {"message": "Welcome to the ITSM Helpdesk API"}

@app.get("/health")
async def health_check():
    from database.mongodb import db
    from services.system_health_service import SystemHealthService
    service = SystemHealthService(db.db)
    return await service.get_full_system_health()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
