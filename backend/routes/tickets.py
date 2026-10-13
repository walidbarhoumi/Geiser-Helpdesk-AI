from fastapi import APIRouter, Depends, Query, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from typing import List, Optional
from database.mongodb import get_database
from core.deps import get_current_user, RoleChecker
from schemas.schemas import (
    TicketCreate, TicketOut, TicketStatus, TicketUpdate,
    StatusUpdateRequest, AssignAgentRequest, UserRole,
    TicketResolveRequest, SendTicketResponseRequest, SubmitSatisfactionRequest,
    PriorityCalculationRequest, PriorityCalculationResponse, PrioritySource,
    TicketActionType, AttachmentOut, AttachmentUploadResponse
)
from services.email_service import EmailService

from controllers.ticket_controller import TicketController
from services.ticket_service import TicketService
from services.routing_service import RoutingService
from services.attachment_service import AttachmentService
from schemas.schemas import RoutingResult
from models.base import MongoModel
from core.config import settings
import os
import logging
from datetime import datetime

router = APIRouter()
logger = logging.getLogger(__name__)


def _role_value(user: dict) -> str:
    role = user.get("role")
    return role.value if hasattr(role, "value") else str(role)


async def _agent_scope(db, user: dict):
    """Return the agent record and teams available to this authenticated agent."""
    agent = await db.agents.find_one({"user_id": str(user.get("id"))})
    if not agent:
        return None, set()
    agent_id = str(agent.get("_id"))
    teams = await db.teams.find({"agent_ids": agent_id}).to_list(length=100)
    return agent, {str(team.get("_id")) for team in teams}


async def _ticket_in_scope(db, ticket: dict, user: dict) -> bool:
    role = _role_value(user)
    if role in (UserRole.ADMIN.value, UserRole.SUPERVISOR.value):
        return True
    if role == UserRole.USER.value:
        return str(ticket.get("user_id")) == str(user.get("id"))
    if role == UserRole.AGENT.value:
        agent, team_ids = await _agent_scope(db, user)
        if not agent:
            return False
        return (
            str(ticket.get("assigned_agent_id")) == str(agent.get("_id"))
            or str(ticket.get("assigned_team_id")) in team_ids
        )
    return False


async def _require_ticket_scope(db, ticket: dict, user: dict) -> None:
    # Use 404 for out-of-scope tickets so callers cannot distinguish them
    # from ticket IDs that do not exist.
    if not await _ticket_in_scope(db, ticket, user):
        raise HTTPException(status_code=404, detail="Ticket not found")


