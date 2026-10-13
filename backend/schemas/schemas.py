import uuid
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Any, Dict, Union
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    USER = "USER"
    AGENT = "AGENT"
    SUPERVISOR = "SUPERVISOR"
    ADMIN = "ADMIN"


class TicketStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    PENDING = "PENDING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class TicketPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class ImpactLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class UrgencyLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class PrioritySource(str, Enum):
    MANUAL = "manual"
    AI = "ai"
    ITIL_MATRIX = "itil_matrix"


class TicketChannel(str, Enum):
    WEB = "WEB"
    EMAIL = "EMAIL"
    CHAT = "CHAT"


class SLAStatus(str, Enum):
    ON_TRACK = "ON_TRACK"
    AT_RISK = "AT_RISK"
    BREACHED = "BREACHED"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"



# ──────────────────────────────────────────────
# User Schemas
# ──────────────────────────────────────────────

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    department: Optional[str] = None
    role: UserRole = UserRole.USER
    is_active: bool = True
    two_factor_enabled: bool = False
    auth_provider: str = "local"
    ldap_username: Optional[str] = None


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    department: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserOut(BaseModel):
    """
    Uses `id` as the primary key field.
    Both `id` and `_id` are populated by MongoModel.format_id before serialization.
    """
    id: str
    email: str
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    department: Optional[str] = None
    role: UserRole
    is_active: bool
    two_factor_enabled: bool = False
    auth_provider: str = "local"
    ldap_username: Optional[str] = None
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
    email: str  # Can be an email address or an LDAP / Active Directory username
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
    new_password: str = Field(..., min_length=8, description="New password with minimum 8 characters")


class TokenRefresh(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    """Optional payload during logout to explicitly revoke a refresh token as well as the bearer access token."""
    refresh_token: Optional[str] = None


class TokenBlacklistDoc(BaseModel):
    """Document schema for revoked tokens stored in MongoDB token_blacklist collection."""
    jti: str
    user_id: Optional[str] = None
    token_type: str = "access"  # "access" or "refresh"
    expires_at: datetime
    revoked_at: datetime = Field(default_factory=datetime.utcnow)
    reason: str = "logout"


# ──────────────────────────────────────────────

# 2FA Management Schemas (Profile)
# ──────────────────────────────────────────────

class TwoFactorStatusOut(BaseModel):
    """Current 2FA status for the authenticated user. Never exposes OTP code."""
    enabled: bool
    method: str = "email"


class TwoFactorEnableRequest(BaseModel):
    """Step 1 — request OTP to be sent to the user's registered email."""
    pass  # No body required; user is identified via JWT


class TwoFactorEnableConfirm(BaseModel):
    """Step 2 — confirm activation with the OTP received by email."""
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$",
                      description="6-digit numeric OTP sent by email")


class TwoFactorDisableRequest(BaseModel):
    """Step 1 — request OTP to be sent to the user's registered email for disable confirmation."""
    password: str = Field(..., min_length=1, description="Current account password for identity verification")


class TwoFactorDisableConfirm(BaseModel):
    """Step 2 — confirm disable with OTP received by email."""
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$",
                      description="6-digit numeric OTP sent by email")


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
# Ticket Schemas & Action History (ISO 27001 Audit)
# ──────────────────────────────────────────────

class TicketActionType(str, Enum):
    CREATED = "CREATED"
    STATUS_CHANGED = "STATUS_CHANGED"
    AGENT_ASSIGNED = "AGENT_ASSIGNED"
    AGENT_REASSIGNED = "AGENT_REASSIGNED"
    PRIORITY_CHANGED = "PRIORITY_CHANGED"
    ITIL_CALCULATED = "ITIL_CALCULATED"
    SLA_RECALCULATED = "SLA_RECALCULATED"
    RESPONSE_SENT = "RESPONSE_SENT"
    RESOLUTION_RECORDED = "RESOLUTION_RECORDED"
    ATTACHMENT_UPLOADED = "ATTACHMENT_UPLOADED"
    SATISFACTION_SUBMITTED = "SATISFACTION_SUBMITTED"


