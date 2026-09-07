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


class SLAStatus(str, Enum):
    ON_TRACK = "ON_TRACK"
    AT_RISK = "AT_RISK"
    BREACHED = "BREACHED"



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
    attachments: Optional[List[str]] = []
    keywords: Optional[List[str]] = []
    resolution_note: Optional[str] = None


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
    routing_reason: Optional[str] = None
    keywords: Optional[List[str]] = None
    resolution_note: Optional[str] = None


class StatusUpdateRequest(BaseModel):
    """Request body for updating ticket status."""
    status: TicketStatus


class TicketResolveRequest(BaseModel):
    """Request body for resolving a ticket with a resolution note."""
    resolution_note: str


class SendTicketResponseRequest(BaseModel):
    """Request body for sending an official response to the ticket creator."""
    response_text: str


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
    routing_reason: Optional[str] = None
    attachments: List[str] = []
    keywords: List[str] = []
    resolution_note: Optional[str] = None
    # SLA Fields
    sla_deadline: Optional[datetime] = None
    sla_status: SLAStatus = SLAStatus.ON_TRACK
    sla_breached_at: Optional[datetime] = None
    sla_response_deadline: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True



# ──────────────────────────────────────────────
# SLA Policy Schemas
# ──────────────────────────────────────────────

class SLAPolicyOut(BaseModel):
    """SLA Policy definition for each priority level."""
    priority: TicketPriority
    response_time_hours: float       # Max time to first response
    resolution_time_hours: float     # Max time to resolve
    at_risk_threshold_pct: float = 0.20  # Trigger AT_RISK when < 20% time left


class SLAPolicyUpdate(BaseModel):
    response_time_hours: Optional[float] = None
    resolution_time_hours: Optional[float] = None
    at_risk_threshold_pct: Optional[float] = None


class SLAAlertOut(BaseModel):
    """An active SLA warning for a specific ticket."""
    ticket_id: str
    subject: str
    priority: TicketPriority
    sla_status: SLAStatus
    sla_deadline: Optional[datetime] = None
    time_remaining_minutes: Optional[int] = None
    assigned_agent_id: Optional[str] = None
    created_at: datetime


class SLATicketDetailOut(BaseModel):
    """Full SLA detail for a specific ticket."""
    ticket_id: str
    subject: Optional[str] = None
    priority: TicketPriority
    sla_status: SLAStatus
    sla_deadline: Optional[datetime] = None
    sla_response_deadline: Optional[datetime] = None
    sla_breached_at: Optional[datetime] = None
    time_remaining_minutes: Optional[int] = None
    pct_consumed: Optional[float] = None
    policy: Optional[dict] = None


class SLAScanResult(BaseModel):
    scanned: int
    at_risk: int
    breached: int
    alerted: int


class RoutingResult(BaseModel):
    id: Optional[str] = None
    ticket_id: str
    selected_team: Optional[str] = None
    selected_agent: Optional[str] = None
    team_name: str
    agent_name: str
    confidence_score: float
    match_quality: str
    routing_reason: str
    created_at: datetime


class KnowledgeBaseItem(BaseModel):
    title: str
    category: str
    keywords: List[str]
    auto_response: str
    suggestions: List[str]
    confidence_threshold: float = 0.7
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AIHistoryRecord(BaseModel):
    ticket_id: str
    generated_response: str
    suggestions: List[str]
    confidence_score: float
    intent: str
    accepted: bool = False
    resolved: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


# ──────────────────────────────────────────────
# Chatbot Schemas
# ──────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str # "user", "assistant", "system"
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    suggested_actions: List[str] = []
    can_escalate: bool = False
    intent: Optional[str] = None
    confidence_score: float = 0.8
    source: str = "llm" # "knowledge_base" or "llm" or "fallback"


class ChatEscalateRequest(BaseModel):
    messages: List[ChatMessage]
    custom_subject: Optional[str] = None
    attachments: Optional[List[str]] = []


# ──────────────────────────────────────────────
# Intelligent Triage Schemas
# ──────────────────────────────────────────────

class SimilarTicketOut(BaseModel):
    ticket_id: str
    subject: str
    category: str
    subcategory: Optional[str] = None
    priority: TicketPriority
    status: TicketStatus
    similarity_score: float  # 0 to 100%
    resolution_note: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None


