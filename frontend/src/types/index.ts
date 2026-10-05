export const UserRole = {
  USER: "USER",
  AGENT: "AGENT",
  SUPERVISOR: "SUPERVISOR",
  ADMIN: "ADMIN",
} as const;
export type UserRole = typeof UserRole[keyof typeof UserRole];

export const TicketStatus = {
  OPEN: "OPEN",
  IN_PROGRESS: "IN_PROGRESS",
  PENDING: "PENDING",
  RESOLVED: "RESOLVED",
  CLOSED: "CLOSED",
} as const;
export type TicketStatus = typeof TicketStatus[keyof typeof TicketStatus];

export const TicketPriority = {
  LOW: "LOW",
  MEDIUM: "MEDIUM",
  HIGH: "HIGH",
  URGENT: "URGENT",
} as const;
export type TicketPriority = typeof TicketPriority[keyof typeof TicketPriority];

export const ImpactLevel = {
  LOW: "LOW",
  MEDIUM: "MEDIUM",
  HIGH: "HIGH",
} as const;
export type ImpactLevel = typeof ImpactLevel[keyof typeof ImpactLevel];

export const UrgencyLevel = {
  LOW: "LOW",
  MEDIUM: "MEDIUM",
  HIGH: "HIGH",
} as const;
export type UrgencyLevel = typeof UrgencyLevel[keyof typeof UrgencyLevel];

export const PrioritySource = {
  MANUAL: "manual",
  AI: "ai",
  ITIL_MATRIX: "itil_matrix",
} as const;
export type PrioritySource = typeof PrioritySource[keyof typeof PrioritySource];

export const TicketChannel = {
  WEB: "WEB",
  EMAIL: "EMAIL",
  CHAT: "CHAT",
} as const;
export type TicketChannel = typeof TicketChannel[keyof typeof TicketChannel];

export const SLAStatus = {
  ON_TRACK: "ON_TRACK",
  AT_RISK: "AT_RISK",
  BREACHED: "BREACHED",
  PAUSED: "PAUSED",
  COMPLETED: "COMPLETED",
} as const;
export type SLAStatus = typeof SLAStatus[keyof typeof SLAStatus];

export type SLAPolicy = {
  priority: TicketPriority;
  response_time_hours: number;
  resolution_time_hours: number;
  at_risk_threshold_pct: number;
};

export type SLATicketDetail = {
  ticket_id: string;
  subject?: string;
  priority: TicketPriority;
  sla_status: SLAStatus;
  sla_deadline?: string;
  sla_response_deadline?: string;
  sla_breached_at?: string;
  time_remaining_minutes?: number;
  pct_consumed?: number;
  policy?: SLAPolicy;
  sla_paused_at?: string;
  sla_total_paused_seconds?: number;
};

export type SLAWarningThreshold = {
  id: string;
  type: 'percentage' | 'time_minutes';
  value: number;
  label: string;
};

export type SLARiskConfig = {
  key: string;
  warning_thresholds: SLAWarningThreshold[];
  risk_alert_enabled: boolean;
  breach_alert_enabled: boolean;
  sms_alerts_enabled: boolean;
  email_alerts_enabled: boolean;
};

export type SLARiskKPISummary = {
  total_active_slas: number;
  on_track_count: number;
  at_risk_count: number;
  breached_count: number;
  paused_count: number;
  compliance_pct: number;
  avg_remaining_minutes: number;
};

export type SLARiskOverview = {
  kpis: SLARiskKPISummary;
  at_risk_tickets: Array<{
    ticket_id: string;
    subject?: string;
    priority: TicketPriority;
    status: string;
    sla_status: string;
    sla_deadline?: string;
    time_remaining_minutes?: number;
    assigned_agent_id?: string;
    crossed_threshold?: string;
    created_at?: string;
  }>;
  active_alerts: Array<{
    id: string;
    ticket_id: string;
    subject?: string;
    priority?: string;
    sla_status?: string;
    alert_type?: string;
    threshold_id?: string;
    threshold_label?: string;
    recipient_email?: string;
    channel?: string;
    delivery_status?: string;
    created_at?: string;
  }>;
};

