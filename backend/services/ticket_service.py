from motor.motor_asyncio import AsyncIOMotorDatabase
from schemas.schemas import TicketCreate, TicketStatus, TicketPriority
from datetime import datetime
from models.base import MongoModel
from bson import ObjectId
import logging
import re
from services.email_service import EmailService


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
        ticket_dict["attachments"] = []

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

        result = await self.tickets.insert_one(ticket_dict)
        ticket_dict["_id"] = result.inserted_id
        formatted_ticket = MongoModel.format_id(ticket_dict)
        
        # Send Email Notification
        user = await self.users.find_one({"_id": MongoModel.to_object_id(user_id)})
        if user and user.get("email"):
            EmailService.send_email(
                user["email"], 
                f"Ticket Created: {ticket_in.subject}", 
                f"<p>Your ticket <b>#{formatted_ticket['id'][-6:].upper()}</b> has been received and is currently in status: <b>{formatted_ticket['status']}</b>.</p>"
            )

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
        await self.tickets.update_one(
            {"_id": oid},
            {"$set": {"status": new_status.value, "updated_at": datetime.utcnow()}}
        )
        updated_ticket = await self.get_ticket(ticket_id)
        
        if updated_ticket:
            user = await self.users.find_one({"_id": MongoModel.to_object_id(updated_ticket["user_id"])})
            if user and user.get("email"):
                EmailService.send_email(
                    user["email"], 
                    f"Ticket Status Updated: {updated_ticket['subject']}", 
                    f"<p>Your ticket <b>#{updated_ticket['id'][-6:].upper()}</b> status is now: <b>{new_status.value}</b>.</p>"
                )
                
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

        # Decrement workload of previously assigned agent
        ticket = await self.get_ticket(ticket_id)
        if ticket and ticket.get("assigned_agent_id"):
            prev_agent_oid = MongoModel.to_object_id(ticket["assigned_agent_id"])
            if prev_agent_oid:
                await self.agents.update_one(
                    {"_id": prev_agent_oid},
                    {"$inc": {"workload": -1}}
                )

        await self.tickets.update_one(
            {"_id": oid},
            {"$set": {
                "assigned_agent_id": agent_id,
                "status": TicketStatus.IN_PROGRESS.value,
                "updated_at": datetime.utcnow()
            }}
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
