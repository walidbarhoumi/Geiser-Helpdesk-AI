from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional, Dict, Any
from datetime import datetime
import re
import logging
from services.ai.ollama_service import OllamaService
from services.ai.ai_classifier import AIClassifier
from services.ticket_service import TicketService
from services.routing_service import RoutingService
from schemas.schemas import (
    ChatMessage, ChatResponse, TicketCreate, TicketPriority,
    TicketChannel, TicketStatus
)
from models.base import MongoModel

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Tu es GEISER Bot, l'assistant virtuel intelligent de support informatique pour l'entreprise GEISER (certifiée ISO/IEC 27001).
Ton objectif est de guider 24/7 les employés et clients dans la résolution rapide de leurs incidents techniques (réseau, authentification, matériel, logiciels, accès VPN, ERP, sécurité).

Consignes impératives :
1. Réponds de façon polie, claire, professionnelle et concise en français.
2. Structure tes conseils avec des puces (étapes numérotées 1, 2, 3 simples).
3. Si le problème nécessite une intervention physique ou des droits administrateur (ex: panne matérielle, réattribution de droits, bug système interne), recommande clairement à l'utilisateur de cliquer sur 'Créer un ticket'.
4. N'invente pas d'informations confidentielles.
"""

CASUAL_PATTERNS = [
    r"^(salut|bonjour|hello|hi|hey|coucou|bonsoir)\b",
    r"^(comment vas[- ]tu|ça va|ca va|how are you|what'?s up)\b",
    r"(météo|meteo|weather|temps qu'il fait)",
    r"(blague|joke|histoire|chanson|poème)",
    r"^(qui es[- ]tu|t'es qui|c'est quoi ton nom)\b",
    r"^(test|ok|merci|thanks|bye|au revoir|super)\b"
]

class ChatbotService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.ollama = OllamaService()
        self.classifier = AIClassifier(self.ollama)
        self.knowledge_base = db.knowledge_base
        self.chat_history = db.chat_sessions

    async def process_chat_message(self, messages: List[ChatMessage], user_id: str) -> ChatResponse:
        """
        Processes a chat conversation:
        1. Checks Knowledge Base for exact/keyword matches.
        2. Queries Ollama local LLM with conversation context.
        3. Returns structured response with suggestions and escalation capability.
        """
        if not messages:
            return ChatResponse(
                reply="Bonjour ! Je suis l'assistant IA de GEISER. Comment puis-je vous aider aujourd'hui ?",
                suggested_actions=["🔑 Mot de passe oublié", "🌐 Problème de connexion VPN", "💻 PC Lent", "🎫 Statut de mes tickets"],
                can_escalate=False,
                source="fallback"
            )

        latest_user_message = next((m.content for m in reversed(messages) if m.role == "user"), "")
        clean_text = latest_user_message.strip().lower()

        # ── 1. Knowledge Base Check ──────────────────────────────
        kb_items = await self.knowledge_base.find().to_list(100)
        for item in kb_items:
            keywords = [k.lower() for k in item.get("keywords", [])]
            if any(k in clean_text for k in keywords if len(k) > 2):
                suggestions = item.get("suggestions", [
                    "Est-ce que cette solution a résolu votre problème ?",
                    "Créer un ticket avec ce diagnostic"
                ])
                return ChatResponse(
                    reply=item.get("auto_response", "Voici la procédure recommandée pour votre demande."),
                    suggested_actions=suggestions,
                    can_escalate=True,
                    intent=item.get("category", "KNOWLEDGE_BASE"),
                    confidence_score=0.95,
                    source="knowledge_base"
                )

        # ── 2. Local LLM Generation via Ollama ────────────────────
        conversation_context = ""
        for msg in messages[-5:]:
            role_label = "Utilisateur" if msg.role == "user" else "Assistant"
            conversation_context += f"{role_label}: {msg.content}\n"

        prompt = f"""Historique de la conversation :
{conversation_context}

