# -*- coding: utf-8 -*-
import logging
from typing import List, Dict, Any, Optional
from rag.retriever import RAGRetriever, SearchResult
from rag.indexer import RAGIndexer
from core.config import settings

logger = logging.getLogger(__name__)

RAG_SYSTEM_PROMPT = """Tu es GEISER Support IA, l'assistant officiel de support informatique disponible 24/7 pour l'entreprise GEISER (certifiée ISO/IEC 27001).

Tu aides les utilisateurs et employés à résoudre efficacement leurs problèmes informatiques.
Tu disposes d'une base de connaissances issue de conversations de support réelles résolues.

RÈGLES IMPÉRATIVES :
1. Réponds en français par défaut avec professionnalisme, clarté et bienveillance.
2. Utilise en priorité les solutions et procédures SOP pertinentes issues du CONTEXTE RAG fourni ci-dessous.
3. Ne prétends JAMAIS avoir effectué une action réelle dans le système (ex: 'j'ai envoyé un SMS', 'j'ai commandé un toner', 'j'ai débloqué votre compte') car tu es un assistant conversationnel en lecture seule. Indique plutôt ce que l'utilisateur doit faire ou ce qu'un technicien peut faire.
4. Ne demande JAMAIS de mot de passe, ni de code MFA complet ou de token secret.
5. Si le contexte fourni est insuffisant pour résoudre le problème avec certitude, pose une question de clarification ciblée ou invite à créer un ticket.
6. Ne fabrique JAMAIS de fausse procédure, faux numéro de ticket ou faux SOP.
7. Ne divulgue aucune donnée personnelle (noms de famille, numéros de téléphone réels) éventuellement présente dans les exemples.
8. Structure toujours ta réponse selon le format suivant :
   - 🔍 **Diagnostic probable** : 1 phrase expliquant la cause la plus plausible.
   - 🛠️ **Étapes à suivre** : étapes claires et numérotées (1, 2, 3) pour résoudre le problème ou le vérifier.
   - 🎫 **Escalade / Précision** : question de confirmation ou proposition de créer un ticket officiel si le blocage persiste.
"""


class RAGService:
    """
    Service d'orchestration RAG pour GEISER Support IA.
    Fait le lien entre la recherche vectorielle FAISS et la génération par le LLM.
    """
    _instance = None

    def __init__(self):
        self.retriever = RAGRetriever()

    def search_knowledge(
        self,
        query: str,
        top_k: int = settings.RAG_TOP_K,
        min_score: float = settings.RAG_SCORE_THRESHOLD
    ) -> List[SearchResult]:
        """
        Recherche dans l'index FAISS les conversations de support les plus similaires.
        """
        try:
            return self.retriever.search(query=query, top_k=top_k, min_score=min_score)
        except Exception as e:
            logger.error(f"Erreur lors de la recherche RAG : {e}")
            return []

    @staticmethod
    def build_rag_context(results: List[SearchResult]) -> str:
        """
        Formate les documents retrouvés sous forme de contexte textuel structuré pour le LLM.
        """
        if not results:
            return "Aucun document similaire pertinent trouvé dans la base de connaissances locale."

        blocks = []
        for i, res in enumerate(results, 1):
            ctx_os = res.context.get("os", "N/A")
            ctx_app = res.context.get("app", "N/A")
            sop_info = f" | Procédure: {res.sop}" if res.sop else ""

            block = (
                f"--- EXEMPLE RÉSOLU #{i} (Pertinence: {int(res.score * 100)}%) ---\n"
                f"Intention: {res.intent}{sop_info} | App: {ctx_app} | OS: {ctx_os}\n"
                f"Symptôme initial: {res.first_user_query or 'N/A'}\n"
                f"Solution validée: {res.last_assistant_solution or 'N/A'}\n"
                f"Détails de l'échange :\n{res.content}"
            )
            blocks.append(block)

        return "\n\n".join(blocks)

    def prepare_augmented_prompt(
        self,
        user_query: str,
        conversation_history: str,
        results: List[SearchResult]
    ) -> tuple:
        """
        Construit le prompt complet prêt à être transmis au LLM local.
        """
        rag_context = self.build_rag_context(results)

        user_prompt = f"""CONTEXTE RAG (Conversations et solutions validées issues de la base locale) :
{rag_context}

HISTORIQUE RÉCENT DE LA CONVERSATION :
{conversation_history}

QUESTION ACTUELLE DE L'UTILISATEUR :
{user_query}

Réponds à l'utilisateur en appliquant scrupuleusement les consignes système et en t'appuyant sur les solutions éprouvées du CONTEXTE RAG :"""

        return RAG_SYSTEM_PROMPT, user_prompt

    def reindex(self) -> Dict[str, Any]:
        """
        Reconstruit l'index FAISS complet à partir du fichier source.
        """
        indexer = RAGIndexer()
        return indexer.rebuild_index()
