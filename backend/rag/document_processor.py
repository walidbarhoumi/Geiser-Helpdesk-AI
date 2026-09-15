# -*- coding: utf-8 -*-
import logging
from typing import List, Dict, Any, Tuple
from rag.data_loader import SupportTicketDocument

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    Transforme les documents structurés de tickets de support en représentations textuelles
    enrichies et standardisées pour l'indexation sémantique FAISS.
    """

    @staticmethod
    def format_conversation_text(doc: SupportTicketDocument) -> str:
        """
        Génère une vue textuelle claire et hiérarchisée de la conversation
        avec ses métadonnées contextuelles (OS, application, intention, SOP, tags).
        """
        ctx = doc.context or {}
        os_info = ctx.get("os", "N/A")
        app_info = ctx.get("app", "N/A")
        impact_info = ctx.get("imp", "N/A")
        tags_str = ", ".join(doc.tags) if doc.tags else "N/A"
        sop_str = doc.sop or "Aucun"
        result_str = doc.result or "N/A"

        dialogue_lines = []
        for turn in doc.conversation:
            if isinstance(turn, (list, tuple)) and len(turn) >= 2:
                speaker_raw, text = turn[0], turn[1]
                speaker = "Utilisateur" if speaker_raw == "u" else "Assistant"
                dialogue_lines.append(f"{speaker} :\n{text}")

        dialogue_block = "\n\n".join(dialogue_lines)

        formatted = (
            f"Conversation ID: {doc.id}\n"
            f"Catégorie: {doc.category} | Priorité: {doc.priority} | Intention: {doc.intent}\n"
            f"Système/Application: {app_info} | OS: {os_info} | Impact: {impact_info}\n"
            f"Tags: {tags_str} | SOP: {sop_str} | Résultat: {result_str}\n\n"
            f"Échange de support :\n\n"
            f"{dialogue_block}"
        )
        return formatted

    @staticmethod
    def extract_solution_details(conversation: list) -> Tuple[str, List[str]]:
        """
        Extrait les étapes concrètes de résolution et la solution complète
        en filtrant les simples politesses de clôture (ex: '✅', 'De rien !', 'Bonne journée 🎉').
        """
        trivial_closings = {
            "✅", "de rien !", "de rien", "bonne journée !", "bonne journée 🎉",
            "bonne journée", "bon courage !", "a votre service", "merci", "ok",
            "merci !", "parfait", "c'est noté"
        }

        steps: List[str] = []
        for turn in conversation:
            if isinstance(turn, (list, tuple)) and len(turn) >= 2:
                speaker, text = turn[0], str(turn[1]).strip()
                if speaker == "a":
                    clean_lower = text.lower().strip(" .!🎉✅\r\n\t")
                    # Filtrer les simples accusés de réception ou clôtures sans instruction
                    if clean_lower not in trivial_closings and len(text) > 4:
                        steps.append(text)
                    elif len(text) > 1 and not steps:
                        steps.append(text)

        if not steps and conversation:
            # Si tout a été filtré, conserver tous les tours de l'assistant
            steps = [str(turn[1]).strip() for turn in conversation if turn[0] == "a"]

        full_solution = "\n".join([f"• {s}" for s in steps]) if len(steps) > 1 else (steps[0] if steps else "Consultez le dialogue complet pour la résolution.")
        return full_solution, steps

    @classmethod
    def process_documents(
        cls,
        documents: List[SupportTicketDocument]
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Traite une liste de documents et produit :
        1. Une liste de textes à vectoriser (1 document complet par conversation pour éviter la perte de contexte).
        2. Une liste de dictionnaires de métadonnées parfaitement alignée (1-to-1) pour le stockage JSON.
        """
        texts: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for doc in documents:
            formatted_text = cls.format_conversation_text(doc)
            doc.searchable_text = formatted_text
            texts.append(formatted_text)

            # Extraction de la première question utilisateur (symptôme initial)
            first_user_query = ""
            for turn in doc.conversation:
                if isinstance(turn, (list, tuple)) and len(turn) >= 2:
                    if turn[0] == "u" and not first_user_query:
                        first_user_query = str(turn[1]).strip()

            # Extraction des étapes concrètes de résolution
            full_solution, solution_steps = cls.extract_solution_details(doc.conversation)

            metadata = {
                "id": doc.id,
                "category": doc.category,
                "priority": doc.priority,
                "intent": doc.intent,
                "context": doc.context,
                "sop": doc.sop,
                "result": doc.result,
                "tags": doc.tags,
                "first_user_query": first_user_query,
                "last_assistant_solution": full_solution,
                "solution_steps": solution_steps,
                "text_snippet": formatted_text[:400]
            }
            metadatas.append(metadata)

        logger.info(f"Traitement de {len(texts)} documents terminé avec succès.")
        return texts, metadatas