@router.post("/{id}/auto-route", response_model=RoutingResult)
async def auto_route_ticket(
    id: str,
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.AGENT])),
    db=Depends(get_database)
):
    """Triggers the intelligent AI routing for a specific ticket."""
    ticket = await TicketService(db).get_ticket(id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    await _require_ticket_scope(db, ticket, current_user)
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
    return await TicketController.create_ticket(ticket_in, current_user["id"], db, actor_user=current_user)


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
    elif _role_value(current_user) == UserRole.AGENT.value:
        agent, team_ids = await _agent_scope(db, current_user)
        if not agent:
            return []
        scope = [{"assigned_agent_id": str(agent.get("_id"))}]
        if team_ids:
            scope.append({"assigned_team_id": {"$in": list(team_ids)}})
        filters["$or"] = scope

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
    await _require_ticket_scope(db, ticket, current_user)
    return ticket


@router.put("/{id}/assign", response_model=TicketOut)
async def assign_ticket(
    id: str,
    body: AssignAgentRequest,
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR])),
    db=Depends(get_database)
):
    service = TicketService(db)
    try:
        ticket = await service.assign_agent(id, body.agent_id, actor_user=current_user)
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")
        return ticket
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{id}/status", response_model=TicketOut)
async def update_status(
    id: str,
    body: StatusUpdateRequest,
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.AGENT])),
    db=Depends(get_database)
):
    service = TicketService(db)
    current_ticket = await service.get_ticket(id)
    if not current_ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    await _require_ticket_scope(db, current_ticket, current_user)
    requested_status = body.status.value if hasattr(body.status, "value") else str(body.status)
    if (
        _role_value(current_user) == UserRole.AGENT.value
        and requested_status == TicketStatus.CLOSED.value
    ):
        raise HTTPException(status_code=403, detail="Agents cannot close tickets")
    try:
        ticket = await service.update_status(id, body.status, actor_user=current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ticket


@router.put("/{id}", response_model=TicketOut)
async def update_ticket(
    id: str,
    ticket_in: TicketUpdate,
    current_user=Depends(get_current_user),
    db=Depends(get_database)
):
    """Update permitted ticket fields after role and record-scope checks."""
    service = TicketService(db)
    ticket = await service.get_ticket(id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    await _require_ticket_scope(db, ticket, current_user)

    role = _role_value(current_user)
    user_fields = {"subject", "description"}
    agent_fields = {
        "subject", "description", "category", "subcategory", "status",
        "keywords", "resolution_note",
    }
    supervisor_fields = agent_fields | {"priority_source", "routing_reason"}
    allowed_fields = {
        UserRole.USER.value: user_fields,
        UserRole.AGENT.value: agent_fields,
        UserRole.SUPERVISOR.value: supervisor_fields,
        UserRole.ADMIN.value: supervisor_fields,
    }.get(role, set())

    update_data = ticket_in.dict(exclude_unset=True)
    if "assigned_agent_id" in update_data:
        # Assignment uses the dedicated supervisor/admin-only /assign route.
        raise HTTPException(status_code=403, detail="Assignment changes are not permitted here")
    if not set(update_data).issubset(allowed_fields):
        raise HTTPException(status_code=403, detail="One or more ticket fields cannot be updated")

    if "status" in update_data:
        status = update_data.pop("status")
        status_value = status.value if hasattr(status, "value") else str(status)
        if role == UserRole.AGENT.value and status_value == TicketStatus.CLOSED.value:
            raise HTTPException(status_code=403, detail="Agents cannot close tickets")
        try:
            await service.update_status(id, status, actor_user=current_user)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    if not update_data:
        updated_ticket = await service.get_ticket(id)
        return updated_ticket

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

    # ISO 27001 Action History
    if priority_changed:
        await service.record_ticket_action(
            ticket_id=id,
            action_type=TicketActionType.PRIORITY_CHANGED.value,
            actor_user=current_user,
            details={"old_priority": ticket.get("priority"), "new_priority": update_data.get("priority")},
            comment=f"Priorité modifiée de {ticket.get('priority')} à {update_data.get('priority')}"
        )
    if priority_changed or category_changed or subcategory_changed:
        await service.record_ticket_action(
            ticket_id=id,
            action_type=TicketActionType.SLA_RECALCULATED.value,
            actor_user=current_user,
            details={"applied_rule": sla_calc.get("applied_rule"), "new_deadline": str(sla_calc.get("resolution_deadline"))},
            comment="Recalcul des délais SLA suite à modification"
        )

    final_ticket = await service.get_ticket(id)
    if final_ticket and priority_changed:
        try:
            from websocket.dispatcher import event_dispatcher
            await event_dispatcher.publish_ticket_priority_changed(
                ticket=final_ticket,
                old_priority=ticket.get("priority"),
                new_priority=update_data.get("priority"),
                actor=current_user
            )
        except Exception as ws_err:
            logger.debug(f"[WS] Priority change event dispatch failed: {ws_err}")

    return final_ticket


@router.post("/{id}/send-response")
async def send_ticket_response(
    id: str,
    body: SendTicketResponseRequest,
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.AGENT])),
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
    await _require_ticket_scope(db, ticket, current_user)

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

    # ISO 27001 Action History
    await service.record_ticket_action(
        ticket_id=id,
        action_type=TicketActionType.RESPONSE_SENT.value,
        actor_user=current_user,
        details={"content_preview": (body.response_text[:80] + "...") if len(body.response_text) > 80 else body.response_text},
        comment="Réponse officielle transmise au demandeur"
    )

    # Live WebSocket dispatch (STEP 5)
    try:
        from websocket.dispatcher import event_dispatcher
        await event_dispatcher.publish_ticket_comment(
            ticket=ticket,
            response_data=new_response,
            actor=current_user
        )
    except Exception as ws_err:
        logger.debug(f"[WS] Comment added event dispatch failed: {ws_err}")

    return {"success": True, "message": "Réponse envoyée avec succès par e-mail au demandeur."}


