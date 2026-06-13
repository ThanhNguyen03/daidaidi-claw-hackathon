/**
 * Chat Window Component
 * =====================
 * Main chat interface with message list and input.
 */

import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2 } from 'lucide-react';
import { MessageBubble } from './MessageBubble';
import { QuestionCard } from './QuestionCard';
import type { Message, Question, Checkpoint, Brief, ChatMode } from '../lib/types';

interface ChatWindowProps {
  messages: Message[];
  isLoading: boolean;
  error: string | null;
  pendingQuestions: Question[];
  activeCheckpoint: Checkpoint | null;
  mode: ChatMode;
  onSendMessage: (message: string, brief?: Brief) => void;
  onAnswerQuestion: (questionId: string, answer: string) => void;
  onSkipQuestion?: (questionId: string) => void; // Day 3: Skip optional question
  onFreeTextAnswer?: (freeText: string) => void; // Day 3: C.5 §5 - answer multiple questions at once
  onApproveCheckpoint: () => void;
  onRejectCheckpoint: () => void;
  onEditCheckpoint: (params: Record<string, unknown>) => void;
  onClearError: () => void;
}

// Checkpoint Card Component
function CheckpointCard({
  checkpoint,
  onApprove,
  onReject,
  onEdit,
}: {
  checkpoint: Checkpoint;
  onApprove: () => void;
  onReject: () => void;
  onEdit: (params: Record<string, unknown>) => void;
}) {
  return (
    <div
      style={{
        border: '1px solid #3b82f6',
        backgroundColor: '#eff6ff',
        padding: '1rem',
        borderRadius: '0.5rem',
        marginBottom: '1rem',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
        <span style={{ fontSize: '1.25rem' }}>⚠️</span>
        <div style={{ flex: 1 }}>
          <h3 style={{ fontWeight: '600', color: '#1e40af', marginBottom: '0.5rem' }}>
            Action Requires Approval
          </h3>
          <p style={{ fontSize: '0.875rem', color: '#1e3a8a', marginBottom: '0.75rem' }}>
            {checkpoint.action.description}
          </p>

          {/* Preview if available */}
          {checkpoint.action.preview && (
            <div
              style={{
                backgroundColor: '#ffffff',
                padding: '0.75rem',
                borderRadius: '0.375rem',
                marginBottom: '1rem',
                fontSize: '0.8125rem',
              }}
            >
              <pre style={{ whiteSpace: 'pre-wrap', margin: 0 }}>
                {JSON.stringify(checkpoint.action.preview, null, 2)}
              </pre>
            </div>
          )}

          {/* Action buttons */}
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              onClick={onApprove}
              style={{
                padding: '0.5rem 1rem',
                backgroundColor: '#3b82f6',
                color: '#ffffff',
                border: 'none',
                borderRadius: '0.375rem',
                fontSize: '0.875rem',
                fontWeight: '500',
                cursor: 'pointer',
              }}
            >
              Approve
            </button>
            <button
              onClick={onReject}
              style={{
                padding: '0.5rem 1rem',
                backgroundColor: 'transparent',
                color: '#6b7280',
                border: '1px solid #d1d5db',
                borderRadius: '0.375rem',
                fontSize: '0.875rem',
                cursor: 'pointer',
              }}
            >
              Reject
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export function ChatWindow({
  messages,
  isLoading,
  error,
  pendingQuestions,
  activeCheckpoint,
  mode,
  onSendMessage,
  onAnswerQuestion,
  onSkipQuestion,
  onFreeTextAnswer,
  onApproveCheckpoint,
  onRejectCheckpoint,
  onEditCheckpoint,
  onClearError,
}: ChatWindowProps) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input);
      setInput('');
    }
  };

  // Get mode indicator
  const modeLabels: Record<ChatMode, string> = {
    chat: '💬 Chat Mode',
    planning: '📋 Planning Mode',
    execute: '🚀 Execute Mode',
    brainstorm: '💡 Brainstorm Mode',
  };

  return (
    <div
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        backgroundColor: '#f9fafb',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '1rem 1.5rem',
          backgroundColor: '#ffffff',
          borderBottom: '1px solid #e5e7eb',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <h2 style={{ fontSize: '1.125rem', fontWeight: '600', color: '#111827' }}>
          {modeLabels[mode]}
        </h2>
        {isLoading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#6b7280' }}>
            <Loader2 size={16} className="animate-spin" />
            <span style={{ fontSize: '0.875rem' }}>Thinking...</span>
          </div>
        )}
      </div>

      {/* Error display */}
      {error && (
        <div
          style={{
            padding: '0.75rem 1.5rem',
            backgroundColor: '#fef2f2',
            borderBottom: '1px solid #fecaca',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span style={{ color: '#dc2626', fontSize: '0.875rem' }}>{error}</span>
          <button
            onClick={onClearError}
            style={{
              background: 'none',
              border: 'none',
              color: '#6b7280',
              cursor: 'pointer',
              fontSize: '0.875rem',
            }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Messages area */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '1.5rem',
        }}
      >
        {/* Welcome message if no messages */}
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', padding: '2rem', color: '#6b7280' }}>
            <p style={{ fontSize: '1.125rem', marginBottom: '0.5rem' }}>
              Welcome to Sales AI Assistant! 👋
            </p>
            <p style={{ fontSize: '0.875rem' }}>
              I'm your multi-agent sales assistant. How can I help you today?
            </p>
          </div>
        )}

        {/* Messages */}
        {messages.map((msg, index) => (
          <MessageBubble key={index} message={msg} />
        ))}

        {/* Pending Questions - Day 3: Question cards (yellow, distinct from checkpoint) */}
        {/* Use standalone QuestionCard component - CHECK.md Issue #6 */}
        {pendingQuestions.length > 0 && (
          <QuestionCard
            questions={pendingQuestions}
            onAnswer={onAnswerQuestion}
            onSkip={onSkipQuestion || (() => {})}
            onFreeTextAnswer={onFreeTextAnswer || ((_ft: string) => {})}
            disabled={isLoading}
          />
        )}

        {/* Active Checkpoint */}
        {activeCheckpoint && (
          <CheckpointCard
            checkpoint={activeCheckpoint}
            onApprove={onApproveCheckpoint}
            onReject={onRejectCheckpoint}
            onEdit={onEditCheckpoint}
          />
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div
        style={{
          padding: '1rem 1.5rem',
          backgroundColor: '#ffffff',
          borderTop: '1px solid #e5e7eb',
        }}
      >
        <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '0.75rem' }}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your message..."
            disabled={isLoading}
            style={{
              flex: 1,
              padding: '0.75rem 1rem',
              border: '1px solid #d1d5db',
              borderRadius: '0.5rem',
              fontSize: '0.9375rem',
              outline: 'none',
              transition: 'border-color 0.15s ease',
            }}
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            style={{
              padding: '0.75rem 1.25rem',
              backgroundColor: input.trim() && !isLoading ? '#3b82f6' : '#9ca3af',
              color: '#ffffff',
              border: 'none',
              borderRadius: '0.5rem',
              fontSize: '0.9375rem',
              fontWeight: '500',
              cursor: input.trim() && !isLoading ? 'pointer' : 'not-allowed',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
            }}
          >
            <Send size={18} />
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
