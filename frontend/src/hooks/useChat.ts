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
  sendMessage: (message: string, brief?: Brief, resume?: boolean) => Promise<void>;
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
    { name: 'design', status: 'idle' },
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
    isLoading: boolean;
    isThinking: boolean;
  };
  const savedModeStates = useRef<Record<string, ModeSnapshot>>({});

  // Always reflects the currently-active mode. Updated synchronously at the
  // top of the mode-switch effect so in-flight SSE callbacks can check it
  // without relying on a stale closure value.
  const currentModeRef = useRef<string>(mode);

  useEffect(() => {
    // Always sync ref first — SSE callbacks read this to know the live mode.
    currentModeRef.current = mode;

    const prevMode = prevModeRef.current;
    if (prevMode === mode) return;

    // NOTE: We intentionally do NOT abort the in-flight SSE request here.
    // Instead, the SSE loop checks currentModeRef vs its origin mode and
    // buffers content into savedModeStates so the user sees the response
    // when they switch back to the origin mode.

    // Snapshot current mode's state — include loading/thinking so the stream
    // continues visually when the user returns to this mode.
    savedModeStates.current[prevMode] = {
      sessionId,
      messages,
      brief,
      pendingQuestions,
      activeCheckpoint,
      artifacts,
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
      setIsLoading(saved.isLoading);
      setIsThinking(saved.isThinking);
    } else {
      setSessionId(null);
      setMessages([]);
      setBrief(null);
      setPendingQuestions([]);
      setActiveCheckpoint(null);
      setArtifacts([]);
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
      { name: 'design', status: 'idle' as const },
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
  }, [salespersonId, mode]);

  // Per-mode abort controllers so cancelling one mode's stream never kills another.
  const modeAbortControllers = useRef<Record<string, AbortController | null>>({});

  // Reset agent statuses when starting new message
  const resetAgentStatuses = useCallback(() => {
    setActiveAgents((prev) => prev.map((agent) => ({ ...agent, status: 'idle' as const })));
  }, []);

  // Send message with SSE streaming
  const sendMessage = useCallback(
    async (message: string, brief?: Brief, resume = false) => {
      // Capture origin mode first — everything below is scoped to this mode.
      const myMode = mode;

      // Cancel any existing request for THIS mode only — never touches other
      // modes' streams (that's the whole point of per-mode controllers).
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

      // Add user message immediately
      const userMessage: Message = {
        role: 'user',
        content: message,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMessage]);

      let response: Response;

      const isCs = mode === 'cs';
      const requestBody = isCs
        ? JSON.stringify({ message, session_id: sessionId, salesperson_id: salespersonId })
        : JSON.stringify({ message, session_id: sessionId, salesperson_id: salespersonId, mode, brief, resume });

      try {
        response = await fetch(`${BACKEND_URL}${isCs ? '/cs/chat/stream' : '/chat/stream'}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
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
                // Mode switched while this stream was in flight. Buffer content
                // into the origin mode's saved snapshot so the user sees the
                // response when they switch back — without writing to the wrong
                // mode's live message list.
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
                await handleSSEEvent(data);
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
          // "network error" / "Failed to fetch" is what the browser reports when a
          // stream is cut, which says nothing about whether the work survived — and
          // the rep's own connection is usually fine. Name the likely cause and the
          // action instead of echoing the browser's wording.
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
    async (data: { type: string; [key: string]: unknown }) => {
      switch (data.type) {
        case 'session':
          // Session confirmed — persist id and sync brief from BE
          if (data.session_id) {
            const sid = data.session_id as string;
            setSessionId(sid);
            if (typeof window !== 'undefined') {
              sessionStorage.setItem(`chat_session_${salespersonIdRef.current}`, sid);
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
          // Streaming content chunk — reasoning tokens have already been stripped by the backend
          setIsThinking(false);
          {
            const content = data.content as string;
            // Determine agent name for this streaming turn
            const streamAgent = mode === 'cs' ? 'cs_agent' : 'sales_orchestrator';
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

        case 'session':
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
            }
          }
          break;

        default:
          console.log('Unknown SSE event:', data);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [sessionId]
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
  //
  // The per-question version advanced the pipeline as soon as the first answer
  // landed, which discarded the rest of the card. The card asks for several
  // blocking fields at once precisely because they are needed together, so the
  // commit has to be together too.
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
          await sendMessage('Tiếp tục', undefined, true);
        }
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId, sendMessage]
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
      setActiveCheckpoint(null);

      // The confirmation stops (Chốt 1 / Chốt 2) pause the pipeline mid-run.
      // Approving has to restart it — otherwise the card just disappears and the
      // rep is left staring at a conversation that stopped for no visible reason.
      if (data.resume) {
        await sendMessage('Tiếp tục', undefined, true);
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
          setActiveCheckpoint(null);
          await sendMessage('Tiếp tục', undefined, true);
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

  // Cleanup on unmount — abort all in-flight streams across all modes
  useEffect(() => {
    return () => {
      Object.values(modeAbortControllers.current).forEach((c) => c?.abort());
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

      const res = await fetch(`${BACKEND_URL}/api/user/sessions/${targetSessionId}`, { headers });
      if (!res.ok) {
        throw new Error('Không thể nạp lịch sử cuộc nói chuyện');
      }
      const data = await res.json();
      setSessionId(data.session_id);
      setMessages(data.messages || []);
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
