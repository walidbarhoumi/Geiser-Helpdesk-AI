import uuid
from typing import Optional, Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorDatabase
from schemas.schemas import TicketCreate, TicketStatus, TicketPriority, SLAStatus, TicketActionType
from datetime import datetime, timedelta
from models.base import MongoModel
from bson import ObjectId
import logging
import re
from services.email_service import EmailService
from services.sla_service import SLAService

logger = logging.getLogger(__name__)


class TicketService:
    ALLOWED_STATUS_TRANSITIONS = {
        TicketStatus.OPEN.value: {
            TicketStatus.IN_PROGRESS.value,
            TicketStatus.PENDING.value,
            TicketStatus.RESOLVED.value,
        },
        TicketStatus.IN_PROGRESS.value: {
            TicketStatus.OPEN.value,
            TicketStatus.PENDING.value,
            TicketStatus.RESOLVED.value,
        },
        TicketStatus.PENDING.value: {
            TicketStatus.OPEN.value,
            TicketStatus.IN_PROGRESS.value,
            TicketStatus.RESOLVED.value,
        },
        TicketStatus.RESOLVED.value: {
            TicketStatus.OPEN.value,
            TicketStatus.IN_PROGRESS.value,
            TicketStatus.CLOSED.value,
        },
        TicketStatus.CLOSED.value: set(),
    }

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.tickets = db.tickets
        self.agents = db.agents
        self.users = db.users
        self.routing_history = db.routing_history

    async def _record_routing_history(
        self,
        ticket: dict,
        agent: Optional[dict],
        routing_method: str,
        prior_record_id: Optional[str] = None
    ) -> None:
        """
        Enregistre une décision de routage dans routing_history.

        Parameters
        ----------
        ticket          : document ticket (déjà inséré en base, avec son _id)
        agent           : document agent sélectionné (ou None)
        routing_method  : "automatic" | "manual" | "reassignment" | "ai" | "fallback"
        prior_record_id : si c'est une réassignation, marque l'ancien enregistrement
        """
        ticket_id = str(ticket.get("id") or ticket.get("_id", ""))

        # Marquer l'ancien enregistrement comme réassigné si applicable
        if prior_record_id:
            try:
                await self.routing_history.update_one(
                    {"ticket_id": ticket_id, "outcome_reassigned": False},
                    {
                        "$set": {"outcome_reassigned": True},
                        "$inc": {"outcome_reassignment_count": 1}
                    },
                    sort=[("created_at", -1)]
                )
            except Exception as e:
                logger.warning(f"Impossible de marquer l'historique de routage précédent comme réassigné : {e}")

        record = {
            "ticket_id": ticket_id,
            "selected_team": ticket.get("assigned_team_id"),
            "assigned_agent_id": str(agent["_id"]) if agent else None,
            "team_name": None,
            "agent_name": agent.get("user_id") if agent else "Non assigné",
            # Routing metadata
            "routing_method": routing_method,
            "confidence_score": None,
            "match_quality": "Manual" if routing_method in ("manual", "reassignment") else "Auto",
            "routing_reason": f"Assignation {routing_method} via TicketService",
            "scoring_details": {},
            # Ticket context snapshot
            "category": ticket.get("category"),
            "subcategory": ticket.get("subcategory"),
            "priority": ticket.get("priority"),
            "impact": ticket.get("impact"),
            "urgency": ticket.get("urgency"),
            "sla_applied_rule": ticket.get("sla_applied_rule"),
            "agent_workload_at_assignment": agent.get("workload", 0) if agent else None,
            "agent_skills_match_score": None,
            # Outcome fields
            "outcome_resolved_at": None,
            "outcome_sla_respected": None,
            "outcome_csat_score": None,
            "outcome_reassigned": False,
            "outcome_reassignment_count": 0,
            "created_at": datetime.utcnow(),
        }

        try:
            await self.routing_history.insert_one(record)
        except Exception as e:
            logger.error(f"Échec de l'enregistrement dans routing_history pour le ticket {ticket_id} : {e}")

    async def record_ticket_action(
        self,
        ticket_id: str,
        action_type: str,
        actor_user: Optional[dict] = None,
        details: Optional[Dict[str, Any]] = None,
        comment: Optional[str] = None,
    ):
        """Records an immutable ISO 27001 audit action in the ticket's action_history."""
        oid = MongoModel.to_object_id(ticket_id)
        if not oid:
            return

        actor_id = str(actor_user.get("id")) if actor_user else "SYSTEM"
        actor_name = (actor_user.get("full_name") or actor_user.get("email")) if actor_user else "Système"
        actor_role = actor_user.get("role") if actor_user else "SYSTEM"
        if hasattr(actor_role, "value"):
            actor_role = actor_role.value

        action_entry = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow(),
            "actor_id": str(actor_id),
            "actor_name": str(actor_name),
            "actor_role": str(actor_role),
            "action_type": action_type,
            "details": details or {},
            "comment": comment,
        }

        await self.tickets.update_one(
            {"_id": oid},
            {"$push": {"action_history": action_entry}}
        )

        # Also mirror the action into the global ISO 27001 audit_logs collection
        try:
            from services.audit_service import AuditService
            from schemas.schemas import AuditEventCategory, AuditSeverity
            audit_svc = AuditService(self.db)
            event_type = f"TICKET_{action_type}" if not str(action_type).startswith("TICKET_") else str(action_type)
            severity = AuditSeverity.INFO
            if action_type in ("PRIORITY_CHANGED", "SLA_OVERRIDE"):
                severity = AuditSeverity.WARNING

            import asyncio
            asyncio.create_task(
                audit_svc.log_event(
                    event_category=AuditEventCategory.TICKET,
                    event_type=event_type,
                    severity=severity,
                    target_resource_type="ticket",
                    target_resource_id=str(ticket_id),
                    actor_id=str(actor_id),
                    actor_email=actor_user.get("email") if actor_user else None,
                    actor_name=str(actor_name),
                    actor_role=str(actor_role),
                    status="SUCCESS",
                    details={**(details or {}), **({"comment": comment} if comment else {})}
                )
            )
        except Exception as audit_err:
            logger.error(f"Failed to push ticket audit log: {audit_err}")

    async def create_ticket(self, ticket_in: TicketCreate, user_id: str, actor_user: Optional[dict] = None):
        ticket_dict = ticket_in.dict()
        ticket_dict["user_id"] = user_id
        ticket_dict["status"] = TicketStatus.OPEN.value
        ticket_dict["created_at"] = datetime.utcnow()
        ticket_dict["updated_at"] = datetime.utcnow()
        ticket_dict["attachments"] = ticket_dict.get("attachments") or []
        ticket_dict["keywords"] = ticket_dict.get("keywords") or []


        # Auto-assignment logic
        assigned_agent = await self._auto_assign_agent(ticket_in.category)
        if assigned_agent:
            ticket_dict["assigned_agent_id"] = str(assigned_agent["_id"])
            ticket_dict["status"] = TicketStatus.IN_PROGRESS.value
            # Increment agent workload
            await self.agents.update_one(
                {"_id": assigned_agent["_id"]},
                {"$inc": {"workload": 1}}
            )
        else:
            ticket_dict["assigned_agent_id"] = None

        # Determine Priority via ITIL Matrix if impact & urgency are provided, else fallback to manual/legacy
        from services.itil_service import calculate_priority_from_impact_urgency
        from schemas.schemas import PrioritySource

        if ticket_in.impact and ticket_in.urgency:
            itil_prio = calculate_priority_from_impact_urgency(ticket_in.impact, ticket_in.urgency)
            ticket_dict["priority"] = itil_prio.value
            ticket_dict["priority_source"] = PrioritySource.ITIL_MATRIX.value
            ticket_dict["impact"] = ticket_in.impact.value if hasattr(ticket_in.impact, "value") else str(ticket_in.impact)
            ticket_dict["urgency"] = ticket_in.urgency.value if hasattr(ticket_in.urgency, "value") else str(ticket_in.urgency)
        else:
            prio_val = ticket_in.priority.value if hasattr(ticket_in.priority, "value") else str(ticket_in.priority)
            ticket_dict["priority"] = prio_val
            ticket_dict["priority_source"] = ticket_dict.get("priority_source") or PrioritySource.MANUAL.value
            ticket_dict["impact"] = ticket_in.impact.value if hasattr(ticket_in.impact, "value") else (str(ticket_in.impact) if ticket_in.impact else None)
            ticket_dict["urgency"] = ticket_in.urgency.value if hasattr(ticket_in.urgency, "value") else (str(ticket_in.urgency) if ticket_in.urgency else None)

        # Compute Granular SLA deadlines from priority, category, subcategory
        sla_service = SLAService(self.db)
        created_at = ticket_dict["created_at"]
        priority = ticket_dict["priority"]
        category = ticket_dict.get("category")
        subcategory = ticket_dict.get("subcategory")
        sla_res = await sla_service.calculate_ticket_sla(
            priority=priority,
            created_at=created_at,
            category=category,
            subcategory=subcategory
        )
        ticket_dict["sla_deadline"] = sla_res["resolution_deadline"]
        ticket_dict["sla_response_deadline"] = sla_res["response_deadline"]
        ticket_dict["sla_applied_rule"] = sla_res["applied_rule"]
        ticket_dict["sla_status"] = SLAStatus.ON_TRACK.value
        ticket_dict["sla_breached_at"] = None

        # ISO 27001 Ticket Action History: Record creation action
        creator_name = "Utilisateur"
        creator_role = "USER"
        if actor_user:
            creator_name = actor_user.get("full_name") or actor_user.get("email") or "Utilisateur"
            creator_role = actor_user.get("role", "USER")
        else:
            creator = await self.users.find_one({"_id": MongoModel.to_object_id(user_id)})
            if creator:
                creator_name = creator.get("full_name") or creator.get("email") or "Utilisateur"
                creator_role = creator.get("role", "USER")
        if hasattr(creator_role, "value"):
            creator_role = creator_role.value

        ticket_dict["action_history"] = [{
            "id": str(uuid.uuid4()),
            "timestamp": ticket_dict["created_at"],
            "actor_id": str(user_id),
            "actor_name": str(creator_name),
            "actor_role": str(creator_role),
            "action_type": TicketActionType.CREATED.value,
            "details": {
                "subject": ticket_dict.get("subject"),
                "category": ticket_dict.get("category"),
                "subcategory": ticket_dict.get("subcategory"),
                "priority": ticket_dict.get("priority"),
                "channel": ticket_dict.get("channel"),
                "assigned_agent_id": ticket_dict.get("assigned_agent_id"),
            },
            "comment": "Création du ticket"
        }]

        result = await self.tickets.insert_one(ticket_dict)
        ticket_dict["_id"] = result.inserted_id
        formatted_ticket = MongoModel.format_id(ticket_dict)
        
        # Global ISO 27001 Audit Log for ticket creation
        try:
            from services.audit_service import AuditService
            from schemas.schemas import AuditEventCategory, AuditSeverity
            audit_svc = AuditService(self.db)
            import asyncio
            asyncio.create_task(
                audit_svc.log_event(
                    event_category=AuditEventCategory.TICKET,
                    event_type="TICKET_CREATED",
                    severity=AuditSeverity.INFO,
                    target_resource_type="ticket",
                    target_resource_id=str(formatted_ticket["id"]),
                    actor_id=str(user_id),
                    actor_email=actor_user.get("email") if actor_user else None,
                    actor_name=str(creator_name),
                    actor_role=str(creator_role),
                    status="SUCCESS",
                    details={
                        "subject": formatted_ticket.get("subject"),
                        "category": formatted_ticket.get("category"),
                        "priority": formatted_ticket.get("priority"),
                        "channel": formatted_ticket.get("channel"),
                    }
                )
            )
        except Exception as audit_err:
            logger.error(f"Failed to log ticket creation audit: {audit_err}")

        # Enregistrement dans routing_history si un agent a été assigné automatiquement
        if assigned_agent:
            await self._record_routing_history(
                ticket=formatted_ticket,
                agent=assigned_agent,
                routing_method="automatic"
            )

        # Send Notifications (Email & SMS via NotificationService)
        try:
            from services.notification_service import NotificationService
            await NotificationService(self.db).notify_ticket_created(formatted_ticket)
        except Exception as notify_err:
            logger.error(f"Failed to dispatch ticket creation notification: {notify_err}")

        # Live WebSocket dispatch (STEP 5)
        try:
            from websocket.dispatcher import event_dispatcher
            await event_dispatcher.publish_ticket_created(formatted_ticket, actor=actor_user)
        except Exception as ws_err:
            logger.debug(f"[WS] Failed to dispatch ticket creation live event: {ws_err}")

        return formatted_ticket


    async def _auto_assign_agent(self, category: str):
        """
        1. Find agents with a skill matching the category (case-insensitive).
        2. Filter only available agents.
        3. Sort by workload ascending to balance load.
        """
        cursor = self.agents.find({
            "skills": {"$elemMatch": {"$regex": f"^{re.escape(category)}$", "$options": "i"}},
            "is_available": True
        }).sort("workload", 1).limit(1)

        agents = await cursor.to_list(length=1)
        return agents[0] if agents else None

    async def get_tickets(self, filters: dict, skip: int = 0, limit: int = 100):
        cursor = self.tickets.find(filters).skip(skip).limit(limit).sort("created_at", -1)
        tickets = await cursor.to_list(length=limit)
        return MongoModel.format_id(tickets)

    async def get_ticket(self, ticket_id: str):
        oid = MongoModel.to_object_id(ticket_id)
        if not oid:
            return None
        ticket = await self.tickets.find_one({"_id": oid})
        return MongoModel.format_id(ticket)

    async def update_status(self, ticket_id: str, new_status: TicketStatus, actor_user: Optional[dict] = None):
        oid = MongoModel.to_object_id(ticket_id)
        if not oid:
            return None

        ticket = await self.tickets.find_one({"_id": oid})
        if not ticket:
            return None

        old_status = ticket.get("status", TicketStatus.OPEN.value)
        if hasattr(old_status, "value"):
            old_status = old_status.value
        new_status_val = new_status.value if hasattr(new_status, "value") else str(new_status)
        if (
            new_status_val != old_status
            and new_status_val not in self.ALLOWED_STATUS_TRANSITIONS.get(old_status, set())
        ):
            raise ValueError(f"Invalid ticket status transition: {old_status} -> {new_status_val}")
        update_fields: dict = {"status": new_status_val, "updated_at": datetime.utcnow()}

        now = datetime.utcnow()

        # ── SLA Lifecycle Transitions ─────────────────────────────────
        sla_service = SLAService(self.db)
        from services.audit_service import AuditService
        from schemas.schemas import AuditEventCategory, AuditSeverity
        audit_svc = AuditService(self.db)

        # 1. Entering PENDING state -> PAUSE SLA
        if new_status_val in (TicketStatus.PENDING.value, "PENDING"):
            update_fields["sla_status"] = SLAStatus.PAUSED.value
            update_fields["sla_paused_at"] = now
            try:
                import asyncio
                asyncio.create_task(audit_svc.log_event(
                    event_category=AuditEventCategory.SLA,
                    event_type="SLA_PAUSED",
                    severity=AuditSeverity.INFO,
                    target_resource_type="ticket",
                    target_resource_id=ticket_id,
                    actor_id=str(actor_user.get("id")) if actor_user else "SYSTEM",
                    actor_email=actor_user.get("email") if actor_user else "system@geiser.internal",
                    actor_role=actor_user.get("role", "SYSTEM") if actor_user else "SYSTEM",
                    status="SUCCESS",
                    details={"ticket_id": ticket_id, "paused_at": now.isoformat()}
                ))
            except Exception:
                pass

        # 2. Leaving PENDING state -> RESUME SLA & Extend Deadlines
        elif old_status in (TicketStatus.PENDING.value, "PENDING"):
            paused_at = ticket.get("sla_paused_at")
            pause_duration = (now - paused_at) if (paused_at and isinstance(paused_at, datetime)) else timedelta(0)
            update_fields["sla_paused_at"] = None
            update_fields["sla_total_paused_seconds"] = (ticket.get("sla_total_paused_seconds") or 0.0) + pause_duration.total_seconds()

            eval_ticket = dict(ticket)
            if ticket.get("sla_deadline"):
                new_deadline = ticket["sla_deadline"] + pause_duration
                update_fields["sla_deadline"] = new_deadline
                eval_ticket["sla_deadline"] = new_deadline

            if ticket.get("sla_response_deadline"):
                update_fields["sla_response_deadline"] = ticket["sla_response_deadline"] + pause_duration

            eval_ticket["status"] = new_status_val
            new_sla_status = await sla_service.compute_sla_status(eval_ticket, now=now)
            update_fields["sla_status"] = new_sla_status.value if hasattr(new_sla_status, "value") else new_sla_status

            try:
                import asyncio
                asyncio.create_task(audit_svc.log_event(
                    event_category=AuditEventCategory.SLA,
                    event_type="SLA_RESUMED",
                    severity=AuditSeverity.INFO,
                    target_resource_type="ticket",
                    target_resource_id=ticket_id,
                    actor_id=str(actor_user.get("id")) if actor_user else "SYSTEM",
                    actor_email=actor_user.get("email") if actor_user else "system@geiser.internal",
                    actor_role=actor_user.get("role", "SYSTEM") if actor_user else "SYSTEM",
                    status="SUCCESS",
                    details={
                        "ticket_id": ticket_id,
                        "pause_seconds": pause_duration.total_seconds(),
                        "new_deadline": update_fields.get("sla_deadline", "").isoformat() if isinstance(update_fields.get("sla_deadline"), datetime) else None
                    }
                ))
            except Exception:
                pass

        # 3. Terminal State: RESOLVED or CLOSED -> COMPLETED or BREACHED
        elif new_status_val in (TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value, "RESOLVED", "CLOSED"):
            if ticket.get("sla_breached_at") or ticket.get("sla_status") == SLAStatus.BREACHED.value:
                update_fields["sla_status"] = SLAStatus.BREACHED.value
            else:
                update_fields["sla_status"] = SLAStatus.COMPLETED.value
                try:
                    import asyncio
                    asyncio.create_task(audit_svc.log_event(
                        event_category=AuditEventCategory.SLA,
                        event_type="SLA_COMPLETED",
                        severity=AuditSeverity.INFO,
                        target_resource_type="ticket",
                        target_resource_id=ticket_id,
                        actor_id=str(actor_user.get("id")) if actor_user else "SYSTEM",
                        actor_email=actor_user.get("email") if actor_user else "system@geiser.internal",
                        actor_role=actor_user.get("role", "SYSTEM") if actor_user else "SYSTEM",
                        status="SUCCESS",
                        details={"ticket_id": ticket_id, "resolved_at": now.isoformat()}
                    ))
                except Exception:
                    pass

        # 4. Active transition (e.g. OPEN -> IN_PROGRESS)
        elif ticket:
            eval_ticket = dict(ticket)
            eval_ticket["status"] = new_status_val
            new_sla_status = await sla_service.compute_sla_status(eval_ticket, now=now)
            update_fields["sla_status"] = new_sla_status.value if hasattr(new_sla_status, "value") else new_sla_status
            if new_sla_status == SLAStatus.BREACHED and ticket.get("sla_status") != SLAStatus.BREACHED.value:
                update_fields["sla_breached_at"] = now

        await self.tickets.update_one({"_id": oid}, {"$set": update_fields})

        # ISO 27001 Action History: Record status transition
        if old_status != new_status_val:
            await self.record_ticket_action(
                ticket_id=ticket_id,
                action_type=TicketActionType.STATUS_CHANGED.value,
                actor_user=actor_user,
                details={"old_status": old_status, "new_status": new_status_val},
                comment=f"Statut modifié de {old_status} à {new_status_val}"
            )

        updated_ticket = await self.get_ticket(ticket_id)
        
        if updated_ticket:
            try:
                from services.notification_service import NotificationService
                await NotificationService(self.db).notify_status_changed(
                    ticket=updated_ticket,
                    old_status=old_status,
                    new_status=new_status_val
                )
            except Exception as notify_err:
                logger.error(f"Failed to dispatch status change notification: {notify_err}")

            # Live WebSocket dispatch (STEP 5)
            try:
                from websocket.dispatcher import event_dispatcher
                await event_dispatcher.publish_ticket_status_changed(
                    ticket=updated_ticket,
                    old_status=old_status,
                    new_status=new_status_val,
                    actor=actor_user
                )
            except Exception as ws_err:
                logger.debug(f"[WS] Failed to dispatch status change live event: {ws_err}")

        # Mise à jour du résultat dans routing_history lors de la résolution ou clôture
        if new_status_val in (TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value):
            try:
                sla_respected = (
                    updated_ticket.get("sla_status") not in ("BREACHED",)
                    if updated_ticket else None
                )
                await self.routing_history.update_one(
                    {"ticket_id": ticket_id, "outcome_resolved_at": None},
                    {"$set": {
                        "outcome_resolved_at": datetime.utcnow(),
                        "outcome_sla_respected": sla_respected
                    }},
                    sort=[("created_at", -1)]
                )
            except Exception as e:
                logger.warning(f"Impossible de mettre à jour routing_history avec le résultat pour le ticket {ticket_id} : {e}")

        return updated_ticket

    async def assign_agent(self, ticket_id: str, agent_id: str, actor_user: Optional[dict] = None):
        oid = MongoModel.to_object_id(ticket_id)
        if not oid:
            return None

        # Check if agent exists
        new_agent_oid = MongoModel.to_object_id(agent_id)
        if not new_agent_oid:
            raise ValueError("Invalid agent ID")
        
        new_agent = await self.agents.find_one({"_id": new_agent_oid})
        if not new_agent:
            raise ValueError("Agent not found")

        ticket = await self.get_ticket(ticket_id)
        if not ticket:
            return None

        old_agent_id = ticket.get("assigned_agent_id")

        # Idempotency guard: If the ticket is already assigned to this exact agent, no-op
        if old_agent_id and str(old_agent_id) == str(agent_id):
            return ticket

        update_set = {
            "assigned_agent_id": agent_id,
            "status": TicketStatus.IN_PROGRESS.value,
            "updated_at": datetime.utcnow()
        }

        # Case 1: True Reassignment from a previous agent to a different agent
        if old_agent_id and str(old_agent_id) != str(agent_id):
            prev_agent_oid = MongoModel.to_object_id(old_agent_id)
            if prev_agent_oid:
                await self.agents.update_one(
                    {"_id": prev_agent_oid},
                    {"$inc": {"workload": -1}}
                )

            reassign_event = {
                "from_agent_id": str(old_agent_id),
                "to_agent_id": str(agent_id),
                "reassigned_at": datetime.utcnow()
            }

            await self.tickets.update_one(
                {"_id": oid},
                {
                    "$set": update_set,
                    "$push": {"reassignment_history": reassign_event},
                    "$addToSet": {"reassigned_from_agent_ids": str(old_agent_id)},
                    "$inc": {"reassignment_count": 1}
                }
            )

            # ISO 27001 Action History: Reassignment
            await self.record_ticket_action(
                ticket_id=ticket_id,
                action_type=TicketActionType.AGENT_REASSIGNED.value,
                actor_user=actor_user,
                details={"from_agent_id": str(old_agent_id), "to_agent_id": str(agent_id)},
                comment=f"Ticket réassigné de l'agent {str(old_agent_id)[:8]} à {str(agent_id)[:8]}"
            )

        # Case 2: First-time assignment
        else:
            await self.tickets.update_one(
                {"_id": oid},
                {"$set": update_set}
            )

            # ISO 27001 Action History: First-time assignment
            await self.record_ticket_action(
                ticket_id=ticket_id,
                action_type=TicketActionType.AGENT_ASSIGNED.value,
                actor_user=actor_user,
                details={"assigned_agent_id": str(agent_id)},
                comment=f"Ticket assigné à l'agent {str(agent_id)[:8]}"
            )

        # Increment new agent's workload
        await self.agents.update_one(
            {"_id": new_agent_oid},
            {"$inc": {"workload": 1}}
        )

        # Enregistrement dans routing_history (après l'incrément de workload)
        final_ticket = await self.get_ticket(ticket_id)
        is_reassignment = bool(old_agent_id and str(old_agent_id) != str(agent_id))
        await self._record_routing_history(
            ticket=final_ticket,
            agent=new_agent,
            routing_method="reassignment" if is_reassignment else "manual",
            prior_record_id=ticket_id if is_reassignment else None
        )

        # Live WebSocket dispatch (STEP 5)
        if final_ticket:
            try:
                from websocket.dispatcher import event_dispatcher
                await event_dispatcher.publish_ticket_assigned(
                    ticket=final_ticket,
                    agent_id=str(agent_id),
                    prior_agent_id=str(old_agent_id) if is_reassignment else None,
                    actor=actor_user
                )
            except Exception as ws_err:
                logger.debug(f"[WS] Failed to dispatch assignment live event: {ws_err}")

        return final_ticket


    async def delete_ticket(self, ticket_id: str, actor_user: Optional[dict] = None):
        oid = MongoModel.to_object_id(ticket_id)
        if not oid:
            return False
        ticket = await self.tickets.find_one({"_id": oid})

        # ── Purge physical attachment files before deleting the ticket ──────
        try:
            from services.attachment_service import AttachmentService
            att_svc = AttachmentService(self.db)
            purged = await att_svc.delete_ticket_attachments(ticket_id)
            if purged:
                logger.info("Purged %d attachment(s) for ticket %s", purged, ticket_id)
        except Exception as exc:
            logger.error("Failed to purge attachments for ticket %s: %s", ticket_id, exc)

        result = await self.tickets.delete_one({"_id": oid})
        if result.deleted_count > 0:
            # ISO 27001 Security Audit Log
            try:
                from services.audit_service import AuditService
                from schemas.schemas import AuditEventCategory, AuditSeverity
                audit_svc = AuditService(self.db)
                actor_id = str(actor_user.get("id")) if actor_user else None
                actor_email = actor_user.get("email") if actor_user else None
                actor_name = (actor_user.get("full_name") or actor_user.get("email")) if actor_user else None
                actor_role = actor_user.get("role") if actor_user else "ADMIN"
                if hasattr(actor_role, "value"):
                    actor_role = actor_role.value

                import asyncio
                asyncio.create_task(
                    audit_svc.log_event(
                        event_category=AuditEventCategory.TICKET,
                        event_type="TICKET_DELETED",
                        severity=AuditSeverity.CRITICAL,
                        target_resource_type="ticket",
                        target_resource_id=ticket_id,
                        actor_id=actor_id,
                        actor_email=actor_email,
                        actor_name=actor_name,
                        actor_role=actor_role,
                        status="SUCCESS",
                        details={
                            "deleted_ticket_subject": ticket.get("subject") if ticket else "",
                            "deleted_ticket_category": ticket.get("category") if ticket else "",
                            "deleted_ticket_priority": ticket.get("priority") if ticket else "",
                        }
                    )
                )
            except Exception as e:
                logger.error(f"Failed to log ticket deletion audit: {e}")

        return result.deleted_count > 0
