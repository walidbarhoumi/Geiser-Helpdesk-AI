# -*- coding: utf-8 -*-
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import numpy as np

from rag.embeddings import EmbeddingService
from rag.faiss_index import FAISSVectorIndex
from rag.config import DEFAULT_TOP_K, DEFAULT_SCORE_THRESHOLD

logger = logging.getLogger(__name__)


class SearchResult(BaseModel):
    id: str
    score: float
    intent: str
    category: str
    priority: str
    sop: Optional[str] = None
    result: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    first_user_query: Optional[str] = None
    last_assistant_solution: Optional[str] = None
    solution_steps: List[str] = Field(default_factory=list)
    content: str


class RAGRetriever:
    """
    Retriever pour le système RAG GEISER.
    Prend en charge la vectorisation de la requête, la recherche dans FAISS,
    et le filtrage selon le seuil de similarité minimal.
    """

    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
        vector_index: Optional[FAISSVectorIndex] = None
    ):
        self.embeddings = embedding_service or EmbeddingService()
        self.vector_index = vector_index or FAISSVectorIndex()

    def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        min_score: float = DEFAULT_SCORE_THRESHOLD,
        filter_category: Optional[str] = None
    ) -> List[SearchResult]:
        """
        Recherche sémantique des documents les plus proches de la requête.
        """
        cleaned_query = query.strip()
        if not cleaned_query:
            return []

        # Vérifier si l'index est chargé
        if not self.vector_index.is_ready():
            if not self.vector_index.load():
                logger.warning("Index FAISS indisponible pour la recherche.")
                return []

        # Encodage de la requête
        query_vector = self.embeddings.encode(cleaned_query, normalize=True)

        # Recherche FAISS (demander un peu plus si un filtre est actif)
        search_k = top_k * 2 if filter_category else top_k
        scores, indices = self.vector_index.search(query_vector, top_k=search_k)

        results: List[SearchResult] = []
        for score, idx in zip(scores, indices):
            if idx < 0 or idx >= len(self.vector_index.metadata):
                continue

            float_score = float(score)
            if float_score < min_score:
                # Score trop faible : ne pas inclure pour éviter les faux positifs
                continue

            meta = self.vector_index.metadata[idx]

            # Filtrage de catégorie si spécifié
            if filter_category and meta.get("category", "").lower() != filter_category.lower():
                continue

            result = SearchResult(
                id=meta.get("id", ""),
                score=round(float_score, 4),
                intent=meta.get("intent", ""),
                category=meta.get("category", ""),
                priority=meta.get("priority", ""),
                sop=meta.get("sop"),
                result=meta.get("result"),
                context=meta.get("context", {}),
                first_user_query=meta.get("first_user_query"),
                last_assistant_solution=meta.get("last_assistant_solution"),
                solution_steps=meta.get("solution_steps", []),
                content=meta.get("text_snippet", "")
            )
            results.append(result)

            if len(results) >= top_k:
                break

        logger.info(
            f"RAG Search pour '{cleaned_query[:40]}...' -> {len(results)} résultats retenus (min_score={min_score})"
        )
        return results
