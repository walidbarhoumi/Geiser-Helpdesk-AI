from fastapi import APIRouter, Depends, HTTPException
from typing import List
from database.mongodb import get_database
from core.deps import get_current_user, RoleChecker
from schemas.schemas import UserOut, UserCreate, UserUpdate, UserRole
from services.user_agent_team_service import UserService
from services.auth_service import AuthService

router = APIRouter()


@router.get("/", response_model=List[UserOut])
async def list_users(
    current_user=Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database)
):
    service = UserService(db)
    return await service.get_users()


@router.post("/", response_model=UserOut)
async def create_user(
    user_in: UserCreate,
    current_user=Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database)
):
    auth_service = AuthService(db)
    created = await auth_service.register_user(user_in)

    # ISO 27001 Audit Log
    try:
        from services.audit_service import AuditService
        from schemas.schemas import AuditEventCategory, AuditSeverity
        import asyncio
        asyncio.create_task(
            AuditService(db).log_event(
                event_category=AuditEventCategory.USER_MGMT,
                event_type="USER_CREATED",
                severity=AuditSeverity.INFO,
                target_resource_type="user",
                target_resource_id=str(created.get("id")),
                actor_id=str(current_user.get("id")),
                actor_email=current_user.get("email"),
                actor_role=current_user.get("role"),
                status="SUCCESS",
                details={
                    "created_user_email": user_in.email,
                    "created_user_role": user_in.role if hasattr(user_in.role, "value") else str(user_in.role),
                    "created_user_name": user_in.full_name,
                }
            )
        )
    except Exception as err:
        pass

    return created


@router.get("/me", response_model=UserOut)
async def get_me(current_user=Depends(get_current_user)):
    return current_user


@router.put("/{id}", response_model=UserOut)
async def update_user(
    id: str,
    user_in: UserUpdate,
    current_user=Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database)
):
    service = UserService(db)
    updated = await service.update_user(id, user_in)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")

    # ISO 27001 Audit Log
    try:
        from services.audit_service import AuditService
        from schemas.schemas import AuditEventCategory, AuditSeverity
        import asyncio
        asyncio.create_task(
            AuditService(db).log_event(
                event_category=AuditEventCategory.USER_MGMT,
                event_type="USER_UPDATED",
                severity=AuditSeverity.INFO,
                target_resource_type="user",
                target_resource_id=id,
                actor_id=str(current_user.get("id")),
                actor_email=current_user.get("email"),
                actor_role=current_user.get("role"),
                status="SUCCESS",
                details=user_in.dict(exclude_unset=True)
            )
        )
    except Exception as err:
        pass

    return updated


@router.delete("/{id}")
async def delete_user(
    id: str,
    current_user=Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database)
):
    service = UserService(db)
    await service.delete_user(id)

    # ISO 27001 Audit Log
    try:
        from services.audit_service import AuditService
        from schemas.schemas import AuditEventCategory, AuditSeverity
        import asyncio
        asyncio.create_task(
            AuditService(db).log_event(
                event_category=AuditEventCategory.USER_MGMT,
                event_type="USER_DELETED",
                severity=AuditSeverity.WARNING,
                target_resource_type="user",
                target_resource_id=id,
                actor_id=str(current_user.get("id")),
                actor_email=current_user.get("email"),
                actor_role=current_user.get("role"),
                status="SUCCESS",
                details={"deleted_user_id": id}
            )
        )
    except Exception as err:
        pass

    return {"message": "User deleted"}
