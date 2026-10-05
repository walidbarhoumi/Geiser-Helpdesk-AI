"""
services/system_health_service.py
=================================
Central monitoring and health diagnostics service for GEISER.
Evaluates connectivity, latency, status and operational metrics
across MongoDB, Ollama AI, RAG, SMTP, IMAP, Notifications, SLA, WebSockets, and Backups.
"""

import time
import socket
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

from core.config import settings
from ai.ollama_client import OllamaClient
from services.imap_service import is_imap_configured
from services.job_tracker import job_tracker
from websocket.manager import connection_manager

logger = logging.getLogger(__name__)

# Server boot timestamp for uptime calculation
SERVER_BOOT_TIME = datetime.utcnow()


class SystemHealthService:
    def __init__(self, db: Optional[AsyncIOMotorDatabase] = None):
        self.db = db

    async def check_mongodb(self) -> Dict[str, Any]:
        """
        Pings MongoDB with a short timeout and measures real round-trip latency.
        """
        if self.db is None:
            return {
                "name": "MongoDB Database",
                "status": "unhealthy",
                "critical": True,
                "latency_ms": None,
                "database_name": getattr(settings, "DATABASE_NAME", "unknown"),
                "details": "Database reference is null"
            }

        start = time.time()
        try:
            # 2.0s timeout to never hang the health check
            await asyncio.wait_for(self.db.command("ping"), timeout=2.0)
            latency_ms = round((time.time() - start) * 1000, 2)
            
            # Fetch collection counts safely
            collections = await self.db.list_collection_names()
            return {
                "name": "MongoDB Database",
                "status": "healthy",
                "critical": True,
                "latency_ms": latency_ms,
                "database_name": self.db.name,
                "collections_count": len(collections),
                "details": f"Connected ({latency_ms}ms, {len(collections)} collections)"
            }
        except asyncio.TimeoutError:
            return {
                "name": "MongoDB Database",
                "status": "unhealthy",
                "critical": True,
                "latency_ms": None,
                "database_name": getattr(settings, "DATABASE_NAME", "unknown"),
                "details": "Connection timed out (>2000ms)"
            }
        except Exception as e:
            return {
                "name": "MongoDB Database",
                "status": "unhealthy",
                "critical": True,
                "latency_ms": None,
                "database_name": getattr(settings, "DATABASE_NAME", "unknown"),
                "details": f"Connection error: {str(e)}"
            }

    async def check_ai_engine(self) -> Dict[str, Any]:
        """
        Verifies Ollama connectivity and model availability.
        Optional service: unreachability degrades the system rather than marking it unhealthy.
        """
        client = OllamaClient()
        try:
            # 3.0s timeout
            status_data = await asyncio.wait_for(client.check_health(), timeout=3.0)
            status_str = status_data.get("status")
            if status_str == "healthy":
                component_status = "healthy"
                details = f"Model '{status_data.get('model')}' ready ({status_data.get('hardware', 'CPU')})"
            else:
                component_status = "degraded"
                details = status_data.get("error") or f"Status: {status_str}"

            return {
                "name": "Moteur IA (Ollama)",
                "status": component_status,
                "critical": False,
                "model": status_data.get("model", settings.OLLAMA_MODEL),
                "hardware": status_data.get("hardware", "CPU"),
                "reachable": status_data.get("reachable", False),
                "details": details
            }
        except asyncio.TimeoutError:
            return {
                "name": "Moteur IA (Ollama)",
                "status": "degraded",
                "critical": False,
                "model": settings.OLLAMA_MODEL,
                "hardware": "N/A",
                "reachable": False,
                "details": "Health check timed out (>3000ms)"
            }
        except Exception as e:
            return {
                "name": "Moteur IA (Ollama)",
                "status": "degraded",
                "critical": False,
                "model": settings.OLLAMA_MODEL,
                "hardware": "N/A",
                "reachable": False,
                "details": f"Unreachable: {str(e)}"
            }

    async def check_rag_system(self) -> Dict[str, Any]:
        """
        Verifies RAG vector index presence and document database status.
        """
        try:
            import os
            from rag.config import DEFAULT_INDEX_DIR, DEFAULT_DATABASE_PATH
            index_path = os.path.join(DEFAULT_INDEX_DIR, "faiss_index.bin")
            has_index = os.path.exists(index_path)
            has_db = os.path.exists(DEFAULT_DATABASE_PATH)
            
            # Count knowledge documents in MongoDB if available
            doc_count = 0
            if self.db is not None:
                try:
                    doc_count = await self.db.knowledge_documents.count_documents({})
                except Exception:
                    pass

            if has_index or doc_count > 0:
                return {
                    "name": "Base de Connaissances RAG",
                    "status": "healthy",
                    "critical": False,
                    "index_available": has_index,
                    "dataset_available": has_db,
                    "documents_count": doc_count,
                    "details": f"Index prêt ({doc_count} documents indexés)"
                }
            else:
                return {
                    "name": "Base de Connaissances RAG",
                    "status": "degraded",
                    "critical": False,
                    "index_available": False,
                    "dataset_available": has_db,
                    "documents_count": 0,
                    "details": "Index vectoriel vide ou non initialisé"
                }
        except Exception as e:
            return {
                "name": "Base de Connaissances RAG",
                "status": "degraded",
                "critical": False,
                "details": f"Erreur de vérification: {str(e)}"
            }

    def check_smtp_email(self) -> Dict[str, Any]:
        """
        Verifies outbound SMTP server configuration.
        """
        host = getattr(settings, "SMTP_HOST", "")
        port = getattr(settings, "SMTP_PORT", 587)
        user = getattr(settings, "SMTP_USER", "")
        password = getattr(settings, "SMTP_PASSWORD", "")

        is_configured = bool(host and user and password)
        if not is_configured:
            return {
                "name": "Service Email Sortant (SMTP)",
                "status": "not_configured",
                "critical": False,
                "host": host or None,
                "port": port,
                "configured": False,
                "details": "Identifiants SMTP non configurés"
            }

        return {
            "name": "Service Email Sortant (SMTP)",
            "status": "healthy",
            "critical": False,
            "host": host,
            "port": port,
            "configured": True,
            "details": f"Configuré sur {host}:{port}"
        }

    def check_imap_email(self) -> Dict[str, Any]:
        """
        Verifies inbound Email-to-Ticket (IMAP) configuration.
        """
        configured = is_imap_configured()
        if not configured:
            return {
                "name": "Collecte Email Entrante (IMAP)",
                "status": "not_configured",
                "critical": False,
                "configured": False,
                "details": "IMAP désactivé ou non configuré"
            }

        host = getattr(settings, "EMAIL_IMAP_HOST", None) or getattr(settings, "IMAP_HOST", "")
        port = getattr(settings, "EMAIL_IMAP_PORT", None) or getattr(settings, "IMAP_PORT", 993)
        folder = getattr(settings, "EMAIL_IMAP_FOLDER", None) or getattr(settings, "IMAP_FOLDER", "INBOX")
        interval = getattr(settings, "EMAIL_POLL_INTERVAL_SECONDS", 60)

        return {
            "name": "Collecte Email Entrante (IMAP)",
            "status": "healthy",
            "critical": False,
            "configured": True,
            "host": host,
            "port": port,
            "folder": folder,
            "interval_seconds": interval,
            "details": f"Actif sur {host} ({folder}, poll chaque {interval}s)"
        }

    async def check_notification_worker(self) -> Dict[str, Any]:
        """
        Verifies notification reliability worker and queue stats.
        """
        queue_stats = {"pending": 0, "failed": 0, "dead_letter": 0, "sent": 0}
        if self.db is not None:
            try:
                pipeline = [
                    {"$group": {"_id": "$status", "count": {"$sum": 1}}}
                ]
                counts = await self.db.notifications.aggregate(pipeline).to_list(10)
                for item in counts:
                    st = (item["_id"] or "").lower()
                    if st in queue_stats:
                        queue_stats[st] = item["count"]
            except Exception:
                pass

        dead_letters = queue_stats["dead_letter"]
        status = "degraded" if dead_letters > 20 else "healthy"

        return {
            "name": "Worker de Fiabilité des Notifications",
            "status": status,
            "critical": False,
            "queue_stats": queue_stats,
            "details": f"File d'attente : {queue_stats['pending']} en attente, {dead_letters} rebuts"
        }

    def check_sla_scheduler(self) -> Dict[str, Any]:
        """
        Verifies APScheduler background runner state and jobs.
        """
        from main import scheduler
        is_running = bool(scheduler and scheduler.running)
        jobs = scheduler.get_jobs() if is_running else []

        return {
            "name": "Ordonnanceur & Moniteur SLA",
            "status": "healthy" if is_running else "degraded",
            "critical": False,
            "running": is_running,
            "active_jobs_count": len(jobs),
            "jobs": [j.id for j in jobs],
            "details": f"Ordonnanceur actif avec {len(jobs)} tâche(s) planifiée(s)" if is_running else "Ordonnanceur arrêté ou en attente"
        }

    def check_websocket_service(self) -> Dict[str, Any]:
        """
        Verifies WebSocket connection manager availability and client count.
        """
        stats = connection_manager.get_stats()
        return {
            "name": "Serveur WebSocket Temps Réel",
            "status": "healthy",
            "critical": False,
            "active_connections": stats.get("active_connections", 0),
            "active_users": stats.get("active_users", 0),
            "details": f"{stats.get('active_connections', 0)} connexion(s) active(s) ({stats.get('active_users', 0)} utilisateurs)"
        }

    async def check_backup_system(self) -> Dict[str, Any]:
        """
        Verifies automated backup and disaster recovery readiness.
        """
        enabled = getattr(settings, "BACKUP_ENABLED", True)
        if not enabled:
            return {
                "name": "Sauvegardes Automatiques & PRA",
                "status": "not_configured",
                "critical": False,
                "enabled": False,
                "details": "Sauvegardes automatiques désactivées"
            }

        last_backup = None
        if self.db is not None:
            try:
                last_backup = await self.db.backups.find_one({}, sort=[("created_at", -1)])
            except Exception:
                pass

        cron = getattr(settings, "BACKUP_SCHEDULE_CRON", "0 2 * * *")
        last_status = last_backup.get("status") if last_backup else "NONE"
        component_status = "degraded" if last_status in ["FAILED", "CORRUPTED"] else "healthy"

        return {
            "name": "Sauvegardes Automatiques & PRA",
            "status": component_status,
            "critical": False,
            "enabled": True,
            "cron_schedule": cron,
            "last_backup_status": last_status,
            "last_backup_at": last_backup.get("created_at").isoformat() if last_backup and last_backup.get("created_at") else None,
            "details": f"Planifié à '{cron}', dernier état: {last_status}"
        }

    async def get_full_system_health(self) -> Dict[str, Any]:
        """
        Runs all subsystem health checks in parallel and determines overall system status.
        """
        # Execute asynchronous and synchronous checks
        db_res, ai_res, rag_res, notif_res, backup_res = await asyncio.gather(
            self.check_mongodb(),
            self.check_ai_engine(),
            self.check_rag_system(),
            self.check_notification_worker(),
            self.check_backup_system(),
            return_exceptions=True
        )

        # Handle exceptions gracefully
        if isinstance(db_res, Exception):
            db_res = {"name": "MongoDB Database", "status": "unhealthy", "critical": True, "details": str(db_res)}
        if isinstance(ai_res, Exception):
            ai_res = {"name": "Moteur IA (Ollama)", "status": "degraded", "critical": False, "details": str(ai_res)}
        if isinstance(rag_res, Exception):
            rag_res = {"name": "Base de Connaissances RAG", "status": "degraded", "critical": False, "details": str(rag_res)}
        if isinstance(notif_res, Exception):
            notif_res = {"name": "Worker de Fiabilité des Notifications", "status": "degraded", "critical": False, "details": str(notif_res)}
        if isinstance(backup_res, Exception):
            backup_res = {"name": "Sauvegardes Automatiques & PRA", "status": "degraded", "critical": False, "details": str(backup_res)}

        smtp_res = self.check_smtp_email()
        imap_res = self.check_imap_email()
        sla_res = self.check_sla_scheduler()
        ws_res = self.check_websocket_service()

        components = [
            db_res,
            ai_res,
            rag_res,
            smtp_res,
            imap_res,
            notif_res,
            sla_res,
            ws_res,
            backup_res
        ]

        # Calculate overall status
        # Unhealthy if any CRITICAL component is unhealthy
        has_critical_failure = any(c.get("status") == "unhealthy" and c.get("critical", False) for c in components)
        has_degraded = any(c.get("status") in ["degraded", "unhealthy"] for c in components)

        if has_critical_failure:
            overall_status = "unhealthy"
        elif has_degraded:
            overall_status = "degraded"
        else:
            overall_status = "healthy"

        uptime_seconds = int((datetime.utcnow() - SERVER_BOOT_TIME).total_seconds())

        return {
            "status": overall_status,
            "version": getattr(settings, "VERSION", "1.0.0"),
            "server_time": datetime.utcnow().isoformat(),
            "uptime_seconds": uptime_seconds,
            "components": components,
            "summary": {
                "total_components": len(components),
                "healthy_count": sum(1 for c in components if c.get("status") == "healthy"),
                "degraded_count": sum(1 for c in components if c.get("status") == "degraded"),
                "unhealthy_count": sum(1 for c in components if c.get("status") == "unhealthy"),
                "not_configured_count": sum(1 for c in components if c.get("status") == "not_configured")
            }
        }

    async def get_operational_metrics(self) -> Dict[str, Any]:
        """
        Aggregates real operational metrics across tickets, SLAs, queues, and security.
        """
        metrics = {
            "tickets": {
                "total": 0, "open": 0, "in_progress": 0,
                "resolved": 0, "closed": 0, "created_last_24h": 0
            },
            "sla": {
                "on_track": 0, "at_risk": 0, "breached": 0
            },
            "notifications": {
                "total": 0, "pending": 0, "delivered": 0,
                "failed": 0, "dead_letter": 0
            },
            "email_to_ticket": {
                "total_processed": 0, "success": 0, "failed": 0
            },
            "websockets": connection_manager.get_stats(),
            "security": {
                "total_users": 0, "active_users": 0, "logins_last_24h": 0, "failed_logins_24h": 0
            },
            "system": {
                "version": getattr(settings, "VERSION", "1.0.0"),
                "server_time": datetime.utcnow().isoformat(),
                "uptime_seconds": int((datetime.utcnow() - SERVER_BOOT_TIME).total_seconds())
            }
        }

        if self.db is None:
            return metrics

        now = datetime.utcnow()
        day_ago = now - timedelta(hours=24)

        try:
            # 1. Tickets breakdown
            ticket_pipeline = [
                {"$facet": {
                    "by_status": [
                        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
                    ],
                    "created_last_24h": [
                        {"$match": {"created_at": {"$gte": day_ago}}},
                        {"$count": "count"}
                    ],
                    "by_sla": [
                        {"$group": {"_id": "$sla_status", "count": {"$sum": 1}}}
                    ]
                }}
            ]
            facet_res = await self.db.tickets.aggregate(ticket_pipeline).to_list(1)
            if facet_res:
                f = facet_res[0]
                total_tickets = 0
                for item in f.get("by_status", []):
                    st = str(item.get("_id", "")).upper()
                    c = item.get("count", 0)
                    total_tickets += c
                    if st == "OPEN":
                        metrics["tickets"]["open"] = c
                    elif st == "IN_PROGRESS":
                        metrics["tickets"]["in_progress"] = c
                    elif st == "RESOLVED":
                        metrics["tickets"]["resolved"] = c
                    elif st == "CLOSED":
                        metrics["tickets"]["closed"] = c
                metrics["tickets"]["total"] = total_tickets

                last_24 = f.get("created_last_24h", [])
                metrics["tickets"]["created_last_24h"] = last_24[0]["count"] if last_24 else 0

                for item in f.get("by_sla", []):
                    sla_st = str(item.get("_id", "")).upper()
                    c = item.get("count", 0)
                    if sla_st == "ON_TRACK":
                        metrics["sla"]["on_track"] = c
                    elif sla_st == "AT_RISK":
                        metrics["sla"]["at_risk"] = c
                    elif sla_st == "BREACHED":
                        metrics["sla"]["breached"] = c
        except Exception as e:
            logger.warning(f"[Monitoring] Error aggregating ticket metrics: {e}")

        try:
            # 2. Notifications count
            notif_counts = await self.db.notifications.aggregate([
                {"$group": {"_id": "$status", "count": {"$sum": 1}}}
            ]).to_list(10)
            total_n = 0
            for item in notif_counts:
                st = str(item.get("_id", "")).lower()
                c = item.get("count", 0)
                total_n += c
                if st in metrics["notifications"]:
                    metrics["notifications"][st] = c
            metrics["notifications"]["total"] = total_n
        except Exception as e:
            logger.warning(f"[Monitoring] Error aggregating notification metrics: {e}")

        try:
            # 3. Email-to-ticket processed emails
            email_counts = await self.db.processed_emails.aggregate([
                {"$group": {"_id": "$status", "count": {"$sum": 1}}}
            ]).to_list(10)
            total_e = 0
            for item in email_counts:
                st = str(item.get("_id", "")).lower()
                c = item.get("count", 0)
                total_e += c
                if st == "processed" or st == "success":
                    metrics["email_to_ticket"]["success"] += c
                elif st in ["failed", "rejected", "error"]:
                    metrics["email_to_ticket"]["failed"] += c
            metrics["email_to_ticket"]["total_processed"] = total_e
        except Exception as e:
            logger.warning(f"[Monitoring] Error aggregating email-to-ticket metrics: {e}")

        try:
            # 4. Users & security
            total_users = await self.db.users.count_documents({})
            active_users = await self.db.users.count_documents({"is_active": True})
            metrics["security"]["total_users"] = total_users
            metrics["security"]["active_users"] = active_users

            # Check audit logs for auth events in last 24h
            auth_pipeline = [
                {"$match": {"timestamp": {"$gte": day_ago}}},
                {"$group": {"_id": "$action", "count": {"$sum": 1}}}
            ]
            auth_res = await self.db.audit_logs.aggregate(auth_pipeline).to_list(20)
            logins = 0
            failed_logins = 0
            for a in auth_res:
                act = str(a.get("_id", "")).upper()
                cnt = a.get("count", 0)
                if "LOGIN_SUCCESS" in act or "AUTH_SUCCESS" in act:
                    logins += cnt
                elif "LOGIN_FAIL" in act or "AUTH_FAIL" in act:
                    failed_logins += cnt
            metrics["security"]["logins_last_24h"] = logins
            metrics["security"]["failed_logins_24h"] = failed_logins
        except Exception as e:
            logger.warning(f"[Monitoring] Error aggregating security metrics: {e}")

        return metrics