export type User = {
  id: string;
  email: string;
  full_name?: string;
  role: UserRole;
  is_active: boolean;
  two_factor_enabled?: boolean;
  auth_provider?: 'local' | 'ldap' | string;
  department?: string;
  ldap_username?: string;
  created_at: string;
};

export type Attachment = {
  id: string;
  ticket_id: string;
  original_filename: string;
  stored_filename: string;
  mime_type: string;
  size_bytes: number;
  uploaded_by: string;
  created_at: string;
};

export type Ticket = {
  id: string;
  subject: string;
  description: string;
  category: string;
  subcategory?: string;
  priority: TicketPriority;
  impact?: ImpactLevel;
  urgency?: UrgencyLevel;
  priority_source?: PrioritySource;
  channel: TicketChannel;
  status: TicketStatus;
  user_id: string;
  assigned_agent_id?: string | null;
  routing_reason?: string;
  attachments: (Attachment | string)[];
  keywords?: string[];
  sla_deadline?: string;
  sla_status?: SLAStatus;
  sla_breached_at?: string;
  sla_response_deadline?: string;
  resolution_note?: string;
  responses?: Array<{
    id?: string;
    sender_name?: string;
    role?: string;
    content: string;
    created_at?: string;
    is_internal?: boolean;
  }>;
  action_history?: Array<{
    id: string;
    timestamp: string;
    actor_id: string;
    actor_name: string;
    actor_role: string;
    action_type: string;
    details?: Record<string, any>;
    comment?: string;
  }>;
  // CSAT Customer Satisfaction
  satisfaction_rating?: number | null;
  satisfaction_comment?: string | null;
  satisfaction_submitted_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type TicketActionLog = {
  id: string;
  timestamp: string;
  actor_id: string;
  actor_name: string;
  actor_role: string;
  action_type: string;
  details?: Record<string, any>;
  comment?: string;
};


export type Agent = {
  id: string;
  user_id: string;
  skills: string[];
  is_available: boolean;
  workload: number;
};

export type Team = {
  id: string;
  name: string;
  competencies: string[];
  agent_ids: string[];
};

export type AuthResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};

/** Shape of the login response (token + user) */
export type LoginResponse = AuthResponse & {
  user: User;
};

export type RoutingResult = {
  id?: string;
  ticket_id: string;
  selected_team?: string;
  selected_agent?: string;
  team_name: string;
  agent_name: string;
  confidence_score: number;
  match_quality: string;
  routing_reason: string;
  created_at: string;
};

export type SimilarTicket = {
  ticket_id: string;
  subject: string;
  category: string;
  subcategory?: string;
  priority: TicketPriority;
  status: TicketStatus;
  similarity_score: number;
  resolution_note?: string;
  created_at: string;
  resolved_at?: string;
};

export type BestSolution = {
  recommended_solution: string;
  confidence_score: number;
  source_type: "HISTORICAL_TICKET" | "KNOWLEDGE_BASE" | "AI_SYNTHESIS" | string;
  source_reference?: string;
  actionable_steps: string[];
  key_findings: string[];
};

export type CannedResponseTemplate = {
  id: string;
  category: "RESOLUTION" | "CLARIFICATION" | "IN_PROGRESS" | "ESCALATION" | string;
  title: string;
  preview_text: string;
  full_body: string;
};

export type IntelligentTriageResult = {
  ticket_id: string;
  is_repetitive: boolean;
  recurrence_count: number;
  repetitive_reason?: string;
  similarity_threshold_used: number;
  similar_tickets: SimilarTicket[];
  best_solution: BestSolution;
  canned_responses: CannedResponseTemplate[];
  intent?: string;
  created_at: string;
};