class TicketActionLog(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    actor_id: str
    actor_name: str
    actor_role: str
    action_type: TicketActionType
    details: Dict[str, Any] = Field(default_factory=dict)
    comment: Optional[str] = None


class TicketBase(BaseModel):
    subject: str
    description: str
    category: str
    subcategory: Optional[str] = None
    priority: TicketPriority = TicketPriority.LOW
    impact: Optional[ImpactLevel] = None
    urgency: Optional[UrgencyLevel] = None
    priority_source: Optional[PrioritySource] = None
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
    impact: Optional[ImpactLevel] = None
    urgency: Optional[UrgencyLevel] = None
    priority_source: Optional[PrioritySource] = None
    assigned_agent_id: Optional[str] = None
    routing_reason: Optional[str] = None
    keywords: Optional[List[str]] = None
    resolution_note: Optional[str] = None

    class Config:
        # Reject fields that are not part of the public update contract instead
        # of silently accepting them from a caller.
        extra = "forbid"


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


class SubmitSatisfactionRequest(BaseModel):
    """Request body for customer satisfaction rating (1-5) and optional comment."""
    rating: int = Field(..., ge=1, le=5, description="Satisfaction score between 1 and 5")
    comment: Optional[str] = Field(None, max_length=1000)


class PriorityCalculationRequest(BaseModel):
    """Request body to preview ITIL priority from impact and urgency."""
    impact: ImpactLevel
    urgency: UrgencyLevel


class PriorityCalculationResponse(BaseModel):
    """Calculated ITIL priority response."""
    impact: ImpactLevel
    urgency: UrgencyLevel
    priority: TicketPriority
    source: PrioritySource = PrioritySource.ITIL_MATRIX


# ──────────────────────────────────────────────
# Ticket Attachment Schemas
# ──────────────────────────────────────────────

class AttachmentOut(BaseModel):
    """Structured metadata for a ticket attachment."""
    id: str
    ticket_id: str
    original_filename: str
    stored_filename: str
    mime_type: str
    size_bytes: int
    uploaded_by: str
    created_at: datetime


class AttachmentUploadResponse(BaseModel):
    """Response returned after a successful attachment upload."""
    attachment: AttachmentOut
    message: str = "Pièce jointe téléversée avec succès"


class TicketOut(BaseModel):
    id: str
    subject: str
    description: str
    category: str
    subcategory: Optional[str] = None
    priority: TicketPriority
    impact: Optional[ImpactLevel] = None
    urgency: Optional[UrgencyLevel] = None
    priority_source: Optional[PrioritySource] = None
    channel: TicketChannel
    status: TicketStatus
    user_id: str
    assigned_agent_id: Optional[str] = None
    routing_reason: Optional[str] = None
    attachments: List[Union[AttachmentOut, str]] = []
    keywords: List[str] = []
    resolution_note: Optional[str] = None
    responses: List[Dict[str, Any]] = []
    # Customer Satisfaction (CSAT)
    satisfaction_rating: Optional[int] = Field(None, ge=1, le=5)
    satisfaction_comment: Optional[str] = None
    satisfaction_submitted_at: Optional[datetime] = None
    # SLA Fields
    sla_deadline: Optional[datetime] = None
    sla_status: SLAStatus = SLAStatus.ON_TRACK
    sla_breached_at: Optional[datetime] = None
    sla_response_deadline: Optional[datetime] = None
    sla_applied_rule: Optional[Dict[str, Any]] = None
    # Reassignment Tracking & Feedback Loop
    reassignment_count: int = 0
    reassigned_from_agent_ids: List[str] = []
    reassignment_history: List[Dict[str, Any]] = []
    # ISO 27001 Action History Audit Trail
    action_history: List[TicketActionLog] = []
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
    category: Optional[str] = None
    subcategory: Optional[str] = None


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
    threshold_id: Optional[str] = None
    channel: Optional[str] = None
    recipient_email: Optional[str] = None


class SLATicketDetailOut(BaseModel):
    """Full SLA detail for a specific ticket."""
    ticket_id: str
    subject: Optional[str] = None
    priority: TicketPriority
    sla_status: SLAStatus
    sla_deadline: Optional[datetime] = None
    sla_response_deadline: Optional[datetime] = None
    sla_breached_at: Optional[datetime] = None
    sla_paused_at: Optional[datetime] = None
    sla_total_paused_seconds: Optional[float] = None
    time_remaining_minutes: Optional[int] = None
    remaining_seconds: Optional[float] = None
    remaining_percentage: Optional[float] = None
    crossed_threshold: Optional[str] = None
    pct_consumed: Optional[float] = None
    policy: Optional[dict] = None
    applied_rule: Optional[Dict[str, Any]] = None


class SLACalculateRequest(BaseModel):
    """Request payload to preview SLA deadlines."""
    priority: TicketPriority
    category: Optional[str] = None
    subcategory: Optional[str] = None
    created_at: Optional[datetime] = None


class SLACalculateResponse(BaseModel):
    """Computed SLA response with deadlines and audit rule details."""
    priority: TicketPriority
    category: Optional[str] = None
    subcategory: Optional[str] = None
    response_time_hours: float
    resolution_time_hours: float
    response_deadline: datetime
    resolution_deadline: datetime
    rule_level: str
    applied_rule: Dict[str, Any]


class SLAScanResult(BaseModel):
    scanned: int
    on_track: int = 0
    at_risk: int
    breached: int
    paused: int = 0
    alerted: int


# ──────────────────────────────────────────────
# SLA Risk & Alert Detection Schemas (Step 4)
# ──────────────────────────────────────────────

class SLAWarningThreshold(BaseModel):
    id: str
    type: str  # "percentage" or "time_minutes"
    value: float
    label: str


class SLARiskConfigOut(BaseModel):
    warning_thresholds: List[SLAWarningThreshold] = []
    risk_alert_enabled: bool = True
    breach_alert_enabled: bool = True
    sms_alerts_enabled: bool = True
    email_alerts_enabled: bool = True


class SLARiskConfigUpdate(BaseModel):
    warning_thresholds: Optional[List[SLAWarningThreshold]] = None
    risk_alert_enabled: Optional[bool] = None
    breach_alert_enabled: Optional[bool] = None
    sms_alerts_enabled: Optional[bool] = None
    email_alerts_enabled: Optional[bool] = None


class SLARiskEvaluationResult(BaseModel):
    ticket_id: str
    state: SLAStatus
    remaining_seconds: Optional[float] = None
    remaining_percentage: Optional[float] = None
    deadline: Optional[datetime] = None
    crossed_threshold: Optional[str] = None
    crossed_threshold_label: Optional[str] = None
    should_alert: bool = False


class SLARiskKPISummary(BaseModel):
    total_active_slas: int
    on_track_count: int
    at_risk_count: int
    breached_count: int
    paused_count: int
    compliance_pct: Optional[float] = None
    avg_remaining_minutes: Optional[float] = None


class SLARiskOverviewOut(BaseModel):
    kpis: SLARiskKPISummary
    at_risk_tickets: List[Dict[str, Any]] = []
    active_alerts: List[Dict[str, Any]] = []


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
# AI Ticket Classification Schemas (Step 1)
# ──────────────────────────────────────────────

class TicketClassificationRequest(BaseModel):
    subject: str = Field(..., min_length=2, max_length=255, description="Objet ou titre du problème")
    description: str = Field(..., min_length=5, max_length=5000, description="Description détaillée de l'incident")


class TicketClassificationResponse(BaseModel):
    category: str = Field(..., description="Catégorie issue de la taxonomie GEISER")
    subcategory: str = Field(..., description="Sous-catégorie issue de la taxonomie GEISER")
    priority: TicketPriority = Field(..., description="Priorité estimée (LOW, MEDIUM, HIGH, URGENT)")
    tags: List[str] = Field(default_factory=list, description="Mots-clés et tags techniques")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Indicateur de confiance interne entre 0.0 et 1.0")
    reasoning: str = Field(..., min_length=5, description="Explication courte et compréhensible")


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
    avg_resolution_hours: Optional[float] = None


class AgentPerformanceOut(BaseModel):
    agent_id: str
    agent_name: str
    email: str
    skills: List[str] = []
    is_available: bool
    workload: int
    assigned_count: int
    resolved_count: int
    avg_resolution_hours: Optional[float] = None
    sla_compliance_pct: Optional[float] = None
    efficiency_rating: str  # "Excellent", "Bon", "En progression"
    avg_csat_score: Optional[float] = None
    csat_responses_count: int = 0


class MTTRByPriority(BaseModel):
    priority: TicketPriority
    avg_resolution_hours: Optional[float] = None
    sla_target_hours: float
    is_within_sla: Optional[bool] = None


class MTTRMetricsOut(BaseModel):
    overall_avg_hours: Optional[float] = None
    by_priority: List[MTTRByPriority] = []
    by_category: List[CategoryBreakdown] = []
    sla_compliance_overall_pct: Optional[float] = None


class StrategicRecurrentIssue(BaseModel):
    cluster_id: str
    title: str
    category: str
    recurrence_count: int
    impact_level: str  # "CRITIQUE", "ÉLEVÉ", "MOYEN"
    estimated_hours_lost: Optional[float] = None
    root_cause_analysis: str
    ai_strategic_recommendation: str
    preventive_action_plan: List[str] = []
    sample_ticket_ids: List[str] = []


class DailyForecastPoint(BaseModel):
    date: str  # YYYY-MM-DD
    day_name: str  # "Lun", "Mar", etc.
    predicted_count: int
    lower_bound: int
    upper_bound: int
    confidence_pct: float = 85.0


class VolumeForecastOut(BaseModel):
    forecast_days: int = 7
    daily_forecasts: List[DailyForecastPoint] = []
    total_predicted_volume: Optional[int] = None
    historical_daily_avg: Optional[float] = None
    growth_trend_pct: Optional[float] = None
    spike_risk: Optional[str] = None  # "ÉLEVÉ", "MODÉRÉ", "FAIBLE"
    confidence_level: str = "MEDIUM"  # "HIGH", "MEDIUM", "LOW"
    is_baseline: bool = False
    peak_days: List[str] = []
    data_points_analyzed: int = 0


class ResolutionTimePredictionIn(BaseModel):
    category: Optional[str] = None
    subcategory: Optional[str] = None
    priority: Optional[TicketPriority] = None
    impact: Optional[ImpactLevel] = None
    urgency: Optional[UrgencyLevel] = None
    assigned_team_id: Optional[str] = None
    assigned_agent_id: Optional[str] = None
    ticket_id: Optional[str] = None


class ResolutionTimeFactor(BaseModel):
    factor: str
    impact_hours: float
    description: str


class ResolutionTimePredictionOut(BaseModel):
    predicted_hours: float
    predicted_duration_formatted: str
    confidence_score: float  # 0.0 - 100.0
    confidence_level: str  # "HIGH", "MEDIUM", "LOW"
    sla_target_hours: Optional[float] = None
    estimated_sla_compliance: bool = True
    historical_sample_size: int = 0
    baseline_used: str  # "category_priority", "category", "priority", "global"
    contributing_factors: List[ResolutionTimeFactor] = []
    explanation: str


class SLABreachRiskTicket(BaseModel):
    ticket_id: str
    reference: str
    subject: str
    priority: TicketPriority
    status: TicketStatus
    category: str
    subcategory: Optional[str] = None
    assigned_agent_id: Optional[str] = None
    assigned_agent_name: Optional[str] = None
    created_at: datetime
    sla_deadline: Optional[datetime] = None
    remaining_hours: Optional[float] = None
    predicted_remaining_hours: float
    breach_probability_pct: float  # 0.0 - 100.0
    risk_level: str  # "CRITIQUE", "ÉLEVÉ", "MODÉRÉ", "FAIBLE"
    risk_factors: List[str] = []
    recommended_action: str


class SLABreachRisksOut(BaseModel):
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)
    total_active_tickets: int = 0
    at_risk_count: int = 0
    critical_count: int = 0
    tickets: List[SLABreachRiskTicket] = []
    summary: str = ""


