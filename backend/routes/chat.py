import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from database.mongodb import get_database
from core.deps import get_current_user
from core.config import settings
from schemas.schemas import ChatRequest, ChatResponse, ChatEscalateRequest, TicketOut
from services.ai.chatbot_service import ChatbotService
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/message", response_model=ChatResponse)
async def send_chat_message(
    chat_data: ChatRequest,
    current_user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Receives multi-turn messages from the user, interacts with Knowledge Base & local Ollama LLM,
    and returns an actionable technical response.
    """
    chatbot_service = ChatbotService(db)
    try:
        return await chatbot_service.process_chat_message(chat_data.messages, current_user["id"])
    except Exception as e:
        logger.error(f"Error processing chat message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing chat message"
        )

@router.post("/upload-attachment")
async def upload_chat_attachment(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):
    """
    Uploads an attachment from the chat widget to the uploads folder.
    """
    if not os.path.exists(settings.UPLOAD_DIR):
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        
    unique_prefix = uuid.uuid4().hex[:8]
    clean_filename = f"{unique_prefix}_{file.filename}"
    file_path = os.path.join(settings.UPLOAD_DIR, clean_filename)
    
    try:
        content = await file.read()
        with open(file_path, "wb") as buffer:
            buffer.write(content)
        return {
            "filename": file.filename,
            "path": file_path,
            "size": len(content)
        }
    except Exception as e:
        logger.error(f"Failed to save chat attachment: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload attachment")

@router.post("/escalate", response_model=TicketOut)
async def escalate_chat_to_ticket(
    data: ChatEscalateRequest,
    current_user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Converts a live chat conversation into an official Ticket with channel='CHAT'.
    The AI automatically:
    - Validates that the request is a real, valid IT issue (rejects casual small talk).
    - Determines the Category & Subcategory.
    - Prioritizes according to Impact and Urgency.
    - Proposes technical Keywords for triaging.
    - Attaches any optional uploaded files.
    """
    chatbot_service = ChatbotService(db)
    try:
        created_ticket = await chatbot_service.escalate_to_ticket(
            messages=data.messages,
            user_id=current_user["id"],
            custom_subject=data.custom_subject,
            attachments=data.attachments or []
        )
        return created_ticket
    except ValueError as ve:
        logger.warning(f"Ticket escalation validation failed: {ve}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        logger.error(f"Error escalating chat to ticket: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error escalating chat to ticket"
        )


@router.post("/reindex")
async def reindex_rag_knowledge_base(
    current_user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Reconstruit l'index vectoriel FAISS et recharge le fichier source JSONL.
    Accessible aux administrateurs et agents de support.
    """
    role = str(current_user.get("role", "")).upper()
    if role not in ["ADMIN", "SUPERADMIN", "AGENT"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Action réservée aux administrateurs et agents de support."
        )

    import asyncio
    chatbot_service = ChatbotService(db)
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, chatbot_service.rag_service.reindex)
        return {
            "message": "Réindexation RAG réussie avec succès",
            "details": result
        }
    except Exception as e:
        logger.error(f"Erreur lors de la réindexation RAG : {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Échec de la réindexation RAG : {str(e)}"
        )



