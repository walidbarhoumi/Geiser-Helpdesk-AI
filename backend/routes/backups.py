from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, status
from database.mongodb import get_database
from core.deps import RoleChecker, get_current_user
from schemas.schemas import UserRole
from backup.backup_models import (
    BackupOut,
    BackupListResponse,
    BackupStatsOut,
    BackupType,
    RestoreTestResult,
    ProductionRestoreRequest,
    ProductionRestoreResult,
)
from backup.backup_service import BackupService

router = APIRouter()


@router.get("", response_model=BackupListResponse)
async def list_backups(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filtrer par statut (SUCCESS, FAILED, CORRUPTED)"),
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR])),
    db=Depends(get_database),
):
    """
    Lists backups with pagination and status filtering.
    Accessible to Administrators and Supervisors (Read-Only).
    """
    service = BackupService(db)
    items, total = await service.list_backups(skip=skip, limit=limit, status=status)
    return BackupListResponse(
        total=total,
        skip=skip,
        limit=limit,
        items=[BackupOut(**item) for item in items]
    )


@router.get("/stats", response_model=BackupStatsOut)
async def get_backup_stats(
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR])),
    db=Depends(get_database),
):
    """
    Retrieves backup storage statistics, counts, and last execution timestamps.
    """
    service = BackupService(db)
    stats = await service.get_backup_stats()
    return BackupStatsOut(**stats)


@router.get("/{backup_id}", response_model=BackupOut)
async def get_backup_details(
    backup_id: str,
    current_user=Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPERVISOR])),
    db=Depends(get_database),
):
    """
    Retrieves detailed metadata for a specific backup by ID.
    """
    service = BackupService(db)
    doc = await service.collection.find_one({"backup_id": backup_id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backup '{backup_id}' not found"
        )
    return BackupOut(**doc)


@router.post("/run", response_model=BackupOut)
async def run_manual_backup(
    current_user=Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database),
):
    """
    Triggers an on-demand manual MongoDB backup.
    Restricted strictly to Administrators.
    """
    service = BackupService(db)
    actor = {
        "id": str(current_user.id if hasattr(current_user, "id") else current_user.get("_id", "")),
        "email": getattr(current_user, "email", current_user.get("email", "")),
        "role": getattr(current_user, "role", current_user.get("role", "")),
    }
    metadata = await service.create_backup(backup_type=BackupType.MANUAL, actor=actor)
    return BackupOut(**metadata.dict())


@router.post("/{backup_id}/verify")
async def verify_backup(
    backup_id: str,
    current_user=Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database),
):
    """
    Recalculates SHA-256 hash of the backup archive on disk and validates integrity.
    Restricted strictly to Administrators.
    """
    service = BackupService(db)
    try:
        result = await service.verify_backup_integrity(backup_id)
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{backup_id}/restore-test", response_model=RestoreTestResult)
async def test_isolated_restore(
    backup_id: str,
    current_user=Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database),
):
    """
    MODE A — Performs safe isolated restoration testing in a temporary database.
    Verifies checksum, restores, counts documents across collections, and drops the test DB.
    Restricted strictly to Administrators.
    """
    service = BackupService(db)
    try:
        result = await service.test_isolated_restore(backup_id)
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{backup_id}/restore-production", response_model=ProductionRestoreResult)
async def restore_production(
    backup_id: str,
    body: ProductionRestoreRequest,
    current_user=Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database),
):
    """
    MODE B — Destructive Production Restoration.
    STRICT CONTROLS:
    - Global feature switch BACKUP_ALLOW_PRODUCTION_RESTORE must be enabled on server.
    - confirm_production_overwrite must be True.
    - target_database_name must match production database.
    - Automatic pre-restore snapshot taken prior to overwrite.
    - Restricted strictly to Administrators.
    """
    service = BackupService(db)
    actor = {
        "id": str(current_user.id if hasattr(current_user, "id") else current_user.get("_id", "")),
        "email": getattr(current_user, "email", current_user.get("email", "")),
        "role": getattr(current_user, "role", current_user.get("role", "")),
    }

    try:
        result = await service.restore_production(
            backup_id=backup_id,
            request=body,
            actor=actor
        )
        return result
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{backup_id}")
async def delete_backup(
    backup_id: str,
    current_user=Depends(RoleChecker([UserRole.ADMIN])),
    db=Depends(get_database),
):
    """
    Safely deletes a backup archive from disk and marks record as DELETED.
    Restricted strictly to Administrators.
    """
    service = BackupService(db)
    actor = {
        "id": str(current_user.id if hasattr(current_user, "id") else current_user.get("_id", "")),
        "email": getattr(current_user, "email", current_user.get("email", "")),
        "role": getattr(current_user, "role", current_user.get("role", "")),
    }
    try:
        await service.delete_backup(backup_id, actor=actor)
        return {"message": f"Backup '{backup_id}' deleted successfully"}
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
