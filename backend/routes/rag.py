# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException, status, Query
from database.mongodb import get_database
from core.deps import get_current_user
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import logging
import time

from rag.config import DEFAULT_DATABASE_PATH, DEFAULT_INDEX_DIR, DEFAULT_SCORE_THRESHOLD
from rag.data_loader import JSONLLoader, SupportTicketDocument
from rag.retriever import RAGRetriever, SearchResult
from rag.indexer import RAGIndexer
from services.ai.rag_service import RAGService
from services.ai.ollama_service import OllamaService

router = APIRouter()
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Schémas Pydantic pour le RAG
# ──────────────────────────────────────────────

class RAGSearchRequest(BaseModel):
    query: str
    top_k: int = 4
    min_score: float = 0.25
    filter_category: Optional[str] = None


class RAGGenerateTestRequest(BaseModel):
    query: str
    top_k: int = 3
    min_score: float = 0.25


class RAGEvaluationCreate(BaseModel):
    query: str
    retrieved_docs: List[str] = Field(default_factory=list) # IDs G0001, G0002...
    generated_reply: str
    rating: int = Field(ge=1, le=5, description="Note de pertinence globale sur 5 étoiles")
    is_sop_correct: bool = True
    is_helpful: bool = True
    feedback_notes: Optional[str] = None


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────

@router.get("/dataset")
async def get_rag_dataset(
    search: Optional[str] = None,
    category: Optional[str] = None,
    intent: Optional[str] = None,
    priority: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=250),
    current_user=Depends(get_current_user)
):
    """
    Renvoie la liste des conversations du dataset de support avec pagination, filtres et statistiques.
    """
    try:
        loader = JSONLLoader(DEFAULT_DATABASE_PATH)
        all_docs = loader.load()

        # Filtrage
        filtered = all_docs
        if search:
            s = search.lower().strip()
            filtered = [
                d for d in filtered
                if s in d.id.lower()
                or s in d.intent.lower()
                or s in (d.sop or "").lower()
                or any(s in tag.lower() for tag in d.tags)
                or any(s in str(turn).lower() for turn in d.conversation)
            ]

        if category:
            filtered = [d for d in filtered if d.category.lower() == category.lower()]

        if intent:
            filtered = [d for d in filtered if d.intent.lower() == intent.lower()]

        if priority:
            filtered = [d for d in filtered if d.priority.upper() == priority.upper()]

        # Statistiques
        all_categories = sorted(list({d.category for d in all_docs if d.category}))
        all_intents = sorted(list({d.intent for d in all_docs if d.intent}))
        all_sops = sorted(list({d.sop for d in all_docs if d.sop}))
        all_priorities = sorted(list({d.priority for d in all_docs if d.priority}))

        paginated = filtered[skip : skip + limit]

        # Formatage simplifié pour la liste
        items = []
        for d in paginated:
            first_user = ""
            for turn in d.conversation:
                if len(turn) >= 2 and turn[0] == "u" and not first_user:
                    first_user = str(turn[1]).strip()

            from rag.document_processor import DocumentProcessor
            full_sol, steps = DocumentProcessor.extract_solution_details(d.conversation)

            items.append({
                "id": d.id,
                "category": d.category,
                "priority": d.priority,
                "intent": d.intent,
                "context": d.context,
                "sop": d.sop,
                "result": d.result,
                "tags": d.tags,
                "turns_count": len(d.conversation),
                "first_user_query": first_user,
                "last_solution": full_sol,
                "solution_steps": steps
            })

        return {
            "total_items": len(filtered),
            "total_dataset_count": len(all_docs),
            "skip": skip,
            "limit": limit,
            "categories": all_categories,
            "intents": all_intents,
            "sops_count": len(all_sops),
            "priorities": all_priorities,
            "items": items
        }
    except Exception as e:
        logger.error(f"Erreur lors de la lecture du dataset RAG : {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Impossible de charger la base de données RAG : {str(e)}"
        )


@router.get("/dataset/{doc_id}")
async def get_rag_document_details(
    doc_id: str,
    current_user=Depends(get_current_user)
):
    """
    Renvoie les détails complets et la conversation intégrale d'un document du dataset.
    """
    loader = JSONLLoader(DEFAULT_DATABASE_PATH)
    all_docs = loader.load()
    doc = next((d for d in all_docs if d.id.upper() == doc_id.upper()), None)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} introuvable.")

    return {
        "id": doc.id,
        "category": doc.category,
        "priority": doc.priority,
        "intent": doc.intent,
        "context": doc.context,
        "sop": doc.sop,
        "result": doc.result,
        "tags": doc.tags,
        "conversation": doc.conversation
    }


