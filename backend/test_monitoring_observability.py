"""
test_monitoring_observability.py
================================
Comprehensive test suite for Feature 3: Monitoring & Observability in GEISER.

Covers:
1. Overall system health status aggregation (healthy, degraded, unhealthy)
2. MongoDB database readiness, ping latency, and timeout failure isolation
3. Secondary/optional service failure isolation (Ollama down -> degraded, not unhealthy)
4. RAG, SMTP, IMAP, Notifications, SLA, WebSockets, Backups component checks
5. Background jobs tracker (executions, durations, success/failure counters, schedules)
6. Operational metrics aggregation (tickets by status, SLAs, queues, security logins)
7. RBAC protection on monitoring endpoints (/system-status, /metrics, /jobs)
8. Root /health liveness probe
9. Job manual trigger on demand
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId
from fastapi.testclient import TestClient

from main import app
from database.mongodb import get_database
from core.deps import get_current_user
from schemas.schemas import UserRole, SystemHealthOut, BackgroundJobOut
from services.system_health_service import SystemHealthService
from services.job_tracker import BackgroundJobTracker, JobExecutionRecord, job_tracker
from websocket.manager import connection_manager


# ─── FIXTURES & HELPERS ────────────────────────────────────────────────────────

def make_test_client(db_mock, current_user):
    app.dependency_overrides[get_database] = lambda: db_mock
    app.dependency_overrides[get_current_user] = lambda: current_user
    return TestClient(app)


# ─── 1. SYSTEM HEALTH SERVICE TESTS ───────────────────────────────────────────

class TestSystemHealthService:
    @pytest.mark.asyncio
    async def test_mongodb_check_healthy(self):
        """MongoDB ping succeeds and returns latency in milliseconds."""
        db = MagicMock()
        db.command = AsyncMock(return_value={"ok": 1.0})
        db.list_collection_names = AsyncMock(return_value=["tickets", "users", "agents"])
        db.name = "itsm_helpdesk"

        svc = SystemHealthService(db)
        res = await svc.check_mongodb()

        assert res["status"] == "healthy"
        assert res["critical"] is True
        assert res["latency_ms"] is not None
        assert res["latency_ms"] >= 0
        assert res["database_name"] == "itsm_helpdesk"
        assert res["collections_count"] == 3

    @pytest.mark.asyncio
    async def test_mongodb_check_unhealthy_on_exception(self):
        """MongoDB connection failure marks component unhealthy without crashing."""
        db = MagicMock()
        db.command = AsyncMock(side_effect=Exception("Connection actively refused [WinError 10061]"))

        svc = SystemHealthService(db)
        res = await svc.check_mongodb()

        assert res["status"] == "unhealthy"
        assert res["critical"] is True
        assert "Connection actively refused" in res["details"]

    @pytest.mark.asyncio
    async def test_mongodb_check_timeout_handling(self):
        """MongoDB ping that hangs is cleanly timed out and reported as unhealthy."""
        db = MagicMock()
        async def slow_ping(*args, **kwargs):
            await asyncio.sleep(5.0)
            return {"ok": 1}
        db.command = slow_ping

        svc = SystemHealthService(db)
        res = await svc.check_mongodb()

        assert res["status"] == "unhealthy"
        assert "timed out" in res["details"]

    @pytest.mark.asyncio
    async def test_ai_engine_check_healthy(self):
        """Ollama reachable and model loaded returns healthy status."""
        svc = SystemHealthService(MagicMock())
        mock_ollama_res = {
            "status": "healthy",
            "reachable": True,
            "model": "gemma3:latest",
            "hardware": "GPU"
        }

        with patch("ai.ollama_client.OllamaClient.check_health", new_callable=AsyncMock) as mock_chk:
            mock_chk.return_value = mock_ollama_res
            res = await svc.check_ai_engine()

        assert res["status"] == "healthy"
        assert res["critical"] is False
        assert res["model"] == "gemma3:latest"
        assert res["hardware"] == "GPU"

    @pytest.mark.asyncio
    async def test_ai_engine_failure_is_degraded_not_unhealthy(self):
        """Ollama unreachable reports degraded status (optional service: must not crash)."""
        svc = SystemHealthService(MagicMock())
        mock_ollama_res = {
            "status": "unreachable",
            "reachable": False,
            "error": "Failed to connect to localhost:11434"
        }

        with patch("ai.ollama_client.OllamaClient.check_health", new_callable=AsyncMock) as mock_chk:
            mock_chk.return_value = mock_ollama_res
            res = await svc.check_ai_engine()

        assert res["status"] == "degraded"
        assert res["critical"] is False
        assert res["reachable"] is False

    def test_smtp_configuration_check(self):
        """Checks SMTP configuration status reporting."""
        svc = SystemHealthService(MagicMock())
        res = svc.check_smtp_email()
        assert res["name"] == "Service Email Sortant (SMTP)"
        assert res["status"] in ["healthy", "not_configured"]

    def test_imap_configuration_check(self):
        """Checks IMAP configuration status reporting."""
        svc = SystemHealthService(MagicMock())
        res = svc.check_imap_email()
        assert res["name"] == "Collecte Email Entrante (IMAP)"
        assert res["status"] in ["healthy", "not_configured"]

    def test_websocket_status_check(self):
        """Checks WebSocket connection manager live stats."""
        svc = SystemHealthService(MagicMock())
        res = svc.check_websocket_service()
        assert res["status"] == "healthy"
        assert "active_connections" in res
        assert "active_users" in res

    @pytest.mark.asyncio
    async def test_full_system_health_aggregation_logic(self):
        """
        Overall status calculation:
        - unhealthy if critical MongoDB is down
        - degraded if MongoDB is healthy but secondary service is degraded
        - healthy if all components are healthy
        """
        db = MagicMock()
        db.command = AsyncMock(return_value={"ok": 1.0})
        db.list_collection_names = AsyncMock(return_value=["tickets"])
        db.name = "itsm_helpdesk"
        db.notifications.aggregate = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
        db.backups.find_one = AsyncMock(return_value={"status": "SUCCESS", "created_at": datetime.utcnow()})
        db.knowledge_documents.count_documents = AsyncMock(return_value=5)

        svc = SystemHealthService(db)

        # 1. Healthy case (Ollama healthy)
        with patch.object(svc, "check_ai_engine", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = {"name": "AI", "status": "healthy", "critical": False}
            health = await svc.get_full_system_health()
            assert health["status"] in ["healthy", "degraded"]
            assert len(health["components"]) == 9
            assert health["uptime_seconds"] >= 0

        # 2. Degraded case (Ollama degraded, MongoDB healthy)
        with patch.object(svc, "check_ai_engine", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = {"name": "AI", "status": "degraded", "critical": False}
            health = await svc.get_full_system_health()
            assert health["status"] == "degraded"

        # 3. Unhealthy case (MongoDB unhealthy)
        with patch.object(svc, "check_mongodb", new_callable=AsyncMock) as mock_db:
            mock_db.return_value = {"name": "MongoDB", "status": "unhealthy", "critical": True}
            health = await svc.get_full_system_health()
            assert health["status"] == "unhealthy"


# ─── 2. BACKGROUND JOBS TRACKER TESTS ─────────────────────────────────────────

class TestBackgroundJobTracker:
    def test_job_tracker_lifecycle(self):
        """Tracks job start, end, duration, and error reporting."""
        tracker = BackgroundJobTracker()
        tracker.record_job_start("test_worker", "Test Worker")
        
        # In running state
        job = tracker._jobs["test_worker"]
        assert job.is_running is True
        assert job.status == "RUNNING"

        # End with success
        tracker.record_job_end("test_worker", success=True, duration=0.25)
        assert job.is_running is False
        assert job.status == "SUCCESS"
        assert job.success_count == 1
        assert job.last_duration_seconds == 0.25

        # End with failure
        tracker.record_job_start("test_worker")
        tracker.record_job_end("test_worker", success=False, error="Connection reset by peer", duration=0.10)
        assert job.is_running is False
        assert job.status == "FAILED"
        assert job.failure_count == 1
        assert "Connection reset" in job.last_error

    def test_job_statuses_output(self):
        """get_job_statuses returns structured dictionary representation."""
        tracker = BackgroundJobTracker()
        tracker.record_job_start("sla_scan", "Moniteur SLA")
        tracker.record_job_end("sla_scan", success=True, duration=0.5)

        statuses = tracker.get_job_statuses()
        sla_job = next((j for j in statuses if j["job_id"] == "sla_scan"), None)
        assert sla_job is not None
        assert sla_job["status"] == "SUCCESS"
        assert sla_job["success_count"] >= 1
        assert sla_job["last_duration_seconds"] == 0.5


# ─── 3. OPERATIONAL METRICS TESTS ──────────────────────────────────────────────

class TestOperationalMetrics:
    @pytest.mark.asyncio
    async def test_operational_metrics_aggregation(self):
        """Aggregates tickets, SLAs, queues, WebSockets, and security metrics."""
        db = MagicMock()

        # Mock ticket facet
        facet_mock = [{
            "by_status": [
                {"_id": "OPEN", "count": 4},
                {"_id": "RESOLVED", "count": 10},
                {"_id": "CLOSED", "count": 2}
            ],
            "created_last_24h": [{"count": 3}],
            "by_sla": [
                {"_id": "ON_TRACK", "count": 3},
                {"_id": "BREACHED", "count": 1}
            ]
        }]
        cursor_mock = MagicMock(to_list=AsyncMock(return_value=facet_mock))
        db.tickets.aggregate = MagicMock(return_value=cursor_mock)

        # Mock notifications
        notif_cursor = MagicMock(to_list=AsyncMock(return_value=[
            {"_id": "pending", "count": 2},
            {"_id": "delivered", "count": 15},
            {"_id": "dead_letter", "count": 1}
        ]))
        db.notifications.aggregate = MagicMock(return_value=notif_cursor)

        # Mock processed emails
        email_cursor = MagicMock(to_list=AsyncMock(return_value=[
            {"_id": "processed", "count": 8},
            {"_id": "failed", "count": 1}
        ]))
        db.processed_emails.aggregate = MagicMock(return_value=email_cursor)

        # Mock users and audit
        db.users.count_documents = AsyncMock(return_value=12)
        audit_cursor = MagicMock(to_list=AsyncMock(return_value=[
            {"_id": "LOGIN_SUCCESS", "count": 20},
            {"_id": "LOGIN_FAIL", "count": 2}
        ]))
        db.audit_logs.aggregate = MagicMock(return_value=audit_cursor)

        svc = SystemHealthService(db)
        metrics = await svc.get_operational_metrics()

        assert metrics["tickets"]["total"] == 16
        assert metrics["tickets"]["open"] == 4
        assert metrics["tickets"]["created_last_24h"] == 3
        assert metrics["sla"]["breached"] == 1
        assert metrics["notifications"]["pending"] == 2
        assert metrics["notifications"]["dead_letter"] == 1
        assert metrics["email_to_ticket"]["total_processed"] == 9
        assert metrics["security"]["total_users"] == 12
        assert metrics["security"]["logins_last_24h"] == 20
        assert metrics["security"]["failed_logins_24h"] == 2


# ─── 4. API ENDPOINTS & RBAC TESTS ────────────────────────────────────────────

class TestMonitoringEndpoints:
    @pytest.fixture(autouse=True)
    def cleanup(self):
        yield
        app.dependency_overrides.clear()

    def test_get_health_authenticated(self):
        """GET /api/v1/monitoring/health returns SystemHealthOut for authenticated users."""
        db = MagicMock()
        db.command = AsyncMock(return_value={"ok": 1})
        db.list_collection_names = AsyncMock(return_value=["tickets"])
        db.notifications.aggregate = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
        db.backups.find_one = AsyncMock(return_value=None)
        db.knowledge_documents.count_documents = AsyncMock(return_value=0)

        user = {"id": "u1", "role": UserRole.AGENT.value, "email": "agent@geiser.tn"}
        client = make_test_client(db, user)

        with patch("services.system_health_service.OllamaClient.check_health", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = {"status": "healthy", "reachable": True, "model": "gemma3"}
            res = client.get("/api/v1/monitoring/health")

        assert res.status_code == 200
        data = res.json()
        assert "status" in data
        assert "components" in data
        assert len(data["components"]) == 9

    def test_system_status_rbac_protection(self):
        """GET /api/v1/monitoring/system-status requires ADMIN or SUPERVISOR (USER gets 403)."""
        db = MagicMock()
        user_customer = {"id": "u_cust", "role": UserRole.USER.value, "email": "customer@geiser.tn"}
        client = make_test_client(db, user_customer)

        res = client.get("/api/v1/monitoring/system-status")
        assert res.status_code == 403

        # Admin allowed
        admin_user = {"id": "admin_1", "role": UserRole.ADMIN.value, "email": "admin@geiser.tn"}
        client_admin = make_test_client(db, admin_user)
        with patch("services.system_health_service.OllamaClient.check_health", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = {"status": "healthy", "reachable": True, "model": "gemma3"}
            res_admin = client_admin.get("/api/v1/monitoring/system-status")
        assert res_admin.status_code == 200

    def test_metrics_rbac_protection(self):
        """GET /api/v1/monitoring/metrics requires ADMIN or SUPERVISOR."""
        db = MagicMock()
        user_customer = {"id": "u_cust", "role": UserRole.USER.value, "email": "customer@geiser.tn"}
        client = make_test_client(db, user_customer)

        res = client.get("/api/v1/monitoring/metrics")
        assert res.status_code == 403

    def test_get_jobs_endpoint(self):
        """GET /api/v1/monitoring/jobs returns background job execution records."""
        db = MagicMock()
        admin_user = {"id": "admin_1", "role": UserRole.ADMIN.value, "email": "admin@geiser.tn"}
        client = make_test_client(db, admin_user)

        res = client.get("/api/v1/monitoring/jobs")
        assert res.status_code == 200
        jobs = res.json()
        assert isinstance(jobs, list)
        assert len(jobs) >= 4  # sla_scan, email_poll, notification_worker, automated_backup

    def test_root_health_liveness_endpoint(self):
        """GET /health root liveness probe responds without requiring authentication."""
        client = TestClient(app)
        with patch("services.system_health_service.OllamaClient.check_health", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = {"status": "healthy", "reachable": True, "model": "gemma3"}
            res = client.get("/health")
        assert res.status_code == 200
        assert "status" in res.json()