/* ─── Predictive Analytics Types ─── */
export type VolumeTrendPoint = {
  date: string;
  label: string;
  total_tickets: number;
  resolved_count: number;
  urgent_count: number;
};

export type CategoryBreakdown = {
  category: string;
  count: number;
  percentage: number;
  avg_resolution_hours: number;
};

export type AgentPerformance = {
  agent_id: string;
  agent_name: string;
  email: string;
  skills: string[];
  is_available: boolean;
  workload: number;
  assigned_count: number;
  resolved_count: number;
  avg_resolution_hours: number;
  sla_compliance_pct: number;
  efficiency_rating: string;
  avg_csat_score?: number | null;
  csat_responses_count?: number;
};

export type MTTRByPriority = {
  priority: TicketPriority;
  avg_resolution_hours: number;
  sla_target_hours: number;
  is_within_sla: boolean;
};

export type MTTRMetrics = {
  overall_avg_hours: number;
  by_priority: MTTRByPriority[];
  by_category: CategoryBreakdown[];
  sla_compliance_overall_pct: number;
};

export type StrategicRecurrentIssue = {
  cluster_id: string;
  title: string;
  category: string;
  recurrence_count: number;
  impact_level: "CRITIQUE" | "ÉLEVÉ" | "MOYEN" | string;
  estimated_hours_lost: number;
  root_cause_analysis: string;
  ai_strategic_recommendation: string;
  preventive_action_plan: string[];
  sample_ticket_ids: string[];
};

export type DailyForecastPoint = {
  date: string;
  day_name: string;
  predicted_count: number;
  lower_bound: number;
  upper_bound: number;
  confidence_pct: number;
};

export type VolumeForecast = {
  forecast_days: number;
  daily_forecasts: DailyForecastPoint[];
  total_predicted_volume: number;
  historical_daily_avg: number;
  growth_trend_pct: number;
  spike_risk: "ÉLEVÉ" | "MODÉRÉ" | "FAIBLE" | string;
  confidence_level: "HIGH" | "MEDIUM" | "LOW" | string;
  is_baseline: boolean;
  peak_days: string[];
  data_points_analyzed: number;
};

export type ResolutionTimeFactor = {
  factor: string;
  impact_hours: number;
  description: string;
};

export type ResolutionTimePrediction = {
  predicted_hours: number;
  predicted_duration_formatted: string;
  confidence_score: number;
  confidence_level: "HIGH" | "MEDIUM" | "LOW" | string;
  sla_target_hours?: number;
  estimated_sla_compliance: boolean;
  historical_sample_size: number;
  baseline_used: string;
  contributing_factors: ResolutionTimeFactor[];
  explanation: string;
};

export type SLABreachRiskTicket = {
  ticket_id: string;
  reference: string;
  subject: string;
  priority: TicketPriority;
  status: TicketStatus;
  category: string;
  subcategory?: string;
  assigned_agent_id?: string;
  assigned_agent_name?: string;
  created_at: string;
  sla_deadline?: string;
  remaining_hours?: number;
  predicted_remaining_hours: number;
  breach_probability_pct: number;
  risk_level: "CRITIQUE" | "ÉLEVÉ" | "MODÉRÉ" | "FAIBLE" | string;
  risk_factors: string[];
  recommended_action: string;
};

export type SLABreachRisks = {
  evaluated_at: string;
  total_active_tickets: number;
  at_risk_count: number;
  critical_count: number;
  tickets: SLABreachRiskTicket[];
  summary: string;
};

export type RecurringTicketSummary = {
  ticket_id: string;
  reference: string;
  subject: string;
  status: string;
  priority: string;
  category: string;
  created_at: string;
  similarity_to_cluster: number;
};

export type RecurringCluster = {
  cluster_id: string;
  title: string;
  category: string;
  subcategory?: string;
  keywords: string[];
  occurrence_count: number;
  status: "ACTIVE" | "RESOLVED" | string;
  impact_level: "CRITIQUE" | "ÉLEVÉ" | "MOYEN" | string;
  estimated_hours_lost: number;
  first_seen: string;
  last_seen: string;
  average_similarity_pct: number;
  root_cause_analysis: string;
  common_solutions: string[];
  preventive_action_plan: string[];
  sample_tickets: RecurringTicketSummary[];
};

