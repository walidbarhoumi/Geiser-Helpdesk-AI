export const UserRole = {
  USER: "USER",
  AGENT: "AGENT",
  ADMIN: "ADMIN",
} as const;
export type UserRole = typeof UserRole[keyof typeof UserRole];

export const TicketStatus = {
  OPEN: "OPEN",
  IN_PROGRESS: "IN_PROGRESS",
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
};

export type User = {
  id: string;
  email: string;
  full_name?: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
};

export type Ticket = {
  id: string;
  subject: string;
  description: string;
  category: string;
  subcategory?: string;
  priority: TicketPriority;
  channel: TicketChannel;
  status: TicketStatus;
  user_id: string;
  assigned_agent_id?: string | null;
  routing_reason?: string;
  attachments: string[];
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
  created_at: string;
  updated_at: string;
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

export type AIPredictiveInsights = {
  forecast_summary: string;
  predicted_volume_next_week: number;
  volume_growth_trend_pct: number;
  predicted_spike_risk: "ÉLEVÉ" | "MODÉRÉ" | "FAIBLE" | string;
  peak_time_windows: string[];
  strategic_issues: StrategicRecurrentIssue[];
  recommended_focus_areas: string[];
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
};

export type AnalyticsDashboardData = {
  kpis: SummaryKPIs;
  volume_trends: VolumeTrendPoint[];
  category_distribution: CategoryBreakdown[];
  agent_performances: AgentPerformance[];
  mttr_metrics: MTTRMetrics;
  predictive_insights: AIPredictiveInsights;
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



