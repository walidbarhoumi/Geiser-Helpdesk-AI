from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timedelta
from bson import ObjectId
from typing import Dict, Any, List, Optional
import logging
import re
from ai.ollama_client import OllamaClient
from models.base import MongoModel
from schemas.schemas import TicketStatus, TicketPriority

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Centralized Adaptive Routing Configuration (STEP 2)
# ──────────────────────────────────────────────────────────────
DEFAULT_ROUTING_CONFIG: Dict[str, Any] = {
    # Component weights (Skill, Workload, Historical Success, Category Experience, Reassignment Penalty)
    "weights": {
        "skill": 0.35,
        "workload": 0.20,
        "historical_success": 0.25,
        "category_experience": 0.15,
        "reassignment_penalty": 0.15,
    },
    # Bayesian smoothing parameters:
    # baseline: prior resolution rate (0.80 = 80% baseline expectation)
    # k: weight of prior pseudo-observations to stabilize small sample sizes
    "bayesian_baseline": 0.80,
    "bayesian_k": 5.0,
    # Volume of tickets in category required for full experience score saturation (1.0)
    "experience_saturation_tickets": 10,
    # Minimum subcategory ticket volume required before prioritizing subcategory over category
    "min_subcategory_sample": 3,
    # Time decay windows (age in days -> weight multiplier)
    "time_decay_windows": [
        (30, 1.0),            # 0 to 30 days: recent performance has 100% weight
        (90, 0.7),            # 31 to 90 days: medium recency has 70% weight
        (float("inf"), 0.4),  # > 90 days: older performance retained with 40% weight
    ],
    # Maximum cap on reassignment penalty
    "max_reassignment_penalty": 0.40,
    # Bounded priority adjustment (subtle nudge, does not overpower skills, experience or history)
    "priority_boosts": {
        TicketPriority.URGENT.value: 0.08,
        TicketPriority.HIGH.value: 0.04,
        TicketPriority.MEDIUM.value: 0.0,
        TicketPriority.LOW.value: 0.0,
    }
}