export type RecurringIssuesResponse = {
  total_clusters: number;
  active_clusters: number;
  total_tickets_in_clusters: number;
  clusters: RecurringCluster[];
  detection_method: string;
};

export type AIPredictiveInsights = {
  forecast_summary: string;
  predicted_volume_next_week: number;
  volume_growth_trend_pct: number;
  predicted_spike_risk: "ÉLEVÉ" | "MODÉRÉ" | "FAIBLE" | string;
  peak_time_windows: string[];
  strategic_issues: StrategicRecurrentIssue[];
  recommended_focus_areas: string[];
  volume_forecast?: VolumeForecast;
  sla_breach_risks?: SLABreachRisks;
  recurring_clusters?: RecurringCluster[];
};

export type SummaryKPIs = {
  total_tickets: number;
  open_tickets: number;
  in_progress_tickets: number;
  resolved_tickets: number;
  resolution_rate_pct: number;
  overall_mttr_hours: number;
  overall_sla_compliance_pct: number;
  critical_recurring_count: number;
  avg_response_hours?: number;
  satisfaction_avg?: number;
  satisfaction_responses_count?: number;
  positive_satisfaction_rate_pct?: number;
};

export type CSATRatingDistribution = {
  [key: string]: number;
};

export type CSATTrendPoint = {
  date: string;
  label: string;
  avg_rating: number;
  count: number;
};

export type CSATAgentStat = {
  agent_id: string;
  agent_name?: string | null;
  avg_rating: number;
  count: number;
};

export type CSATCategoryStat = {
  category: string;
  avg_rating: number;
  count: number;
};

export type CSATRecentFeedback = {
  ticket_id: string;
  rating: number;
  comment?: string | null;
  category?: string | null;
  agent_id?: string | null;
  submitted_at?: string | null;
};

export type CSATAnalytics = {
  total_ratings: number;
  avg_rating: number;
  satisfaction_rate_pct: number;
  distribution: CSATRatingDistribution;
  trend: CSATTrendPoint[];
  by_agent: CSATAgentStat[];
  by_category: CSATCategoryStat[];
  recent_feedback: CSATRecentFeedback[];
  period_days: number;
};

export type AnalyticsDashboardData = {
  kpis: SummaryKPIs;
  volume_trends: VolumeTrendPoint[];
  category_distribution: CategoryBreakdown[];
  agent_performances: AgentPerformance[];
  mttr_metrics: MTTRMetrics;
  predictive_insights: AIPredictiveInsights;
  csat?: CSATAnalytics | null;
  generated_at: string;
};

// ──────────────────────────────────────────────
// Agent Assistant (Copilot) Types
// ──────────────────────────────────────────────

export type ThreadSummary = {
  ticket_id: string;
  summary: string;
  problem_statement: string;
  actions_already_taken: string[];
  current_blocker?: string | null;
  suggested_next_step: string;
  urgency_evaluation: string;
  generated_at: string;
};

export type SuggestedAction = {
  id: string;
  action_type: "COMMUNICATION" | "DIAGNOSTIC" | "SYSTEM" | "ESCALATION" | string;
  title: string;
  description: string;
  snippet_to_insert?: string | null;
  impact: "HIGH" | "MEDIUM" | "LOW" | string;
  category: string;
};

export type InternalDocItem = {
  id: string;
  title: string;
  category: string;
  tags: string[];
  content_snippet: string;
  full_content: string;
  relevance_score: number;
  source_type: "SOP_INTERNE" | "GUIDE_SECURITE_ISO27001" | "BASE_CONNAISSANCES" | string;
};

export type TicketClassificationResult = {
  category: string;
  subcategory: string;
  priority: TicketPriority;
  tags: string[];
  confidence: number;
  reasoning: string;
};

