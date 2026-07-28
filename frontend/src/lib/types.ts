/**
 * Shared TypeScript Types
 * ======================
 * Type definitions shared between frontend and backend.
 */

// =============================================================================
// Mode Types
// =============================================================================

export type ChatMode = 'chat' | 'cs';

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
  /** Suggested answers, rendered as chips. Never a closed set — the card always
   *  pairs them with a free-text box. Backend has carried this field all along;
   *  the type was simply missing it, so the options were dropped on arrival. */
  options?: string[];
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
    // Confirmation stops: the pipeline pauses so the rep can correct course
    // before work is spent on the wrong thing. Keep in sync with
    // backend/schemas/state.py CheckpointAction.type.
    | 'confirm_brief'
    | 'confirm_solution'
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

export interface ComplianceFinding {
  severity: 'block' | 'warn' | 'info';
  policy_ref: string;
  message: string;
  suggestion?: string;
  details?: Record<string, unknown>;
}

export interface Checkpoint {
  id: string;
  action: CheckpointAction;
  status: 'AWAITING' | 'APPROVED' | 'EDITED' | 'REJECTED' | 'FAILED';
  auto_approve_session: boolean;
  preview?: Record<string, unknown>;
  result?: Record<string, unknown>;
  error?: string;
  compliance_findings?: ComplianceFinding[];
  created_at: string;
  updated_at: string;
  decided_at?: string;
}

// =============================================================================
// Feedback Rule (Day 4)
// =============================================================================

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
// Profile
// =============================================================================

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
  proposalAssets?: { deck_url?: string; pptx_url?: string };
  thinkingSteps?: ThinkingStep[];
}

// =============================================================================
// Thinking Step (Agent reasoning trace)
// =============================================================================

export interface ThinkingStep {
  step: string;
  content: string;
  timestamp: string;
  agent?: string;
  status?: 'running' | 'completed' | 'failed';
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
  | 'assistant_message'
  | 'content'
  | 'error'
  | 'done'
  | 'session_updated'
  | 'question'
  | 'question_card'
  | 'checkpoint'
  | 'agent_status'
  | 'thinking_trace';

export interface SSEEvent {
  type: SSEEventType;
  data?: Record<string, unknown>;
}

// =============================================================================
// Model & Quota Types
// =============================================================================

/** One model's declared ceilings and what this app has spent against them.
 *  `used_*` is counted by the backend, not reported by Google — see ModelsResponse.caveat.
 *  `limit_*` is null when the limits file declares no ceiling for that model. */
export interface ModelInfo {
  model: string;
  state: 'ok' | 'unused' | 'rate_limited' | 'out_of_quota_today';
  used_rpm: number;
  used_rpd: number;
  limit_rpm: number | null;
  limit_rpd: number | null;
  note: string;
  successes: number;
  rate_limits: number;
  other_errors: number;
  last_error: string;
}

export interface SkillModel {
  skill: string;
  /** What it will start on: override first, then MODEL_<NAME>. */
  model: string;
  /** What the environment says, which differs from `model` once overridden. */
  configured: string | null;
  overridden: boolean;
  /** What actually served its last call — differs from `model` when a fallback fired. */
  last_used: string | null;
  chain: string[];
}

export interface ModelsResponse {
  skills: SkillModel[];
  models: ModelInfo[];
  overrides: Record<string, string>;
  fallback_chain: string[];
  caveat: string;
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

// =============================================================================
// Auth & User Types
// =============================================================================

export type UserRole = 'admin' | 'account_manager' | 'sales_rep';

export interface User {
  id: number;
  username: string;
  full_name: string;
  role: UserRole;
  token: string;
}

// =============================================================================
// Org Rule (Admin Learning System)
// =============================================================================

export interface OrgRule {
  id: number;
  title: string;
  content: string;
  scope: string;
  is_active: number; // 1 = on, 0 = off
  created_by: number | null;
  created_at: string;
}

// =============================================================================
// Chat Session History
// =============================================================================

export interface ChatSessionSummary {
  session_id: string;
  title: string;
  updated_at: string;
}
