from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime
from bson import ObjectId
import logging
import re
from ai.ollama_client import OllamaClient
from models.base import MongoModel
from schemas.schemas import TicketStatus, TicketPriority

logger = logging.getLogger(__name__)

class RoutingService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.tickets = db.tickets
        self.agents = db.agents
        self.teams = db.teams
        self.history = db.routing_history
        self.ai_client = OllamaClient()

    async def auto_route_ticket(self, ticket_id: str):
        """
        Main logic for intelligent routing.
        """
        # 1. Fetch ticket
        oid = MongoModel.to_object_id(ticket_id)
        ticket = await self.tickets.find_one({"_id": oid})
        if not ticket:
            raise ValueError("Ticket not found")

        # 2. AI Analysis
        ai_analysis = await self.ai_client.analyze_ticket(ticket)
        keywords = ai_analysis.get("keywords", [])
        
        if not keywords:
            logger.warning(f"AI Analysis returned no keywords for ticket {ticket_id}. Using fallback matching.")
        else:
            logger.info(f"AI Analysis success for ticket {ticket_id}. Keywords: {keywords}")
        
        # Add original category/subcategory to keywords for matching
        keywords.extend([ticket.get("category", ""), ticket.get("subcategory", "")])
        keywords = [k.lower() for k in keywords if k]
        keywords = list(set(keywords)) # deduplicate

        # 3. Find Best Team
        all_teams = await self.teams.find().to_list(length=100)
        best_team = None
        best_team_score = -1

        for team in all_teams:
            score = self._calculate_matching_score(keywords, team.get("competencies", []))
            if score > best_team_score:
                best_team_score = score
                best_team = team

        if not best_team:
            # Fallback to first team if no match
            best_team = all_teams[0] if all_teams else None
            best_team_score = 0.1

        # 4. Find Best Agent within Team
        best_agent = None
        best_agent_score = -1
        
        if best_team:
            agent_ids = [MongoModel.to_object_id(aid) for aid in best_team.get("agent_ids", [])]
            team_agents = await self.agents.find({"_id": {"$in": agent_ids}, "is_available": True}).to_list(length=100)
            
            for agent in team_agents:
                # Skill score
                skill_score = self._calculate_matching_score(keywords, agent.get("skills", []))
                
                # Workload score (lower is better, inversely proportional)
                # Assuming max workload of 10 for normalization
                workload = agent.get("workload", 0)
                workload_score = max(0, (10 - workload) / 10)
                
                # Priority boost
                priority_boost = 0
                if ticket.get("priority") == TicketPriority.URGENT.value:
                    priority_boost = 0.5
                elif ticket.get("priority") == TicketPriority.HIGH.value:
                    priority_boost = 0.2

                total_agent_score = (skill_score * 0.6) + (workload_score * 0.4) + priority_boost
                
                if total_agent_score > best_agent_score:
                    best_agent_score = total_agent_score
                    best_agent = agent

        # 5. Final Selection & Updates
        confidence_score = round(min(best_agent_score, 1.0) * 100, 2) if best_agent else 0
        match_quality = self._get_match_quality(confidence_score)
        
        reason = f"Matched based on keywords: {', '.join(keywords[:5])}. "
        if best_agent:
            reason += f"Agent {best_agent.get('user_id')} has matching skills and low workload."
        else:
            reason += "No suitable agent found in the best matching team."

        result = {
            "ticket_id": ticket_id,
            "selected_team": str(best_team["_id"]) if best_team else None,
            "selected_agent": str(best_agent["_id"]) if best_agent else None,
            "team_name": best_team.get("name") if best_team else "Unknown",
            "agent_name": best_agent.get("user_id") if best_agent else "Unassigned",
            "confidence_score": confidence_score,
            "match_quality": match_quality,
            "routing_reason": reason,
            "created_at": datetime.utcnow()
        }

        # Update Ticket & Workload
        if best_agent:
            # Handle previous assignment if exists
            old_agent_id = ticket.get("assigned_agent_id")
            if old_agent_id and old_agent_id != str(best_agent["_id"]):
                old_oid = MongoModel.to_object_id(old_agent_id)
                if old_oid:
                    await self.agents.update_one({"_id": old_oid}, {"$inc": {"workload": -1}})

            update_data = {
                "assigned_agent_id": str(best_agent["_id"]),
                "status": TicketStatus.IN_PROGRESS.value,
                "routing_reason": reason,
                "updated_at": datetime.utcnow()
            }
            await self.tickets.update_one({"_id": oid}, {"$set": update_data})
            
            # Increment New Agent Workload
            if old_agent_id != str(best_agent["_id"]):
                await self.agents.update_one({"_id": best_agent["_id"]}, {"$inc": {"workload": 1}})

        # Save to History
        await self.history.insert_one(result)

        return MongoModel.format_id(result)

    def _calculate_matching_score(self, keywords, competencies):
        if not competencies or not keywords:
            return 0
        
        matches = 0
        comp_lower = [c.lower() for c in competencies]
        
        for kw in keywords:
            for comp in comp_lower:
                if kw in comp or comp in kw:
                    matches += 1
                    break
        
        return matches / max(len(keywords), 1)

    def _get_match_quality(self, score):
        if score >= 80:
            return "Excellent Match"
        elif score >= 50:
            return "Good Match"
        else:
            return "Weak Match"
