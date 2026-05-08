from fastapi import APIRouter, Depends, HTTPException
from typing import List
from database.mongodb import get_database
from core.deps import RoleChecker, get_current_user
from schemas.schemas import AgentCreate, AgentOut, AgentUpdate, UserRole
from services.user_agent_team_service import AgentService
from models.base import MongoModel

router = APIRouter()


@router.post("/", response_model=AgentOut)
async def create_agent(
    agent_in: AgentCreate,
    current_user=Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database)
):
    service = AgentService(db)
    return await service.create_agent(agent_in)


@router.get("/", response_model=List[AgentOut])
async def list_agents(
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.AGENT])),
    db=Depends(get_database)
):
    service = AgentService(db)
    return await service.get_agents()


@router.get("/{id}", response_model=AgentOut)
async def get_agent(
    id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database)
):
    service = AgentService(db)
    agent = await service.get_agent_by_id(id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.put("/{id}/skills", response_model=AgentOut)
async def update_agent_skills(
    id: str,
    skills: List[str],
    current_user=Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database)
):
    oid = MongoModel.to_object_id(id)
    if not oid:
        raise HTTPException(status_code=400, detail="Invalid agent ID")
    await db.agents.update_one(
        {"_id": oid},
        {"$set": {"skills": skills}}
    )
    agent = await db.agents.find_one({"_id": oid})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return MongoModel.format_id(agent)


@router.put("/{id}/availability", response_model=AgentOut)
async def update_agent_availability(
    id: str,
    is_available: bool,
    current_user=Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database)
):
    oid = MongoModel.to_object_id(id)
    if not oid:
        raise HTTPException(status_code=400, detail="Invalid agent ID")
    await db.agents.update_one(
        {"_id": oid},
        {"$set": {"is_available": is_available}}
    )
    agent = await db.agents.find_one({"_id": oid})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return MongoModel.format_id(agent)


@router.put("/{id}", response_model=AgentOut)
async def update_agent(
    id: str,
    agent_in: AgentUpdate,
    current_user=Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database)
):
    service = AgentService(db)
    agent = await service.update_agent(id, agent_in.dict(exclude_unset=True))
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.delete("/{id}")
async def delete_agent(
    id: str,
    current_user=Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database)
):
    service = AgentService(db)
    deleted = await service.delete_agent(id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"message": "Agent deleted"}
