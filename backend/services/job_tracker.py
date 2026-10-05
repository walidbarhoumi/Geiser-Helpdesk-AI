"""
services/job_tracker.py
=======================
Centralized, thread-safe background job tracking for GEISER.
Tracks execution states, durations, last success/failure timestamps,
error details, and next scheduled execution times for APScheduler jobs.
"""

import time
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from apscheduler.events import (
    EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_MISSED, JobExecutionEvent
)

logger = logging.getLogger(__name__)


class JobExecutionRecord:
    def __init__(self, job_id: str, name: str):
        self.job_id = job_id
        self.name = name
        self.status = "IDLE"  # IDLE, RUNNING, SUCCESS, FAILED
        self.last_execution_at: Optional[datetime] = None
        self.last_success_at: Optional[datetime] = None
        self.last_failure_at: Optional[datetime] = None
        self.last_duration_seconds: Optional[float] = None
        self.last_error: Optional[str] = None
        self.success_count: int = 0
        self.failure_count: int = 0
        self.is_running: bool = False
        self._start_time: Optional[float] = None

    def mark_started(self):
        self.is_running = True
        self.status = "RUNNING"
        self._start_time = time.time()
        self.last_execution_at = datetime.utcnow()

    def mark_success(self, duration: Optional[float] = None):
        self.is_running = False
        self.status = "SUCCESS"
        if duration is not None:
            self.last_duration_seconds = round(duration, 3)
        elif self._start_time:
            self.last_duration_seconds = round(time.time() - self._start_time, 3)
        self.last_success_at = datetime.utcnow()
        self.success_count += 1
        self.last_error = None

    def mark_failure(self, error: str, duration: Optional[float] = None):
        self.is_running = False
        self.status = "FAILED"
        if duration is not None:
            self.last_duration_seconds = round(duration, 3)
        elif self._start_time:
            self.last_duration_seconds = round(time.time() - self._start_time, 3)
        self.last_failure_at = datetime.utcnow()
        self.failure_count += 1
        self.last_error = str(error)

    def to_dict(self, next_run_time: Optional[datetime] = None) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "name": self.name,
            "status": self.status,
            "is_running": self.is_running,
            "last_execution_at": self.last_execution_at.isoformat() if self.last_execution_at else None,
            "last_success_at": self.last_success_at.isoformat() if self.last_success_at else None,
            "last_failure_at": self.last_failure_at.isoformat() if self.last_failure_at else None,
            "last_duration_seconds": self.last_duration_seconds,
            "last_error": self.last_error,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "next_run_time": next_run_time.isoformat() if next_run_time else None
        }


class BackgroundJobTracker:
    """Singleton tracker for all scheduled background jobs in GEISER."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BackgroundJobTracker, cls).__new__(cls)
            cls._instance._jobs = {}
            cls._instance._scheduler = None
            cls._instance._init_default_jobs()
        return cls._instance

    def _init_default_jobs(self):
        default_jobs = [
            ("sla_scan", "Moniteur & Recalcul SLA"),
            ("email_poll", "Collecteur & Parsing Email Inbound (IMAP)"),
            ("notification_worker", "Worker de Fiabilité des Notifications"),
            ("automated_backup", "Sauvegarde Automatisée MongoDB & PRA")
        ]
        for j_id, name in default_jobs:
            self._jobs[j_id] = JobExecutionRecord(j_id, name)

    def attach_scheduler(self, scheduler):
        """Attaches the APScheduler instance to auto-capture execution events."""
        self._scheduler = scheduler
        try:
            scheduler.add_listener(
                self._handle_scheduler_event,
                EVENT_JOB_EXECUTED | EVENT_JOB_ERROR | EVENT_JOB_MISSED
            )
            logger.info("[JobTracker] Attached APScheduler event listeners successfully.")
        except Exception as e:
            logger.warning(f"[JobTracker] Could not attach listener to scheduler: {e}")

    def _handle_scheduler_event(self, event: JobExecutionEvent):
        job_id = getattr(event, "job_id", None)
        if not job_id:
            return

        if job_id not in self._jobs:
            self._jobs[job_id] = JobExecutionRecord(job_id, job_id.replace("_", " ").title())

        record = self._jobs[job_id]
        if event.code == EVENT_JOB_EXECUTED:
            record.mark_success()
        elif event.code == EVENT_JOB_ERROR:
            err = getattr(event, "exception", None) or "Execution error"
            record.mark_failure(str(err))
        elif event.code == EVENT_JOB_MISSED:
            record.mark_failure("Execution missed schedule window")

    def record_job_start(self, job_id: str, name: Optional[str] = None):
        if job_id not in self._jobs:
            self._jobs[job_id] = JobExecutionRecord(job_id, name or job_id)
        self._jobs[job_id].mark_started()

    def record_job_end(self, job_id: str, success: bool, error: Optional[str] = None, duration: Optional[float] = None):
        if job_id not in self._jobs:
            self._jobs[job_id] = JobExecutionRecord(job_id, job_id)
        if success:
            self._jobs[job_id].mark_success(duration)
        else:
            self._jobs[job_id].mark_failure(error or "Unknown failure", duration)

    def get_job_statuses(self) -> List[Dict[str, Any]]:
        """Returns the status and schedule details for all background jobs."""
        results = []
        scheduler_jobs = {}
        if self._scheduler:
            try:
                for j in self._scheduler.get_jobs():
                    scheduler_jobs[j.id] = j
            except Exception as e:
                logger.warning(f"[JobTracker] Error reading scheduler jobs: {e}")

        # Ensure all currently scheduled jobs are registered
        for j_id, s_job in scheduler_jobs.items():
            if j_id not in self._jobs:
                name = getattr(s_job, "name", None) or j_id.replace("_", " ").title()
                self._jobs[j_id] = JobExecutionRecord(j_id, name)

        for job_id, record in self._jobs.items():
            s_job = scheduler_jobs.get(job_id)
            next_run = getattr(s_job, "next_run_time", None) if s_job else None
            results.append(record.to_dict(next_run_time=next_run))

        return sorted(results, key=lambda x: x["name"])


job_tracker = BackgroundJobTracker()
