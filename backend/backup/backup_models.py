from enum import Enum
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class BackupStatus(str, Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CORRUPTED = "CORRUPTED"
    DELETED = "DELETED"


class BackupType(str, Enum):
    SCHEDULED = "SCHEDULED"
    MANUAL = "MANUAL"
    SNAPSHOT = "SNAPSHOT"


class RetentionClass(str, Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    MANUAL = "MANUAL"


class VerificationStatus(str, Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    CORRUPTED = "CORRUPTED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class BackupMetadata(BaseModel):
    backup_id: str
    database_name: str
    filename: str
    filepath: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    size_bytes: int = 0
    checksum_sha256: Optional[str] = None
    status: BackupStatus = BackupStatus.RUNNING
    duration_seconds: float = 0.0
    backup_type: BackupType = BackupType.MANUAL
    verification_status: VerificationStatus = VerificationStatus.PENDING
    last_verified_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retention_class: RetentionClass = RetentionClass.DAILY
    deleted_at: Optional[datetime] = None
    is_protected: bool = False
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        use_enum_values = True


class BackupOut(BaseModel):
    backup_id: str
    database_name: str
    filename: str
    created_at: datetime
    size_bytes: int
    checksum_sha256: Optional[str] = None
    status: str
    duration_seconds: float
    backup_type: str
    verification_status: str
    last_verified_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retention_class: str
    deleted_at: Optional[datetime] = None
    is_protected: bool = False


class BackupListResponse(BaseModel):
    total: int
    skip: int
    limit: int
    items: List[BackupOut]


class BackupStatsOut(BaseModel):
    total_backups: int
    active_backups: int
    total_storage_bytes: int
    last_successful_backup: Optional[datetime] = None
    last_failed_backup: Optional[datetime] = None
    verified_count: int
    corrupted_count: int
    failed_count: int
    allow_production_restore: bool = False


class RestoreTestResult(BaseModel):
    backup_id: str
    test_database: str
    success: bool
    duration_seconds: float
    checksum_verified: bool
    collections_found: List[str]
    total_documents_restored: int
    details: Dict[str, Any]
    error_message: Optional[str] = None


class ProductionRestoreRequest(BaseModel):
    confirm_production_overwrite: bool
    target_database_name: str
    create_pre_restore_snapshot: bool = True
    reason: str = "Disaster Recovery"


class ProductionRestoreResult(BaseModel):
    backup_id: str
    target_database: str
    success: bool
    pre_restore_snapshot_id: Optional[str] = None
    duration_seconds: float
    error_message: Optional[str] = None
