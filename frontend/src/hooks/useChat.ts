/**
 * Chat Hook with SSE Support
 * ==========================
 * Custom hook for handling chat with server-sent events streaming.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import type { ChatRequest, Message, Brief, ChatMode, Question, Checkpoint, FeedbackRule, SalespersonProfile, ThinkingStep } from '../lib/types';
import { getApiBaseUrl } from '../lib/api';

const BACKEND_URL = getApiBaseUrl();

interface UseChatOptions {
  salespersonId: string;
  displayName: string;
  mode?: ChatMode;
  onBriefChange?: (brief: Brief | null) => void;
}

interface AgentStatus {
  name: string;
  status: 'idle' | 'thinking' | 'waiting' | 'completed' | 'failed';
  /** Model that served this skill's last call — set by the terminal status event. */
  model?: string | null;
}

// Artifact types for Day 6
interface Artifact {
  id: string;
  type: 'pptx' | 'userflow' | 'quote' | 'wireframe';
  title: string;
  preview?: string;
  data?: string;
  download_url?: string;   // backend-relative URL, e.g. /artifact/pptx_abc123
  artifact_id?: string;    // artifact registry key
}

// deck_url/pptx_url only ever got attached to a single message bubble — there was
// no single place listing every file generated across a whole session. Each one
// also carries a unique artifact id in its URL, so turning them into Artifact
// entries lets the existing "Generated Artifacts" list in ContextPanel (built for
// the older checkpoint-approval flow, currently empty because that flow doesn't
// run any more) double as a running index of every deck/PPTX this conversation
// has produced, not just the latest one.
function proposalAssetsToArtifacts(
  assets: { deck_url?: string; pptx_url?: string },
  createdAtIso?: string
): Artifact[] {
  // Every deck this session produces is titled identically ("Đề xuất (HTML)"),
  // so two real, distinct proposals (e.g. rebuilt after a follow-up edit) were
  // indistinguishable in the list — a rep had no way to tell which entry was
  // which before clicking. A time suffix is enough to tell them apart without
  // needing a real per-artifact label from the backend.
  const stamp = new Date(createdAtIso ?? Date.now()).toLocaleTimeString('vi-VN', {
    hour: '2-digit',
    minute: '2-digit',
  });
  const out: Artifact[] = [];
  if (assets.deck_url) {
    out.push({
      id: assets.deck_url,
      type: 'wireframe',
      title: `Đề xuất (HTML) — ${stamp}`,
      download_url: assets.deck_url,
    });
  }
  if (assets.pptx_url) {
    out.push({
      id: assets.pptx_url,
      type: 'pptx',
      title: `Đề xuất (PPTX) — ${stamp}`,
      download_url: assets.pptx_url,
    });
  }
  return out;
}

// download_url embeds the artifact id, so it is the natural de-dupe key — the
// same deck re-emitted on a later turn (see main.py's "re-emit artifacts produced
// on an earlier turn") must not show up twice in the list.
function mergeArtifacts(prev: Artifact[], fresh: Artifact[]): Artifact[] {
  const seen = new Set(prev.map((a) => a.download_url ?? a.id));
  const additions = fresh.filter((a) => !seen.has(a.download_url ?? a.id));
  return additions.length > 0 ? [...prev, ...additions] : prev;
}

// Human-readable stand-in for the raw "Tiếp tục" resume message, so approving
// a checkpoint leaves a readable trace of what was actually approved instead
// of erasing the card and showing a bare "continue".
function checkpointTitle(checkpoint: Checkpoint): string {
  return checkpoint.action.type === 'confirm_brief'
    ? 'Chốt — Xác nhận cách hiểu brief'
    : checkpoint.action.type === 'confirm_solution'
      ? 'Chốt — Duyệt hướng giải pháp'
      : 'Đã duyệt bước này';
}

// `action.description` is boilerplate instruction text ("Bạn xác nhận giúp
// trước khi mình chạy phân tích — sửa bây giờ rẻ hơn sửa sau khi đã có
// proposal."), identical on every confirm_brief checkpoint — not a summary of
// what's actually being confirmed. The real content lives in
// `action.preview.groups` (said/inferred/assumed brief fields), same data
// CheckpointCard itself renders as a table. Placeholder assumed rows
// ("(chưa có — sẽ phỏng đoán)") are skipped — there's no real value there to
// trace back to.
function buildCheckpointDataSummary(checkpoint: Checkpoint): string {
  const preview = checkpoint.action.preview as
    | { groups?: Record<string, Array<{ field: string; label: string; value: string }>> }
    | undefined;
  const groups = preview?.groups;
  // "- " (a real markdown list item), not "• " — this string ends up in an
  // assistant message rendered through ReactMarkdown, which treats a bare
  // single "\n" as a soft break (often just a space), collapsing "•" bullets
  // onto one line. A markdown list is what actually forces one line per item.
  if (groups) {
    const lines: string[] = [];
    for (const key of ['said', 'inferred', 'assumed']) {
      for (const item of groups[key] ?? []) {
        if (typeof item.value === 'string' && item.value.trim().startsWith('(')) continue;
        lines.push(`- **${item.label}:** ${item.value}`);
      }
    }
    if (lines.length > 0) return lines.join('\n');
  }

  // Non-brief checkpoints 
  if (checkpoint.action.preview && typeof checkpoint.action.preview === 'object') {
    const lines = Object.entries(checkpoint.action.preview as Record<string, unknown>)
      .filter(([k]) => !['skill', 'status', 'agent', 'model'].includes(k))
      .map(([k, v]) => {
        const label = k.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
        return `- **${label}:** ${typeof v === 'object' ? JSON.stringify(v) : String(v)}`;
      });
    if (lines.length > 0) return lines.join('\n');
  }

  return '';
}