Génère la réponse de l'Assistant GEISER Bot pour aider l'utilisateur :"""

        llm_reply = await self.ollama.generate_response(prompt, SYSTEM_PROMPT)

        if llm_reply and len(llm_reply.strip()) > 10:
            classification = await self.classifier.classify_intent("Chat Inquiry", latest_user_message)
            intent = classification.get("intent", "GENERAL")
            
            suggested_actions = [
                "Créer un ticket de support",
                "J'ai besoin d'une assistance humaine",
                "Mon problème est résolu, merci"
            ]

            return ChatResponse(
                reply=llm_reply,
                suggested_actions=suggested_actions,
                can_escalate=True,
                intent=intent,
                confidence_score=0.88,
                source="llm"
            )

        # ── 3. Fallback when LLM is unavailable ──────────────────
        return ChatResponse(
            reply=(
                "J'ai bien pris note de votre message. Notre moteur de support IA analyse votre demande. "
                "Si votre problème persiste ou nécessite l'intervention d'un technicien GEISER, "
                "vous pouvez directement escalader cet échange en ticket de support."
            ),
            suggested_actions=[
                "Créer un ticket de support",
                "Réinitialiser le mot de passe",
                "Contacter un technicien"
            ],
            can_escalate=True,
            intent="GENERAL",
            confidence_score=0.6,
            source="fallback"
        )

    async def validate_and_synthesize_ticket(self, messages: List[ChatMessage]) -> Dict[str, Any]:
        """
        Analyzes the conversation with AI to:
        1. VALIDATE: Verify this is a REAL, ACTIONABLE IT support issue (not small talk/weather/trivia).
        2. CLASSIFY: Determine Category and Subcategory.
        3. PRIORITIZE: Prioritize strictly according to Impact & Urgency (LOW, MEDIUM, HIGH, URGENT).
        4. TAG: Propose 3-6 technical keywords to ease triaging and routing.
        5. SUMMARIZE: Generate subject and incident summary.
        """
        user_texts = [m.content for m in messages if m.role == "user"]
        combined = "\n".join(user_texts).strip()

        if not combined or len(combined) < 5:
            return {
                "is_valid_ticket": False,
                "rejection_reason": "Veuillez décrire un problème technique ou une demande de support précise avant de créer un ticket."
            }

        # Check for casual chat / greetings
        combined_lower = combined.lower()
        if len(combined) < 25 and any(re.search(p, combined_lower) for p in CASUAL_PATTERNS):
            return {
                "is_valid_ticket": False,
                "rejection_reason": "Impossible de créer un ticket pour une conversation informelle. Veuillez décrire un problème informatique réel (ex: panne d'accès, mot de passe oublié, bug logiciel, problème matériel...)."
            }

        system_prompt = """Tu es un Expert ITSM en triage de tickets d'assistance informatique.
Analyse la conversation utilisateur et réponds au format JSON strict :

RÈGLE DE VALIDATION :
- Si la conversation ne contient AUCUN problème informatique réel (ex: salutations simples, météo, blagues, bavardage, test vide) :
  {"is_valid_ticket": false, "rejection_reason": "Explication en français invitant l'utilisateur à décrire un vrai problème technique."}

- Si la conversation contient un VRAI problème technique ou une demande de support IT :
  {
    "is_valid_ticket": true,
    "subject": "Titre clair et concis du problème (max 60 caractères, en français)",
    "category": "Une parmi: Infrastructure & Réseau, Matériel & Poste de Travail, Logiciels & Applications, Authentification & Accès, Sécurité IT, Support Général",
    "subcategory": "Sous-catégorie précise (ex: VPN & Accès Distant, Écran & Affichage, Imprimante & Scanner, Suite Office / Messagerie, Réinitialisation Mot de passe, Email Suspect / Phishing, etc.)",
    "priority": "Évaluée selon impact & urgence: URGENT (bloquant total/sécurité critique), HIGH (impact fort sur le travail), MEDIUM (incident standard), LOW (demande d'info/mineur)",
    "keywords": ["mot-cle-1", "mot-cle-2", "mot-cle-3", "mot-cle-4"],
    "summary": "Résumé de l'incident en 1 ou 2 phrases claires."
  }
