from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import re
import logging
from bson import ObjectId

from schemas.schemas import (
    SimilarTicketOut, BestSolutionOut, CannedResponseTemplate,
    IntelligentTriageResult, TicketStatus, TicketPriority
)
from services.ai.ollama_service import OllamaService
from models.base import MongoModel

logger = logging.getLogger(__name__)

# Stopwords for French & English IT triage similarity
STOPWORDS = {
    "le", "la", "les", "un", "une", "des", "du", "de", "d", "l", "en", "et", "a", "au",
    "aux", "est", "ce", "que", "qui", "dans", "pour", "sur", "mon", "ma", "mes", "ton",
    "ta", "tes", "son", "sa", "ses", "notre", "nos", "votre", "vos", "leur", "leurs",
    "je", "tu", "il", "elle", "nous", "vous", "ils", "elles", "avec", "sans", "ne", "pas",
    "the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "with", "is", "it",
    "this", "that", "my", "your", "our", "their", "problem", "probleme", "erreur", "error",
    "issue", "ticket", "bonjour", "salut", "merci", "aide", "urgent", "svp", "please"
}


class IntelligentTriageService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.tickets = db.tickets
        self.knowledge_base = db.knowledge_base
        self.ollama = OllamaService()

    @staticmethod
    def _tokenize(text: str) -> set:
        """Tokenize text into lower-case keywords, removing stopwords and punctuation."""
        if not text:
            return set()
        words = re.findall(r'[a-zA-Z0-9àâäéèêëîïôöùûüç]+', text.lower())
        return {w for w in words if len(w) >= 3 and w not in STOPWORDS}

    def _compute_text_similarity(self, tokens1: set, tokens2: set) -> float:
        """Jaccard similarity on tokens."""
        if not tokens1 or not tokens2:
            return 0.0
        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)
        return len(intersection) / len(union) if union else 0.0

    async def find_similar_tickets(self, current_ticket: dict, limit: int = 5) -> Tuple[List[SimilarTicketOut], bool, int, Optional[str]]:
        """
        Scan MongoDB ticket history to detect similar and repetitive tickets.
        Returns: (similar_tickets, is_repetitive, recurrence_count, repetitive_reason)
        """
        current_id = current_ticket.get("_id")
        current_subject = current_ticket.get("subject", "")
        current_desc = current_ticket.get("description", "")
        current_cat = current_ticket.get("category", "")
        current_subcat = current_ticket.get("subcategory", "")
        current_keywords = set(current_ticket.get("keywords") or [])
        current_tokens = self._tokenize(f"{current_subject} {current_desc}") | current_keywords

        # Fetch candidate tickets from the last 180 days (or all past tickets)
        query = {}
        if current_id:
            query["_id"] = {"$ne": current_id}

        cursor = self.tickets.find(query).sort("created_at", -1).limit(200)
        past_tickets = await cursor.to_list(length=200)

        scored_tickets = []

        for pt in past_tickets:
            pt_id = str(pt["_id"])
            pt_subject = pt.get("subject", "")
            pt_desc = pt.get("description", "")
            pt_cat = pt.get("category", "")
            pt_subcat = pt.get("subcategory", "")
            pt_keywords = set(pt.get("keywords") or [])
            pt_tokens = self._tokenize(f"{pt_subject} {pt_desc}") | pt_keywords

            # 1. Text / Keyword Jaccard score (0 to 50 points)
            jaccard = self._compute_text_similarity(current_tokens, pt_tokens)
            score = jaccard * 50.0

            # 2. Category match bonus (up to 20 points)
            if current_cat and pt_cat and current_cat.lower() == pt_cat.lower():
                score += 20.0
                # Subcategory match bonus (15 points)
                if current_subcat and pt_subcat and current_subcat.lower() == pt_subcat.lower():
                    score += 15.0

            # 3. Keyword exact intersection bonus (up to 15 points)
            common_kw = current_keywords.intersection(pt_keywords)
            if common_kw:
                score += min(15.0, len(common_kw) * 5.0)

            score = min(100.0, round(score, 1))

            # Keep matches with significant similarity (>= 30%)
            if score >= 30.0:
                scored_tickets.append({
                    "ticket_id": pt_id,
                    "subject": pt_subject,
                    "category": pt_cat,
                    "subcategory": pt_subcat,
                    "priority": pt.get("priority", TicketPriority.MEDIUM.value),
                    "status": pt.get("status", TicketStatus.OPEN.value),
                    "similarity_score": score,
                    "resolution_note": pt.get("resolution_note"),
                    "created_at": pt.get("created_at", datetime.utcnow()),
                    "resolved_at": pt.get("updated_at") if pt.get("status") in [TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value] else None
                })

        # Sort descending by similarity score
        scored_tickets.sort(key=lambda x: x["similarity_score"], reverse=True)
        top_similar = scored_tickets[:limit]

        # Evaluate repetitiveness:
        # If at least 2 tickets have similarity >= 50% OR any ticket has similarity >= 75%
        high_sim_tickets = [t for t in scored_tickets if t["similarity_score"] >= 50.0]
        is_repetitive = len(high_sim_tickets) >= 2 or (len(scored_tickets) > 0 and scored_tickets[0]["similarity_score"] >= 75.0)
        recurrence_count = len(high_sim_tickets)

        repetitive_reason = None
        if is_repetitive:
            repetitive_reason = f"Incident récurrent détecté : {recurrence_count} ticket(s) similaire(s) dans l'historique."

        converted_similar = [
            SimilarTicketOut(
                ticket_id=t["ticket_id"],
                subject=t["subject"],
                category=t["category"],
                subcategory=t["subcategory"],
                priority=t["priority"],
                status=t["status"],
                similarity_score=t["similarity_score"],
                resolution_note=t["resolution_note"],
                created_at=t["created_at"],
                resolved_at=t["resolved_at"]
            )
            for t in top_similar
        ]

        return converted_similar, is_repetitive, recurrence_count, repetitive_reason

    async def evaluate_best_solution(self, current_ticket: dict, similar_tickets: List[SimilarTicketOut]) -> BestSolutionOut:
        """
        Evaluate the best resolution for this ticket from:
        1. Past resolved tickets with resolution_note
        2. Knowledge Base matches
        3. LLM / Heuristic synthesis
        """
        subject = current_ticket.get("subject", "")
        description = current_ticket.get("description", "")
        category = current_ticket.get("category", "")
        subcategory = current_ticket.get("subcategory", "")
        keywords = current_ticket.get("keywords") or []

        # 1. Search in past resolved tickets that have a resolution_note
        resolved_with_notes = [
            t for t in similar_tickets 
            if t.resolution_note and t.status in [TicketStatus.RESOLVED, TicketStatus.CLOSED, "RESOLVED", "CLOSED"]
        ]

        if resolved_with_notes and resolved_with_notes[0].similarity_score >= 45.0:
            best_past = resolved_with_notes[0]
            confidence = min(98.0, round(best_past.similarity_score * 1.05, 1))

            
            # Extract actionable steps from resolution note
            steps = [s.strip() for s in re.split(r'[\n\r;•\-\d+\.]', best_past.resolution_note) if len(s.strip()) > 8]
            if not steps:
                steps = [best_past.resolution_note]

            return BestSolutionOut(
                recommended_solution=best_past.resolution_note,
                confidence_score=confidence,
                source_type="HISTORICAL_TICKET",
                source_reference=f"Ticket #{best_past.ticket_id[-6:].upper()} ({best_past.subject})",
                actionable_steps=steps[:5],
                key_findings=[
                    f"Solution éprouvée issue du ticket résolu #{best_past.ticket_id[-6:].upper()}",
                    f"Score de similarité avec l'incident initial : {best_past.similarity_score}%",
                    f"Catégorie : {best_past.category} > {best_past.subcategory or 'Général'}"
                ]
            )

        # 2. Search Knowledge Base
        kb_query = " ".join([subject, category, subcategory or ""] + keywords).lower()
        kb_items = await self.knowledge_base.find().to_list(50)
        
        best_kb = None
        best_kb_score = 0
        for item in kb_items:
            item_kw = [k.lower() for k in item.get("keywords", [])]
            match_count = sum(1 for kw in item_kw if kw in kb_query)
            if match_count > best_kb_score:
                best_kb_score = match_count
                best_kb = item

        if best_kb and best_kb_score >= 2:
            auto_resp = best_kb.get("auto_response", "")
            suggestions = best_kb.get("suggestions", [])
            return BestSolutionOut(
                recommended_solution=auto_resp,
                confidence_score=88.5,
                source_type="KNOWLEDGE_BASE",
                source_reference=f"Base de connaissances : {best_kb.get('title', 'Article Support')}",
                actionable_steps=suggestions if suggestions else ["Suivre la procédure officielle GEISER de l'article KB"],
                key_findings=[
                    f"Article KB correspondant : {best_kb.get('title')}",
                    f"Catégorie : {best_kb.get('category')}",
                    "Solution certifiée par les administrateurs support"
                ]
            )

        # 3. AI / Heuristic Synthesis
        system_prompt = """
        Tu es l'analyste IA expert du Support IT GEISER.
        Analyse le problème soumis et synthétise :
        1. La meilleure solution technique recommandée (claire, professionnelle et concise).
        2. Les étapes d'action concrètes (liste de 2 à 4 étapes).
        Format de réponse JSON strict :
        {
          "solution": "Description de la solution...",
          "steps": ["Étape 1...", "Étape 2...", "Étape 3..."],
          "confidence": 78.0
        }
        """
        prompt = f"Catégorie: {category} > {subcategory}\nSujet: {subject}\nDescription: {description}"
        ai_json = await self.ollama.generate_json(prompt, system_prompt)

        if ai_json and "solution" in ai_json:
            steps = ai_json.get("steps", [])
            confidence = float(ai_json.get("confidence", 75.0))
            return BestSolutionOut(
                recommended_solution=ai_json["solution"],
                confidence_score=confidence,
                source_type="AI_SYNTHESIS",
                source_reference="Modèle IA Gemma 3 (Synthèse Contextuelle)",
                actionable_steps=steps,
                key_findings=[
                    "Synthèse générée à partir des meilleures pratiques ITIL",
                    f"Diagnostic axé sur la catégorie {category}",
                    "Recommandation à valider par le technicien avant application"
                ]
            )

        # Fallback default heuristic
        fallback_sol = f"Effectuer un diagnostic préliminaire sur la catégorie {category}. Vérifier les droits d'accès de l'utilisateur, tester la connectivité réseau et vérifier les journaux système."
        fallback_steps = [
            f"Contrôler l'état des services liés à {category}",
            "Demander confirmation à l'utilisateur des messages d'erreur exacts",
            "Appliquer les correctifs usuels ou escalader si persistant"
        ]
        return BestSolutionOut(
            recommended_solution=fallback_sol,
            confidence_score=70.0,
            source_type="AI_SYNTHESIS",
            source_reference="Moteur de règles heuristiques",
            actionable_steps=fallback_steps,
            key_findings=["Diagnostic préliminaire recommandé"]
        )

    def generate_canned_responses(self, current_ticket: dict, best_solution: BestSolutionOut) -> List[CannedResponseTemplate]:
        """
        Generate 4 contextual standard response templates (Réponses types):
        1. RESOLUTION: Ready-to-send resolution steps.
        2. CLARIFICATION: Asking for specific technical logs/screenshots.
        3. IN_PROGRESS: Acknowledging and providing estimated ETA.
        4. ESCALATION: Transferring to Level 2 specialist team.
        """
        subject = current_ticket.get("subject", "")
        category = current_ticket.get("category", "Support IT")
        ticket_id = str(current_ticket.get("_id", "XXXXXX"))[-6:].upper()

        steps_formatted = "\n".join([f"  {idx+1}. {step}" for idx, step in enumerate(best_solution.actionable_steps)])

        # 1. RESOLUTION TEMPLATE
        res_body = (
            f"Bonjour,\n\n"
            f"Nous avons analysé votre demande concernant « {subject} » (Ticket #{ticket_id}).\n\n"
            f"Voici la procédure recommandée pour résoudre ce dysfonctionnement :\n"
            f"{best_solution.recommended_solution}\n\n"
            f"Étapes à suivre :\n{steps_formatted}\n\n"
            f"Merci de tester cette démarche et de nous confirmer si votre problème est résolu.\n\n"
            f"Cordialement,\n"
            f"L'équipe Support Technique GEISER"
        )

        # 2. CLARIFICATION TEMPLATE
        clarif_body = (
            f"Bonjour,\n\n"
            f"Nous traitons actuellement votre demande concernant « {subject} » (Ticket #{ticket_id}).\n\n"
            f"Afin de poursuivre notre diagnostic sur l'environnement {category}, pourriez-vous nous préciser les éléments suivants :\n"
            f"  1. Le message d'erreur exact ou une capture d'écran du blocage.\n"
            f"  2. L'heure précise de survenance de l'incident.\n"
            f"  3. Le poste ou navigateur utilisé (ainsi que la version).\n\n"
            f"Dès réception de ces informations, nous reprendrons immédiatement le traitement de votre ticket.\n\n"
            f"Cordialement,\n"
            f"L'équipe Support Technique GEISER"
        )

        # 3. IN PROGRESS TEMPLATE
        prog_body = (
            f"Bonjour,\n\n"
            f"Votre ticket #{ticket_id} relatif à « {subject} » a été pris en charge par notre équipe technique.\n\n"
            f"Nos ingénieurs procèdent actuellement aux vérifications et diagnostics nécessaires. "
            f"Nous mettons tout en œuvre pour vous apporter une solution dans le respect de nos engagements de service (SLA).\n\n"
            f"Nous reviendrons vers vous dans les plus brefs délais avec une mise à jour.\n\n"
            f"Cordialement,\n"
            f"L'équipe Support Technique GEISER"
        )

        # 4. ESCALATION TEMPLATE
        escal_body = (
            f"Bonjour,\n\n"
            f"Suite aux premières investigations sur votre ticket #{ticket_id} (« {subject} »), "
            f"cette demande nécessite une intervention approfondie de notre équipe d'ingénierie N2 / Infrastructure.\n\n"
            f"Le dossier leur a été transmis en priorité. Vous serez notifié dès qu'une action ou résolution sera déployée.\n\n"
            f"Nous vous remercions pour votre patience.\n\n"
            f"Cordialement,\n"
            f"Pôle Support Avancé GEISER"
        )

        return [
            CannedResponseTemplate(
                id="canned_resolution",
                category="RESOLUTION",
                title="✅ Procédure de Résolution Validée",
                preview_text=f"Solution étape par étape basée sur {best_solution.source_type}",
                full_body=res_body
            ),
            CannedResponseTemplate(
                id="canned_clarification",
                category="CLARIFICATION",
                title="🔍 Demande de Précisions Techniques",
                preview_text="Demande de captures, messages d'erreur et contexte",
                full_body=clarif_body
            ),
            CannedResponseTemplate(
                id="canned_in_progress",
                category="IN_PROGRESS",
                title="⏳ Prise en Charge & Diagnostic",
                preview_text="Accusé de traitement et confirmation de respect du SLA",
                full_body=prog_body
            ),
            CannedResponseTemplate(
                id="canned_escalation",
                category="ESCALATION",
                title="🚀 Escalade vers Ingénierie N2",
                preview_text="Information de transfert vers l'équipe d'infrastructure",
                full_body=escal_body
            ),
        ]

    async def run_full_triage(self, ticket_id: str) -> IntelligentTriageResult:
        """
        Orchestrates full intelligent triage for a ticket:
        1. Find similar tickets in history & detect recurrence
        2. Evaluate best resolution
        3. Propose standard canned responses
        """
        oid = MongoModel.to_object_id(ticket_id)
        if not oid:
            raise ValueError(f"Invalid ticket ID: {ticket_id}")

        ticket = await self.tickets.find_one({"_id": oid})
        if not ticket:
            raise ValueError(f"Ticket not found: {ticket_id}")

        similar_tickets, is_rep, recurrence_count, rep_reason = await self.find_similar_tickets(ticket, limit=5)
        best_solution = await self.evaluate_best_solution(ticket, similar_tickets)
        canned_responses = self.generate_canned_responses(ticket, best_solution)

        # Classify intent
        intent = "GENERAL"
        try:
            from services.ai.ai_classifier import AIClassifier
            classifier = AIClassifier(self.ollama)
            cl_result = await classifier.classify_intent(ticket.get("subject", ""), ticket.get("description", ""))
            intent = cl_result.get("intent", "GENERAL")
        except Exception as e:
            logger.warning(f"Could not classify intent during triage: {e}")

        return IntelligentTriageResult(
            ticket_id=ticket_id,
            is_repetitive=is_rep,
            recurrence_count=recurrence_count,
            repetitive_reason=rep_reason,
            similarity_threshold_used=60.0,
            similar_tickets=similar_tickets,
            best_solution=best_solution,
            canned_responses=canned_responses,
            intent=intent,
            created_at=datetime.utcnow()
        )
