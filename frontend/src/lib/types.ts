/**
 * Shared TypeScript Types
 * ======================
 * Type definitions shared between frontend and backend (BFF layer).
 */

// =============================================================================
// Mode Types
// =============================================================================

export type ChatMode = 'chat' | 'planning' | 'execute' | 'brainstorm';

// =============================================================================
// Brief
// =============================================================================

export interface Brief {
  industry?: string;
  budget_vnd?: number;
  goal?: string;
  timeline?: string;
  target_audience?: string;
  specific_requirements?: string[];
  constraints?: string[];
  additional_context?: string;
}

// =============================================================================
// Question
// =============================================================================

export interface Question {
  id: string;
  text: string;
  priority: number;
  is_mandatory: boolean;
  assumption?: string;
  target_field: string;
  asked_count: number;
  answered: boolean;
  answer?: string;
  was_helpful?: boolean;
}

// =============================================================================
// Agent Output
// =============================================================================

export interface AgentOutput {
  agent: string;
  status: 'COMPLETE' | 'NEEDS_INPUT' | 'NEEDS_AGENT' | 'FAILED';
  payload: Record<string, unknown>;
  summary: string;
  confidence: number;
  needs?: {
    agent: string;
    reason: string;
    context: Record<string, unknown>;
  };
  questions: Question[];
}

// =============================================================================
// Validation Report
// =============================================================================

export interface ValidationReport {
  missing_required: string[];
  ambiguities: Array<{
    field: string;
    interpretations: string[];
    why: string;
  }>;
  kb_confidence: number;
  out_of_scope: boolean;
  status: 'READY' | 'PENDING' | 'BLOCKED';
  severity: 'critical' | 'major' | 'minor';
}

// =============================================================================
// Checkpoint
// =============================================================================

export interface CheckpointAction {
  type:
    | 'generate_pptx'
    | 'generate_wireframe'
    | 'generate_userflow'
    | 'generate_quote'
    | 'send_external'
    | 'other';
  description: string;
  parameters: Record<string, unknown>;
  preview?: Record<string, unknown>;
}

export interface Checkpoint {
  id: string;
  action: CheckpointAction;
  status: 'AWAITING' | 'APPROVED' | 'EDITED' | 'REJECTED';
  auto_approve_session: boolean;
  created_at: string;
  updated_at: string;
  decided_at?: string;
}

// =============================================================================
// Feedback Rule (Day 4)
# =============================================================================

export interface FeedbackRule {
  rule_id: string;
  salesperson_id: string;
  type: 'NEGATIVE_CONSTRAINT' | 'POSITIVE_CONSTRAINT' | 'PREFERENCE' | 'FACT';
  scope: string[];
  rule: string;
  source_quote: string;
  active: boolean;
  created_at: string;
  updated_at?: string;
}

// =============================================================================
# Profile
# =============================================================================

export interface ProfileHistoryItem {
  case_id: string;
  summary: string;
  chosen_solution?: string;
  outcome?: 'won' | 'lost' | 'pending';
}

export interface SalespersonProfile {
  salesperson_id: string;
  display_name: string;
  style: 'terse' | 'balanced' | 'detailed';
  question_frequency: number;
  preferences: Record<string, unknown>;
  constraints: string[];
  history: ProfileHistoryItem[];
}

// =============================================================================
// Session State
// =============================================================================

export interface SessionState {
  session_id: string;
  salesperson_id: string;
  mode: ChatMode;
  brief?: Brief;
  validation_status: 'PENDING' | 'READY' | 'BLOCKED';
  validation_report?: ValidationReport;
  question_stack: Question[];
  outputs: Record<string, AgentOutput>;
  visited: string[];
  hop_depth: number;
  profile?: SalespersonProfile;
  checkpoint?: Checkpoint;
  messages: Message[];
  summary: string;
}

export interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  agent?: string;
  timestamp: string;
}

// =============================================================================
// API Request/Response Types
// =============================================================================

export interface ChatRequest {
  message: string;
  session_id?: string;
  salesperson_id: string;
  mode: ChatMode;
  brief?: Brief;
  context?: Record<string, unknown>;
}

export interface ChatResponse {
  session_id: string;
  message: string;
  agent: string;
  done: boolean;
}

// =============================================================================
// SSE Event Types
// =============================================================================

export type SSEEventType =
  | 'session'
  | 'user_message'
  | 'content'
  | 'error'
  | 'done'
  | 'session_updated'
  | 'question'
  | 'question_card'
  | 'checkpoint';

export interface SSEEvent {
  type: SSEEventType;
  data?: Record<string, unknown>;
}

// =============================================================================
// UI State Types
// =============================================================================

export interface UIState {
  // Identity
  salespersonId: string;
  displayName: string;

  // Session
  sessionId: string | null;
  mode: ChatMode;

  // UI state
  isLoading: boolean;
  error: string | null;

  // Messages
  messages: Message[];

  // Brief (current working brief)
  brief: Brief | null;

  // Questions pending
  pendingQuestions: Question[];

  // Active checkpoint
  activeCheckpoint: Checkpoint | null;

  // Active agents with status
  activeAgents: Array<{
    name: string;
    status: 'idle' | 'thinking' | 'waiting' | 'failed';
  }>;
}
