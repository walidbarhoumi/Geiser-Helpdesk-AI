import logging
from database.mongodb import db as mongo_db
from services.sla_service import SLAService

logger = logging.getLogger(__name__)


async def run_sla_scan():
    """Background job: scan tickets and fire SLA alerts."""
    try:
        database = mongo_db.db
        if database is None:
            logger.warning("SLA monitor: database not connected, skipping scan")
            return
        stats = await SLAService(database).scan_tickets_and_alert()
        logger.info(f"SLA monitor scan: {stats}")
    except Exception as e:
        logger.error(f"SLA monitor scan failed: {e}")