"""
        prompt = f"Contenu de la demande utilisateur :\n{combined}"

        try:
            data = await self.ollama.generate_json(prompt, system_prompt)
            if isinstance(data, dict):
                if data.get("is_valid_ticket") is False:
                    return {
                        "is_valid_ticket": False,
                        "rejection_reason": data.get("rejection_reason", "Veuillez décrire un problème technique réel pour ouvrir un ticket de support.")
                    }

                if data.get("subject") and data.get("category"):
                    prio_str = str(data.get("priority", "MEDIUM")).upper()
                    if prio_str not in ["LOW", "MEDIUM", "HIGH", "URGENT"]:
                        prio_str = "MEDIUM"

                    keywords = data.get("keywords") or []
                    if not isinstance(keywords, list):
                        keywords = [str(keywords)]

                    return {
                        "is_valid_ticket": True,
                        "subject": str(data.get("subject")).strip(),
                        "category": str(data.get("category")).strip(),
                        "subcategory": str(data.get("subcategory") or "Général").strip(),
                        "priority": TicketPriority(prio_str),
                        "keywords": [str(k).lower().strip() for k in keywords if k],
                        "summary": str(data.get("summary", "")).strip()
                    }
        except Exception as e:
            logger.warning(f"Error in LLM ticket validation/synthesis: {e}")

        # Deterministic Heuristic Fallback
        return self._heuristic_validation_and_metadata(messages, combined)

    def _heuristic_validation_and_metadata(self, messages: List[ChatMessage], combined: str) -> Dict[str, Any]:
        combined_lower = combined.lower()

        # Reject pure small talk
        if any(re.search(p, combined_lower) for p in CASUAL_PATTERNS) and len(combined) < 30:
            return {
                "is_valid_ticket": False,
                "rejection_reason": "Votre message semble être une salutation ou un échange informel. Veuillez décrire un problème informatique précis (matériel, réseau, compte, logiciel...) pour créer un ticket."
            }

        first_user_msg = next((m.content for m in messages if m.role == "user"), "Demande de support")
        clean_subj = first_user_msg.replace("\n", " ").strip()
        if len(clean_subj) > 60:
            clean_subj = clean_subj[:57] + "..."
        if not clean_subj:
            clean_subj = "Demande d'assistance technique"

        # Prioritize based on impact & urgency
        if any(w in combined_lower for w in ["urgent", "bloquant", "critique", "panne totale", "impossible de travailler", "attaque", "piratage"]):
            priority = TicketPriority.URGENT
        elif any(w in combined_lower for w in ["important", "bloqué", "bloque", "erreur", "ne fonctionne pas", "rapide", "échec"]):
            priority = TicketPriority.HIGH
        elif any(w in combined_lower for w in ["information", "question", "comment", "quand", "conseil"]):
            priority = TicketPriority.LOW
        else:
            priority = TicketPriority.MEDIUM

        # Categorize & Extract keywords
        keywords = []
        if any(w in combined_lower for w in ["vpn", "wifi", "réseau", "connexion", "ip", "dns", "internet", "routeur"]):
            category = "Infrastructure & Réseau"
            subcategory = "VPN & Accès Distant" if "vpn" in combined_lower else "Connexion Wi-Fi / Filaire"
            keywords = ["réseau", "connexion", "infrastructure", "vpn" if "vpn" in combined_lower else "wifi"]
        elif any(w in combined_lower for w in ["mot de passe", "password", "compte", "login", "2fa", "accès", "authentification"]):
            category = "Authentification & Accès"
            subcategory = "Réinitialisation Mot de passe" if "mot de passe" in combined_lower or "password" in combined_lower else "Double Facteur (2FA)"
            keywords = ["authentification", "compte", "accès", "mot-de-passe"]
        elif any(w in combined_lower for w in ["pc", "ordinateur", "écran", "souris", "clavier", "imprimante", "scanner", "matériel"]):
            category = "Matériel & Poste de Travail"
            subcategory = "Imprimante & Scanner" if "imprimante" in combined_lower else "PC Portable / Fixe"
            keywords = ["matériel", "poste-de-travail", "équipement", "imprimante" if "imprimante" in combined_lower else "pc"]
        elif any(w in combined_lower for w in ["virus", "phishing", "piratage", "suspect", "sécurité", "spam", "alerte"]):
            category = "Sécurité IT"
            subcategory = "Email Suspect / Phishing" if "mail" in combined_lower or "phishing" in combined_lower else "Alerte Antivirus"
            keywords = ["sécurité", "iso-27001", "incident", "menace"]
        elif any(w in combined_lower for w in ["outlook", "office", "excel", "logiciel", "application", "erp", "sap", "bug", "installation"]):
            category = "Logiciels & Applications"
            subcategory = "Suite Office / Messagerie" if "outlook" in combined_lower or "mail" in combined_lower else "ERP & Outils Métier"
            keywords = ["logiciel", "application", "bug", "système"]
        else:
            category = "Support Général"
            subcategory = "Assistance Utilisateur"
            keywords = ["support", "assistance", "incident"]

        return {
            "is_valid_ticket": True,
            "subject": clean_subj,
            "category": category,
            "subcategory": subcategory,
            "priority": priority,
            "keywords": keywords,
            "summary": "Demande d'assistance soumise et analysée par l'IA GEISER 24/7."
        }

    async def escalate_to_ticket(
        self,
        messages: List[ChatMessage],
        user_id: str,
        custom_subject: Optional[str] = None,
        attachments: Optional[List[str]] = None
    ) -> dict:
        """
        Converts the chat session into an official Ticket with channel='CHAT'.
        The AI automatically:
        1. Validates that this is a REAL IT problem (not small talk).
        2. Determines Category & Subcategory.
        3. Prioritizes according to Impact & Urgency.
        4. Proposes technical Keywords for triaging.
        5. Formats Description with executive summary and complete transcript.
        """
        # Validate and synthesize via AI
        ai_analysis = await self.validate_and_synthesize_ticket(messages)

        if not ai_analysis.get("is_valid_ticket", False):
            raise ValueError(ai_analysis.get("rejection_reason", "Demande invalide pour la création d'un ticket de support."))

        subject = (custom_subject or ai_analysis["subject"]).strip()
        category = ai_analysis["category"]
        subcategory = ai_analysis["subcategory"]
        priority = ai_analysis["priority"]
        keywords = ai_analysis.get("keywords", [])
        summary = ai_analysis.get("summary", subject)

        # Format transcript
        transcript_lines = []
        for m in messages:
            sender = "Utilisateur" if m.role == "user" else "Assistant IA"
            transcript_lines.append(f"[{sender}]: {m.content}")

        transcript_text = "\n".join(transcript_lines)

        # Build Description
        description = (
            f"## 📌 Résumé de l'incident (Analysé par IA)\n"
            f"{summary}\n\n"
            f"## 🏷️ Mots-clés IA de triage : {', '.join(keywords)}\n\n"
            f"## 💬 Transcrit de la conversation Chatbot 24/7\n"
            f"{transcript_text}\n"
        )

        ticket_in = TicketCreate(
            subject=subject,
            description=description,
            category=category,
            subcategory=subcategory,
            priority=priority,
            channel=TicketChannel.CHAT,
            attachments=attachments or [],
            keywords=keywords
        )

        ticket_service = TicketService(self.db)
        created_ticket = await ticket_service.create_ticket(ticket_in, user_id)

        # Trigger Intelligent AI Routing
        routing_service = RoutingService(self.db)
        try:
            routing_result = await routing_service.auto_route_ticket(created_ticket["id"])
            created_ticket["routing_result"] = routing_result
        except Exception as e:
            logger.warning(f"Chat ticket auto-routing warning: {e}")

        # Re-fetch ticket to have latest assigned agent info, keywords and attachments
        refreshed_ticket = await ticket_service.get_ticket(created_ticket["id"])
        return refreshed_ticket or created_ticket
