/**
 * Chat Hook with SSE Support
 * ==========================
 * Custom hook for handling chat with server-sent events streaming.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import type { ChatRequest, Message, Brief, ChatMode, Question, Checkpoint, FeedbackRule, SalespersonProfile } from '../lib/types';
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
  brainState: {  // Day 7: Brainstorm state
    session_id: string;
    participants: Array<{ agent_name: string; is_active: boolean; rounds_spoken: number }>;
    current_speaker: string | null;
    ask_lock_holder: string | null;
    round_count: number;
    max_rounds: number;
    is_frozen: boolean;
    is_ended: boolean;
  } | null;

  // Actions
  sendMessage: (message: string, brief?: Brief) => Promise<void>;
  answerQuestion: (questionId: string, answer: string) => Promise<void>;
  skipQuestion: (questionId: string) => Promise<void>;
  freeTextAnswer: (freeText: string) => Promise<void>;  // Day 3: C.5 §5
  revokeConstraint: (ruleId: string) => Promise<void>;  // Day 4: Revoke constraint
  loadConstraints: () => Promise<void>;  // Day 4: Load constraints
  loadProfile: () => Promise<void>;  // Day 4: Load profile
  approveCheckpoint: () => Promise<void>;
  rejectCheckpoint: () => Promise<void>;
  editCheckpoint: (params: Record<string, unknown>) => Promise<void>;
  clearError: () => void;
  // Day 7: Brainstorm actions
  addParticipant: (agentName: string) => void;
  removeParticipant: (agentName: string) => void;
  requestAskLock: () => void;
  releaseAskLock: () => void;
}

export function useChat(options: UseChatOptions): UseChatReturn {
  const { salespersonId, displayName, mode = 'chat' } = options;

  // State
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingQuestions, setPendingQuestions] = useState<Question[]>([]);
  const [activeCheckpoint, setActiveCheckpoint] = useState<Checkpoint | null>(null);
  const [activeAgents, setActiveAgents] = useState<AgentStatus[]>([
    { name: 'scoping', status: 'idle' },
    { name: 'sales_orchestrator', status: 'idle' },
    { name: 'requirement_elicitation', status: 'idle' },
    { name: 'market_strategy', status: 'idle' },
    { name: 'compliance', status: 'idle' },
    { name: 'product_solution', status: 'idle' },
    { name: 'design', status: 'idle' },
    { name: 'client_simulator', status: 'idle' },
  ]);

  // Day 4: Constraints and profile state
  const [constraints, setConstraints] = useState<FeedbackRule[]>([]);
  const [profile, setProfile] = useState<SalespersonProfile | null>(null);
  const [brief, setBrief] = useState<Brief | null>(null);

  // Thinking state — true while the LLM is emitting <think> reasoning tokens
  const [isThinking, setIsThinking] = useState(false);

  // Day 6: Artifacts state
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);

  // Day 7: Brainstorm state
  const [brainState, setBrainState] = useState<{
    session_id: string;
    participants: Array<{ agent_name: string; is_active: boolean; rounds_spoken: number }>;
    current_speaker: string | null;
    ask_lock_holder: string | null;
    round_count: number;
    max_rounds: number;
    is_frozen: boolean;
    is_ended: boolean;
  } | null>(null);

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

  // Ref for aborting requests
  const abortControllerRef = useRef<AbortController | null>(null);

  // Reset agent statuses when starting new message
  const resetAgentStatuses = useCallback(() => {
    setActiveAgents((prev) => prev.map((agent) => ({ ...agent, status: 'idle' as const })));
  }, []);

  // Send message with SSE streaming
  const sendMessage = useCallback(
    async (message: string, brief?: Brief) => {
      // Cancel any existing request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      abortControllerRef.current = new AbortController();

      setIsLoading(true);
      setError(null);
      setIsThinking(false);
      resetAgentStatuses();

      // Add user message immediately
      const userMessage: Message = {
        role: 'user',
        content: message,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMessage]);

      let response: Response;

      const requestBody = JSON.stringify({
        message,
        session_id: sessionId,
        salesperson_id: salespersonId,
        mode,
        brief,
      });

      try {
        response = await fetch(`${BACKEND_URL}/chat/stream`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: requestBody,
          signal: abortControllerRef.current.signal,
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
          // Request was cancelled, ignore
          return;
        }
        setError((e as Error).message);
      } finally {
        setIsLoading(false);
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
          // New session created
          if (data.session_id && !sessionId) {
            setSessionId(data.session_id as string);
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
            setMessages((prev) => {
              const last = prev[prev.length - 1];
              if (last && last.role === 'assistant' && last.agent === 'sales_orchestrator') {
                // Append to existing assistant message
                return [...prev.slice(0, -1), { ...last, content: last.content + content }];
              } else {
                // Create new assistant message
                return [
                  ...prev,
                  {
                    role: 'assistant',
                    content,
                    agent: 'sales_orchestrator',
                    timestamp: new Date().toISOString(),
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
          // Session state updated
          if (data.session_id) {
            setSessionId(data.session_id as string);
          }
          // Update brief if provided
          if (data.brief) {
            setBrief(data.brief as Brief);
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
            if (agentName && agentStatus) {
              setActiveAgents((prev) => {
                // Update or add agent status
                const existing = prev.findIndex((a) => a.name === agentName);
                const newAgent = { name: agentName, status: agentStatus as AgentStatus['status'] };
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

        case 'constraint_added':
          // Day 4: New constraint added from feedback
          {
            const constraint = data.constraint as FeedbackRule;
            if (constraint) {
              setConstraints((prev) => [...prev, constraint]);
            }
          }
          break;

        // Day 7: Brainstorm mode events
        case 'brainstorm_start':
          {
            const sessionId_bs = data.session_id as string;
            const participants_bs = data.participants as string[];
            setBrainState({
              session_id: sessionId_bs,
              participants: participants_bs.map(name => ({
                agent_name: name,
                is_active: true,
                rounds_spoken: 0,
              })),
              current_speaker: null,
              ask_lock_holder: null,
              round_count: 0,
              max_rounds: 8,
              is_frozen: false,
              is_ended: false,
            });
          }
          break;

        case 'speaker_turn':
          {
            const speaker = data.speaker as string;
            setBrainState(prev => prev ? {
              ...prev,
              current_speaker: speaker,
              round_count: prev.round_count + 1,
              participants: prev.participants.map(p => ({
                ...p,
                rounds_spoken: p.agent_name === speaker ? p.rounds_spoken + 1 : p.rounds_spoken,
              })),
            } : null);
          }
          break;

        case 'brainstorm_end':
          {
            const reason = data.reason as string;
            const summary = data.summary as string;
            setBrainState(prev => prev ? {
              ...prev,
              is_ended: true,
            } : null);
            // Add summary as assistant message
            const msg: Message = {
              role: 'assistant',
              content: `Brainstorm ended (${reason}): ${summary}`,
              agent: 'moderator',
              timestamp: new Date().toISOString(),
            };
            setMessages((prev) => [...prev, msg]);
          }
          break;

        case 'continue':
          {
            const nextSpeaker = data.next_speaker as string;
            setBrainState(prev => prev ? {
              ...prev,
              current_speaker: nextSpeaker,
            } : null);
          }
          break;

        case 'ask_lock_granted':
          {
            const holder = data.holder as string;
            setBrainState(prev => prev ? {
              ...prev,
              ask_lock_holder: holder,
            } : null);
          }
          break;

        case 'ask_lock_released':
          {
            setBrainState(prev => prev ? {
              ...prev,
              ask_lock_holder: null,
            } : null);
          }
          break;

        default:
          console.log('Unknown SSE event:', data);
      }
    },
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
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setIsLoading(false);
    }
  }, [sessionId, activeCheckpoint]);

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

        if (data.checkpoint) {
          setActiveCheckpoint(data.checkpoint);
        } else {
          setActiveCheckpoint(null);
        }

        const msg: Message = {
          role: 'assistant',
          content: 'Parameters updated. Please review the new preview and approve.',
          agent: 'sales_orchestrator',
          timestamp: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, msg]);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId, activeCheckpoint]
  );

  // Clear error
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  // Day 7: Brainstorm actions
  const addParticipant = useCallback((agentName: string) => {
    setBrainState(prev => prev ? {
      ...prev,
      participants: [...prev.participants, {
        agent_name: agentName,
        is_active: true,
        rounds_spoken: 0,
      }],
    } : null);
  }, []);

  const removeParticipant = useCallback((agentName: string) => {
    setBrainState(prev => prev ? {
      ...prev,
      participants: prev.participants.filter(p => p.agent_name !== agentName),
    } : null);
  }, []);

  const requestAskLock = useCallback(() => {
    // In a real implementation, this would call the backend
    // For now, just update local state (backend will validate)
    console.log('Requesting ask lock...');
  }, []);

  const releaseAskLock = useCallback(() => {
    // In a real implementation, this would call the backend
    console.log('Releasing ask lock...');
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
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
    brainState,  // Day 7: Brainstorm state
    sendMessage,
    answerQuestion,
    skipQuestion,
    freeTextAnswer,
    revokeConstraint,  // Day 4
    loadConstraints,  // Day 4
    loadProfile,  // Day 4
    approveCheckpoint,
    rejectCheckpoint,
    editCheckpoint,
    clearError,
    // Day 7: Brainstorm actions
    addParticipant,
    removeParticipant,
    requestAskLock,
    releaseAskLock,
  };
}