class BestSolutionOut(BaseModel):
    recommended_solution: str
    confidence_score: float  # 0 to 100%
    source_type: str  # "HISTORICAL_TICKET", "KNOWLEDGE_BASE", "AI_SYNTHESIS"
    source_reference: Optional[str] = None  # e.g. "Ticket #E4A19B" or "KB: Réinitialisation VPN"
    actionable_steps: List[str] = []
    key_findings: List[str] = []


class CannedResponseTemplate(BaseModel):
    id: str
    category: str  # "RESOLUTION", "CLARIFICATION", "IN_PROGRESS", "ESCALATION"
    title: str
    preview_text: str
    full_body: str


class IntelligentTriageResult(BaseModel):
    ticket_id: str
    is_repetitive: bool
    recurrence_count: int
    repetitive_reason: Optional[str] = None
    similarity_threshold_used: float = 65.0
    similar_tickets: List[SimilarTicketOut] = []
    best_solution: BestSolutionOut
    canned_responses: List[CannedResponseTemplate] = []
    intent: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ──────────────────────────────────────────────
# Predictive Analytics & Dashboard Schemas
# ──────────────────────────────────────────────

class VolumeTrendPoint(BaseModel):
    date: str  # e.g. "2026-09-01" or "Semaine 35"
    label: str
    total_tickets: int
    resolved_count: int
    urgent_count: int


class CategoryBreakdown(BaseModel):
    category: str
    count: int
    percentage: float
    avg_resolution_hours: float


class AgentPerformanceOut(BaseModel):
    agent_id: str
    agent_name: str
    email: str
    skills: List[str] = []
    is_available: bool
    workload: int
    assigned_count: int
    resolved_count: int
    avg_resolution_hours: float
    sla_compliance_pct: float
    efficiency_rating: str  # "Excellent", "Bon", "En progression"


class MTTRByPriority(BaseModel):
    priority: TicketPriority
    avg_resolution_hours: float
    sla_target_hours: float
    is_within_sla: bool


class MTTRMetricsOut(BaseModel):
    overall_avg_hours: float
    by_priority: List[MTTRByPriority] = []
    by_category: List[CategoryBreakdown] = []
    sla_compliance_overall_pct: float


class StrategicRecurrentIssue(BaseModel):
    cluster_id: str
    title: str
    category: str
    recurrence_count: int
    impact_level: str  # "CRITIQUE", "ÉLEVÉ", "MOYEN"
    estimated_hours_lost: float
    root_cause_analysis: str
    ai_strategic_recommendation: str
    preventive_action_plan: List[str] = []
    sample_ticket_ids: List[str] = []


class AIPredictiveInsights(BaseModel):
    forecast_summary: str
    predicted_volume_next_week: int
    volume_growth_trend_pct: float
    predicted_spike_risk: str  # "ÉLEVÉ", "MODÉRÉ", "FAIBLE"
    peak_time_windows: List[str] = []
    strategic_issues: List[StrategicRecurrentIssue] = []
    recommended_focus_areas: List[str] = []


class SummaryKPIs(BaseModel):
    total_tickets: int
    open_tickets: int
    in_progress_tickets: int
    resolved_tickets: int
    resolution_rate_pct: float
    overall_mttr_hours: float
    overall_sla_compliance_pct: float
    critical_recurring_count: int


class AnalyticsDashboardOut(BaseModel):
    kpis: SummaryKPIs
    volume_trends: List[VolumeTrendPoint] = []
    category_distribution: List[CategoryBreakdown] = []
    agent_performances: List[AgentPerformanceOut] = []
    mttr_metrics: MTTRMetricsOut
    predictive_insights: AIPredictiveInsights
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ──────────────────────────────────────────────
# Agent Assistant (Copilot) Schemas
# ──────────────────────────────────────────────

class ThreadSummaryOut(BaseModel):
    ticket_id: str
    summary: str
    problem_statement: str
    actions_already_taken: List[str] = []
    current_blocker: Optional[str] = None
    suggested_next_step: str
    urgency_evaluation: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class SuggestedActionItem(BaseModel):
    id: str
    action_type: str  # "COMMUNICATION", "DIAGNOSTIC", "SYSTEM", "ESCALATION"
    title: str
    description: str
    snippet_to_insert: Optional[str] = None
    impact: str  # "HIGH", "MEDIUM", "LOW"
    category: str


class InternalDocItem(BaseModel):
    id: str
    title: str
    category: str
    tags: List[str] = []
    content_snippet: str
    full_content: str
    relevance_score: float
    source_type: str = "SOP_INTERNE"  # "SOP_INTERNE", "GUIDE_SECURITE_ISO27001", "BASE_CONNAISSANCES"


