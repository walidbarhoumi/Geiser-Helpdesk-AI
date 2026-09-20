from fastapi import APIRouter, Depends, HTTPException, Body
from ai.ollama_client import OllamaClient
from services.ai.ai_response_service import AIResponseService
from database.mongodb import get_database
from core.deps import RoleChecker, get_current_user
from schemas.schemas import (
    UserRole, KnowledgeBaseItem, IntelligentTriageResult,
    ThreadSummaryOut, SuggestedActionItem, InternalDocItem,
    TicketClassificationRequest, TicketClassificationResponse
)
from services.ai.ai_classifier import AIClassifier
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from typing import List, Optional

router = APIRouter()


@router.post("/classify-ticket", response_model=TicketClassificationResponse)
async def classify_ticket(
    payload: TicketClassificationRequest,
    current_user=Depends(get_current_user)
):
    """
    Real-time AI-assisted ticket classification for ticket creation.
    Analyzes subject and description to automatically suggest category,
    subcategory, priority, keywords/tags, confidence score and technical reasoning.
    """
    classifier = AIClassifier()
    return await classifier.classify_ticket(payload.subject, payload.description)


@router.get("/status")
async def get_ai_status(
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.AGENT]))
):
    client = OllamaClient()
    return await client.check_health()

@router.post("/tickets/{ticket_id}/generate-response")
async def generate_ai_response(
    ticket_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.AGENT]))
):
    """
    Analyzes ticket and generates a suggested AI response.
    """
    ticket = await db.tickets.find_one({"_id": ObjectId(ticket_id)})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    ai_service = AIResponseService(db)
    return await ai_service.generate_full_response(ticket_id, ticket)

@router.get("/tickets/{ticket_id}/intelligent-triage", response_model=IntelligentTriageResult)
async def get_intelligent_triage(
    ticket_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.AGENT]))
):
    """
    Runs full intelligent triage: detects repetitive tickets,
    evaluates best resolution, and proposes standard canned responses.
    """
    from services.ai.intelligent_triage_service import IntelligentTriageService
    service = IntelligentTriageService(db)
    try:
        return await service.run_full_triage(ticket_id)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Triage error: {str(e)}")


@router.get("/knowledge-base")
async def get_knowledge_base(
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(get_current_user)
):
    kb = await db.knowledge_base.find().to_list(100)
    for item in kb: item["_id"] = str(item["_id"])
    return kb

@router.post("/knowledge-base")
async def add_to_knowledge_base(
    item: KnowledgeBaseItem,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(RoleChecker([UserRole.ADMIN]))
):
    ai_service = AIResponseService(db)
    await ai_service.save_kb_item(item.dict())
    return {"message": "Knowledge base item added successfully"}


@router.get("/tickets/{ticket_id}/summarize", response_model=ThreadSummaryOut)
async def summarize_ticket_thread(
    ticket_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.AGENT]))
):
    """
    Summarizes entire conversation thread for agents: initial issue,
    actions taken, blockers, and next steps.
    """
    from services.ai.agent_assistant_service import AgentAssistantService
    service = AgentAssistantService(db)
    try:
        return await service.summarize_ticket_thread(ticket_id)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summary error: {str(e)}")


@router.get("/tickets/{ticket_id}/suggested-actions", response_model=List[SuggestedActionItem])
async def get_suggested_actions(
    ticket_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.AGENT]))
):
    """
    Provides smart recommended next actions for the agent handling the ticket.
    """
    from services.ai.agent_assistant_service import AgentAssistantService
    service = AgentAssistantService(db)
    try:
        return await service.suggest_smart_actions(ticket_id)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Actions error: {str(e)}")


@router.get("/internal-docs/search", response_model=List[InternalDocItem])
async def search_internal_documentation(
    query: str = "",
    category: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.AGENT]))
):
    """
    Quickly search internal SOPs and ISO 27001 / KB documentation.
    """
    from services.ai.agent_assistant_service import AgentAssistantService
    service = AgentAssistantService(db)
    try:
        return await service.search_internal_docs(query=query, category=category)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Docs search error: {str(e)}")