// The agent-voice version — what the card was proposing, kept as a normal
// assistant message once the interactive card itself is dismissed so
// scrollback still shows what the rep's "✅ Đã duyệt" reply was actually
// replying to. Title + actual data, not the instruction sentence.
function describeCheckpointForHistory(checkpoint: Checkpoint | null): string {
  if (!checkpoint) return '';
  const title = checkpointTitle(checkpoint);
  const summary = buildCheckpointDataSummary(checkpoint);
  // Blank line before the list — markdown needs it to recognize a list block
  // right after a plain text line, not swallow the "-" into the same paragraph.
  return summary ? `${title}\n\n${summary}` : title;
}

// The rep's own reply stays short — the agent-voice message right above it
// (describeCheckpointForHistory) already carries the full data, so repeating
// it here was pure duplication of the same text twice in a row.
function describeCheckpointApproval(checkpoint: Checkpoint | null): string {
  if (!checkpoint) return '✅ Đã duyệt';
  return `✅ Đã duyệt ${checkpointTitle(checkpoint)}`;
}

// Same idea for a batch of question-card answers — shows what was actually
// answered instead of a bare "continue" once the card disappears.
function describeQuestionAnswers(
  answers: Record<string, string>,
  questions: Question[]
): string {
  const lines = Object.entries(answers).map(([qid, value]) => {
    const q = questions.find((q) => q.id === qid);
    return q ? `• ${q.text} → ${value}` : `• ${value}`;
  });
  return `✅ Đã trả lời:\n${lines.join('\n')}`;
}

function describeCheckpointEdit(params: Record<string, unknown>): string {
  const lines = Object.entries(params).map(([field, value]) => {
    const label = field.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
    return `• ${label}: ${value}`;
  });
  return lines.length > 0 ? `✅ Đã sửa:\n${lines.join('\n')}` : '✅ Đã sửa';
}

interface UseChatReturn {
  // State
  sessionId: string | null;
  messages: Message[];
  isLoading: boolean;
  isThinking: boolean;
  error: string | null;
  pendingQuestions: Question[];
  activeCheckpoint: Checkpoint | null;
  activeAgents: AgentStatus[];
  constraints: FeedbackRule[];  // Day 4: Active constraints
  profile: SalespersonProfile | null;  // Day 4: User profile
  brief: Brief | null;  // Day 4: Current brief
  artifacts: Artifact[];  // Day 6: Generated artifacts
  proposalAssets: { deck_url?: string; pptx_url?: string } | null;
  thinkingSteps: ThinkingStep[];  // Live thinking trace for current turn

  // Actions
  sendMessage: (message: string, brief?: Brief, resume?: boolean, isActionSummary?: boolean) => Promise<void>;
  answerQuestion: (questionId: string, answer: string) => Promise<void>;
  answerAllQuestions: (answers: Record<string, string>) => Promise<void>;
  skipQuestion: (questionId: string) => Promise<void>;
  freeTextAnswer: (freeText: string) => Promise<void>;  // Day 3: C.5 §5
  revokeConstraint: (ruleId: string) => Promise<void>;  // Day 4: Revoke constraint
  loadConstraints: () => Promise<void>;  // Day 4: Load constraints
  loadProfile: () => Promise<void>;  // Day 4: Load profile
  approveCheckpoint: () => Promise<void>;
  rejectCheckpoint: () => Promise<void>;
  editCheckpoint: (params: Record<string, unknown>) => Promise<void>;
  clearError: () => void;
  resetSession: () => void;  // Clear session and start fresh
  loadSession: (sid: string) => Promise<void>;  // Load a session from backend
}

