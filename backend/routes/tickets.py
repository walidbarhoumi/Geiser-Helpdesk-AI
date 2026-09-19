from fastapi import APIRouter, Depends, Query, UploadFile, File, HTTPException
from typing import List, Optional
from database.mongodb import get_database
from core.deps import get_current_user, RoleChecker
from schemas.schemas import (
    TicketCreate, TicketOut, TicketStatus, TicketUpdate,
    StatusUpdateRequest, AssignAgentRequest, UserRole,
    TicketResolveRequest, SendTicketResponseRequest, SubmitSatisfactionRequest,
    PriorityCalculationRequest, PriorityCalculationResponse, PrioritySource
)
from services.email_service import EmailService

from controllers.ticket_controller import TicketController
from services.ticket_service import TicketService
from services.routing_service import RoutingService
from schemas.schemas import RoutingResult
from models.base import MongoModel
from core.config import settings
import os
import logging
from datetime import datetime

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


@router.post("/calculate-priority", response_model=PriorityCalculationResponse)
async def calculate_priority_preview(
    body: PriorityCalculationRequest,
    current_user=Depends(get_current_user),
):
    """Preview ITIL priority calculated from impact and urgency."""
    from services.itil_service import calculate_priority_from_impact_urgency
    try:
        calculated = calculate_priority_from_impact_urgency(body.impact, body.urgency)
        return {
            "impact": body.impact,
            "urgency": body.urgency,
            "priority": calculated,
            "source": PrioritySource.ITIL_MATRIX,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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

    # ITIL priority calculation if impact or urgency is updated
    impact_or_urgency_in_update = "impact" in update_data or "urgency" in update_data
    if impact_or_urgency_in_update:
        active_impact = update_data.get("impact", ticket.get("impact"))
        active_urgency = update_data.get("urgency", ticket.get("urgency"))
        if active_impact and active_urgency:
            from services.itil_service import calculate_priority_from_impact_urgency
            try:
                itil_prio = calculate_priority_from_impact_urgency(active_impact, active_urgency)
                update_data["priority"] = itil_prio.value
                update_data["priority_source"] = PrioritySource.ITIL_MATRIX.value
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

    # Recompute SLA deadlines only if priority, category or subcategory actually changed
    priority_changed = "priority" in update_data and update_data["priority"] != ticket.get("priority")
    category_changed = "category" in update_data and update_data["category"] != ticket.get("category")
    subcategory_changed = "subcategory" in update_data and update_data["subcategory"] != ticket.get("subcategory")

    if priority_changed or category_changed or subcategory_changed:
        from services.sla_service import SLAService
        sla_service = SLAService(db)
        created_at = ticket.get("created_at") or datetime.utcnow()
        active_prio = update_data.get("priority", ticket.get("priority"))
        active_cat = update_data.get("category", ticket.get("category"))
        active_subcat = update_data.get("subcategory", ticket.get("subcategory"))

        sla_calc = await sla_service.calculate_ticket_sla(
            priority=active_prio,
            created_at=created_at,
            category=active_cat,
            subcategory=active_subcat
        )
        update_data["sla_deadline"] = sla_calc["resolution_deadline"]
        update_data["sla_response_deadline"] = sla_calc["response_deadline"]
        update_data["sla_applied_rule"] = sla_calc["applied_rule"]
        new_sla_status = await sla_service.compute_sla_status({**ticket, **update_data})
        update_data["sla_status"] = new_sla_status.value if hasattr(new_sla_status, "value") else new_sla_status

    update_data["updated_at"] = datetime.utcnow()
    await db.tickets.update_one({"_id": MongoModel.to_object_id(id)}, {"$set": update_data})
    return await service.get_ticket(id)


@router.post("/{id}/send-response")
async def send_ticket_response(
    id: str,
    body: SendTicketResponseRequest,
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.AGENT])),
    db=Depends(get_database)
):
    """
    Sends an official support response to the user via email
    and logs the response in the ticket audit thread.
    """
    service = TicketService(db)
    ticket = await service.get_ticket(id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    user = await db.users.find_one({"_id": MongoModel.to_object_id(ticket["user_id"])})
    if user and user.get("email"):
        formatted_html = body.response_text.replace("\n", "<br/>")
        EmailService.send_email(
            user["email"],
            f"Mise à jour Support GEISER : #{ticket['id'][-6:].upper()} - {ticket['subject']}",
            f"<div style='font-family: Arial, sans-serif; line-height: 1.6; color: #1e293b;'>"
            f"<p>Bonjour,</p>"
            f"<p>Un technicien du support GEISER a répondu à votre ticket <b>#{ticket['id'][-6:].upper()}</b> :</p>"
            f"<div style='background: #f8fafc; border-left: 4px solid #7c3aed; padding: 12px 16px; margin: 16px 0; border-radius: 4px;'>"
            f"{formatted_html}"
            f"</div>"
            f"<p>Pour toute question ou complément, répondez à ce message ou consultez votre portail d'assistance.</p>"
            f"<p>Cordialement,<br/><b>L'équipe Support GEISER</b></p>"
            f"</div>"
        )

    # Append response to thread
    new_response = {
        "sender_id": str(current_user["id"]),
        "sender_name": current_user.get("full_name") or current_user.get("email"),
        "role": current_user.get("role", "AGENT"),
        "content": body.response_text,
        "created_at": datetime.utcnow()
    }

    await db.tickets.update_one(
        {"_id": MongoModel.to_object_id(id)},
        {
            "$push": {"responses": new_response},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )

    return {"success": True, "message": "Réponse envoyée avec succès par e-mail au demandeur."}


@router.post("/{id}/resolve", response_model=TicketOut)
async def resolve_ticket(
    id: str,
    body: TicketResolveRequest,
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.AGENT])),
    db=Depends(get_database)
):
    """
    Resolves a ticket and records the resolution_note for historical AI learning and triage.
    """
    service = TicketService(db)
    ticket = await service.get_ticket(id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    oid = MongoModel.to_object_id(id)
    now = datetime.utcnow()

    # Update ticket to RESOLVED with resolution note
    await db.tickets.update_one(
        {"_id": oid},
        {
            "$set": {
                "status": TicketStatus.RESOLVED.value,
                "resolution_note": body.resolution_note,
                "updated_at": now
            }
        }
    )

    updated_ticket = await service.get_ticket(id)

    # Notify user of resolution
    user = await db.users.find_one({"_id": MongoModel.to_object_id(ticket["user_id"])})
    if user and user.get("email"):
        EmailService.send_email(
            user["email"],
            f"Ticket Résolu : #{ticket['id'][-6:].upper()} - {ticket['subject']}",
            f"<div style='font-family: Arial, sans-serif; line-height: 1.6; color: #1e293b;'>"
            f"<h2 style='color: #059669;'>Votre ticket a été résolu</h2>"
            f"<p>Votre demande <b>#{ticket['id'][-6:].upper()}</b> ({ticket['subject']}) a été clôturée avec succès.</p>"
            f"<div style='background: #f0fdf4; border-left: 4px solid #10b981; padding: 12px 16px; margin: 16px 0; border-radius: 4px;'>"
            f"<b>Solution appliquée :</b><br/>{body.resolution_note.replace(chr(10), '<br/>')}"
            f"</div>"
            f"<p>Merci d'avoir fait appel au support GEISER.</p>"
            f"</div>"
        )

    return updated_ticket


@router.post("/{id}/satisfaction", response_model=TicketOut)
async def submit_ticket_satisfaction(
    id: str,
    body: SubmitSatisfactionRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Submits a Customer Satisfaction (CSAT) rating (1-5) and optional comment for a resolved/closed ticket.
    """
    service = TicketService(db)
    ticket = await service.get_ticket(id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Only ticket creator or admin/agent can rate
    if current_user["role"] == UserRole.USER and ticket["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Access denied")

    oid = MongoModel.to_object_id(id)
    now = datetime.utcnow()

    await db.tickets.update_one(
        {"_id": oid},
        {
            "$set": {
                "satisfaction_rating": body.rating,
                "satisfaction_comment": body.comment,
                "satisfaction_submitted_at": now,
                "updated_at": now
            }
        }
    )

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
