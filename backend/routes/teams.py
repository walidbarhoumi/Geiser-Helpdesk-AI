from fastapi import APIRouter, Depends, HTTPException
from typing import List
from database.mongodb import get_database
from core.deps import RoleChecker, get_current_user
from schemas.schemas import TeamCreate, TeamOut, TeamUpdate, UserRole
from services.user_agent_team_service import TeamService
from models.base import MongoModel

router = APIRouter()


@router.post("/", response_model=TeamOut)
async def create_team(
    team_in: TeamCreate,
    current_user=Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database)
):
    service = TeamService(db)
    return await service.create_team(team_in)


@router.get("/", response_model=List[TeamOut])
async def list_teams(
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.AGENT])),
    db=Depends(get_database)
):
    service = TeamService(db)
    return await service.get_teams()


@router.get("/{id}", response_model=TeamOut)
async def get_team(
    id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database)
):
    oid = MongoModel.to_object_id(id)
    if not oid:
        raise HTTPException(status_code=400, detail="Invalid team ID")
    team = await db.teams.find_one({"_id": oid})
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return MongoModel.format_id(team)


@router.put("/{id}/add-agent", response_model=TeamOut)
async def add_agent(
    id: str,
    agent_id: str,
    current_user=Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database)
):
    service = TeamService(db)
    team = await service.add_agent_to_team(id, agent_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@router.put("/{id}/remove-agent", response_model=TeamOut)
async def remove_agent(
    id: str,
    agent_id: str,
    current_user=Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database)
):
    service = TeamService(db)
    team = await service.remove_agent_from_team(id, agent_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@router.put("/{id}", response_model=TeamOut)
async def update_team(
    id: str,
    team_in: TeamUpdate,
    current_user=Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database)
):
    service = TeamService(db)
    team = await service.update_team(id, team_in.dict(exclude_unset=True))
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@router.delete("/{id}")
async def delete_team(
    id: str,
    current_user=Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database)
):
    service = TeamService(db)
    deleted = await service.delete_team(id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Team not found")
    return {"message": "Team deleted"}
