import csv
import io
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from models.base import MongoModel
from schemas.schemas import AuditEventCategory, AuditSeverity

logger = logging.getLogger(__name__)


class AuditService:
    """
    ISO/IEC 27001:2013 Annex A.12.4 compliant Security Audit Service.
    Maintains an immutable, chronologically ordered log of all security-sensitive events,
    access control decisions, authentication attempts, policy modifications, and administrative operations.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.audit_logs

    async def log_event(
        self,
        event_category: AuditEventCategory,
        event_type: str,
        severity: AuditSeverity,
        target_resource_type: str,
        target_resource_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        actor_email: Optional[str] = None,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None,
        client_ip: str = "127.0.0.1",
        user_agent: str = "Unknown",
        status: str = "SUCCESS",
        details: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Appends an immutable security audit record.
        Never raises exceptions to calling services to preserve business flow continuity.
        """
        try:
            category_val = event_category.value if hasattr(event_category, "value") else str(event_category)
            severity_val = severity.value if hasattr(severity, "value") else str(severity)

            record = {
                "timestamp": datetime.utcnow(),
                "actor_id": str(actor_id) if actor_id else None,
                "actor_email": actor_email,
                "actor_name": actor_name,
                "actor_role": actor_role,
                "client_ip": client_ip,
                "user_agent": user_agent,
                "event_category": category_val,
                "event_type": event_type,
                "severity": severity_val,
                "target_resource_type": target_resource_type,
                "target_resource_id": str(target_resource_id) if target_resource_id else None,
                "status": status,
                "details": details or {},
            }

            result = await self.collection.insert_one(record)
            record["_id"] = result.inserted_id
            return MongoModel.format_id(record)
        except Exception as e:
            logger.error(f"[ISO 27001 Audit] Failed to record audit log: {e}", exc_info=True)
            return None

    async def get_audit_logs(
        self,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        actor_id: Optional[str] = None,
        actor_email: Optional[str] = None,
        actor_role: Optional[str] = None,
        target_resource_type: Optional[str] = None,
        target_resource_id: Optional[str] = None,
        status: Optional[str] = None,
        event_type: Optional[str] = None,
        search: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves paginated audit trail records sorted in reverse chronological order with multi-dimensional filters.
        """
        query: Dict[str, Any] = {}

        if category:
            query["event_category"] = category
        if severity:
            query["severity"] = severity
        if actor_id:
            query["actor_id"] = actor_id
        if actor_email:
            query["actor_email"] = {"$regex": actor_email, "$options": "i"}
        if actor_role:
            query["actor_role"] = actor_role
        if target_resource_type:
            query["target_resource_type"] = target_resource_type
        if target_resource_id:
            query["target_resource_id"] = target_resource_id
        if status:
            query["status"] = status
        if event_type:
            query["event_type"] = {"$regex": event_type, "$options": "i"}

        if search:
            query["$or"] = [
                {"event_type": {"$regex": search, "$options": "i"}},
                {"actor_email": {"$regex": search, "$options": "i"}},
                {"actor_name": {"$regex": search, "$options": "i"}},
                {"target_resource_type": {"$regex": search, "$options": "i"}},
                {"target_resource_id": {"$regex": search, "$options": "i"}},
            ]

        if start_date or end_date:
            date_filter: Dict[str, Any] = {}
            if start_date:
                date_filter["$gte"] = start_date
            if end_date:
                date_filter["$lte"] = end_date
            query["timestamp"] = date_filter

        cursor = self.collection.find(query).sort("timestamp", -1).skip(skip).limit(limit)
        records = await cursor.to_list(length=limit)
        return MongoModel.format_id(records)

    async def get_security_stats(self) -> Dict[str, int]:
        """
        Aggregates high-level ISO 27001 security metrics for monitoring and compliance dashboards.
        """
        total_events = await self.collection.count_documents({})
        info_count = await self.collection.count_documents({"severity": "INFO"})
        warning_count = await self.collection.count_documents({"severity": "WARNING"})
        critical_count = await self.collection.count_documents({"severity": "CRITICAL"})

        login_successes = await self.collection.count_documents({"event_type": "AUTH_LOGIN_SUCCESS"})
        login_failures = await self.collection.count_documents({"event_type": "AUTH_LOGIN_FAILURE"})
        access_denied_count = await self.collection.count_documents({"event_type": "ACCESS_DENIED"})
        ticket_events = await self.collection.count_documents({"event_category": "TICKET"})
        user_mgmt_events = await self.collection.count_documents({"event_category": "USER_MGMT"})
        team_mgmt_events = await self.collection.count_documents({"event_category": "TEAM_MGMT"})

        return {
            "total_events": total_events,
            "info_count": info_count,
            "warning_count": warning_count,
            "critical_count": critical_count,
            "login_successes": login_successes,
            "login_failures": login_failures,
            "access_denied_count": access_denied_count,
            "ticket_events": ticket_events,
            "user_mgmt_events": user_mgmt_events,
            "team_mgmt_events": team_mgmt_events,
        }

    async def export_audit_logs_csv(
        self,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        actor_email: Optional[str] = None,
        actor_role: Optional[str] = None,
        target_resource_type: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 2000
    ) -> io.StringIO:
        """
        Generates an ISO 27001 compliant CSV export of filtered audit trail events.
        """
        records = await self.get_audit_logs(
            category=category,
            severity=severity,
            actor_email=actor_email,
            actor_role=actor_role,
            target_resource_type=target_resource_type,
            status=status,
            search=search,
            limit=limit,
            skip=0
        )
        output = io.StringIO()
        writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)

        # Header
        writer.writerow([
            "Timestamp (UTC)",
            "Severity",
            "Category",
            "Event Type",
            "Status",
            "Actor Email",
            "Actor Role",
            "Client IP",
            "Target Resource",
            "Target ID",
            "Details"
        ])

        for r in records:
            ts = r.get("timestamp")
            ts_str = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
            writer.writerow([
                ts_str,
                r.get("severity", ""),
                r.get("event_category", ""),
                r.get("event_type", ""),
                r.get("status", ""),
                r.get("actor_email", "") or "",
                r.get("actor_role", "") or "",
                r.get("client_ip", "") or "",
                r.get("target_resource_type", "") or "",
                r.get("target_resource_id", "") or "",
                str(r.get("details", ""))
            ])

        output.seek(0)
        return output
