"""
services/predictive_analytics_service.py
=========================================
Feature 1: Advanced Predictive Analytics + Recurring Ticket Detection

Provides:
1. Ticket volume forecasting (daily projections, trend estimation, spike risk detection, baseline fallback)
2. Resolution-time prediction (segment-based MTTR with category/priority/urgency/impact multipliers & explainability)
3. SLA breach prediction (probability scoring, risk classification, preventative recommendations)
4. Recurring ticket detection (hybrid keyword + Jaccard token clustering, occurrence tracking, solution extraction)
"""

from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Union
import logging
import re
import math
from collections import defaultdict
from bson import ObjectId

from schemas.schemas import (
    TicketPriority, TicketStatus, SLAStatus, ImpactLevel, UrgencyLevel,
    DailyForecastPoint, VolumeForecastOut,
    ResolutionTimePredictionIn, ResolutionTimePredictionOut, ResolutionTimeFactor,
    SLABreachRiskTicket, SLABreachRisksOut,
    RecurringTicketSummary, RecurringClusterOut, RecurringIssuesResponse,
    StrategicRecurrentIssue
)
from services.sla_service import DEFAULT_SLA_POLICIES
from models.base import MongoModel

logger = logging.getLogger(__name__)

# Stopwords for French & English IT triage similarity
IT_STOPWORDS = {
    "le", "la", "les", "un", "une", "des", "du", "de", "d", "l", "en", "et", "a", "au",
    "aux", "est", "ce", "que", "qui", "dans", "pour", "sur", "mon", "ma", "mes", "ton",
    "ta", "tes", "son", "sa", "ses", "notre", "nos", "votre", "vos", "leur", "leurs",
    "je", "tu", "il", "elle", "nous", "vous", "ils", "elles", "avec", "sans", "ne", "pas",
    "the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "with", "is", "it",
    "this", "that", "my", "your", "our", "their", "problem", "probleme", "erreur", "error",
    "issue", "ticket", "bonjour", "salut", "merci", "aide", "urgent", "svp", "please",
    "depuis", "faire", "plus", "tout", "tous", "avoir", "etre", "fait"
}

FRENCH_DAYS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]


