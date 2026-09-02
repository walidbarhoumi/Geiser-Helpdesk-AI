import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from database.mongodb import connect_to_mongo, close_mongo_connection
from routes.api import api_router
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os
import logging

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
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

    # SLA monitoring — scan every 15 minutes
    from sla_monitor import run_sla_scan
    scheduler.add_job(run_sla_scan, "interval", minutes=15, id="sla_scan", replace_existing=True)

    # Inbound email polling
    from email_monitor import run_email_poll
    from services.imap_service import is_imap_configured
    if is_imap_configured():
        scheduler.add_job(
            run_email_poll, "interval",
            minutes=settings.EMAIL_POLL_INTERVAL_MINUTES,
            id="email_poll", replace_existing=True,
        )
        logger.info(f"Email monitor scheduled (every {settings.EMAIL_POLL_INTERVAL_MINUTES} minutes)")
    else:
        logger.info("Email monitor not scheduled — IMAP not configured (set IMAP_ENABLED=true)")

    scheduler.start()
    logger.info("SLA monitor scheduled (every 15 minutes)")

@app.on_event("shutdown")
async def shutdown_db_client():
    if scheduler.running:
        scheduler.shutdown(wait=False)
    await close_mongo_connection()

@app.get("/")
async def root():
    return {"message": "Welcome to the ITSM Helpdesk API"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
