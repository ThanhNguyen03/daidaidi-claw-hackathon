/**
 * Chat Hook with SSE Support
 * ==========================
 * Custom hook for handling chat with server-sent events streaming.
 */

import { useState, useCallback, useRef, useEffect } from "react";
import type { ChatRequest, Message, Brief, ChatMode, Question, Checkpoint } from "../lib/types";

// Use BFF route ( Next.js API route) to keep API key server-side
// Fall back to direct backend call if BFF is not available
const BFF_URL = "/api/chat";
const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface UseChatOptions {
  salespersonId: string;
  displayName: string;
  mode?: ChatMode;
}

interface UseChatReturn {
  // State
  sessionId: string | null;
  messages: Message[];
  isLoading: boolean;
  error: string | null;
  pendingQuestions: Question[];
  activeCheckpoint: Checkpoint | null;

  // Actions
  sendMessage: (message: string, brief?: Brief) => Promise<void>;
  answerQuestion: (questionId: string, answer: string) => Promise<void>;
  approveCheckpoint: () => Promise<void>;
  rejectCheckpoint: () => Promise<void>;
  editCheckpoint: (params: Record<string, unknown>) => Promise<void>;
  clearError: () => void;
}

export function useChat(options: UseChatOptions): UseChatReturn {
  const { salespersonId, displayName, mode = "chat" } = options;

  // State
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingQuestions, setPendingQuestions] = useState<Question[]>([]);
  const [activeCheckpoint, setActiveCheckpoint] = useState<Checkpoint | null>(null);

  // Ref for aborting requests
  const abortControllerRef = useRef<AbortController | null>(null);

  // Send message with SSE streaming
  const sendMessage = useCallback(async (message: string, brief?: Brief) => {
    // Cancel any existing request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    setIsLoading(true);
    setError(null);

    // Add user message immediately
    const userMessage: Message = {
      role: "user",
      content: message,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);

    try {
      // Try BFF first, fall back to direct backend
      let response: Response;
      try {
        response = await fetch(BFF_URL, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
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
        method: "POST",
        headers: {
          "Content-Type": "application/json",
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

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("No response body");
      }

      const decoder = new TextDecoder();
      let buffer = "";

      // Process SSE stream
      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Process complete SSE events
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              await handleSSEEvent(data);
            } catch (e) {
              console.error("Failed to parse SSE data:", e);
            }
          }
        }
      }
    } catch (e) {
      if ((e as Error).name === "AbortError") {
        // Request was cancelled, ignore
        return;
      }
      setError((e as Error).message);
    } finally {
      setIsLoading(false);
    }
  }, [sessionId, salespersonId, mode]);

  // Handle SSE events
  const handleSSEEvent = useCallback(async (data: { type: string; [key: string]: unknown }) => {
    switch (data.type) {
      case "session":
        // New session created
        if (data.session_id && !sessionId) {
          setSessionId(data.session_id as string);
        }
        break;

      case "user_message":
        // User message echoed back
        break;

      case "content":
        // Streaming content chunk
        const content = data.content as string;
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last && last.role === "assistant" && last.agent === "orchestrator") {
            // Append to existing assistant message
            return [
              ...prev.slice(0, -1),
              { ...last, content: last.content + content },
            ];
          } else {
            // Create new assistant message
            return [
              ...prev,
              {
                role: "assistant",
                content,
                agent: "orchestrator",
                timestamp: new Date().toISOString(),
              },
            ];
          }
        });
        break;

      case "error":
        setError(data.error as string);
        break;

      case "done":
        // Stream complete
        break;

      case "session_updated":
        // Session state updated
        if (data.session_id) {
          setSessionId(data.session_id as string);
        }
        break;

      case "question":
        // Questions from agent
        const questions = data.questions as Question[];
        if (questions) {
          setPendingQuestions(questions);
        }
        break;

      case "checkpoint":
        // Checkpoint requiring approval
        const checkpoint = data.checkpoint as Checkpoint;
        if (checkpoint) {
          setActiveCheckpoint(checkpoint);
        }
        break;

      default:
        console.log("Unknown SSE event:", data);
    }
  }, [sessionId]);

  // Answer a pending question
  const answerQuestion = useCallback(async (questionId: string, answer: string) => {
    // Remove from pending and continue conversation
    setPendingQuestions((prev) => prev.filter((q) => q.id !== questionId));

    // Send answer as a follow-up message
    await sendMessage(`Answer to question: ${answer}`);
  }, [sendMessage]);

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
        role: "assistant",
        content: "Action rejected. How would you like to adjust the parameters?",
        agent: "orchestrator",
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, msg]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setIsLoading(false);
    }
  }, [sessionId, activeCheckpoint]);

  const editCheckpoint = useCallback(async (params: Record<string, unknown>) => {
    if (!sessionId || !activeCheckpoint) return;

    setIsLoading(true);
    try {
      // In full implementation, this would call an API endpoint
      // For now, just clear the checkpoint (re-preview would happen server-side)
      setActiveCheckpoint(null);

      const msg: Message = {
        role: "assistant",
        content: "Parameters updated. Please review the new preview and approve.",
        agent: "orchestrator",
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, msg]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setIsLoading(false);
    }
  }, [sessionId, activeCheckpoint]);

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
    sendMessage,
    answerQuestion,
    approveCheckpoint,
    rejectCheckpoint,
    editCheckpoint,
    clearError,
  };
}