class RoutingService:
    def __init__(self, db: AsyncIOMotorDatabase, config: Optional[Dict[str, Any]] = None):
        self.db = db
        self.tickets = db.tickets
        self.agents = db.agents
        self.teams = db.teams
        self.history = db.routing_history
        self.ai_client = OllamaClient()
        self.config = config or DEFAULT_ROUTING_CONFIG

    async def _compute_agent_historical_stats(
        self,
        agent_id: str,
        category: Optional[str] = None,
        subcategory: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Aggregates historical performance metrics for an agent in a specific category/subcategory.
        Includes Bayesian smoothing, time decay, and reassignment accounting.
        Returns a dictionary with raw metrics, smoothed success score, experience score, and reassignment penalty.
        """
        now = datetime.utcnow()
        cfg = self.config

        default_stats = {
            "assigned_count": 0,
            "resolved_count": 0,
            "reassigned_count": 0,
            "resolution_rate": 0.0,
            "reassignment_rate": 0.0,
            "average_resolution_time": None,
            "sample_size": 0,
            "bayesian_success_score": cfg["bayesian_baseline"],
            "category_experience_score": 0.0,
            "reassignment_penalty": 0.0,
            "is_fallback": False
        }

        try:
            # Query tickets involving this agent (assigned to them OR reassigned away from them)
            query: Dict[str, Any] = {
                "$or": [
                    {"assigned_agent_id": str(agent_id)},
                    {"reassigned_from_agent_ids": str(agent_id)}
                ]
            }
            if category:
                query["category"] = category

            cursor = self.tickets.find(query)
            tickets = await cursor.to_list(length=500)

            if not tickets:
                return default_stats

            # Granularity: check if subcategory has enough tickets (>= min_subcategory_sample)
            subcat_tickets = []
            if subcategory:
                subcat_tickets = [t for t in tickets if t.get("subcategory") == subcategory]

            # Use subcategory tickets if sample size >= 3, otherwise use category tickets
            min_sub = cfg.get("min_subcategory_sample", 3)
            effective_tickets = subcat_tickets if len(subcat_tickets) >= min_sub else tickets

            assigned_count = 0
            resolved_count = 0
            reassigned_count = 0
            resolution_durations = []

            decay_assigned_weight = 0.0
            decay_resolved_weight = 0.0
            decay_reassigned_weight = 0.0

            for t in effective_tickets:
                # Time decay calculation
                t_date = t.get("updated_at") or t.get("created_at") or now
                age_days = (now - t_date).total_seconds() / 86400.0 if isinstance(t_date, datetime) else 0

                weight = 1.0
                for max_days, w in cfg["time_decay_windows"]:
                    if age_days <= max_days:
                        weight = w
                        break

                is_assigned = str(t.get("assigned_agent_id", "")) == str(agent_id)
                was_reassigned_from = str(agent_id) in [str(x) for x in t.get("reassigned_from_agent_ids", [])]

                if is_assigned:
                    assigned_count += 1
                    decay_assigned_weight += weight

                    # Check resolution
                    status = str(t.get("status", "")).upper()
                    if status in [TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value, "RESOLVED", "CLOSED"]:
                        resolved_count += 1
                        decay_resolved_weight += weight

                        c_at = t.get("created_at")
                        u_at = t.get("updated_at")
                        if isinstance(c_at, datetime) and isinstance(u_at, datetime) and u_at > c_at:
                            dur_hours = (u_at - c_at).total_seconds() / 3600.0
                            resolution_durations.append(dur_hours)

                if was_reassigned_from:
                    reassigned_count += 1
                    decay_reassigned_weight += weight

            total_activity = assigned_count + reassigned_count
            res_rate = round(resolved_count / max(assigned_count, 1), 2)
            reassign_rate = round(reassigned_count / max(total_activity, 1), 2)
            avg_dur = round(sum(resolution_durations) / len(resolution_durations), 1) if resolution_durations else None

            # Bayesian Smoothed Success Score
            k = cfg["bayesian_k"]
            baseline = cfg["bayesian_baseline"]
            bayesian_success = (decay_resolved_weight + (k * baseline)) / (decay_assigned_weight + k)
            bayesian_success = round(max(0.0, min(1.0, bayesian_success)), 4)

            # Category Experience Score (0.0 to 1.0, with saturation threshold)
            sat = cfg["experience_saturation_tickets"]
            exp_score = min(1.0, assigned_count / float(sat))
            exp_score = round(exp_score, 4)

            # Reassignment Penalty (bounded and proportional)
            smoothed_reassign_rate = decay_reassigned_weight / (decay_assigned_weight + decay_reassigned_weight + 2.0)
            penalty = min(cfg["max_reassignment_penalty"], smoothed_reassign_rate * 0.6)
            penalty = round(penalty, 4)

            return {
                "assigned_count": assigned_count,
                "resolved_count": resolved_count,
                "reassigned_count": reassigned_count,
                "resolution_rate": res_rate,
                "reassignment_rate": reassign_rate,
                "average_resolution_time": avg_dur,
                "sample_size": assigned_count,
                "bayesian_success_score": bayesian_success,
                "category_experience_score": exp_score,
                "reassignment_penalty": penalty,
                "is_fallback": False
            }

        except Exception as e:
            logger.warning(f"Error computing agent historical stats for {agent_id}: {e}. Falling back to default baseline.")
            default_stats["is_fallback"] = True
            return default_stats

    async def auto_route_ticket(self, ticket_id: str) -> Dict[str, Any]:
        """
        Main logic for intelligent adaptive routing:
        1. Analyzes ticket content & keywords
        2. Selects best team based on competencies
        3. Evaluates agents within the team using the 5-factor adaptive formula:
           - skill_score (35%)
           - workload_score (20%)
           - historical_success_score (25%, Bayesian smoothed)
           - category_experience_score (15%)
           - reassignment_penalty (-15%)
           - bounded priority adjustment
        4. Persists routing decision with full explainability details
        """
        cfg = self.config
        w = cfg["weights"]

        # 1. Fetch ticket
        oid = MongoModel.to_object_id(ticket_id)
        ticket = await self.tickets.find_one({"_id": oid})
        if not ticket:
            raise ValueError("Ticket not found")

        # 2. AI Analysis for Keywords
        ai_analysis = await self.ai_client.analyze_ticket(ticket)
        keywords = ai_analysis.get("keywords", [])

        if not keywords:
            logger.warning(f"AI Analysis returned no keywords for ticket {ticket_id}. Using fallback matching.")
        else:
            logger.info(f"AI Analysis success for ticket {ticket_id}. Keywords: {keywords}")

        # Add category and subcategory to keywords for matching
        keywords.extend([ticket.get("category", ""), ticket.get("subcategory", "")])
        keywords = [k.lower() for k in keywords if k]
        keywords = list(set(keywords))  # deduplicate

        # 3. Find Best Team
        all_teams = await self.teams.find().to_list(length=100)
        best_team = None
        best_team_score = -1.0

        for team in all_teams:
            score = self._calculate_matching_score(keywords, team.get("competencies", []))
            if score > best_team_score:
                best_team_score = score
                best_team = team

        if not best_team:
            best_team = all_teams[0] if all_teams else None
            best_team_score = 0.1

        # 4. Find Best Agent within Team using Adaptive Feedback Loop
        best_agent = None
        best_agent_score = -1.0
        best_details: Dict[str, Any] = {
            "skill_score": 0.0,
            "workload_score": 0.0,
            "historical_success_score": cfg["bayesian_baseline"],
            "category_experience_score": 0.0,
            "reassignment_penalty": 0.0,
            "sample_size": 0,
            "final_score": 0.0
        }

        if best_team:
            agent_ids = [MongoModel.to_object_id(aid) for aid in best_team.get("agent_ids", [])]
            team_agents = await self.agents.find({"_id": {"$in": agent_ids}, "is_available": True}).to_list(length=100)

            # Ticket priority adjustment
            ticket_priority = str(ticket.get("priority", "MEDIUM")).upper()
            prio_boost = cfg["priority_boosts"].get(ticket_priority, 0.0)

            for agent in team_agents:
                # Factor 1: Skill score (0.0 to 1.0)
                skill_score = self._calculate_matching_score(keywords, agent.get("skills", []))

                # Factor 2: Workload score (0.0 to 1.0, lower workload is better)
                workload = agent.get("workload", 0)
                workload_score = max(0.0, min(1.0, (10.0 - workload) / 10.0))

                # Factors 3, 4, 5: Historical Feedback Loop
                agent_str_id = str(agent["_id"])
                stats = await self._compute_agent_historical_stats(
                    agent_id=agent_str_id,
                    category=ticket.get("category"),
                    subcategory=ticket.get("subcategory")
                )

                hist_success_score = stats["bayesian_success_score"]
                cat_experience_score = stats["category_experience_score"]
                reassignment_penalty = stats["reassignment_penalty"]

                # Composite adaptive score
                composite_score = (
                    (skill_score * w["skill"])
                    + (workload_score * w["workload"])
                    + (hist_success_score * w["historical_success"])
                    + (cat_experience_score * w["category_experience"])
                    - (reassignment_penalty * w["reassignment_penalty"])
                    + prio_boost
                )
                total_score = round(max(0.01, composite_score), 4)

                if total_score > best_agent_score:
                    best_agent_score = total_score
                    best_agent = agent
                    best_details = {
                        "skill_score": round(skill_score, 2),
                        "workload_score": round(workload_score, 2),
                        "historical_success_score": round(hist_success_score, 2),
                        "category_experience_score": round(cat_experience_score, 2),
                        "reassignment_penalty": round(reassignment_penalty, 2),
                        "sample_size": stats["sample_size"],
                        "final_score": round(total_score, 2)
                    }

        # 5. Final Selection & Explainability Details
        confidence_score = round(min(best_agent_score, 1.0) * 100, 2) if best_agent else 0
        match_quality = self._get_match_quality(confidence_score)

        if best_agent:
            agent_label = best_agent.get("user_id", "Agent")
            reason = (
                f"Matched based on keywords: {', '.join(keywords[:5])}. "
                f"Agent {agent_label} selected with adaptive score {best_agent_score:.2f} "
                f"(Skills: {best_details['skill_score']:.2f}, "
                f"Success: {best_details['historical_success_score']:.2f}, "
                f"Exp: {best_details['category_experience_score']:.2f}, "
                f"Workload: {best_details['workload_score']:.2f})."
            )
        else:
            reason = f"Matched based on keywords: {', '.join(keywords[:5])}. No suitable agent found in the best matching team."

        result = {
            "ticket_id": ticket_id,
            "selected_team": str(best_team["_id"]) if best_team else None,
            "selected_agent": str(best_agent["_id"]) if best_agent else None,
            "team_name": best_team.get("name") if best_team else "Unknown",
            "agent_name": best_agent.get("user_id") if best_agent else "Unassigned",
            "confidence_score": confidence_score,
            "match_quality": match_quality,
            "routing_reason": reason,
            "scoring_details": best_details,
            "created_at": datetime.utcnow()
        }

        # 6. Update Ticket & Handle Workload / Reassignment
        if best_agent:
            old_agent_id = ticket.get("assigned_agent_id")
            new_agent_id = str(best_agent["_id"])

            update_data: Dict[str, Any] = {
                "assigned_agent_id": new_agent_id,
                "status": TicketStatus.IN_PROGRESS.value,
                "routing_reason": reason,
                "updated_at": datetime.utcnow()
            }

            # If reassigning from an existing agent to another agent
            if old_agent_id and str(old_agent_id) != new_agent_id:
                old_oid = MongoModel.to_object_id(old_agent_id)
                if old_oid:
                    await self.agents.update_one({"_id": old_oid}, {"$inc": {"workload": -1}})

                reassign_event = {
                    "from_agent_id": str(old_agent_id),
                    "to_agent_id": new_agent_id,
                    "reassigned_at": datetime.utcnow()
                }

                await self.tickets.update_one(
                    {"_id": oid},
                    {
                        "$set": update_data,
                        "$push": {"reassignment_history": reassign_event},
                        "$addToSet": {"reassigned_from_agent_ids": str(old_agent_id)},
                        "$inc": {"reassignment_count": 1}
                    }
                )
            else:
                await self.tickets.update_one({"_id": oid}, {"$set": update_data})

            # Increment New Agent Workload if it's a new assignment
            if not old_agent_id or str(old_agent_id) != new_agent_id:
                await self.agents.update_one({"_id": best_agent["_id"]}, {"$inc": {"workload": 1}})

        # 7. Save to History
        await self.history.insert_one(result)

        return MongoModel.format_id(result)

    def _calculate_matching_score(self, keywords: List[str], competencies: List[str]) -> float:
        if not competencies or not keywords:
            return 0.0

        matches = 0
        comp_lower = [c.lower() for c in competencies]

        for kw in keywords:
            for comp in comp_lower:
                if kw in comp or comp in kw:
                    matches += 1
                    break

        return matches / max(len(keywords), 1)

    def _get_match_quality(self, score: float) -> str:
        if score >= 80:
            return "Excellent Match"
        elif score >= 50:
            return "Good Match"
        else:
            return "Weak Match"