class RecurringTicketSummary(BaseModel):
    ticket_id: str
    reference: str
    subject: str
    status: str
    priority: str
    category: str
    created_at: datetime
    similarity_to_cluster: float


class RecurringClusterOut(BaseModel):
    cluster_id: str
    title: str
    category: str
    subcategory: Optional[str] = None
    keywords: List[str] = []
    occurrence_count: int
    status: str = "ACTIVE"  # "ACTIVE" ou "RESOLVED"
    impact_level: str = "MOYEN"  # "CRITIQUE", "ÉLEVÉ", "MOYEN"
    estimated_hours_lost: Optional[float] = None
    first_seen: datetime
    last_seen: datetime
    average_similarity_pct: float
    root_cause_analysis: str
    common_solutions: List[str] = []
    preventive_action_plan: List[str] = []
    sample_tickets: List[RecurringTicketSummary] = []


class RecurringIssuesResponse(BaseModel):
    total_clusters: int = 0
    active_clusters: int = 0
    total_tickets_in_clusters: int = 0
    clusters: List[RecurringClusterOut] = []
    detection_method: str = "HYBRID_SEMANTIC_KEYWORDS"


class AIPredictiveInsights(BaseModel):
    forecast_summary: str
    predicted_volume_next_week: Optional[int] = None
    volume_growth_trend_pct: Optional[float] = None
    predicted_spike_risk: Optional[str] = None  # "ÉLEVÉ", "MODÉRÉ", "FAIBLE"
    peak_time_windows: List[str] = []
    strategic_issues: List[StrategicRecurrentIssue] = []
    recommended_focus_areas: List[str] = []
    # Enhanced predictive analytics fields
    volume_forecast: Optional[VolumeForecastOut] = None
    sla_breach_risks: Optional[SLABreachRisksOut] = None
    recurring_clusters: List[RecurringClusterOut] = []


