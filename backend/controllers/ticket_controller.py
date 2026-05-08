from fastapi import HTTPException, status
from services.ticket_service import TicketService
from schemas.schemas import TicketCreate, TicketStatus


class TicketController:
    @staticmethod
    async def create_ticket(ticket_in: TicketCreate, user_id: str, db):
        service = TicketService(db)
        return await service.create_ticket(ticket_in, user_id)

    @staticmethod
    async def get_tickets(filters: dict, db):
        service = TicketService(db)
        return await service.get_tickets(filters)

    @staticmethod
    async def update_status(ticket_id: str, new_status: TicketStatus, db):
        service = TicketService(db)
        ticket = await service.update_status(ticket_id, new_status)
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")
        return ticket
