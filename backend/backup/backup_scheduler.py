import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from core.config import settings
from database.mongodb import get_database
from backup.backup_models import BackupType

logger = logging.getLogger(__name__)


async def run_scheduled_backup():
    """
    Scheduled task executed periodically by APScheduler.
    Executes automated MongoDB backup, SHA-256 verification, and retention pruning.
    """
    if not getattr(settings, "BACKUP_ENABLED", True):
        logger.info("[BackupScheduler] Automated backups are disabled (BACKUP_ENABLED=false).")
        return

    logger.info("[BackupScheduler] Triggering scheduled backup job...")
    try:
        from backup.backup_service import BackupService
        db = get_database()
        if db is None:
            logger.error("[BackupScheduler] Database not connected; aborting scheduled backup.")
            return

        service = BackupService(db)
        metadata = await service.create_backup(backup_type=BackupType.SCHEDULED)
        logger.info(
            f"[BackupScheduler] Scheduled backup job completed with status '{metadata.status}' "
            f"(ID: {metadata.backup_id})"
        )
    except Exception as e:
        logger.exception(f"[BackupScheduler] Exception during scheduled backup execution: {e}")


def register_backup_schedule(scheduler: AsyncIOScheduler):
    """
    Registers the backup job with the FastAPI application's AsyncIOScheduler.
    """
    if not getattr(settings, "BACKUP_ENABLED", True):
        logger.info("[BackupScheduler] Automated backup schedule not registered (BACKUP_ENABLED=false).")
        return

    cron_expr = getattr(settings, "BACKUP_SCHEDULE_CRON", "0 2 * * *")
    try:
        trigger = CronTrigger.from_crontab(cron_expr)
        scheduler.add_job(
            run_scheduled_backup,
            trigger=trigger,
            id="automated_backup",
            replace_existing=True,
            name="GEISER Daily Automated MongoDB Backup"
        )
        logger.info(f"[BackupScheduler] Registered automated backup job with cron schedule: '{cron_expr}'")
    except Exception as e:
        logger.error(f"[BackupScheduler] Failed to parse BACKUP_SCHEDULE_CRON '{cron_expr}': {e}. Falling back to 24h interval.")
        scheduler.add_job(
            run_scheduled_backup,
            "interval",
            hours=24,
            id="automated_backup",
            replace_existing=True,
            name="GEISER Daily Automated MongoDB Backup (Fallback Interval)"
        )