class CSATTrendPoint(BaseModel):
    date: str
    label: str
    avg_rating: Optional[float] = None
    count: int


class CSATAgentStat(BaseModel):
    agent_id: str
    agent_name: Optional[str] = None
    avg_rating: float
    count: int


class CSATCategoryStat(BaseModel):
    category: str
    avg_rating: float
    count: int


class CSATRecentFeedback(BaseModel):
    ticket_id: str
    rating: int
    comment: Optional[str] = None
    category: Optional[str] = None
    agent_id: Optional[str] = None
    submitted_at: Optional[datetime] = None


class CSATAnalyticsOut(BaseModel):
    total_ratings: int = 0
    avg_rating: Optional[float] = None
    satisfaction_rate_pct: Optional[float] = None  # % of ratings >= 4
    distribution: Dict[str, int] = Field(default_factory=lambda: {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0})
    trend: List[CSATTrendPoint] = []
    by_agent: List[CSATAgentStat] = []
    by_category: List[CSATCategoryStat] = []
    recent_feedback: List[CSATRecentFeedback] = []
    period_days: int = 30


class SummaryKPIs(BaseModel):
    total_tickets: int
    open_tickets: int
    in_progress_tickets: int
    resolved_tickets: int
    resolution_rate_pct: Optional[float] = None
    overall_mttr_hours: Optional[float] = None
    overall_sla_compliance_pct: Optional[float] = None
    critical_recurring_count: int = 0
    avg_response_hours: Optional[float] = None
    satisfaction_avg: Optional[float] = None
    satisfaction_responses_count: int = 0
    positive_satisfaction_rate_pct: Optional[float] = None


