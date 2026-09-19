from motor.motor_asyncio import AsyncIOMotorDatabase
from schemas.schemas import TicketCreate, TicketStatus, TicketPriority, SLAStatus
from datetime import datetime
from models.base import MongoModel
from bson import ObjectId
import logging
import re
from services.email_service import EmailService
from services.sla_service import SLAService



class TicketService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.tickets = db.tickets
        self.agents = db.agents
        self.users = db.users

    async def create_ticket(self, ticket_in: TicketCreate, user_id: str):
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

        result = await self.tickets.insert_one(ticket_dict)
        ticket_dict["_id"] = result.inserted_id
        formatted_ticket = MongoModel.format_id(ticket_dict)
        
        # Send Notifications (Email & SMS via NotificationService)
        try:
            from services.notification_service import NotificationService
            await NotificationService(self.db).notify_ticket_created(formatted_ticket)
        except Exception as notify_err:
            logger.error(f"Failed to dispatch ticket creation notification: {notify_err}")

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

    async def update_status(self, ticket_id: str, new_status: TicketStatus):
        oid = MongoModel.to_object_id(ticket_id)
        if not oid:
            return None

        ticket = await self.tickets.find_one({"_id": oid})
        update_fields: dict = {"status": new_status.value, "updated_at": datetime.utcnow()}

        if ticket and new_status not in (TicketStatus.RESOLVED, TicketStatus.CLOSED):
            sla_service = SLAService(self.db)
            new_sla_status = await sla_service.compute_sla_status(ticket)
            update_fields["sla_status"] = new_sla_status.value if hasattr(new_sla_status, "value") else new_sla_status
            if new_sla_status == SLAStatus.BREACHED and ticket.get("sla_status") != SLAStatus.BREACHED.value:
                update_fields["sla_breached_at"] = datetime.utcnow()

        await self.tickets.update_one({"_id": oid}, {"$set": update_fields})
        updated_ticket = await self.get_ticket(ticket_id)
        
        if updated_ticket:
            try:
                from services.notification_service import NotificationService
                old_status = ticket.get("status") if ticket else "OPEN"
                await NotificationService(self.db).notify_status_changed(
                    ticket=updated_ticket,
                    old_status=old_status,
                    new_status=new_status.value
                )
            except Exception as notify_err:
                logger.error(f"Failed to dispatch status change notification: {notify_err}")
                
        return updated_ticket

    async def assign_agent(self, ticket_id: str, agent_id: str):
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

        # Case 2: First-time assignment
        else:
            await self.tickets.update_one(
                {"_id": oid},
                {"$set": update_set}
            )

        # Increment new agent's workload
        await self.agents.update_one(
            {"_id": new_agent_oid},
            {"$inc": {"workload": 1}}
        )

        return await self.get_ticket(ticket_id)


    async def delete_ticket(self, ticket_id: str):
        oid = MongoModel.to_object_id(ticket_id)
        if not oid:
            return False
        result = await self.tickets.delete_one({"_id": oid})
        return result.deleted_count > 0
