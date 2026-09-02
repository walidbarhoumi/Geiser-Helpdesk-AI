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
