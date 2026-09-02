import asyncio
import logging
from database.mongodb import db as mongo_db
from services.email_ticket_service import EmailTicketService

logger = logging.getLogger(__name__)


async def run_email_poll():
    """Background job: poll IMAP inbox and create tickets from support emails."""
    try:
        database = mongo_db.db
        if database is None:
            logger.warning("Email monitor: database not connected, skipping poll")
            return
        stats = await EmailTicketService(database).poll_and_process()
        if stats.get("fetched", 0) > 0:
            logger.info(f"Email monitor poll: {stats}")
    except Exception as e:
        logger.error(f"Email monitor poll failed: {e}")
