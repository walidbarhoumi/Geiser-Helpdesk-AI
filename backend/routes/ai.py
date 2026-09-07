from fastapi import APIRouter, Depends, HTTPException, Body
from ai.ollama_client import OllamaClient
from services.ai.ai_response_service import AIResponseService
from database.mongodb import get_database
from core.deps import RoleChecker, get_current_user
from schemas.schemas import UserRole, KnowledgeBaseItem, IntelligentTriageResult
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

router = APIRouter()

@router.get("/status")
async def get_ai_status(
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.AGENT]))
):
    client = OllamaClient()
    return await client.check_health()

@router.post("/tickets/{ticket_id}/generate-response")
async def generate_ai_response(
    ticket_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.AGENT]))
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
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.AGENT]))
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