export type SecurityAuditLog = {
  id: string;
  timestamp: string;
  actor_id?: string;
  actor_email?: string;
  actor_name?: string;
  actor_role?: string;
  client_ip?: string;
  user_agent?: string;
  event_category: string;
  event_type: string;
  severity: "INFO" | "WARNING" | "CRITICAL";
  target_resource_type: string;
  target_resource_id?: string;
  status: string;
  details?: Record<string, any>;
};

export type AuditStats = {
  total_events: number;
  info_count: number;
  warning_count: number;
  critical_count: number;
  login_successes: number;
  login_failures: number;
  access_denied_count: number;
};

export type BackupRecord = {
  backup_id: string;
  database_name: string;
  filename: string;
  created_at: string;
  size_bytes: number;
  checksum_sha256?: string;
  status: "RUNNING" | "SUCCESS" | "FAILED" | "CORRUPTED" | "DELETED";
  duration_seconds: number;
  backup_type: "SCHEDULED" | "MANUAL" | "SNAPSHOT";
  verification_status: "PENDING" | "VERIFIED" | "CORRUPTED" | "FAILED" | "SKIPPED";
  last_verified_at?: string;
  error_message?: string;
  retention_class: "DAILY" | "WEEKLY" | "MONTHLY" | "MANUAL";
  deleted_at?: string;
  is_protected: boolean;
};

export type BackupStats = {
  total_backups: number;
  active_backups: number;
  total_storage_bytes: number;
  last_successful_backup?: string;
  last_failed_backup?: string;
  verified_count: number;
  corrupted_count: number;
  failed_count: number;
  allow_production_restore: boolean;
};

export type RestoreTestResult = {
  backup_id: string;
  test_database: string;
  success: boolean;
  duration_seconds: number;
  checksum_verified: boolean;
  collections_found: string[];
  total_documents_restored: number;
  details: Record<string, number>;
  error_message?: string;
};

// ──────────────────────────────────────────────
// Module 4: Monitoring & Observability Types
// ──────────────────────────────────────────────

export type ComponentHealth = {
  name: string;
  status: "healthy" | "degraded" | "unhealthy" | "not_configured" | string;
  critical?: boolean;
  latency_ms?: number | null;
  details?: string | null;
  [key: string]: any;
};

export type SystemHealthSummary = {
  total_components: number;
  healthy_count: number;
  degraded_count: number;
  unhealthy_count: number;
  not_configured_count: number;
};

export type SystemHealth = {
  status: "healthy" | "degraded" | "unhealthy" | string;
  version: string;
  server_time: string;
  uptime_seconds: number;
  components: ComponentHealth[];
  summary: SystemHealthSummary;
};

export type BackgroundJob = {
  job_id: string;
  name: string;
  status: "IDLE" | "RUNNING" | "SUCCESS" | "FAILED" | string;
  is_running: boolean;
  last_execution_at?: string | null;
  last_success_at?: string | null;
  last_failure_at?: string | null;
  last_duration_seconds?: number | null;
  last_error?: string | null;
  success_count: number;
  failure_count: number;
  next_run_time?: string | null;
};

export type OperationalMetrics = {
  tickets: {
    total: number;
    open: number;
    in_progress: number;
    resolved: number;
    closed: number;
    created_last_24h: number;
  };
  sla: {
    on_track: number;
    at_risk: number;
    breached: number;
  };
  notifications: {
    total: number;
    pending: number;
    delivered: number;
    failed: number;
    dead_letter: number;
  };
  email_to_ticket: {
    total_processed: number;
    success: number;
    failed: number;
  };
  websockets: {
    active_users: number;
    active_connections: number;
    roles_connected: Record<string, number>;
  };
  security: {
    total_users: number;
    active_users: number;
    logins_last_24h: number;
    failed_logins_24h: number;
  };
  system: {
    version: string;
    server_time: string;
    uptime_seconds: number;
  };
};





