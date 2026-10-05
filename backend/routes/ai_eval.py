# -*- coding: utf-8 -*-
"""
AI/RAG Evaluation routes for GEISER.

Endpoints:
  POST /api/v1/ai-eval/run          — trigger a full evaluation (ADMIN/SUPERVISOR)
  GET  /api/v1/ai-eval/latest       — return cached latest result (ADMIN/SUPERVISOR)
  GET  /api/v1/ai-eval/classification — return latest classification eval only
  GET  /api/v1/ai-eval/rag          — return latest RAG eval only
  GET  /api/v1/ai-eval/triage       — return latest triage eval only
  GET  /api/v1/ai-eval/status       — quick status (all authenticated users)

Evaluation results are cached in memory to avoid expensive re-runs on every request.
Admin can force a refresh via POST /run.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from core.deps import RoleChecker, get_current_user
from schemas.schemas import UserRole, AIEvaluationOut
from services.ai_evaluation_service import AIEvaluationService

logger = logging.getLogger(__name__)
router = APIRouter()

# ── In-process evaluation cache ────────────────────────────────────────────────
_eval_cache: Optional[Dict[str, Any]] = None
_eval_lock = asyncio.Lock()
_eval_running = False


async def _run_and_cache() -> Dict[str, Any]:
    """Run the full evaluation and store in module-level cache."""
    global _eval_cache, _eval_running
    _eval_running = True
    try:
        svc = AIEvaluationService()
        result = await svc.run_full_evaluation()
        _eval_cache = result
        return result
    except Exception as e:
        logger.error(f"AI evaluation failed: {e}")
        raise
    finally:
        _eval_running = False


# ── Endpoints ───────────────────────────────────────────────────────────────────

@router.post(
    "/run",
    summary="Trigger a full AI/RAG evaluation (ADMIN/SUPERVISOR only)",
    response_model=AIEvaluationOut,
)
async def run_evaluation(
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR]))
):
    """
    Runs the complete AI/RAG evaluation pipeline and caches the result.
    Calling again while an evaluation is already running returns 409.
    """
    global _eval_running
    if _eval_running:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An evaluation is already running. Please wait and retry.",
        )
    async with _eval_lock:
        result = await _run_and_cache()
    return result


@router.get(
    "/latest",
    summary="Return latest cached evaluation result (ADMIN/SUPERVISOR only)",
    response_model=AIEvaluationOut,
)
async def get_latest_evaluation(
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR]))
):
    """
    Returns the most recent cached evaluation result.
    If no evaluation has been run yet, automatically triggers one.
    """
    if _eval_cache is None:
        async with _eval_lock:
            if _eval_cache is None:
                await _run_and_cache()
    return _eval_cache


@router.get(
    "/classification",
    summary="Latest classification evaluation metrics",
)
async def get_classification_eval(
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR]))
):
    if _eval_cache is None:
        async with _eval_lock:
            if _eval_cache is None:
                await _run_and_cache()
    return _eval_cache["classification"]  # type: ignore[index]


@router.get(
    "/rag",
    summary="Latest RAG retrieval evaluation metrics",
)
async def get_rag_eval(
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR]))
):
    if _eval_cache is None:
        async with _eval_lock:
            if _eval_cache is None:
                await _run_and_cache()
    return _eval_cache["rag_retrieval"]  # type: ignore[index]


@router.get(
    "/triage",
    summary="Latest triage similarity evaluation metrics",
)
async def get_triage_eval(
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR]))
):
    if _eval_cache is None:
        async with _eval_lock:
            if _eval_cache is None:
                await _run_and_cache()
    return _eval_cache["triage_similarity"]  # type: ignore[index]


@router.get(
    "/status",
    summary="Quick AI evaluation status (any authenticated user)",
)
async def get_eval_status(current_user=Depends(get_current_user)):
    """
    Returns a lightweight summary without sensitive per-sample details.
    """
    if _eval_cache is None:
        return {
            "evaluated": False,
            "overall_status": None,
            "evaluated_at": None,
            "ollama_available": None,
            "running": _eval_running,
        }

    c = _eval_cache
    return {
        "evaluated": True,
        "overall_status": c.get("overall_status"),
        "evaluated_at": c.get("evaluated_at"),
        "ollama_available": c.get("ollama_available"),
        "model": c.get("model"),
        "running": _eval_running,
        "summary": c.get("summary"),
    }