@router.post("/{id}/resolve", response_model=TicketOut)
async def resolve_ticket(
    id: str,
    body: TicketResolveRequest,
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.AGENT])),
    db=Depends(get_database)
):
    """
    Resolves a ticket and records the resolution_note for historical AI learning and triage.
    """
    service = TicketService(db)
    ticket = await service.get_ticket(id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    await _require_ticket_scope(db, ticket, current_user)

    oid = MongoModel.to_object_id(id)
    now = datetime.utcnow()

    try:
        await service.update_status(id, TicketStatus.RESOLVED, actor_user=current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Update ticket to RESOLVED with resolution note
    await db.tickets.update_one(
        {"_id": oid},
        {
            "$set": {
                "resolution_note": body.resolution_note,
                "updated_at": now
            }
        }
    )

    # ISO 27001 Action History
    await service.record_ticket_action(
        ticket_id=id,
        action_type=TicketActionType.RESOLUTION_RECORDED.value,
        actor_user=current_user,
        details={"resolution_note": body.resolution_note},
        comment="Ticket résolu avec note technique de clôture"
    )

    updated_ticket = await service.get_ticket(id)

    # Mise à jour du résultat dans routing_history
    try:
        sla_respected = updated_ticket.get("sla_status") not in ("BREACHED",) if updated_ticket else None
        await db.routing_history.update_one(
            {"ticket_id": id, "outcome_resolved_at": None},
            {"$set": {
                "outcome_resolved_at": now,
                "outcome_sla_respected": sla_respected
            }},
            sort=[("created_at", -1)]
        )
    except Exception as resolve_err:
        logger.warning(f"Impossible de mettre à jour routing_history avec le résultat de résolution pour le ticket {id} : {resolve_err}")

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

    # Ticket must be in RESOLVED or CLOSED status
    allowed_statuses = {TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value, "RESOLVED", "CLOSED"}
    current_status = ticket.get("status")
    if hasattr(current_status, "value"):
        current_status = current_status.value
    if current_status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Satisfaction rating can only be submitted for RESOLVED or CLOSED tickets (current status: {current_status})"
        )

    # Only the ticket creator or an administrator can rate.
    user_role = current_user.get("role")
    if hasattr(user_role, "value"):
        user_role = user_role.value
    current_user_id = str(current_user.get("id"))
    ticket_user_id = str(ticket.get("user_id"))

    if not (
        user_role == UserRole.ADMIN.value
        or (user_role == UserRole.USER.value and ticket_user_id == current_user_id)
    ):
        raise HTTPException(status_code=403, detail="Access denied: you can only rate your own tickets")

    # Prevent duplicate rating
    if ticket.get("satisfaction_rating") is not None:
        raise HTTPException(status_code=409, detail="A satisfaction rating has already been submitted for this ticket")

    # Clean comment
    comment_clean = body.comment.strip() if body.comment and body.comment.strip() else None

    oid = MongoModel.to_object_id(id)
    now = datetime.utcnow()

    await db.tickets.update_one(
        {"_id": oid},
        {
            "$set": {
                "satisfaction_rating": body.rating,
                "satisfaction_comment": comment_clean,
                "satisfaction_submitted_at": now,
                "updated_at": now
            }
        }
    )

    # ISO 27001 Action History
    await service.record_ticket_action(
        ticket_id=id,
        action_type=TicketActionType.SATISFACTION_SUBMITTED.value,
        actor_user=current_user,
        details={"rating": body.rating, "comment": comment_clean},
        comment=f"Évaluation CSAT enregistrée : {body.rating}/5"
    )

    # Mise à jour du score CSAT dans routing_history pour l'apprentissage historique
    try:
        await db.routing_history.update_one(
            {"ticket_id": id, "outcome_csat_score": None},
            {"$set": {"outcome_csat_score": body.rating}},
            sort=[("created_at", -1)]
        )
    except Exception as csat_err:
        logger.warning(f"Impossible de mettre à jour routing_history avec le CSAT pour le ticket {id} : {csat_err}")

    return await service.get_ticket(id)


@router.post(
    "/{id}/attachments",
    response_model=AttachmentUploadResponse,
    summary="Téléverser une pièce jointe (sécurisé)",
)
async def upload_attachment(
    id: str,
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Uploads a file attachment to a ticket.

    Security enforced:
    - RBAC: only ticket owner, agents, supervisors or admins may upload.
    - MIME whitelist: only approved types accepted.
    - Size limit: configurable (default 10 MB).
    - Magic-byte verification for common types.
    - UUID-based stored filename: user-controlled names never touch the filesystem path.
    """
    service = AttachmentService(db)
    attachment = await service.upload_attachment(
        ticket_id=id, file=file, current_user=current_user
    )
    return AttachmentUploadResponse(attachment=attachment)


@router.get(
    "/{id}/attachments",
    response_model=List[AttachmentOut],
    summary="Lister les pièces jointes d'un ticket",
)
async def list_attachments(
    id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Returns the metadata list of all attachments for a ticket.
    Access is restricted to the ticket owner, assigned agent, or admin/supervisor.
    """
    service = AttachmentService(db)
    return await service.list_attachments(ticket_id=id, current_user=current_user)


@router.get(
    "/{id}/attachments/{attachment_id}/download",
    summary="Télécharger une pièce jointe (sécurisé)",
)
async def download_attachment(
    id: str,
    attachment_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Securely serves a ticket attachment.

    Security enforced:
    - RBAC: only ticket owner, assigned agent, or admin/supervisor.
    - Path traversal protection: resolved path must be inside UPLOAD_DIR.
    - Content-Type set to the stored MIME type.
    - X-Content-Type-Options: nosniff header to prevent MIME sniffing.
    - Content-Disposition: attachment to force browser download.
    """
    service = AttachmentService(db)
    file_path, original_filename, mime_type = await service.get_attachment_for_download(
        ticket_id=id,
        attachment_id=attachment_id,
        current_user=current_user,
    )
    return FileResponse(
        path=file_path,
        media_type=mime_type,
        filename=original_filename,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@router.delete("/{id}")
async def delete_ticket(
    id: str,
    current_user=Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database)
):
    service = TicketService(db)
    deleted = await service.delete_ticket(id, actor_user=current_user)
    if not deleted:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {"message": "Ticket deleted"}
