from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Any
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    USER = "USER"
    AGENT = "AGENT"
    ADMIN = "ADMIN"


class TicketStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class TicketPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class TicketChannel(str, Enum):
    WEB = "WEB"
    EMAIL = "EMAIL"
    CHAT = "CHAT"


# ──────────────────────────────────────────────
# User Schemas
# ──────────────────────────────────────────────

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    role: UserRole = UserRole.USER
    is_active: bool = True
    two_factor_enabled: bool = False


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserOut(BaseModel):
    """
    Uses `id` as the primary key field.
    Both `id` and `_id` are populated by MongoModel.format_id before serialization.
    """
    id: str
    email: EmailStr
    full_name: Optional[str] = None
    role: UserRole
    is_active: bool
    two_factor_enabled: bool = False
    created_at: datetime

    class Config:
        populate_by_name = True


# ──────────────────────────────────────────────
# Auth Schemas
# ──────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(Token):
    user: UserOut


class LoginResponse2FA(BaseModel):
    requires_2fa: bool
    email: str
    message: str


class Verify2FARequest(BaseModel):
    email: EmailStr
    code: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class TokenRefresh(BaseModel):
    refresh_token: str


# ──────────────────────────────────────────────
# Agent Schemas
# ──────────────────────────────────────────────

class AgentBase(BaseModel):
    user_id: str
    skills: List[str] = []
    is_available: bool = True
    workload: int = 0


class AgentCreate(AgentBase):
    pass


class AgentUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    skills: Optional[List[str]] = None
    is_available: Optional[bool] = None


class AgentOut(BaseModel):
    id: str
    user_id: str
    skills: List[str] = []
    is_available: bool
    workload: int

    class Config:
        populate_by_name = True


# ──────────────────────────────────────────────
# Team Schemas
# ──────────────────────────────────────────────

class TeamBase(BaseModel):
    name: str
    description: Optional[str] = None
    competencies: List[str] = []
    agent_ids: List[str] = []


class TeamCreate(TeamBase):
    pass


class TeamUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    competencies: Optional[List[str]] = None


class TeamOut(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    competencies: List[str] = []
    agent_ids: List[str] = []

    class Config:
        populate_by_name = True


# ──────────────────────────────────────────────
# Ticket Schemas
# ──────────────────────────────────────────────

class TicketBase(BaseModel):
    subject: str
    description: str
    category: str
    subcategory: Optional[str] = None
    priority: TicketPriority = TicketPriority.LOW
    channel: TicketChannel = TicketChannel.WEB


class TicketCreate(TicketBase):
    pass


class TicketUpdate(BaseModel):
    subject: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    status: Optional[TicketStatus] = None
    priority: Optional[TicketPriority] = None
    assigned_agent_id: Optional[str] = None


class StatusUpdateRequest(BaseModel):
    """Request body for updating ticket status."""
    status: TicketStatus


class AssignAgentRequest(BaseModel):
    """Request body for assigning an agent to a ticket."""
    agent_id: str


class TicketOut(BaseModel):
    id: str
    subject: str
    description: str
    category: str
    subcategory: Optional[str] = None
    priority: TicketPriority
    channel: TicketChannel
    status: TicketStatus
    user_id: str
    assigned_agent_id: Optional[str] = None
    attachments: List[str] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True