export function useChat(options: UseChatOptions): UseChatReturn {
  const { salespersonId, displayName, mode = 'chat' } = options;

  // Keep a ref to the current salespersonId so SSE callbacks always use the
  // latest value — the useState lazy init captures the salespersonId at mount
  // time ('demo_user' because the name hasn't been entered yet), causing the
  // session to be stored under the wrong key when the user later types their name.
  const salespersonIdRef = useRef(salespersonId);
  useEffect(() => { salespersonIdRef.current = salespersonId; }, [salespersonId]);

  // Always start with null — messages are not persisted so restoring only the
  // session_id creates an inconsistent state (empty UI + old backend context).
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingQuestions, setPendingQuestions] = useState<Question[]>([]);
  const [activeCheckpoint, setActiveCheckpoint] = useState<Checkpoint | null>(null);
  const [activeAgents, setActiveAgents] = useState<AgentStatus[]>([
    { name: 'market_strategy', status: 'idle' },
    { name: 'compliance', status: 'idle' },
    { name: 'product_solution', status: 'idle' },
    { name: 'client_simulator', status: 'idle' },
    { name: 'proposal_assembler', status: 'idle' },
    { name: 'wireframe_designer', status: 'idle' },
  ]);

  // Day 4: Constraints and profile state
  const [constraints, setConstraints] = useState<FeedbackRule[]>([]);
  const [profile, setProfile] = useState<SalespersonProfile | null>(null);
  const [brief, setBrief] = useState<Brief | null>(null);

  // Thinking state — true while the LLM is emitting <think> reasoning tokens
  const [isThinking, setIsThinking] = useState(false);

  // Day 6: Artifacts state
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);

  // Proposal deck assets — set when wireframe_designer completes after proposal_assembler
  const [proposalAssets, setProposalAssets] = useState<{ deck_url?: string; pptx_url?: string } | null>(null);

  // Thinking trace — accumulated steps for the current turn, shown live in the chat
  const [thinkingSteps, setThinkingSteps] = useState<ThinkingStep[]>([]);
  // Ref mirrors the state so SSE callbacks can read the latest value without stale closures
  const thinkingStepsRef = useRef<ThinkingStep[]>([]);
  // --- Mode isolation: save/restore state per mode ---
  const prevModeRef = useRef<string>(mode);
  type ModeSnapshot = {
    sessionId: string | null;
    messages: Message[];
    brief: Brief | null;
    pendingQuestions: Question[];
    activeCheckpoint: Checkpoint | null;
    artifacts: Artifact[];
    // Travels with the snapshot for the same reason artifacts does: it is per-conversation,
    // and the pinned deliverables bar reads it.
    proposalAssets: { deck_url?: string; pptx_url?: string } | null;
    isLoading: boolean;
    isThinking: boolean;
  };
  const savedModeStates = useRef<Record<string, ModeSnapshot>>({});

  // Always reflects the currently-active mode. 
  const currentModeRef = useRef<string>(mode);

  useEffect(() => {
    // Always sync ref first — SSE callbacks read this to know the live mode.
    currentModeRef.current = mode;

    const prevMode = prevModeRef.current;
    if (prevMode === mode) return;

    // NOTE: We intentionally do NOT abort the in-flight SSE request here.
    savedModeStates.current[prevMode] = {
      sessionId,
      messages,
      brief,
      pendingQuestions,
      activeCheckpoint,
      artifacts,
      proposalAssets,
      isLoading,
      isThinking,
    };

    // Restore target mode's state (or start fresh)
    const saved = savedModeStates.current[mode];
    if (saved) {
      setSessionId(saved.sessionId);
      setMessages(saved.messages);
      setBrief(saved.brief);
      setPendingQuestions(saved.pendingQuestions);
      setActiveCheckpoint(saved.activeCheckpoint);
      setArtifacts(saved.artifacts);
      setProposalAssets(saved.proposalAssets);
      setIsLoading(saved.isLoading);
      setIsThinking(saved.isThinking);
    } else {
      setSessionId(null);
      setMessages([]);
      setBrief(null);
      setPendingQuestions([]);
      setActiveCheckpoint(null);
      setArtifacts([]);
      setProposalAssets(null);
      setIsLoading(false);
      setIsThinking(false);
    }

    setError(null);

    // Reset agents for the new mode
    const csAgents = [
      { name: 'cs_agent', status: 'idle' as const },
      { name: 'predict_agent', status: 'idle' as const },
    ];
    const saleAgents = [
      { name: 'market_strategy', status: 'idle' as const },
      { name: 'compliance', status: 'idle' as const },
      { name: 'product_solution', status: 'idle' as const },
      { name: 'client_simulator', status: 'idle' as const },
      { name: 'proposal_assembler', status: 'idle' as const },
      { name: 'wireframe_designer', status: 'idle' as const },
    ];
    setActiveAgents(mode === 'cs' ? csAgents : saleAgents);

    prevModeRef.current = mode;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  // Load artifacts from sessionStorage on mount
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const stored = sessionStorage.getItem('artifacts');
      if (stored) {
        try {
          setArtifacts(JSON.parse(stored));
        } catch (e) {
          console.error('Failed to parse stored artifacts:', e);
        }
      }
    }
  }, []);

  // Expose a resetSession helper so UI can start a fresh conversation
  const resetSession = useCallback(() => {
    if (typeof window !== 'undefined') {
      sessionStorage.removeItem(`chat_session_${salespersonIdRef.current}`);
    }
    // Clear saved snapshot for current mode too
    delete savedModeStates.current[mode];
    setSessionId(null);
    setMessages([]);
    setBrief(null);
    setPendingQuestions([]);
    setActiveCheckpoint(null);
    setArtifacts([]);
    // Was missed here as well as in loadSession: a new conversation starting with the
    // previous one's deck and PPTX offered on the pinned bar is a cross-client leak, not
    // just stale UI.
    setProposalAssets(null);
  }, [mode]);

  // Per-mode abort controllers so cancelling one mode's stream never kills another.
  const modeAbortControllers = useRef<Record<string, AbortController | null>>({});

  // Reset agent statuses when starting new message
  const resetAgentStatuses = useCallback(() => {
    setActiveAgents((prev) => prev.map((agent) => ({ ...agent, status: 'idle' as const })));
  }, []);

  // Send message with SSE streaming
  const sendMessage = useCallback(
    async (message: string, brief?: Brief, resume = false, isActionSummary = false) => {
      // Capture origin mode first — everything below is scoped to this mode.
      const myMode = mode;

      // Cancel any existing request for THIS mode only
      modeAbortControllers.current[myMode]?.abort();
      const controller = new AbortController();
      modeAbortControllers.current[myMode] = controller;

      setIsLoading(true);
      setError(null);
      setIsThinking(false);
      resetAgentStatuses();
      // Reset thinking trace for the new turn
      thinkingStepsRef.current = [];
      setThinkingSteps([]);
      setPendingQuestions([]);

      // Add user message immediately
      const userMessage: Message = {
        role: 'user',
        content: message,
        timestamp: new Date().toISOString(),
        isActionSummary,
      };
      setMessages((prev) => [...prev, userMessage]);

      let response: Response;

      const isCs = mode === 'cs';
      const requestBody = isCs
        ? JSON.stringify({ message, session_id: sessionId, salesperson_id: salespersonId })
        : JSON.stringify({ message, session_id: sessionId, salesperson_id: salespersonId, mode, brief, resume });

      try {
        const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
        const fetchHeaders: Record<string, string> = { 'Content-Type': 'application/json' };
        if (token) fetchHeaders['Authorization'] = `Bearer ${token}`;

        response = await fetch(`${BACKEND_URL}${isCs ? '/cs/chat/stream' : '/chat/stream'}`, {
          method: 'POST',
          headers: fetchHeaders,
          body: requestBody,
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`Server error: ${response.status}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error('No response body');
        }

        const decoder = new TextDecoder();
        let buffer = '';

        // Process SSE stream
        while (true) {
          const { done, value } = await reader.read();

          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // Process complete SSE events
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              if (currentModeRef.current !== myMode) {
                try {
                  const data = JSON.parse(line.slice(6));
                  if (data.type === 'content' && data.content) {
                    const saved = savedModeStates.current[myMode];
                    if (saved) {
                      const chunk = data.content as string;
                      const lastMsg = saved.messages[saved.messages.length - 1];
                      if (lastMsg && lastMsg.role === 'assistant') {
                        saved.messages = [
                          ...saved.messages.slice(0, -1),
                          { ...lastMsg, content: lastMsg.content + chunk },
                        ];
                      } else {
                        saved.messages = [
                          ...saved.messages,
                          {
                            role: 'assistant' as const,
                            content: chunk,
                            agent: myMode === 'cs' ? 'cs_agent' : 'sales_orchestrator',
                            timestamp: new Date().toISOString(),
                          },
                        ];
                      }
                      savedModeStates.current[myMode] = { ...saved };
                    }
                  }
                } catch {
                  // ignore parse errors while buffering
                }
                continue; // don't touch current mode's React state
              }
              // Normal path: process event for the currently active mode
              try {
                const data = JSON.parse(line.slice(6));
                handleSSEEvent(data);
              } catch {
                console.error('Failed to parse SSE data');
              }
            }
          }
        }
      } catch (e) {
        if ((e as Error).name === 'AbortError') {
          // Cancelled by a new sendMessage call — ignore
          return;
        }
        if (currentModeRef.current === myMode) {
          // "network error"
          const raw = (e as Error).message || '';
          const dropped = /network|failed to fetch|load failed|terminated/i.test(raw);
          setError(
            dropped
              ? 'Mất kết nối tới máy chủ giữa chừng. Lượt vừa rồi có thể vẫn đang chạy — gửi lại tin nhắn sau ít giây là tiếp tục được.'
              : raw
          );
        }
      } finally {
        modeAbortControllers.current[myMode] = null;
        if (currentModeRef.current === myMode) {
          // Still on our mode — clear live state
          setIsLoading(false);
          setIsThinking(false);
        } else {
          // User has switched away — update the snapshot so loading clears
          // when they return to this mode.
          const snap = savedModeStates.current[myMode];
          if (snap) {
            savedModeStates.current[myMode] = { ...snap, isLoading: false, isThinking: false };
          }
        }
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [sessionId, salespersonId, resetAgentStatuses, mode]
  );

  // Handle SSE events
  const handleSSEEvent = useCallback(
    (data: { type: string; [key: string]: unknown }) => {
      switch (data.type) {
        case 'session':
          // Session confirmed — persist id and sync brief from BE
          if (data.session_id) {
            const sid = data.session_id as string;
            setSessionId(sid);
            if (typeof window !== 'undefined') {
              sessionStorage.setItem(`chat_session_${salespersonIdRef.current}`, sid);
              window.dispatchEvent(new Event('session_updated'));
            }
          }
          // Sync brief from BE (provides latest accumulated brief on session resume)
          if (data.brief && typeof data.brief === 'object') {
            setBrief(data.brief as Brief);
          }
          break;

        case 'user_message':
          // User message echoed back
          break;

        case 'assistant_message':
          {
            const agentName = (data.agent as string) || 'sales_orchestrator';
            const agentContent = (data.content as string) || '';
            if (agentContent) {
              setIsThinking(false);
              // Attach accumulated thinking steps to the first assistant message of this turn
              const steps = thinkingStepsRef.current.length > 0 ? [...thinkingStepsRef.current] : undefined;
              if (steps) {
                thinkingStepsRef.current = [];
                setThinkingSteps([]);
              }
              setMessages((prev) => [
                ...prev,
                {
                  role: 'assistant',
                  content: agentContent,
                  agent: agentName,
                  timestamp: new Date().toISOString(),
                  thinkingSteps: steps,
                },
              ]);
            }
          }
          break;

        case 'thinking_start':
          setIsThinking(true);
          break;

        case 'thinking_end':
          setIsThinking(false);
          break;

        case 'content':
          // Streaming content chunk
          setIsThinking(false);
          {
            const content = data.content as string;
            // Determine agent name for this streaming turn
            const streamAgent = currentModeRef.current === 'cs' ? 'cs_agent' : 'sales_orchestrator';
            // Attach accumulated thinking steps to the first assistant message of this turn
            const steps = thinkingStepsRef.current.length > 0 ? [...thinkingStepsRef.current] : undefined;
            if (steps) {
              thinkingStepsRef.current = [];
              setThinkingSteps([]);
            }
            setMessages((prev) => {
              const last = prev[prev.length - 1];
              if (last && last.role === 'assistant') {
                // Append to existing assistant message (any agent - within same streaming turn)
                return [...prev.slice(0, -1), { ...last, content: last.content + content }];
              } else {
                // Create new assistant message — attach thinking steps
                return [
                  ...prev,
                  {
                    role: 'assistant',
                    content,
                    agent: streamAgent,
                    timestamp: new Date().toISOString(),
                    thinkingSteps: steps,
                  },
                ];
              }
            });
          }
          break;

        case 'error':
          setError(data.error as string);
          break;

        case 'done':
          // Stream complete
          break;

        case 'session_updated':
          // Session state updated — sync brief and persist session id
          if (data.session_id) {
            const sid = data.session_id as string;
            setSessionId(sid);
            if (typeof window !== 'undefined') {
              sessionStorage.setItem(`chat_session_${salespersonIdRef.current}`, sid);
            }
          }
          // Only update brief if BE returned a non-empty brief object
          if (data.brief && typeof data.brief === 'object' && Object.keys(data.brief as object).length > 0) {
            setBrief(data.brief as Brief);
          }
          if (typeof window !== 'undefined') {
            window.dispatchEvent(new Event('session_updated'));
          }
          break;

        case 'question':
          // Questions from agent
          {
            const questions = data.questions as Question[];
            if (questions) {
              setPendingQuestions(questions);
            }
          }
          break;

        case 'question_card':
          // Question card for validation (Day 3)
          {
            const questionCardData = data.questions as Question[];
            if (questionCardData) {
              setIsLoading(false); // pause loading UI while waiting for user answers
              setIsThinking(false);
              setPendingQuestions(questionCardData);
            }
          }
          break;

        case 'checkpoint':
        case 'checkpoint_card':
          // Checkpoint requiring approval (backend may emit either event name)
          {
            const checkpoint = data.checkpoint as Checkpoint;
            if (checkpoint) {
              setIsLoading(false); // pause loading UI while waiting for user approval
              setIsThinking(false);
              setActiveCheckpoint(checkpoint);
            }
          }
          break;

        case 'agent_message':
          // A specialized agent completed and is sending its response as a
          // separate chat bubble.
          {
            const agentName = (data.agent as string) || 'assistant';
            const agentContent = (data.content as string) || '';
            if (agentContent) {
              setMessages((prev) => [
                ...prev,
                {
                  role: 'assistant',
                  content: agentContent,
                  agent: agentName,
                  timestamp: new Date().toISOString(),
                },
              ]);
            }
          }
          break;

        case 'agent_status':
          // Agent status update for sidebar
          {
            const agentName = data.agent as string;
            const agentStatus = data.status as string;
            const agentModel = (data.model as string | null) ?? null;
            if (agentName && agentStatus) {
              setActiveAgents((prev) => {
                // Update or add agent status
                const existing = prev.findIndex((a) => a.name === agentName);
                // Only the terminal events carry a model. Keep the previous one on a
                // "thinking" update rather than blanking the row mid-turn.
                const newAgent = {
                  name: agentName,
                  status: agentStatus as AgentStatus['status'],
                  model: agentModel ?? (existing >= 0 ? prev[existing].model : null),
                };
                if (existing >= 0) {
                  const updated = [...prev];
                  updated[existing] = newAgent;
                  return updated;
                }
                return [...prev, newAgent];
              });
            }
          }
          break;

        case 'thinking_trace':
          // Agent reasoning step — accumulate for display
          {
            const traceStep: ThinkingStep = {
              step: (data.step as string) || 'unknown',
              content: (data.content as string) || '',
              agent: (data.agent as string) || undefined,
              timestamp: new Date().toISOString(),
            };
            thinkingStepsRef.current = [...thinkingStepsRef.current, traceStep];
            setThinkingSteps([...thinkingStepsRef.current]);
          }
          break;

        case 'constraint_added':
          // Day 4: New constraint added from feedback
          {
            const constraint = data.constraint as FeedbackRule;
            if (constraint) {
              setConstraints((prev) => [...prev, constraint]);
            }
          }
          break;

        case 'proposal_assets':
          // PPTX + HTML deck generated after proposal_assembler
          {
            const assets: { deck_url?: string; pptx_url?: string } = {};
            if (data.deck_url) assets.deck_url = data.deck_url as string;
            if (data.pptx_url) assets.pptx_url = data.pptx_url as string;
            if (Object.keys(assets).length > 0) {
              setProposalAssets(assets);
              // Attach to last assistant message for scoped rendering
              setMessages((prev) => {
                const last = prev[prev.length - 1];
                if (last && last.role === 'assistant') {
                  return [...prev.slice(0, -1), { ...last, proposalAssets: assets }];
                }
                return prev;
              });
              // Also index it in the session-wide artifacts list
              setArtifacts((prev) => mergeArtifacts(prev, proposalAssetsToArtifacts(assets)));
            }
          }
          break;

        default:
          console.log('Unknown SSE event:', data);
      }
    },
    // Every value read above is a ref or a setState function — both stable
    // identities — so this callback never needs to change.
    []
  );

  // Answer a pending question
  const answerQuestion = useCallback(
    async (questionId: string, answer: string) => {
      // Remove from pending locally (will be updated from SSE after response)
      setPendingQuestions((prev) => prev.filter((q) => q.id !== questionId));

      // Send answer to backend to update brief
      try {
        const response = await fetch(`${BACKEND_URL}/workflow/interact`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            action: 'answer',
            session_id: sessionId,
            question_id: questionId,
            answer: answer,
          }),
        });

        if (response.ok) {
          // Show feedback that answer was received
          setMessages((prev) => [
            ...prev,
            {
              role: 'system',
              content: '✓ Answer received. Processing...',
              timestamp: new Date().toISOString(),
            },
          ]);

          // Reload session state
          const data = await response.json();
          if (data.brief) {
            setBrief(data.brief);
          }
          if (data.questions && data.questions.length > 0) {
            setPendingQuestions(data.questions);
          } else {
            // No more questions - trigger agents to continue
            setPendingQuestions([]);
            // Send a continuation message to trigger agent execution
            await sendMessage('Continue');
          }
        }
      } catch {
        // Fallback: send as message
        await sendMessage(`Answer to question: ${answer}`);
      }
    },
    [sessionId, sendMessage]
  );

  // Submit every answer on the card in one request.
  const answerAllQuestions = useCallback(
    async (answers: Record<string, string>) => {
      if (!sessionId || Object.keys(answers).length === 0) return;

      setIsLoading(true);
      try {
        const response = await fetch(`${BACKEND_URL}/workflow/interact`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'answer', session_id: sessionId, answers }),
        });
        if (!response.ok) throw new Error('Failed to submit answers');

        const data = await response.json();
        if (data.brief) setBrief(data.brief);

        const remaining = (data.questions as Question[]) ?? [];
        setPendingQuestions(remaining);

        if (remaining.length === 0) {
          // Everything answered — let the pipeline pick up where it stopped.
          // Summarizing the answers (instead of a bare "Tiếp tục") keeps the
          // question card's content readable on scrollback after it's gone.
          await sendMessage(describeQuestionAnswers(answers, pendingQuestions), undefined, true, true);
        }
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId, sendMessage, pendingQuestions]
  );

  // Skip an optional question (Day 3: C.5 §6)
  const skipQuestion = useCallback(
    async (questionId: string) => {
      setPendingQuestions((prev) => prev.filter((q) => q.id !== questionId));

      // Notify backend to skip
      try {
        const response = await fetch(`${BACKEND_URL}/workflow/interact`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            action: 'skip_question',
            session_id: sessionId,
            question_id: questionId,
          }),
        });

        if (response.ok) {
          // Show feedback that question was skipped
          setMessages((prev) => [
            ...prev,
            {
              role: 'system',
              content: '✓ Question skipped. Continuing...',
              timestamp: new Date().toISOString(),
            },
          ]);

          const data = await response.json();
          if (data.brief) {
            setBrief(data.brief);
          }
          if (data.questions && data.questions.length > 0) {
            setPendingQuestions(data.questions);
          } else {
            // No more questions - trigger agents to continue
            setPendingQuestions([]);
            await sendMessage('Continue');
          }
        }
      } catch {
        // Silently fail - continue without blocking the chat flow
      }
    },
    [sessionId, sendMessage]
  );

  // Free text answer - maps to multiple brief fields (C.5 §5, CHECK.md Issue #7)
  const freeTextAnswer = useCallback(
    async (freeText: string) => {
      if (!sessionId) {
        console.error('No session ID for free text answer');
        return;
      }

      setIsLoading(true);
      setPendingQuestions([]); // Clear pending while processing

      try {
        const response = await fetch(`${BACKEND_URL}/workflow/interact`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            action: 'answer_free_text',
            session_id: sessionId,
            message: freeText,
            salesperson_id: salespersonId,
            mode: 'chat',
          }),
        });

        if (response.ok) {
          // Show feedback
          setMessages((prev) => [
            ...prev,
            {
              role: 'system',
              content: '✓ Answer received. Processing...',
              timestamp: new Date().toISOString(),
            },
          ]);

          const data = await response.json();
          if (data.brief) {
            setBrief(data.brief);
          }
          // Update pending questions if any remain
          if (data.questions && data.questions.length > 0) {
            setPendingQuestions(data.questions);
          }
          // If ready, the flow will continue via SSE events
        } else {
          // Fallback: send as regular message
          await sendMessage(freeText);
        }
      } catch (e) {
        console.error('Free text answer failed:', e);
        // Fallback: send as regular message
        await sendMessage(freeText);
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId, salespersonId, sendMessage]
  );

  // Day 4: Load constraints from backend
  const loadConstraints = useCallback(async () => {
    if (!salespersonId) return;

    try {
      const response = await fetch(`${BACKEND_URL}/memory/constraints/${salespersonId}`);
      if (response.ok) {
        const data = await response.json();
        setConstraints(data.constraints || []);
      }
    } catch (e) {
      console.error('Failed to load constraints:', e);
    }
  }, [salespersonId]);

  // Day 4: Revoke a constraint
  const revokeConstraint = useCallback(async (ruleId: string) => {
    if (!salespersonId) return;

    try {
      const response = await fetch(
        `${BACKEND_URL}/memory/constraints/${ruleId}/toggle?active=false&salesperson_id=${salespersonId}`,
        { method: 'POST' }
      );
      if (response.ok) {
        // Remove from local state
        setConstraints((prev) => prev.filter((c) => c.rule_id !== ruleId));
      }
    } catch (e) {
      console.error('Failed to revoke constraint:', e);
    }
  }, [salespersonId]);

  // Day 4: Load profile from backend
  const loadProfile = useCallback(async () => {
    if (!salespersonId) return;

    try {
      const response = await fetch(`${BACKEND_URL}/memory/profile/${salespersonId}`);
      if (response.ok) {
        const data = await response.json();
        setProfile(data);
      }
    } catch (e) {
      console.error('Failed to load profile:', e);
    }
  }, [salespersonId]);

  // Checkpoint actions - now returns result with artifacts info
  const approveCheckpoint = useCallback(async () => {
    if (!sessionId || !activeCheckpoint) return;

    setIsLoading(true);
    try {
      const response = await fetch(`${BACKEND_URL}/workflow/interact`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'checkpoint_decision',
          session_id: sessionId,
          checkpoint_id: activeCheckpoint.id,
          decision: 'approve',
        }),
      });
      if (!response.ok) throw new Error('Failed to approve checkpoint');
      const data = await response.json();

      // Get the checkpoint result (generated artifact info)
      const checkpoint = data.checkpoint;
      if (checkpoint?.result) {
        const result = checkpoint.result as Record<string, unknown>;
        const artifact: Artifact = {
          id: checkpoint.id,
          type:
            (checkpoint.action?.type?.replace('generate_', '') as
              | 'pptx'
              | 'userflow'
              | 'quote'
              | 'wireframe') || 'pptx',
          title: checkpoint.action?.description || 'Generated Artifact',
          preview:
            typeof result.preview === 'object'
              ? JSON.stringify(result.preview)
              : String(result.preview ?? result.status ?? 'Artifact generated'),
          // Text content for inline render (Mermaid / HTML)
          data: (result.code || result.content || result.mermaid) as string | undefined,
          // Backend download URL (for PPTX and other binary files)
          download_url: result.download_url as string | undefined,
          artifact_id: result.artifact_id as string | undefined,
        };
        setArtifacts((prev) => [...prev, artifact]);
        if (typeof window !== 'undefined') {
          const existing = JSON.parse(sessionStorage.getItem('artifacts') || '[]');
          sessionStorage.setItem('artifacts', JSON.stringify([...existing, artifact]));
        }
      }

      if (data.clarifying_question) {
        const msg: Message = {
          role: 'assistant',
          content: data.clarifying_question,
          agent: 'system',
          timestamp: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, msg]);
      }

      const proposalMsg: Message = {
        role: 'assistant',
        content: describeCheckpointForHistory(activeCheckpoint),
        agent: 'sales_orchestrator',
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, proposalMsg]);

      setActiveCheckpoint(null);

      if (data.resume) {
        await sendMessage(describeCheckpointApproval(activeCheckpoint), undefined, true, true);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setIsLoading(false);
    }
  }, [sessionId, activeCheckpoint, sendMessage]);

  const rejectCheckpoint = useCallback(async () => {
    if (!sessionId || !activeCheckpoint) return;

    setIsLoading(true);
    try {
      const response = await fetch(`${BACKEND_URL}/workflow/interact`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'checkpoint_decision',
          session_id: sessionId,
          checkpoint_id: activeCheckpoint.id,
          decision: 'reject',
        }),
      });
      if (!response.ok) throw new Error('Failed to reject checkpoint');
      const data = await response.json();
      setActiveCheckpoint(null);

      const clarifyingMsg =
        data.clarifying_question || 'Action rejected. How would you like to adjust?';
      const msg: Message = {
        role: 'assistant',
        content: clarifyingMsg,
        agent: 'sales_orchestrator',
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, msg]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setIsLoading(false);
    }
  }, [sessionId, activeCheckpoint]);

  const editCheckpoint = useCallback(
    async (params: Record<string, unknown>) => {
      if (!sessionId || !activeCheckpoint) return;

      setIsLoading(true);
      try {
        const response = await fetch(`${BACKEND_URL}/workflow/interact`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            action: 'checkpoint_decision',
            session_id: sessionId,
            checkpoint_id: activeCheckpoint.id,
            decision: 'edit',
            params,
          }),
        });
        if (!response.ok) throw new Error('Failed to edit checkpoint');
        const data = await response.json();

        if (data.brief) setBrief(data.brief);

        if (data.resume) {
          // The correction is in the brief; the stop was cleared server-side. Re-run
          // so the card comes back showing what was fixed — leaving a stale card on
          // screen next to an "updated" notice tells the rep nothing about whether
          // their edit took.
          //
          // Same as approveCheckpoint: preserve what the card was proposing as a
          // normal assistant message before it disappears, so the rep's own
          // "✅ Đã sửa" reply isn't left replying to nothing on scrollback.
          const proposalMsg: Message = {
            role: 'assistant',
            content: describeCheckpointForHistory(activeCheckpoint),
            agent: 'sales_orchestrator',
            timestamp: new Date().toISOString(),
          };
          setMessages((prev) => [...prev, proposalMsg]);

          setActiveCheckpoint(null);
          await sendMessage(describeCheckpointEdit(params), undefined, true, true);
        } else {
          setActiveCheckpoint(data.checkpoint ?? null);
          setMessages((prev) => [
            ...prev,
            {
              role: 'assistant',
              content: 'Đã cập nhật. Bạn xem lại rồi duyệt giúp mình nhé.',
              agent: 'sales_orchestrator',
              timestamp: new Date().toISOString(),
            },
          ]);
        }
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId, activeCheckpoint, sendMessage]
  );

  // Clear error
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  // Cleanup on unmount — abort all in-flight streams across all modes.
  // Same object reference for the lifetime of the hook (mutated in place,
  // never reassigned), so capturing it here still sees controllers added later.
  useEffect(() => {
    const controllers = modeAbortControllers.current;
    return () => {
      Object.values(controllers).forEach((c) => c?.abort());
    };
  }, []);

  // Load a session by session_id from backend
  const loadSession = useCallback(async (targetSessionId: string) => {
    try {
      setIsLoading(true);
      setError(null);
      const token = localStorage.getItem('auth_token');
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;

      // BACKEND_URL already contains /api (e.g. https://domain/api)
      // Strip it before appending /api/user/sessions to avoid double /api
      const sessionBaseUrl = BACKEND_URL.endsWith('/api') ? BACKEND_URL.slice(0, -4) : BACKEND_URL;
      const res = await fetch(`${sessionBaseUrl}/api/user/sessions/${targetSessionId}`, { headers });
      if (!res.ok) {
        throw new Error('Không thể nạp lịch sử cuộc nói chuyện');
      }
      const data = await res.json();
      setSessionId(data.session_id);
      // The deck/PPTX links only ever arrived as a one-off SSE event on the turn
      // that built them, never saved onto the message itself — so reopening a past
      // conversation from the sidebar showed no way to re-download a deck that was
      // still sitting on disk the whole time. The backend now reconstructs it as
      // `proposal_assets`; attach it to the last assistant turn, same place a live
      // stream would have put it, so MessageBubble's existing download buttons
      // just work without new UI.
      let msgs: Message[] = data.messages || [];
      let lastAssistantTimestamp: string | undefined;
      if (data.proposal_assets && msgs.length > 0) {
        const lastAssistantIdx = msgs.map((m) => m.role).lastIndexOf('assistant');
        if (lastAssistantIdx !== -1) {
          lastAssistantTimestamp = msgs[lastAssistantIdx].timestamp;
          msgs = msgs.map((m, i) =>
            i === lastAssistantIdx ? { ...m, proposalAssets: data.proposal_assets } : m
          );
        }
      }
      setMessages(msgs);
      // Reset rather than merge: this is a different conversation, and the
      // previous session's artifact list (or the stale sessionStorage copy the
      // legacy checkpoint flow writes) must not bleed into it.
      setArtifacts(
        data.proposal_assets
          ? proposalAssetsToArtifacts(data.proposal_assets, lastAssistantTimestamp)
          : []
      );
      // Same reset-not-merge rule as the artifact list above, and for a sharper reason: this
      // state drives the deliverables bar pinned above the composer, so leaving the previous
      // conversation's value in place offers the rep another client's deck and PPTX on this
      // one. Only the SSE handler used to set it, so a resumed session showed no bar at all
      // while a session switch showed the wrong one.
      setProposalAssets(data.proposal_assets ?? null);
      if (data.brief) setBrief(data.brief);
      setPendingQuestions([]);
      setActiveCheckpoint(null);
      setThinkingSteps([]);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Có lỗi khi tải session');
    } finally {
      setIsLoading(false);
    }
  }, []);

  return {
    sessionId,
    messages,
    isLoading,
    isThinking,
    error,
    pendingQuestions,
    activeCheckpoint,
    activeAgents,
    constraints,  // Day 4
    profile,  // Day 4
    brief,  // Day 4
    artifacts,  // Day 6: Generated artifacts
    proposalAssets,
    thinkingSteps,  // Live thinking trace
    sendMessage,
    answerQuestion,
    answerAllQuestions,
    skipQuestion,
    freeTextAnswer,
    revokeConstraint,  // Day 4
    loadConstraints,  // Day 4
    loadProfile,  // Day 4
    approveCheckpoint,
    rejectCheckpoint,
    editCheckpoint,
    clearError,
    resetSession,
    loadSession,
  };
}
