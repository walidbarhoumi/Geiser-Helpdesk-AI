from fastapi import APIRouter, Depends, Query, UploadFile, File, HTTPException
from typing import List, Optional
from database.mongodb import get_database
from core.deps import get_current_user, RoleChecker
from schemas.schemas import (
    TicketCreate, TicketOut, TicketStatus, TicketUpdate,
    StatusUpdateRequest, AssignAgentRequest, UserRole
)
from controllers.ticket_controller import TicketController
from services.ticket_service import TicketService
from services.routing_service import RoutingService
from schemas.schemas import RoutingResult
from models.base import MongoModel
import os
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/{id}/auto-route", response_model=RoutingResult)
async def auto_route_ticket(
    id: str,
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.AGENT])),
    db=Depends(get_database)
):
    """Triggers the intelligent AI routing for a specific ticket."""
    service = RoutingService(db)
    try:
        result = await service.auto_route_ticket(id)
        return result
    except ValueError as e:
        logger.error(f"Routing error: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during routing: {e}")
        raise HTTPException(status_code=500, detail="Internal AI routing error")


@router.post("/create", response_model=TicketOut)
async def create_ticket(
    ticket_in: TicketCreate,
    current_user=Depends(get_current_user),
    db=Depends(get_database)
):
    return await TicketController.create_ticket(ticket_in, current_user["id"], db)


@router.get("/", response_model=List[TicketOut])
async def list_tickets(
    status: Optional[TicketStatus] = None,
    priority: Optional[str] = None,
    category: Optional[str] = None,
    current_user=Depends(get_current_user),
    db=Depends(get_database)
):
    filters = {}
    if status:
        filters["status"] = status.value
    if priority:
        filters["priority"] = priority
    if category:
        filters["category"] = category

    # Non-admins and non-agents only see their own tickets
    if current_user["role"] == UserRole.USER:
        filters["user_id"] = current_user["id"]

    return await TicketController.get_tickets(filters, db)


@router.get("/{id}", response_model=TicketOut)
async def get_ticket(
    id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database)
):
    service = TicketService(db)
    ticket = await service.get_ticket(id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    # Ensure users can only view their own tickets (unless agent/admin)
    if current_user["role"] == UserRole.USER and ticket["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    return ticket


@router.put("/{id}/assign", response_model=TicketOut)
async def assign_ticket(
    id: str,
    body: AssignAgentRequest,
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.AGENT])),
    db=Depends(get_database)
):
    service = TicketService(db)
    try:
        ticket = await service.assign_agent(id, body.agent_id)
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")
        return ticket
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{id}/status", response_model=TicketOut)
async def update_status(
    id: str,
    body: StatusUpdateRequest,
    current_user=Depends(RoleChecker([UserRole.AGENT, UserRole.ADMIN])),
    db=Depends(get_database)
):
    service = TicketService(db)
    ticket = await service.update_status(id, body.status)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.put("/{id}", response_model=TicketOut)
async def update_ticket(
    id: str,
    ticket_in: TicketUpdate,
    current_user=Depends(get_current_user),
    db=Depends(get_database)
):
    """General ticket update — allows updating status, priority, and assigned_agent_id."""
    service = TicketService(db)
    ticket = await service.get_ticket(id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    update_data = ticket_in.dict(exclude_unset=True)
    # Convert enums to their string values for MongoDB storage
    for key, val in update_data.items():
        if hasattr(val, "value"):
            update_data[key] = val.value

    from datetime import datetime
    update_data["updated_at"] = datetime.utcnow()
    await db.tickets.update_one({"_id": MongoModel.to_object_id(id)}, {"$set": update_data})
    return await service.get_ticket(id)


@router.post("/{id}/attachments")
async def upload_attachment(
    id: str,
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db=Depends(get_database)
):
    file_path = os.path.join(settings.UPLOAD_DIR, f"{id}_{file.filename}")
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())

    await db.tickets.update_one(
        {"_id": MongoModel.to_object_id(id)},
        {"$addToSet": {"attachments": file_path}}
    )
    return {"filename": file.filename, "path": file_path}

@router.delete("/{id}")
async def delete_ticket(
    id: str,
    current_user=Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database)
):
    service = TicketService(db)
    deleted = await service.delete_ticket(id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {"message": "Ticket deleted"}
