/**
 * Chat Hook with SSE Support
 * ==========================
 * Custom hook for handling chat with server-sent events streaming.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import type { ChatRequest, Message, Brief, ChatMode, Question, Checkpoint, FeedbackRule, SalespersonProfile } from '../lib/types';

// Use BFF route ( Next.js API route) to keep API key server-side
// Fall back to direct backend call if BFF is not available
const BFF_URL = '/api/chat';
const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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

interface UseChatReturn {
  // State
  sessionId: string | null;
  messages: Message[];
  isLoading: boolean;
  error: string | null;
  pendingQuestions: Question[];
  activeCheckpoint: Checkpoint | null;
  activeAgents: AgentStatus[];
  constraints: FeedbackRule[];  // Day 4: Active constraints
  profile: SalespersonProfile | null;  // Day 4: User profile
  brief: Brief | null;  // Day 4: Current brief

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
    { name: 'orchestrator', status: 'idle' },
    { name: 'tech_solution', status: 'idle' },
    { name: 'market_strategy', status: 'idle' },
    { name: 'account', status: 'idle' },
  ]);

  // Day 4: Constraints and profile state
  const [constraints, setConstraints] = useState<FeedbackRule[]>([]);
  const [profile, setProfile] = useState<SalespersonProfile | null>(null);
  const [brief, setBrief] = useState<Brief | null>(null);

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
      resetAgentStatuses();

      // Add user message immediately
      const userMessage: Message = {
        role: 'user',
        content: message,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMessage]);

      let response: Response;

      // Try BFF first, fall back to direct backend
      try {
        try {
          response = await fetch(BFF_URL, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              message,
              session_id: sessionId,
              salesperson_id: salespersonId,
              mode,
              brief,
            }),
            signal: abortControllerRef.current.signal,
          });
        } catch {
          // Fall back to direct backend call
          response = await fetch(`${BACKEND_URL}/chat/stream`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              message,
              session_id: sessionId,
              salesperson_id: salespersonId,
              mode,
              brief,
            }),
            signal: abortControllerRef.current.signal,
          });
        }

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
    [sessionId, salespersonId, mode, resetAgentStatuses]
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

        case 'content':
          // Streaming content chunk
          {
            const content = data.content as string;
            setMessages((prev) => {
              const last = prev[prev.length - 1];
              if (last && last.role === 'assistant' && last.agent === 'orchestrator') {
                // Append to existing assistant message
                return [...prev.slice(0, -1), { ...last, content: last.content + content }];
              } else {
                // Create new assistant message
                return [
                  ...prev,
                  {
                    role: 'assistant',
                    content,
                    agent: 'orchestrator',
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
          // Checkpoint requiring approval
          {
            const checkpoint = data.checkpoint as Checkpoint;
            if (checkpoint) {
              setActiveCheckpoint(checkpoint);
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
        const response = await fetch(`${BACKEND_URL}/chat/answer`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: sessionId,
            question_id: questionId,
            answer: answer,
          }),
        });

        if (response.ok) {
          // Reload session state
          const data = await response.json();
          if (data.questions) {
            setPendingQuestions(data.questions);
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
        const response = await fetch(`${BACKEND_URL}/chat/skip_question`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: sessionId,
            question_id: questionId,
          }),
        });

        if (response.ok) {
          const data = await response.json();
          if (data.questions) {
            setPendingQuestions(data.questions);
          }
        }
      } catch {
        // Silently fail - assumption will be used
      }
    },
    [sessionId]
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
        const response = await fetch(`${BACKEND_URL}/chat/answer_free_text`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: sessionId,
            message: freeText,
            salesperson_id: salespersonId,
            mode,
          }),
        });

        if (response.ok) {
          const data = await response.json();
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
    [sessionId, salespersonId, mode, sendMessage]
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

  // Checkpoint actions
  const approveCheckpoint = useCallback(async () => {
    if (!sessionId || !activeCheckpoint) return;

    setIsLoading(true);
    try {
      // In full implementation, this would call an API endpoint
      // For now, just clear the checkpoint
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
      // In full implementation, this would call an API endpoint
      setActiveCheckpoint(null);

      // Add a message asking how to adjust
      const msg: Message = {
        role: 'assistant',
        content: 'Action rejected. How would you like to adjust the parameters?',
        agent: 'orchestrator',
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
        // In full implementation, this would call an API endpoint
        // For now, just clear the checkpoint (re-preview would happen server-side)
        setActiveCheckpoint(null);

        const msg: Message = {
          role: 'assistant',
          content: 'Parameters updated. Please review the new preview and approve.',
          agent: 'orchestrator',
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
    error,
    pendingQuestions,
    activeCheckpoint,
    activeAgents,
    constraints,  // Day 4
    profile,  // Day 4
    brief,  // Day 4
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
  };
}