class PredictiveAnalyticsService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.tickets = db.tickets
        self.agents = db.agents
        self.users = db.users
        self.teams = db.teams
        self.knowledge_base = db.knowledge_base

    # ──────────────────────────────────────────────────────────
    # Helper: Tokenization & Similarity
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def _tokenize(text: str) -> set:
        """Tokenize text into lower-case keywords, removing stopwords and punctuation."""
        if not text:
            return set()
        words = re.findall(r'[a-zA-Z0-9àâäéèêëîïôöùûüç]+', text.lower())
        return {w for w in words if len(w) >= 3 and w not in IT_STOPWORDS}

    @staticmethod
    def _compute_jaccard(tokens1: set, tokens2: set) -> float:
        if not tokens1 or not tokens2:
            return 0.0
        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)
        return len(intersection) / len(union) if union else 0.0

    def _compute_pair_similarity(self, t1: Dict[str, Any], t2: Dict[str, Any]) -> float:
        """
        Compute similarity score between two tickets (0.0 to 100.0).
        Reuses text token Jaccard + Category match + Subcategory match + Keywords intersection.
        """
        tokens1 = self._tokenize(f"{t1.get('subject', '')} {t1.get('description', '')}")
        tokens2 = self._tokenize(f"{t2.get('subject', '')} {t2.get('description', '')}")
        
        kw1 = set(t1.get("keywords") or [])
        kw2 = set(t2.get("keywords") or [])
        all_t1 = tokens1 | kw1
        all_t2 = tokens2 | kw2

        # 1. Text & keyword Jaccard (up to 55 points)
        jaccard = self._compute_jaccard(all_t1, all_t2)
        score = jaccard * 55.0

        # 2. Category match (up to 20 points)
        cat1 = (t1.get("category") or "").strip().lower()
        cat2 = (t2.get("category") or "").strip().lower()
        if cat1 and cat2 and cat1 == cat2:
            score += 20.0
            # Subcategory match (up to 15 points)
            sub1 = (t1.get("subcategory") or "").strip().lower()
            sub2 = (t2.get("subcategory") or "").strip().lower()
            if sub1 and sub2 and sub1 == sub2:
                score += 15.0

        # 3. Exact common keywords bonus (up to 10 points)
        common_kw = kw1.intersection(kw2)
        if common_kw:
            score += min(10.0, len(common_kw) * 5.0)

        return min(100.0, round(score, 1))

    async def _safe_to_list(self, cursor: Any, limit: int = 2000) -> List[Dict[str, Any]]:
        """Safely awaits cursor.to_list(limit) across motor and unit mock environments."""
        try:
            if hasattr(cursor, "to_list"):
                p = cursor.to_list(limit)
                if hasattr(p, "__await__"):
                    return await p
            return []
        except Exception as e:
            logger.warning(f"Error reading cursor to list: {e}")
            return []

    # ──────────────────────────────────────────────────────────
    # 1. Ticket Volume Forecasting
    # ──────────────────────────────────────────────────────────

    async def generate_volume_forecast(
        self,
        tickets: Optional[List[Dict[str, Any]]] = None,
        forecast_days: int = 7
    ) -> VolumeForecastOut:
        """
        Forecast future daily ticket volume based on historical ticket creation trends.
        Gracefully handles zero tickets or insufficient historical data.
        """
        forecast_days = max(1, min(30, forecast_days))
        now = datetime.utcnow()

        if tickets is None:
            raw_tickets = await self._safe_to_list(self.tickets.find(), 5000)
        else:
            raw_tickets = tickets

        # Extract creation dates
        creation_dates: List[datetime] = []
        for t in raw_tickets:
            c_at = t.get("created_at")
            if isinstance(c_at, datetime):
                creation_dates.append(c_at)
            elif isinstance(c_at, str):
                try:
                    creation_dates.append(datetime.fromisoformat(c_at.replace("Z", "")))
                except Exception:
                    pass

        total_tickets = len(creation_dates)

        # Build day-by-day counts for the past 30 days
        daily_counts: Dict[str, int] = defaultdict(int)
        for dt in creation_dates:
            key = dt.strftime("%Y-%m-%d")
            daily_counts[key] += 1

        active_days_count = len(daily_counts)

        # ── Case A: Insufficient Historical Data (Fallback Baseline) ──
        if total_tickets < 3 or active_days_count < 2:
            return VolumeForecastOut(
                forecast_days=forecast_days,
                daily_forecasts=[],
                total_predicted_volume=None,
                historical_daily_avg=None,
                growth_trend_pct=None,
                spike_risk=None,
                confidence_level="UNAVAILABLE",
                is_baseline=True,
                peak_days=[],
                data_points_analyzed=total_tickets
            )

        # ── Case B: Sufficient Data (Statistical Rolling Average + Linear Trend) ──
        lookback_days = 30
        series: List[float] = []
        dow_totals: Dict[int, List[int]] = defaultdict(list)

        for d in range(lookback_days - 1, -1, -1):
            day_dt = now - timedelta(days=d)
            k = day_dt.strftime("%Y-%m-%d")
            c = daily_counts.get(k, 0)
            series.append(float(c))
            dow_totals[day_dt.weekday()].append(c)

        n = len(series)
        history_avg = sum(series) / n if n > 0 else 1.0

        # Day-of-week seasonality factors
        dow_factors = {}
        for dow in range(7):
            dow_vals = dow_totals.get(dow, [])
            if dow_vals and sum(dow_vals) > 0 and history_avg > 0:
                dow_avg = sum(dow_vals) / len(dow_vals)
                dow_factors[dow] = max(0.2, min(1.8, dow_avg / history_avg))
            else:
                dow_factors[dow] = 0.4 if dow in [5, 6] else 1.1

        # Linear regression slope over history
        x_mean = (n - 1) / 2.0
        y_mean = history_avg
        numerator = sum((i - x_mean) * (series[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        slope = numerator / denominator if denominator > 0 else 0.0

        forecast_points = []
        for i in range(1, forecast_days + 1):
            f_date = now + timedelta(days=i)
            dow_idx = f_date.weekday()
            dow_factor = dow_factors.get(dow_idx, 1.0)

            # Projected value = (trend line) * (day of week factor)
            x_future = n + i - 1
            projected = max(0.5, (y_mean + slope * (x_future - x_mean))) * dow_factor
            pred_count = max(0, int(round(projected)))

            # Margin bounds
            lower = max(0, int(math.floor(projected * 0.75)))
            upper = int(math.ceil(projected * 1.30)) + 1

            conf = 85.0 if active_days_count >= 14 else 70.0
            forecast_points.append(DailyForecastPoint(
                date=f_date.strftime("%Y-%m-%d"),
                day_name=FRENCH_DAYS[dow_idx],
                predicted_count=pred_count,
                lower_bound=lower,
                upper_bound=upper,
                confidence_pct=conf
            ))

        total_predicted = sum(p.predicted_count for p in forecast_points)
        pred_daily_avg = total_predicted / forecast_days if forecast_days > 0 else 0.0
        growth_pct = round(((pred_daily_avg - history_avg) / history_avg) * 100.0, 1) if history_avg > 0 else 0.0

        # Peak days
        sorted_by_vol = sorted(forecast_points, key=lambda p: p.predicted_count, reverse=True)
        peak_days = [p.date for p in sorted_by_vol[:2] if p.predicted_count > 0]

        # Spike Risk
        if growth_pct >= 20.0 or (history_avg > 0 and pred_daily_avg > history_avg * 1.3):
            spike_risk = "ÉLEVÉ"
        elif growth_pct >= 5.0:
            spike_risk = "MODÉRÉ"
        else:
            spike_risk = "FAIBLE"

        conf_level = "HIGH" if active_days_count >= 14 else "MEDIUM" if active_days_count >= 5 else "LOW"

        return VolumeForecastOut(
            forecast_days=forecast_days,
            daily_forecasts=forecast_points,
            total_predicted_volume=total_predicted,
            historical_daily_avg=round(history_avg, 1),
            growth_trend_pct=growth_pct,
            spike_risk=spike_risk,
            confidence_level=conf_level,
            is_baseline=False,
            peak_days=peak_days,
            data_points_analyzed=total_tickets
        )

    # ──────────────────────────────────────────────────────────
    # 2. Resolution Time Prediction
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def _format_hours(hours: float) -> str:
        """Formats hours into human-readable string like '2h 30m' or '45m'."""
        if hours < 1.0:
            minutes = max(1, int(round(hours * 60)))
            return f"{minutes} min"
        h = int(hours)
        m = int(round((hours - h) * 60))
        if m == 0:
            return f"{h}h"
        return f"{h}h {m:02d}m"

    async def predict_resolution_time(
        self,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        priority: Optional[Union[TicketPriority, str]] = None,
        impact: Optional[Union[ImpactLevel, str]] = None,
        urgency: Optional[Union[UrgencyLevel, str]] = None,
        team_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        ticket_id: Optional[str] = None,
        tickets: Optional[List[Dict[str, Any]]] = None
    ) -> ResolutionTimePredictionOut:
        """
        Predict expected resolution duration in hours using historical segment data,
        ITIL priority targets, urgency, impact, and workload factors.
        """
        # If ticket_id provided, inspect existing ticket for defaults
        if ticket_id:
            ticket_doc = None
            if tickets is not None:
                ticket_doc = next((t for t in tickets if str(t.get("_id") or t.get("id")) == ticket_id), None)
            else:
                try:
                    ticket_doc = await self.tickets.find_one({"_id": MongoModel.to_object_id(ticket_id)})
                except Exception as e:
                    logger.warning(f"Error fetching ticket {ticket_id}: {e}")
            if ticket_doc:
                category = category or ticket_doc.get("category")
                subcategory = subcategory or ticket_doc.get("subcategory")
                priority = priority or ticket_doc.get("priority")
                impact = impact or ticket_doc.get("impact")
                urgency = urgency or ticket_doc.get("urgency")
                agent_id = agent_id or str(ticket_doc.get("assigned_agent_id", ""))

        # Normalize priority
        prio_str = "MEDIUM"
        if priority:
            prio_str = priority.value if hasattr(priority, "value") else str(priority).upper()
        if prio_str not in ["URGENT", "HIGH", "MEDIUM", "LOW"]:
            prio_str = "MEDIUM"

        # SLA Target Policy
        sla_policy = (
            DEFAULT_SLA_POLICIES.get(prio_str) or
            DEFAULT_SLA_POLICIES.get(getattr(prio_enum, "value", str(prio_enum))) or
            DEFAULT_SLA_POLICIES.get(prio_enum) or
            DEFAULT_SLA_POLICIES.get("MEDIUM", {"resolution_time_hours": 8.0})
        )
        sla_target = float(sla_policy.get("resolution_time_hours", 8.0))

        # Fetch resolved historical tickets
        if tickets is None:
            resolved_tickets = await self._safe_to_list(
                self.tickets.find({
                    "status": {"$in": ["RESOLVED", "CLOSED", TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value]}
                }),
                1000
            )
        else:
            resolved_tickets = [
                t for t in tickets
                if t.get("status") in ["RESOLVED", "CLOSED", TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value]
            ]

        # Extract durations
        cat_prio_durations: List[float] = []
        cat_durations: List[float] = []
        prio_durations: List[float] = []
        global_durations: List[float] = []

        norm_cat = (category or "").strip().lower()

        for t in resolved_tickets:
            c_at = t.get("created_at")
            u_at = t.get("updated_at")
            if c_at and u_at and u_at > c_at:
                dur = (u_at - c_at).total_seconds() / 3600.0
                if dur > 0.05 and dur < 500.0:  # Sanity filter
                    global_durations.append(dur)
                    t_cat = (t.get("category") or "").strip().lower()
                    t_prio = (t.get("priority") or "MEDIUM").upper()

                    if t_prio == prio_str:
                        prio_durations.append(dur)
                    if norm_cat and t_cat == norm_cat:
                        cat_durations.append(dur)
                        if t_prio == prio_str:
                            cat_prio_durations.append(dur)

        # Baseline hierarchy selection
        contributing_factors: List[ResolutionTimeFactor] = []
        baseline_used = "global"
        sample_size = 0
        base_hours = sla_target * 0.75  # Default reasonable baseline

        if len(cat_prio_durations) >= 2:
            base_hours = sum(cat_prio_durations) / len(cat_prio_durations)
            baseline_used = "category_priority"
            sample_size = len(cat_prio_durations)
            contributing_factors.append(ResolutionTimeFactor(
                factor="Segment Historique (Catégorie + Priorité)",
                impact_hours=round(base_hours, 1),
                description=f"Moyenne constatée sur {sample_size} tickets similaires résolus"
            ))
        elif len(cat_durations) >= 2:
            cat_mean = sum(cat_durations) / len(cat_durations)
            # Adjust by priority ratio
            prio_multiplier = {"URGENT": 0.5, "HIGH": 0.75, "MEDIUM": 1.0, "LOW": 1.6}.get(prio_str, 1.0)
            base_hours = cat_mean * prio_multiplier
            baseline_used = "category"
            sample_size = len(cat_durations)
            contributing_factors.append(ResolutionTimeFactor(
                factor="Catégorie Métier",
                impact_hours=round(base_hours, 1),
                description=f"Moyenne catégorie ({round(cat_mean, 1)}h) ajustée par priorité {prio_str} (x{prio_multiplier})"
            ))
        elif len(prio_durations) >= 2:
            base_hours = sum(prio_durations) / len(prio_durations)
            baseline_used = "priority"
            sample_size = len(prio_durations)
            contributing_factors.append(ResolutionTimeFactor(
                factor="Priorité Globale",
                impact_hours=round(base_hours, 1),
                description=f"Moyenne observée pour les tickets {prio_str} ({sample_size} tickets)"
            ))
        elif len(global_durations) >= 2:
            base_hours = sum(global_durations) / len(global_durations)
            baseline_used = "global"
            sample_size = len(global_durations)
            contributing_factors.append(ResolutionTimeFactor(
                factor="MTTR Global Plateforme",
                impact_hours=round(base_hours, 1),
                description=f"Moyenne globale de résolution ({sample_size} tickets résolus)"
            ))
        else:
            base_hours = sla_target * 0.70
            baseline_used = "sla_policy_default"
            sample_size = 0
            contributing_factors.append(ResolutionTimeFactor(
                factor="Référentiel SLA Standard",
                impact_hours=round(base_hours, 1),
                description=f"Estimation théorique ITIL (70% du temps cible SLA {sla_target}h)"
            ))

        # Adjustments: Impact & Urgency
        final_hours = base_hours
        imp_str = str(impact.value if hasattr(impact, "value") else impact or "").upper()
        urg_str = str(urgency.value if hasattr(urgency, "value") else urgency or "").upper()

        if imp_str == "HIGH":
            adj = round(base_hours * 0.20, 1)
            final_hours += adj
            contributing_factors.append(ResolutionTimeFactor(
                factor="Impact Élevé",
                impact_hours=+adj,
                description="Complexité accrue et périmètre d'utilisateurs étendu (+20%)"
            ))
        elif imp_str == "LOW":
            adj = round(base_hours * 0.10, 1)
            final_hours = max(0.2, final_hours - adj)
            contributing_factors.append(ResolutionTimeFactor(
                factor="Impact Faible",
                impact_hours=-adj,
                description="Incident circonscrit à un utilisateur isolé (-10%)"
            ))

        if urg_str == "HIGH" and prio_str != "URGENT":
            adj = round(base_hours * 0.15, 1)
            final_hours = max(0.2, final_hours - adj)
            contributing_factors.append(ResolutionTimeFactor(
                factor="Urgence Opérationnelle Forte",
                impact_hours=-adj,
                description="Mobilisation accélérée de l'équipe de support (-15%)"
            ))

        final_hours = max(0.1, round(final_hours, 1))

        # Confidence calculation
        if sample_size >= 10:
            confidence = 90.0
            conf_level = "HIGH"
        elif sample_size >= 4:
            confidence = 75.0
            conf_level = "MEDIUM"
        elif sample_size >= 1:
            confidence = 55.0
            conf_level = "LOW"
        else:
            confidence = 40.0
            conf_level = "LOW"

        is_compliant = final_hours <= sla_target

        explanation = (
            f"Temps moyen estimé à {self._format_hours(final_hours)} (base {baseline_used}, {sample_size} échantillons). "
            f"Objectif SLA pour {prio_str} : {sla_target}h ({'Conforme' if is_compliant else 'Risque de dépassement'})."
        )

        return ResolutionTimePredictionOut(
            predicted_hours=final_hours,
            predicted_duration_formatted=self._format_hours(final_hours),
            confidence_score=confidence,
            confidence_level=conf_level,
            sla_target_hours=sla_target,
            estimated_sla_compliance=is_compliant,
            historical_sample_size=sample_size,
            baseline_used=baseline_used,
            contributing_factors=contributing_factors,
            explanation=explanation
        )

    # ──────────────────────────────────────────────────────────
    # 3. SLA Breach Prediction
    # ──────────────────────────────────────────────────────────

    async def predict_sla_breach_risks(
        self,
        active_tickets: Optional[List[Dict[str, Any]]] = None,
        all_tickets: Optional[List[Dict[str, Any]]] = None
    ) -> SLABreachRisksOut:
        """
        Evaluate all active tickets and predict which ones are likely to breach their SLA
        before the deadline, computing probability, risk level, and preventative steps.
        """
        now = datetime.utcnow()

        if active_tickets is None:
            raw_active = await self._safe_to_list(
                self.tickets.find({
                    "status": {"$in": ["OPEN", "IN_PROGRESS", "REOPENED", TicketStatus.OPEN.value, TicketStatus.IN_PROGRESS.value]}
                }),
                500
            )
        else:
            raw_active = [
                t for t in active_tickets
                if t.get("status") in ["OPEN", "IN_PROGRESS", "REOPENED", TicketStatus.OPEN.value, TicketStatus.IN_PROGRESS.value]
            ]

        # Preload agent cache
        agent_names: Dict[str, str] = {}
        try:
            agents_list = await self._safe_to_list(self.agents.find(), 100)
            for ag in agents_list:
                ag_id = str(ag["_id"])
                agent_names[ag_id] = ag.get("name") or ag.get("email") or f"Agent #{ag_id[-4:]}"
        except Exception:
            pass

        evaluated_tickets: List[SLABreachRiskTicket] = []

        for t in raw_active:
            t_id = str(t.get("_id") or t.get("id", ""))
            ref = t.get("reference") or f"[TICK-{t_id[-6:].upper()}]"
            subject = t.get("subject", "Sans titre")
            prio = t.get("priority", "MEDIUM")
            status = t.get("status", "OPEN")
            cat = t.get("category", "Général")
            subcat = t.get("subcategory")
            ag_id = str(t.get("assigned_agent_id", "")) if t.get("assigned_agent_id") else None
            ag_name = agent_names.get(ag_id) if ag_id else "Non assigné"

            c_at = t.get("created_at") or now
            if isinstance(c_at, str):
                try:
                    c_at = datetime.fromisoformat(c_at.replace("Z", ""))
                except Exception:
                    c_at = now

            # Normalize priority enum
            prio_str = prio.value if hasattr(prio, "value") else str(prio).upper()
            try:
                prio_enum = TicketPriority(prio_str)
            except Exception:
                prio_enum = TicketPriority.MEDIUM

            # SLA deadline resolution
            deadline = t.get("sla_deadline")
            if not deadline:
                policy = (
                    DEFAULT_SLA_POLICIES.get(prio_str) or
                    DEFAULT_SLA_POLICIES.get(getattr(prio_enum, "value", str(prio_enum))) or
                    DEFAULT_SLA_POLICIES.get(prio_enum) or
                    DEFAULT_SLA_POLICIES.get("MEDIUM", {"resolution_time_hours": 8.0})
                )
                target_h = float(policy.get("resolution_time_hours", 8.0))
                deadline = c_at + timedelta(hours=target_h)
            elif isinstance(deadline, str):
                try:
                    deadline = datetime.fromisoformat(deadline.replace("Z", ""))
                except Exception:
                    deadline = c_at + timedelta(hours=8.0)

            # Elapsed and remaining hours
            elapsed_hours = max(0.0, (now - c_at).total_seconds() / 3600.0)
            remaining_seconds = (deadline - now).total_seconds()
            remaining_hours = round(remaining_seconds / 3600.0, 2)
            total_sla_hours = max(0.1, (deadline - c_at).total_seconds() / 3600.0)

            # Predict resolution duration for this ticket
            pred_res = await self.predict_resolution_time(
                category=cat,
                subcategory=subcat,
                priority=prio_enum,
                tickets=all_tickets
            )
            pred_total = pred_res.predicted_hours
            pred_remaining = max(0.2, round(pred_total - (elapsed_hours * 0.4), 1))

            risk_factors: List[str] = []
            recommended_action = "Surveiller l'avancement régulier."

            # Probability & Risk evaluation
            if now >= deadline:
                breach_prob = 100.0
                risk_level = "CRITIQUE"
                risk_factors.append("Délai SLA d'engagement déjà dépassé")
                recommended_action = "Escalade d'urgence au superviseur et traitement prioritaire immédiat"
            elif pred_remaining > remaining_hours:
                gap = pred_remaining - remaining_hours
                breach_prob = min(98.0, round(70.0 + (gap / max(0.5, pred_remaining)) * 28.0, 1))
                risk_level = "CRITIQUE" if breach_prob >= 85.0 else "ÉLEVÉ"
                risk_factors.append(f"Temps estimé restant ({pred_remaining}h) supérieur au SLA restant ({remaining_hours}h)")
                if not ag_id:
                    risk_factors.append("Ticket non assigné en attente de prise en charge")
                    recommended_action = "Assigner immédiatement un agent senior disponible"
                else:
                    recommended_action = "Mobiliser un agent en renfort ou ajuster les priorités en cours"
            elif remaining_hours <= 1.0 or (remaining_hours / total_sla_hours <= 0.20):
                breach_prob = 75.0
                risk_level = "ÉLEVÉ"
                risk_factors.append(f"Moins de 20% du temps SLA restant ({remaining_hours}h)")
                recommended_action = "Finaliser la résolution sans délai pour éviter le dépassement"
            elif pred_remaining > remaining_hours * 0.70:
                breach_prob = 45.0
                risk_level = "MODÉRÉ"
                risk_factors.append("Marge de sécurité temporelle étroite (< 30%)")
                recommended_action = "Vérifier le statut d'investigation lors du prochain point de suivi"
            else:
                breach_prob = 15.0
                risk_level = "FAIBLE"
                risk_factors.append("Délais nominaux et progression conforme aux objectifs")
                recommended_action = "Poursuivre le traitement standard"

            # Check priority risk
            if prio_enum == TicketPriority.URGENT and breach_prob >= 40.0:
                risk_factors.append("Impact critique (Ticket URGENT)")
                if risk_level == "MODÉRÉ":
                    risk_level = "ÉLEVÉ"
                    breach_prob = min(90.0, breach_prob + 15.0)

            evaluated_tickets.append(SLABreachRiskTicket(
                ticket_id=t_id,
                reference=ref,
                subject=subject,
                priority=prio_enum,
                status=TicketStatus(status) if status in [s.value for s in TicketStatus] else TicketStatus.OPEN,
                category=cat,
                subcategory=subcat,
                assigned_agent_id=ag_id,
                assigned_agent_name=ag_name,
                created_at=c_at,
                sla_deadline=deadline,
                remaining_hours=remaining_hours,
                predicted_remaining_hours=pred_remaining,
                breach_probability_pct=breach_prob,
                risk_level=risk_level,
                risk_factors=risk_factors,
                recommended_action=recommended_action
            ))

        # Sort descending by breach probability
        evaluated_tickets.sort(key=lambda t: t.breach_probability_pct, reverse=True)

        at_risk = sum(1 for t in evaluated_tickets if t.risk_level in ["CRITIQUE", "ÉLEVÉ"])
        crit_count = sum(1 for t in evaluated_tickets if t.risk_level == "CRITIQUE")

        summary = (
            f"Analyse prédictive SLA réalisée sur {len(evaluated_tickets)} ticket(s) actif(s) : "
            f"{crit_count} critique(s), {at_risk} à risque élevé."
        )

        return SLABreachRisksOut(
            evaluated_at=now,
            total_active_tickets=len(evaluated_tickets),
            at_risk_count=at_risk,
            critical_count=crit_count,
            tickets=evaluated_tickets,
            summary=summary
        )

    # ──────────────────────────────────────────────────────────
    # 4. Recurring Ticket Detection & Clustering
    # ──────────────────────────────────────────────────────────

    async def detect_recurring_tickets(
        self,
        tickets: Optional[List[Dict[str, Any]]] = None,
        min_similarity: float = 40.0,
        min_cluster_size: int = 2
    ) -> RecurringIssuesResponse:
        """
        Cluster tickets into recurring issue groups using semantic tokens, keywords, and category matching.
        Identifies recurrence count, first/last seen dates, common solutions, and root causes.
        """
        if tickets is None:
            raw_tickets = await self._safe_to_list(self.tickets.find(), 2000)
        else:
            raw_tickets = tickets

        if len(raw_tickets) < min_cluster_size:
            return RecurringIssuesResponse(
                total_clusters=0,
                active_clusters=0,
                total_tickets_in_clusters=0,
                clusters=[],
                detection_method="HYBRID_SEMANTIC_KEYWORDS"
            )

        # Preprocess tickets
        processed: List[Dict[str, Any]] = []
        for t in raw_tickets:
            t_id = str(t.get("_id") or t.get("id", ""))
            c_at = t.get("created_at") or datetime.utcnow()
            if isinstance(c_at, str):
                try:
                    c_at = datetime.fromisoformat(c_at.replace("Z", ""))
                except Exception:
                    c_at = datetime.utcnow()

            processed.append({
                "id": t_id,
                "reference": t.get("reference") or f"[TICK-{t_id[-6:].upper()}]",
                "subject": t.get("subject", ""),
                "description": t.get("description", ""),
                "category": t.get("category", "Général"),
                "subcategory": t.get("subcategory"),
                "priority": str(t.get("priority", "MEDIUM")).upper(),
                "status": str(t.get("status", "OPEN")).upper(),
                "keywords": t.get("keywords") or [],
                "resolution_note": t.get("resolution_note"),
                "created_at": c_at,
                "raw": t
            })

        # Sort chronologically
        processed.sort(key=lambda t: t["created_at"])

        # Partition into buckets by category to keep clustering fast and accurate
        cat_buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for t in processed:
            cat_buckets[t["category"].strip().lower()].append(t)

        detected_clusters: List[Dict[str, Any]] = []

        for cat_name, bucket in cat_buckets.items():
            if len(bucket) < min_cluster_size:
                continue

            # Greedy Leader-Follower Clustering within category
            clusters: List[Dict[str, Any]] = []

            for ticket in bucket:
                matched_cluster = None
                best_sim = 0.0

                for c in clusters:
                    rep = c["representative"]
                    sim = self._compute_pair_similarity(ticket, rep)
                    if sim >= min_similarity and sim > best_sim:
                        best_sim = sim
                        matched_cluster = c

                if matched_cluster:
                    matched_cluster["members"].append((ticket, best_sim))
                else:
                    clusters.append({
                        "representative": ticket,
                        "members": [(ticket, 100.0)]
                    })

            # Filter valid clusters
            for c in clusters:
                if len(c["members"]) >= min_cluster_size:
                    detected_clusters.append(c)

        # Build RecurringClusterOut list
        cluster_outs: List[RecurringClusterOut] = []
        total_tickets_in_all_clusters = 0

        for idx, cl in enumerate(detected_clusters):
            members = cl["members"]
            member_tickets = [m[0] for m in members]
            total_tickets_in_all_clusters += len(member_tickets)

            rep = cl["representative"]
            cat = rep["category"]
            subcat = rep["subcategory"]

            # Compute dates
            dates = [t["created_at"] for t in member_tickets]
            first_seen = min(dates)
            last_seen = max(dates)

            # Active vs Resolved status
            is_active = any(t["status"] in ["OPEN", "IN_PROGRESS", "REOPENED"] for t in member_tickets)
            status_str = "ACTIVE" if is_active else "RESOLVED"

            # Average similarity
            sim_scores = [m[1] for m in members]
            avg_sim = round(sum(sim_scores) / len(sim_scores), 1)

            # Impact level
            count = len(member_tickets)
            has_urgent = any(t["priority"] in ["URGENT", "HIGH"] for t in member_tickets)
            if count >= 4 or has_urgent:
                impact = "CRITIQUE" if count >= 5 else "ÉLEVÉ"
            else:
                impact = "MOYEN"

            # Aggregated keywords
            all_kw = set()
            for t in member_tickets:
                for kw in t["keywords"]:
                    if kw:
                        all_kw.add(kw.lower())
                sub_tokens = self._tokenize(t["subject"])
                for st in sub_tokens:
                    all_kw.add(st)
            top_keywords = sorted(list(all_kw))[:6]

            # Title formulation
            rep_subject = rep["subject"]
            if len(rep_subject) > 45:
                rep_subject = rep_subject[:42] + "..."
            cluster_title = f"Incident Récurrent : {rep_subject} ({cat})"

            # Extract common solutions from resolved tickets
            solutions = []
            for t in member_tickets:
                r_note = t.get("resolution_note")
                if r_note and len(r_note.strip()) > 10 and r_note.strip() not in solutions:
                    solutions.append(r_note.strip())

            # Ticket recurrence is observed; root cause and action plans require investigation.
            root_cause = "Cause non déterminée à partir des seuls tickets récurrents."
            preventive_plan = []

            # Sample tickets
            samples = [
                RecurringTicketSummary(
                    ticket_id=t["id"],
                    reference=t["reference"],
                    subject=t["subject"],
                    status=t["status"],
                    priority=t["priority"],
                    category=t["category"],
                    created_at=t["created_at"],
                    similarity_to_cluster=sim
                )
                for t, sim in members[:8]
            ]

            cluster_id = f"cluster-{abs(hash(cat + (subcat or '') + (top_keywords[0] if top_keywords else ''))):x}"

            cluster_outs.append(RecurringClusterOut(
                cluster_id=cluster_id,
                title=cluster_title,
                category=cat,
                subcategory=subcat,
                keywords=top_keywords,
                occurrence_count=count,
                status=status_str,
                impact_level=impact,
                estimated_hours_lost=None,
                first_seen=first_seen,
                last_seen=last_seen,
                average_similarity_pct=avg_sim,
                root_cause_analysis=root_cause,
                common_solutions=solutions[:3],
                preventive_action_plan=preventive_plan,
                sample_tickets=samples
            ))

        # Sort clusters by occurrence count descending, then impact
        cluster_outs.sort(key=lambda c: (c.occurrence_count, c.impact_level == "CRITIQUE"), reverse=True)

        active_clusters_count = sum(1 for c in cluster_outs if c.status == "ACTIVE")

        return RecurringIssuesResponse(
            total_clusters=len(cluster_outs),
            active_clusters=active_clusters_count,
            total_tickets_in_clusters=total_tickets_in_all_clusters,
            clusters=cluster_outs,
            detection_method="HYBRID_SEMANTIC_KEYWORDS"
        )
