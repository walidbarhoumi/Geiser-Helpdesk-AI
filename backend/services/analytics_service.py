from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
from collections import defaultdict

from fastapi import HTTPException
from core.permissions import Permission, has_role_permission
from schemas.schemas import (
    UserRole,
    VolumeTrendPoint, CategoryBreakdown, AgentPerformanceOut,
    MTTRByPriority, MTTRMetricsOut, StrategicRecurrentIssue,
    AIPredictiveInsights, SummaryKPIs, AnalyticsDashboardOut,
    TicketPriority, TicketStatus, SLAStatus,
    CSATAnalyticsOut, CSATTrendPoint, CSATAgentStat, CSATCategoryStat, CSATRecentFeedback
)
from services.sla_service import DEFAULT_SLA_POLICIES
from services.ai.ollama_service import OllamaService
from models.base import MongoModel

logger = logging.getLogger(__name__)


def _role_val(user: Optional[Dict]) -> Optional[str]:
    if not user:
        return None
    r = user.get("role")
    return r.value if hasattr(r, "value") else str(r)


class AnalyticsService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.tickets = db.tickets
        self.agents = db.agents
        self.users = db.users
        self.ollama = OllamaService()

    async def get_visible_agent_ids(self, current_user: Optional[Dict]) -> set:
        role = _role_val(current_user)
        if role in (UserRole.ADMIN.value, UserRole.SUPERVISOR.value):
            agents = await self.agents.find().to_list(1000)
            return {str(a.get("_id") or a.get("id")) for a in agents}
        if role != UserRole.AGENT.value or not current_user:
            return set()
        agent = await self.agents.find_one({"user_id": str(current_user.get("id"))})
        if not agent:
            return set()
        agent_id = str(agent.get("_id") or agent.get("id"))
        teams = await self.db.teams.find({"agent_ids": agent_id}).to_list(100)
        team_ids = {str(t.get("_id") or t.get("id")) for t in teams}
        team_agent_ids = {str(a) for team in teams for a in team.get("agent_ids", [])}
        return team_agent_ids | {agent_id}

    async def validate_team_scope(self, current_user: Optional[Dict], team_id: str) -> Dict:
        try:
            team = await self.db.teams.find_one({"_id": MongoModel.to_object_id(team_id)})
        except Exception:
            team = None
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        if _role_val(current_user) == UserRole.AGENT.value:
            visible = await self.get_visible_agent_ids(current_user)
            if not visible.intersection(str(a) for a in team.get("agent_ids", [])):
                raise HTTPException(status_code=404, detail="Team not found")
        return team

    async def get_scoped_tickets(self, current_user: Optional[Dict], priority: Optional[str] = None,
                                 team_id: Optional[str] = None, start_date: Optional[str] = None,
                                 end_date: Optional[str] = None, period_days: Optional[int] = None) -> List[Dict]:
        role = _role_val(current_user)
        if not current_user or not has_role_permission(role or "", Permission.ANALYTICS_VIEW):
            raise HTTPException(status_code=403, detail="Analytics access forbidden")
        agent_id = None
        team_ids = set()
        visible_agents = None
        if role == UserRole.AGENT.value:
            agent = await self.agents.find_one({"user_id": str(current_user.get("id"))})
            if agent:
                agent_id = str(agent.get("_id") or agent.get("id"))
                teams = await self.db.teams.find({"agent_ids": agent_id}).to_list(100)
                team_ids = {str(t.get("_id") or t.get("id")) for t in teams}
                visible_agents = {str(a) for t in teams for a in t.get("agent_ids", [])} | {agent_id}
            else:
                visible_agents = set()
        selected_team = await self.validate_team_scope(current_user, team_id) if team_id else None
        raw = await self.tickets.find({}).to_list(10000)
        now = datetime.utcnow()
        start_dt = self._parse_filter_date(start_date) if start_date else (now - timedelta(days=period_days) if period_days else None)
        end_dt = self._parse_filter_date(end_date) if end_date else None
        scoped = []
        for ticket in raw:
            if role == UserRole.AGENT.value:
                assigned_agent = str(ticket.get("assigned_agent_id") or "")
                assigned_team = str(ticket.get("assigned_team_id") or "")
                if assigned_agent not in visible_agents and assigned_team not in team_ids:
                    continue
            if selected_team:
                allowed_agent_ids = {str(a) for a in selected_team.get("agent_ids", [])}
                if str(ticket.get("assigned_agent_id") or "") not in allowed_agent_ids and str(ticket.get("assigned_team_id") or "") != team_id:
                    continue
            created = ticket.get("created_at")
            if start_dt and (not isinstance(created, datetime) or created < start_dt):
                continue
            if end_dt and (not isinstance(created, datetime) or created > end_dt):
                continue
            if priority and str(ticket.get("priority", "")).upper() != priority.upper():
                continue
            scoped.append(ticket)
        return scoped

    @staticmethod
    def _parse_filter_date(value: str) -> datetime:
        try:
            return datetime.fromisoformat(value.replace("Z", ""))
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid date filter")

    async def get_dashboard_analytics(
        self,
        period_days: int = 30,
        priority: Optional[str] = None,
        team_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        current_user: Optional[Dict] = None
    ) -> AnalyticsDashboardOut:
        """
        Orchestrates full predictive analytics and metrics with manager filters:
        - date range / period_days
        - priority filter (URGENT, HIGH, MEDIUM, LOW)
        - team filter (by team_id)
        - role-based scoping (USER -> own tickets, AGENT -> assigned/team tickets, ADMIN/SUPERVISOR -> all)
        """
        role = _role_val(current_user)
        all_tickets = await self.get_scoped_tickets(current_user, priority, team_id, start_date, end_date, period_days)
        agent_id = None
        # 1. Summary KPIs
        kpis = self._compute_summary_kpis(all_tickets)

        # 2. Volume Trends
        volume_trends = self._compute_volume_trends(all_tickets, period_days=period_days)

        # 3. Category Breakdown
        category_distribution = self._compute_category_distribution(all_tickets)

        # 4. Agent Performance (Ordinary users NEVER see agent workforce details)
        if role == UserRole.AGENT.value:
            all_ag = await self._compute_agent_performances(all_tickets)
            visible_agent_ids = await self.get_visible_agent_ids(current_user)
            agent_performances = [ag for ag in all_ag if ag.agent_id in visible_agent_ids]
        else:
            agent_performances = await self._compute_agent_performances(all_tickets)
        if team_id:
            selected_team = await self.validate_team_scope(current_user, team_id)
            selected_agent_ids = {str(a) for a in selected_team.get("agent_ids", [])}
            agent_performances = [a for a in agent_performances if a.agent_id in selected_agent_ids]

        # 5. MTTR Metrics
        mttr_metrics = self._compute_mttr_metrics(all_tickets, category_distribution)

        # 6. Customer Satisfaction (CSAT) Detailed Metrics
        csat = self._compute_csat_analytics(all_tickets, period_days=period_days)
        if role == UserRole.USER.value:
            csat.by_agent = []
        kpis.positive_satisfaction_rate_pct = csat.satisfaction_rate_pct

        # 7. AI Predictive Insights (Ordinary users see limited non-operational view)
        predictive_insights = await self._compute_predictive_insights(all_tickets, kpis, volume_trends)

        # Update kpis critical_recurring_count from strategic issues
        kpis.critical_recurring_count = len(predictive_insights.strategic_issues)

        return AnalyticsDashboardOut(
            kpis=kpis,
            volume_trends=volume_trends,
            category_distribution=category_distribution,
            agent_performances=agent_performances,
            mttr_metrics=mttr_metrics,
            predictive_insights=predictive_insights,
            csat=csat,
            generated_at=datetime.utcnow()
        )

    def _compute_summary_kpis(self, tickets: List[Dict]) -> SummaryKPIs:
        total = len(tickets)
        if total == 0:
            return SummaryKPIs(
                total_tickets=0, open_tickets=0, in_progress_tickets=0,
                resolved_tickets=0, resolution_rate_pct=None,
                overall_mttr_hours=None, overall_sla_compliance_pct=None,
                critical_recurring_count=0,
                avg_response_hours=None,
                satisfaction_avg=None,
                satisfaction_responses_count=0,
                positive_satisfaction_rate_pct=None
            )

        open_c = sum(1 for t in tickets if str(t.get("status", "")).upper() in ["OPEN", TicketStatus.OPEN.value])
        prog_c = sum(1 for t in tickets if str(t.get("status", "")).upper() in ["IN_PROGRESS", TicketStatus.IN_PROGRESS.value])
        res_c = sum(1 for t in tickets if str(t.get("status", "")).upper() in ["RESOLVED", "CLOSED", TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value])

        res_rate = round((res_c / total) * 100.0, 1)

        # MTTR on resolved tickets with valid timestamps
        resolution_durations = []
        for t in tickets:
            if str(t.get("status", "")).upper() in ["RESOLVED", "CLOSED", TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value]:
                c_at = t.get("created_at")
                u_at = t.get("updated_at")
                if c_at and u_at and isinstance(c_at, datetime) and isinstance(u_at, datetime) and u_at > c_at:
                    dur_hours = (u_at - c_at).total_seconds() / 3600.0
                    resolution_durations.append(dur_hours)

        overall_mttr = round(sum(resolution_durations) / len(resolution_durations), 1) if resolution_durations else None

        # Response time calculation (first agent response on ticket)
        response_durations = []
        for t in tickets:
            c_at = t.get("created_at")
            responses = t.get("responses") or []
            if c_at and isinstance(c_at, datetime) and responses and isinstance(responses, list):
                first_resp = responses[0]
                if isinstance(first_resp, dict):
                    r_at = first_resp.get("created_at")
                    if r_at and isinstance(r_at, datetime) and r_at > c_at:
                        dur_hours = (r_at - c_at).total_seconds() / 3600.0
                        response_durations.append(dur_hours)

        avg_resp = round(sum(response_durations) / len(response_durations), 1) if response_durations else None

        # Customer Satisfaction (CSAT) calculation from persisted ratings
        csat_ratings = [t["satisfaction_rating"] for t in tickets if t.get("satisfaction_rating") is not None]
        avg_csat = round(sum(csat_ratings) / len(csat_ratings), 1) if csat_ratings else None
        csat_count = len(csat_ratings)
        positive_rate = round((sum(1 for r in csat_ratings if r >= 4) / csat_count) * 100.0, 1) if csat_count > 0 else None

        # SLA compliance calculation
        known_sla = [t for t in tickets if t.get("sla_status") is not None or t.get("sla_breached_at") is not None]
        breached_count = sum(1 for t in known_sla if t.get("sla_breached_at") is not None or str(t.get("sla_status", "")).upper() in ["BREACHED", SLAStatus.BREACHED.value])
        sla_comp = round(((len(known_sla) - breached_count) / len(known_sla)) * 100.0, 1) if known_sla else None

        return SummaryKPIs(
            total_tickets=total,
            open_tickets=open_c,
            in_progress_tickets=prog_c,
            resolved_tickets=res_c,
            resolution_rate_pct=res_rate,
            overall_mttr_hours=overall_mttr,
            overall_sla_compliance_pct=sla_comp,
            critical_recurring_count=0,
            avg_response_hours=avg_resp,
            satisfaction_avg=avg_csat,
            satisfaction_responses_count=csat_count,
            positive_satisfaction_rate_pct=positive_rate
        )

    def _compute_volume_trends(self, tickets: List[Dict], period_days: int = 14) -> List[VolumeTrendPoint]:
        """Aggregate ticket counts day by day for the last period_days."""
        now = datetime.utcnow()
        days_map = {}

        # Initialize slots for each day
        for d in range(period_days - 1, -1, -1):
            day_dt = now - timedelta(days=d)
            key = day_dt.strftime("%Y-%m-%d")
            label = day_dt.strftime("%d %b")
            days_map[key] = {
                "date": key,
                "label": label,
                "total_tickets": 0,
                "resolved_count": 0,
                "urgent_count": 0
            }

        # Populate from real tickets
        for t in tickets:
            c_at = t.get("created_at")
            if c_at and isinstance(c_at, datetime):
                key = c_at.strftime("%Y-%m-%d")
                if key in days_map:
                    days_map[key]["total_tickets"] += 1
                    if t.get("status") in [TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value, "RESOLVED", "CLOSED"]:
                        days_map[key]["resolved_count"] += 1
                    if t.get("priority") in [TicketPriority.URGENT.value, "URGENT"]:
                        days_map[key]["urgent_count"] += 1

        return [VolumeTrendPoint(**data) for data in days_map.values()]

    def _compute_category_distribution(self, tickets: List[Dict]) -> List[CategoryBreakdown]:
        total = len(tickets)
        if total == 0:
            return []

        cat_counts = defaultdict(int)
        cat_durations = defaultdict(list)

        for t in tickets:
            cat = t.get("category") or "Général / Non classé"
            cat_counts[cat] += 1

            if t.get("status") in [TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value, "RESOLVED", "CLOSED"]:
                c_at = t.get("created_at")
                u_at = t.get("updated_at")
                if c_at and u_at and u_at > c_at:
                    cat_durations[cat].append((u_at - c_at).total_seconds() / 3600.0)

        result = []
        for cat, count in sorted(cat_counts.items(), key=lambda x: x[1], reverse=True):
            pct = round((count / total) * 100.0, 1)
            durations = cat_durations.get(cat, [])
            avg_h = round(sum(durations) / len(durations), 1) if durations else None
            result.append(CategoryBreakdown(
                category=cat,
                count=count,
                percentage=pct,
                avg_resolution_hours=avg_h
            ))

        return result

    async def _compute_agent_performances(self, tickets: List[Dict]) -> List[AgentPerformanceOut]:
        agents_cursor = self.agents.find()
        agents_list = await agents_cursor.to_list(100)

        results = []
        for agent in agents_list:
            agent_id = str(agent.get("_id") or agent.get("id") or "")
            user_id = agent.get("user_id")

            # Look up agent user info (full_name, email)
            user = None
            if user_id:
                try:
                    user = await self.users.find_one({"_id": MongoModel.to_object_id(user_id)})
                except Exception:
                    user = await self.users.find_one({"$or": [{"email": user_id}, {"username": user_id}]})

            if user and user.get("full_name"):
                name = user.get("full_name")
            elif user_id and "." in user_id:
                name = " ".join(p.capitalize() for p in user_id.split("@")[0].split("."))
            elif user_id:
                name = user_id.capitalize()
            else:
                name = f"Agent #{agent_id[-4:]}"

            email = user.get("email") if user else f"{user_id or 'agent'}@geiser.internal"

            # Filter tickets assigned to this agent
            assigned_tickets = [t for t in tickets if str(t.get("assigned_agent_id")) == agent_id]
            assigned_c = len(assigned_tickets)

            resolved_tickets = [t for t in assigned_tickets if str(t.get("status", "")).upper() in [TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value, "RESOLVED", "CLOSED"]]
            resolved_c = len(resolved_tickets)

            # Resolution durations with valid timestamps
            durations = []
            for t in resolved_tickets:
                c_at = t.get("created_at")
                u_at = t.get("updated_at")
                if c_at and u_at and isinstance(c_at, datetime) and isinstance(u_at, datetime) and u_at > c_at:
                    durations.append((u_at - c_at).total_seconds() / 3600.0)

            avg_res_h = round(sum(durations) / len(durations), 1) if durations else None

            # SLA compliance %
            known_sla = [t for t in assigned_tickets if t.get("sla_status") is not None or t.get("sla_breached_at") is not None]
            breached = sum(1 for t in known_sla if t.get("sla_breached_at") is not None or str(t.get("sla_status", "")).upper() in [SLAStatus.BREACHED.value, "BREACHED"])
            sla_pct = round(((len(known_sla) - breached) / len(known_sla)) * 100.0, 1) if known_sla else None

            # Rating
            if sla_pct is None:
                rating = "Insufficient data"
            elif sla_pct >= 90.0 and resolved_c >= 5:
                rating = "Excellent"
            elif sla_pct >= 80.0:
                rating = "Bon"
            else:
                rating = "En progression"

            # CSAT calculation per agent
            ag_csat_ratings = [t["satisfaction_rating"] for t in assigned_tickets if t.get("satisfaction_rating") is not None]
            ag_avg_csat = round(sum(ag_csat_ratings) / len(ag_csat_ratings), 1) if ag_csat_ratings else None
            ag_csat_count = len(ag_csat_ratings)

            results.append(AgentPerformanceOut(
                agent_id=agent_id,
                agent_name=name,
                email=email,
                skills=agent.get("skills", []),
                is_available=agent.get("is_available", True),
                workload=sum(1 for t in assigned_tickets if str(t.get("status", "")).upper() not in ["RESOLVED", "CLOSED"]),
                assigned_count=assigned_c,
                resolved_count=resolved_c,
                avg_resolution_hours=avg_res_h,
                sla_compliance_pct=sla_pct,
                efficiency_rating=rating,
                avg_csat_score=ag_avg_csat,
                csat_responses_count=ag_csat_count
            ))

        # Sort agents by resolved count descending
        results.sort(key=lambda a: a.resolved_count, reverse=True)
        return results

    def _compute_mttr_metrics(self, tickets: List[Dict], category_distribution: List[CategoryBreakdown]) -> MTTRMetricsOut:
        total = len(tickets)
        durations_by_prio = defaultdict(list)
        all_durations = []

        for t in tickets:
            if str(t.get("status", "")).upper() in [TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value, "RESOLVED", "CLOSED"]:
                c_at = t.get("created_at")
                u_at = t.get("updated_at")
                if c_at and u_at and isinstance(c_at, datetime) and isinstance(u_at, datetime) and u_at > c_at:
                    dur_h = (u_at - c_at).total_seconds() / 3600.0
                    prio = t.get("priority", TicketPriority.MEDIUM.value)
                    durations_by_prio[prio].append(dur_h)
                    all_durations.append(dur_h)

        overall_mttr = round(sum(all_durations) / len(all_durations), 1) if all_durations else None

        by_priority_list = []
        for prio in [TicketPriority.URGENT, TicketPriority.HIGH, TicketPriority.MEDIUM, TicketPriority.LOW]:
            policy = DEFAULT_SLA_POLICIES.get(prio, DEFAULT_SLA_POLICIES[TicketPriority.MEDIUM])
            target_h = policy["resolution_time_hours"]

            prio_durations = durations_by_prio.get(prio.value, [])
            actual_avg_h = round(sum(prio_durations) / len(prio_durations), 1) if prio_durations else None
            is_within = (actual_avg_h <= target_h) if actual_avg_h is not None else None

            by_priority_list.append(MTTRByPriority(
                priority=prio,
                avg_resolution_hours=actual_avg_h,
                sla_target_hours=target_h,
                is_within_sla=is_within
            ))

        known_sla = [t for t in tickets if t.get("sla_status") is not None or t.get("sla_breached_at") is not None]
        non_breached = sum(1 for t in known_sla if t.get("sla_breached_at") is None and str(t.get("sla_status", "")).upper() not in [SLAStatus.BREACHED.value, "BREACHED"])
        sla_comp = round((non_breached / len(known_sla)) * 100.0, 1) if known_sla else None

        return MTTRMetricsOut(
            overall_avg_hours=overall_mttr,
            by_priority=by_priority_list,
            by_category=category_distribution,
            sla_compliance_overall_pct=sla_comp
        )

    async def _compute_predictive_insights(self, tickets: List[Dict], kpis: SummaryKPIs, volume_trends: List[VolumeTrendPoint]) -> AIPredictiveInsights:
        """
        AI Predictive Analysis:
        1. Identifies strategic systemic recurring issues (Root cause clusters)
        2. Projects ticket volume for the next 7 days
        3. Identifies SLA breach risks and peak risk windows
        """
        from services.predictive_analytics_service import PredictiveAnalyticsService
        pred_svc = PredictiveAnalyticsService(self.db)

        # 1. Advanced Volume Forecast
        try:
            vol_forecast = await pred_svc.generate_volume_forecast(tickets, forecast_days=7)
        except Exception as e:
            logger.warning(f"Error computing volume forecast: {e}")
            vol_forecast = None

        # 2. SLA Breach Risk Prediction on Active Tickets
        try:
            active_list = [
                t for t in tickets 
                if t.get("status") in ["OPEN", "IN_PROGRESS", "REOPENED", TicketStatus.OPEN.value, TicketStatus.IN_PROGRESS.value]
            ]
            sla_breach_risks = await pred_svc.predict_sla_breach_risks(active_tickets=active_list, all_tickets=tickets)
        except Exception as e:
            logger.warning(f"Error computing SLA breach risks: {e}")
            sla_breach_risks = None

        # 3. Recurring Ticket Detection & Clustering
        try:
            recurring_resp = await pred_svc.detect_recurring_tickets(tickets)
            recurring_clusters = recurring_resp.clusters
        except Exception as e:
            logger.warning(f"Error detecting recurring tickets: {e}")
            recurring_clusters = []

        # Convert recurring clusters to StrategicRecurrentIssue for backward compatibility
        strategic_issues: List[StrategicRecurrentIssue] = []
        for cl in recurring_clusters:
            sample_ids = [t.reference.replace("[TICK-", "").replace("]", "") for t in cl.sample_tickets[:4]]
            strategic_issues.append(StrategicRecurrentIssue(
                cluster_id=cl.cluster_id,
                title=cl.title,
                category=cl.category,
                recurrence_count=cl.occurrence_count,
                impact_level=cl.impact_level,
                estimated_hours_lost=cl.estimated_hours_lost,
                root_cause_analysis=cl.root_cause_analysis,
                ai_strategic_recommendation=cl.common_solutions[0] if cl.common_solutions else "Aucune solution historique identifiée.",
                preventive_action_plan=cl.preventive_action_plan,
                sample_ticket_ids=sample_ids
            ))

        # No fabricated fallback — if no real clusters found, strategic_issues stays empty

        # Predictive volume forecast summary
        if vol_forecast and vol_forecast.confidence_level != "UNAVAILABLE":
            predicted_volume = vol_forecast.total_predicted_volume
            growth_pct = vol_forecast.growth_trend_pct
            spike_risk = vol_forecast.spike_risk
        else:
            last_7_days_volume = sum(p.total_tickets for p in volume_trends[-7:]) if len(volume_trends) >= 7 else kpis.total_tickets
            predicted_volume = None
            growth_pct = None
            spike_risk = None

        sla_risk_summary = ""
        if sla_breach_risks and sla_breach_risks.at_risk_count > 0:
            sla_risk_summary = f" Vigilance SLA : {sla_breach_risks.at_risk_count} ticket(s) actif(s) sous risque de dépassement imminent."

        forecast_summary = (
            f"L'IA prévoit un volume estimé à ~{predicted_volume} tickets pour la semaine à venir ({'+' if growth_pct >= 0 else ''}{growth_pct}%). "
            f"Risque de saturation globale : {spike_risk}.{sla_risk_summary}"
        ) if vol_forecast and vol_forecast.confidence_level != "UNAVAILABLE" else "Prévision indisponible : données historiques insuffisantes."

        focus_areas: List[str] = []
        if sla_breach_risks and sla_breach_risks.critical_count > 0:
            focus_areas.append(f"Traiter en priorité absolue les {sla_breach_risks.critical_count} ticket(s) en dépassement SLA critique")
        if sla_breach_risks and sla_breach_risks.at_risk_count > 0:
            focus_areas.append("Surveiller les tickets URGENTS pour maintenir la conformité SLA au-dessus de 95%")

        return AIPredictiveInsights(
            forecast_summary=forecast_summary,
            predicted_volume_next_week=predicted_volume,
            volume_growth_trend_pct=growth_pct,
            predicted_spike_risk=spike_risk,
            peak_time_windows=[],  # computed from real data only — no hardcoded time windows
            strategic_issues=strategic_issues,
            recommended_focus_areas=focus_areas,
            volume_forecast=vol_forecast,
            sla_breach_risks=sla_breach_risks,
            recurring_clusters=recurring_clusters
        )

    def _compute_csat_analytics(self, tickets: List[Dict], period_days: int = 30) -> CSATAnalyticsOut:
        """
        Computes detailed CSAT metrics:
        - Total ratings count
        - Average rating score (1-5)
        - Satisfaction rate % (percentage of positive ratings: rating >= 4)
        - Star distribution (1 to 5)
        - Temporal trend over period_days
        - Agent-level CSAT aggregation
        - Category-level CSAT aggregation
        - Recent qualitative feedback comments
        """
        rated_tickets = [t for t in tickets if t.get("satisfaction_rating") is not None]
        total_ratings = len(rated_tickets)

        distribution = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
        for t in rated_tickets:
            r_str = str(t.get("satisfaction_rating"))
            if r_str in distribution:
                distribution[r_str] += 1

        if total_ratings > 0:
            ratings = [t["satisfaction_rating"] for t in rated_tickets]
            avg_rating = round(sum(ratings) / total_ratings, 2)
            positive_count = sum(1 for r in ratings if r >= 4)
            satisfaction_rate_pct = round((positive_count / total_ratings) * 100.0, 1)
        else:
            avg_rating = None
            satisfaction_rate_pct = None

        # Temporal trend over time (daily buckets)
        now = datetime.utcnow()
        days_map: Dict[str, Dict] = {}
        for d in range(min(period_days, 30) - 1, -1, -1):
            day_dt = now - timedelta(days=d)
            key = day_dt.strftime("%Y-%m-%d")
            label = day_dt.strftime("%d %b")
            days_map[key] = {"date": key, "label": label, "ratings": []}

        for t in rated_tickets:
            dt = t.get("satisfaction_submitted_at") or t.get("updated_at") or t.get("created_at")
            if dt and isinstance(dt, datetime):
                key = dt.strftime("%Y-%m-%d")
                if key in days_map:
                    days_map[key]["ratings"].append(t["satisfaction_rating"])

        trend: List[CSATTrendPoint] = []
        for key in sorted(days_map.keys()):
            slot = days_map[key]
            r_list = slot["ratings"]
            slot_avg = round(sum(r_list) / len(r_list), 1) if r_list else None
            trend.append(CSATTrendPoint(
                date=slot["date"],
                label=slot["label"],
                avg_rating=slot_avg,
                count=len(r_list)
            ))

        # By category
        cat_map: Dict[str, List[int]] = defaultdict(list)
        for t in rated_tickets:
            cat = t.get("category") or "Général"
            cat_map[cat].append(t["satisfaction_rating"])

        by_category = [
            CSATCategoryStat(
                category=cat,
                avg_rating=round(sum(rats) / len(rats), 1),
                count=len(rats)
            )
            for cat, rats in sorted(cat_map.items(), key=lambda x: len(x[1]), reverse=True)
        ]

        # By agent
        agent_map: Dict[str, List[int]] = defaultdict(list)
        for t in rated_tickets:
            ag_id = t.get("assigned_agent_id")
            if ag_id:
                agent_map[str(ag_id)].append(t["satisfaction_rating"])

        by_agent = [
            CSATAgentStat(
                agent_id=ag_id,
                avg_rating=round(sum(rats) / len(rats), 1),
                count=len(rats)
            )
            for ag_id, rats in sorted(agent_map.items(), key=lambda x: len(x[1]), reverse=True)
        ]

        # Recent qualitative feedback
        feedback_tickets = [t for t in rated_tickets if t.get("satisfaction_comment")]
        feedback_tickets.sort(key=lambda t: t.get("satisfaction_submitted_at") or datetime.min, reverse=True)
        recent_feedback = [
            CSATRecentFeedback(
                ticket_id=str(t.get("_id") or t.get("id")),
                rating=t["satisfaction_rating"],
                comment=t.get("satisfaction_comment"),
                category=t.get("category"),
                agent_id=str(t.get("assigned_agent_id")) if t.get("assigned_agent_id") else None,
                submitted_at=t.get("satisfaction_submitted_at")
            )
            for t in feedback_tickets[:10]
        ]

        return CSATAnalyticsOut(
            total_ratings=total_ratings,
            avg_rating=avg_rating,
            satisfaction_rate_pct=satisfaction_rate_pct,
            distribution=distribution,
            trend=trend,
            by_agent=by_agent,
            by_category=by_category,
            recent_feedback=recent_feedback,
            period_days=period_days
        )

    async def get_csat_analytics(
        self, period_days: int = 30, current_user: Optional[Dict] = None
    ) -> CSATAnalyticsOut:
        """Dedicated method to retrieve CSAT analytics for the given period.

        Applies the same role-based scoping as get_dashboard_analytics:
        - ADMIN / SUPERVISOR → all tickets
        - AGENT → only tickets in the agent's own teams
        - USER → only tickets created by that user
        """
        raw_tickets = await self.get_scoped_tickets(current_user, period_days=period_days)

        now = datetime.utcnow()
        cutoff = now - timedelta(days=period_days)
        tickets = [
            t for t in raw_tickets
            if (t.get("created_at") and isinstance(t.get("created_at"), datetime) and t.get("created_at") >= cutoff)
            or (t.get("satisfaction_submitted_at") and isinstance(t.get("satisfaction_submitted_at"), datetime) and t.get("satisfaction_submitted_at") >= cutoff)
        ] if period_days else raw_tickets
        return self._compute_csat_analytics(tickets, period_days=period_days)

