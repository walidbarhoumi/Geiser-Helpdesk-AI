from fastapi import APIRouter
from routes import auth, users, tickets, agents, teams, ai, chat, sla, email

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(tickets.router, prefix="/tickets", tags=["tickets"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(teams.router, prefix="/teams", tags=["teams"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(sla.router, prefix="/sla", tags=["sla"])
api_router.include_router(email.router, prefix="/email", tags=["email"])