@router.post("/search")
async def search_rag_faiss(
    req: RAGSearchRequest,
    current_user=Depends(get_current_user)
):
    """
    Recherche sémantique en direct dans FAISS avec mesure de temps et scores de similarité.
    """
    start_time = time.time()
    retriever = RAGRetriever()
    try:
        results = retriever.search(
            query=req.query,
            top_k=req.top_k,
            min_score=req.min_score,
            filter_category=req.filter_category
        )
        elapsed_ms = round((time.time() - start_time) * 1000, 2)

        return {
            "query": req.query,
            "elapsed_ms": elapsed_ms,
            "results_count": len(results),
            "min_score_applied": req.min_score,
            "results": [
                {
                    "id": r.id,
                    "score": r.score,
                    "similarity_percent": round(r.score * 100, 1),
                    "intent": r.intent,
                    "category": r.category,
                    "priority": r.priority,
                    "sop": r.sop,
                    "result": r.result,
                    "context": r.context,
                    "first_user_query": r.first_user_query,
                    "last_assistant_solution": r.last_assistant_solution,
                    "solution_steps": r.solution_steps,
                    "content": r.content
                }
                for r in results
            ]
        }
    except Exception as e:
        logger.error(f"Erreur recherche FAISS : {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-generate")
async def test_rag_generation(
    req: RAGGenerateTestRequest,
    current_user=Depends(get_current_user)
):
    """
    Exécute la chaîne RAG complète : Recherche FAISS + Prompt système + Génération LLM locale.
    """
    start_time = time.time()
    rag_service = RAGService()
    ollama = OllamaService()

    # 1. Recherche
    results = rag_service.search_knowledge(req.query, top_k=req.top_k, min_score=req.min_score)

    # 2. Prompt
    sys_prompt, augmented_prompt = rag_service.prepare_augmented_prompt(
        user_query=req.query,
        conversation_history="[Test unitaire en direct]",
        results=results
    )

    # 3. Génération
    llm_reply = await ollama.generate_response(augmented_prompt, sys_prompt)
    elapsed_ms = round((time.time() - start_time) * 1000, 2)

    top_doc = results[0] if results else None
    final_reply = llm_reply or (
        top_doc.last_assistant_solution if top_doc else "Aucune réponse générée par le modèle."
    )

    return {
        "query": req.query,
        "elapsed_ms": elapsed_ms,
        "reply": final_reply,
        "generated_reply": final_reply,
        "source": "rag" if results else "llm_fallback",
        "top_intent": top_doc.intent if top_doc else "UNKNOWN",
        "top_sop": top_doc.sop if top_doc else None,
        "top_score": top_doc.score if top_doc else 0.0,
        "retrieved_count": len(results),
        "docs_used": len(results),
        "retrieved_ids": [r.id for r in results]
    }


@router.post("/evaluate")
async def save_rag_evaluation(
    eval_data: RAGEvaluationCreate,
    current_user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Enregistre une évaluation humaine de la réponse RAG dans MongoDB (ISO 27001 audit & qualité).
    """
    doc = {
        "query": eval_data.query,
        "retrieved_docs": eval_data.retrieved_docs,
        "generated_reply": eval_data.generated_reply,
        "rating": eval_data.rating,
        "is_sop_correct": eval_data.is_sop_correct,
        "is_helpful": eval_data.is_helpful,
        "feedback_notes": eval_data.feedback_notes,
        "evaluator_id": str(current_user.get("id", "")),
        "evaluator_name": f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip() or current_user.get("email"),
        "created_at": datetime.utcnow()
    }

    res = await db.rag_evaluations.insert_one(doc)
    doc["id"] = str(res.inserted_id)
    doc.pop("_id", None)
    return doc


@router.get("/evaluations")
async def get_rag_evaluations(
    limit: int = 50,
    current_user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Retourne la liste des évaluations de réponses avec métriques de satisfaction moyennes.
    """
    cursor = db.rag_evaluations.find().sort("created_at", -1).limit(limit)
    raw_evals = await cursor.to_list(limit)

    evals = []
    total_rating = 0
    correct_sop_count = 0
    helpful_count = 0

    for e in raw_evals:
        rating = e.get("rating", 5)
        total_rating += rating
        if e.get("is_sop_correct", False):
            correct_sop_count += 1
        if e.get("is_helpful", False):
            helpful_count += 1

        evals.append({
            "id": str(e["_id"]),
            "query": e.get("query", ""),
            "retrieved_docs": e.get("retrieved_docs", []),
            "generated_reply": e.get("generated_reply", ""),
            "rating": rating,
            "is_sop_correct": e.get("is_sop_correct", True),
            "is_helpful": e.get("is_helpful", True),
            "feedback_notes": e.get("feedback_notes"),
            "evaluator_name": e.get("evaluator_name", "Anonyme"),
            "created_at": e.get("created_at")
        })

    total = len(evals)
    avg_rating = round(total_rating / total, 2) if total > 0 else 0.0
    sop_accuracy_pct = round((correct_sop_count / total) * 100, 1) if total > 0 else 0.0
    helpfulness_pct = round((helpful_count / total) * 100, 1) if total > 0 else 0.0

    return {
        "total_evaluations": total,
        "average_rating": avg_rating,
        "sop_accuracy_pct": sop_accuracy_pct,
        "helpfulness_pct": helpfulness_pct,
        "evaluations": evals
    }