class AnalyticsDashboardOut(BaseModel):
    kpis: SummaryKPIs
    volume_trends: List[VolumeTrendPoint] = []
    category_distribution: List[CategoryBreakdown] = []
    agent_performances: List[AgentPerformanceOut] = []
    mttr_metrics: MTTRMetricsOut
    predictive_insights: AIPredictiveInsights
    csat: Optional[CSATAnalyticsOut] = None
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


# ──────────────────────────────────────────────
# Module 3: Suivi, Reporting & Manager Schemas
# ──────────────────────────────────────────────

class TicketSatisfactionRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="CSAT Rating between 1 and 5 stars")
    comment: Optional[str] = Field(None, max_length=1000)


class NotificationOut(BaseModel):
    id: str
    user_id: str
    user_email: Optional[str] = None
    ticket_id: Optional[str] = None
    channel: str  # "EMAIL", "SMS", "IN_APP"
    title: str
    message: str
    status: str  # "SENT", "DELIVERED", "FAILED", "SKIPPED_DUPLICATE"
    provider: Optional[str] = None
    provider_message_id: Optional[str] = None
    event_type: Optional[str] = None
    error_detail: Optional[str] = None
    recipient: Optional[str] = None
    attempts: int = 0
    max_retries: int = 5
    next_retry_at: Optional[datetime] = None
    error_type: Optional[str] = None
    idempotency_key: Optional[str] = None
    retry_history: Optional[List[Dict[str, Any]]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


class SMSTestRequest(BaseModel):
    to: str = Field(..., description="Destination phone number (E.164 format, e.g. +33612345678 or +216...)")
    message: str = Field(..., min_length=1, max_length=1600, description="SMS message content")


class SMSTestResponse(BaseModel):
    success: bool
    status: str  # "sent", "failed", "simulated"
    provider: str
    message_id: Optional[str] = None
    to: str
    error: Optional[str] = None


class ManagerKPIs(BaseModel):
    total_tickets: int
    open_tickets: int
    in_progress_tickets: int
    resolved_tickets: int
    sla_compliance_pct: float
    avg_resolution_hours: float
    avg_first_response_hours: float
    avg_csat_score: float  # / 5.0
    csat_response_count: int


class ManagerTeamMetric(BaseModel):
    team_id: str
    team_name: str
    assigned_tickets: int
    resolved_tickets: int
    sla_compliance_pct: float
    avg_resolution_hours: float


class ManagerAgentMetric(BaseModel):
    agent_id: str
    agent_name: str
    email: str
    team_name: Optional[str] = None
    assigned_count: int
    resolved_count: int
    sla_compliance_pct: float
    avg_resolution_hours: float
    avg_csat_score: float
    efficiency_rating: str


class ManagerSatisfactionSummary(BaseModel):
    avg_score: float
    total_reviews: int
    distribution: Dict[str, int] = {}  # "5_star": 10, "4_star": 4, etc.
    recent_feedback: List[Dict[str, Any]] = []


class ManagerDashboardOut(BaseModel):
    kpis: ManagerKPIs
    team_metrics: List[ManagerTeamMetric] = []
    agent_metrics: List[ManagerAgentMetric] = []
    satisfaction_summary: ManagerSatisfactionSummary
    priority_breakdown: Dict[str, int] = {}
    filtered_tickets_count: int
    period_label: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ──────────────────────────────────────────────
# ISO/IEC 27001:2013 Security Audit Trail Schemas
# ──────────────────────────────────────────────

class AuditEventCategory(str, Enum):
    AUTH = "AUTH"
    ACCESS_CONTROL = "ACCESS_CONTROL"
    TICKET = "TICKET"
    SLA = "SLA"
    USER_MGMT = "USER_MGMT"
    TEAM_MGMT = "TEAM_MGMT"
    AI = "AI"
    TELECOM = "TELECOM"
    DATA_EXPORT = "DATA_EXPORT"
    SYSTEM = "SYSTEM"


class AuditSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class SecurityAuditLogOut(BaseModel):
    id: str
    timestamp: datetime
    actor_id: Optional[str] = None
    actor_email: Optional[str] = None
    actor_name: Optional[str] = None
    actor_role: Optional[str] = None
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    event_category: AuditEventCategory
    event_type: str
    severity: AuditSeverity
    target_resource_type: str
    target_resource_id: Optional[str] = None
    status: str = "SUCCESS"  # SUCCESS, FAILURE, DENIED
    details: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        populate_by_name = True


class AuditFilterParams(BaseModel):
    category: Optional[AuditEventCategory] = None
    severity: Optional[AuditSeverity] = None
    actor_id: Optional[str] = None
    actor_email: Optional[str] = None
    actor_role: Optional[str] = None
    target_resource_type: Optional[str] = None
    target_resource_id: Optional[str] = None
    status: Optional[str] = None
    event_type: Optional[str] = None
    search: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = 50
    skip: int = 0


class AuditStatsOut(BaseModel):
    total_events: int
    info_count: int
    warning_count: int
    critical_count: int
    login_successes: int
    login_failures: int
    access_denied_count: int
    ticket_events: int = 0
    user_mgmt_events: int = 0
    team_mgmt_events: int = 0


# ──────────────────────────────────────────────
# Module 4: Monitoring & Observability Schemas
# ──────────────────────────────────────────────

class ComponentHealthOut(BaseModel):
    name: str
    status: str  # "healthy", "degraded", "unhealthy", "not_configured"
    critical: bool = False
    latency_ms: Optional[float] = None
    details: Optional[str] = None


class SystemHealthOut(BaseModel):
    status: str  # "healthy", "degraded", "unhealthy"
    version: str
    server_time: str
    uptime_seconds: int
    components: List[Dict[str, Any]]
    summary: Dict[str, int]


class BackgroundJobOut(BaseModel):
    job_id: str
    name: str
    status: str  # "IDLE", "RUNNING", "SUCCESS", "FAILED"
    is_running: bool
    last_execution_at: Optional[str] = None
    last_success_at: Optional[str] = None
    last_failure_at: Optional[str] = None
    last_duration_seconds: Optional[float] = None
    last_error: Optional[str] = None
    success_count: int = 0
    failure_count: int = 0
    next_run_time: Optional[str] = None


class OperationalMetricsOut(BaseModel):
    tickets: Dict[str, int]
    sla: Dict[str, int]
    notifications: Dict[str, int]
    email_to_ticket: Dict[str, int]
    websockets: Dict[str, Any]
    security: Dict[str, Any]
    system: Dict[str, Any]




# ──────────────────────────────────────────────
# Module 5: AI/RAG Evaluation Schemas
# ──────────────────────────────────────────────

class ClassificationMetricOut(BaseModel):
    accuracy: float
    macro_f1: float
    correct: int
    total: int


class ClassificationEvalOut(BaseModel):
    metric_type: str
    dataset_size: int
    latency_ms: float
    fallback_used: bool
    llm_used: bool
    avg_confidence: float
    category: Dict[str, Any]
    subcategory: Dict[str, Any]
    priority: Dict[str, Any]
    confusion_matrix: Dict[str, Any]
    per_sample: List[Dict[str, Any]]


class RAGRetrievalEvalOut(BaseModel):
    metric_type: str
    dataset_size: int
    latency_ms: float
    hit_rate_at_k: float
    hits: int
    total_queries: int
    zero_result_queries: int
    avg_top_score: float
    per_query: List[Dict[str, Any]]


class AnswerQualityEvalOut(BaseModel):
    metric_type: str
    dataset_size: int
    avg_heuristic_quality_score: float
    per_query: List[Dict[str, Any]]
    note: str


class TriageEvalOut(BaseModel):
    metric_type: str
    dataset_size: int
    latency_ms: float
    accuracy: float
    correct: int
    total: int
    per_pair: List[Dict[str, Any]]


class AIEvalSummaryOut(BaseModel):
    category_accuracy: float
    category_f1: float
    subcategory_accuracy: float
    priority_accuracy: float
    rag_hit_rate: float
    rag_avg_score: float
    answer_quality_score: float
    triage_accuracy: float
    rag_contextual_precision: Optional[float] = None
    rag_contextual_recall: Optional[float] = None
    deepeval_faithfulness: Optional[float] = None
    deepeval_relevancy: Optional[float] = None


class AIEvaluationOut(BaseModel):
    evaluated_at: str
    overall_status: str
    total_latency_ms: float
    ai_provider: str
    model: str
    ollama_available: bool
    ollama_detail: str
    fallback_used: bool
    evaluation_framework: Optional[str] = "DeepEval"
    classification: Dict[str, Any]
    rag_retrieval: Dict[str, Any]
    answer_quality: Dict[str, Any]
    triage_similarity: Dict[str, Any]
    summary: AIEvalSummaryOut
