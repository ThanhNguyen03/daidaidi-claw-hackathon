/**
 * Chat Window Component
 * =====================
 * Main chat interface with message list and input.
 * Uses Tailwind CSS for styling.
 */

import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2, PanelRightClose, Menu, AlertTriangle, Check, X, Edit } from 'lucide-react';
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
  onSkipQuestion?: (questionId: string) => void;
  onFreeTextAnswer?: (freeText: string) => void;
  onApproveCheckpoint: () => void;
  onRejectCheckpoint: () => void;
  onEditCheckpoint: (params: Record<string, unknown>) => void;
  onClearError: () => void;
  onToggleContextPanel?: () => void;
  onToggleMobileSidebar?: () => void;
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
  const [autoApprove, setAutoApprove] = useState(false);
  const [isEditing, setIsEditing] = useState(false);

  const hasBlocking = checkpoint.compliance_findings?.some(f => f.severity === 'block');

  // Format preview as a table
  const formatPreview = (preview: unknown): React.ReactNode => {
    if (!preview) return null;

    if (typeof preview === 'object') {
      const entries = Object.entries(preview as Record<string, unknown>);
      if (entries.length === 0) return null;

      return (
        <div className="bg-surface rounded overflow-hidden text-xs">
          <table className="w-full border-collapse">
            <tbody>
              {entries.map(([key, value]) => (
                <tr key={key} className="border-b border-border">
                  <td className="py-2 px-3 font-medium text-text-muted w-2/5">
                    {key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                  </td>
                  <td className="py-2 px-3 text-text">
                    {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }

    return <pre className="whitespace-pre-wrap m-0">{String(preview)}</pre>;
  };

  const handleEditSubmit = () => {
    onEdit({});
    setIsEditing(false);
  };

  return (
    <div className="border-2 border-accent bg-accent-soft rounded-lg p-4 mb-4">
      {/* Compliance Findings */}
      {checkpoint.compliance_findings && checkpoint.compliance_findings.length > 0 && (
        <div className="mb-4">
          {checkpoint.compliance_findings.map((finding, idx) => (
            <div
              key={idx}
              className={`
                p-3 rounded mb-2
                ${finding.severity === 'block' ? 'bg-red-50 border border-red-200' : ''}
                ${finding.severity === 'warn' ? 'bg-yellow-50 border border-yellow-200' : ''}
                ${finding.severity === 'info' ? 'bg-blue-50 border border-blue-200' : ''}
              `}
            >
              <div className="flex items-start gap-2">
                <span>{finding.severity === 'block' ? '🔴' : finding.severity === 'warn' ? '⚠️' : 'ℹ️'}</span>
                <div className="flex-1">
                  <p className="text-sm font-medium">{finding.message}</p>
                  {finding.suggestion && (
                    <p className="text-xs opacity-80 mt-1">Suggestion: {finding.suggestion}</p>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="flex items-start gap-3">
        <AlertTriangle size={24} className="text-accent shrink-0 mt-0.5" />
        <div className="flex-1">
          <h3 className="font-semibold text-accent-text mb-2">Action Requires Approval</h3>
          <p className="text-sm text-accent-text mb-3">{checkpoint.action.description}</p>

          {/* Preview */}
          {checkpoint.action.preview && !isEditing && <div className="mb-4">{formatPreview(checkpoint.action.preview)}</div>}

          {/* Edit mode */}
          {isEditing && (
            <div className="mb-4 p-3 bg-surface rounded">
              <p className="text-xs text-text-muted mb-2">Edit parameters and re-preview:</p>
              <p className="text-xs text-text-muted">Edit functionality available — modify parameters and submit to re-preview.</p>
            </div>
          )}

          {/* Auto-approve checkbox */}
          {checkpoint.action.type !== 'send_external' && !isEditing && (
            <label className="flex items-center gap-2 mb-3 text-xs text-text-muted cursor-pointer">
              <input
                type="checkbox"
                checked={autoApprove}
                onChange={(e) => setAutoApprove(e.target.checked)}
                className="rounded"
              />
              Don't ask again for {checkpoint.action.type} this session
            </label>
          )}

          {/* Action buttons */}
          <div className="flex gap-2 flex-wrap">
            {isEditing ? (
              <>
                <button
                  onClick={handleEditSubmit}
                  className="flex items-center gap-1 px-4 py-2 bg-accent text-white rounded-md text-sm font-medium hover:opacity-90"
                >
                  <Check size={16} /> Re-preview
                </button>
                <button
                  onClick={() => setIsEditing(false)}
                  className="flex items-center gap-1 px-4 py-2 border border-border text-text-muted rounded-md text-sm hover:bg-surface-hover"
                >
                  <X size={16} /> Cancel
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={onApprove}
                  disabled={hasBlocking}
                  className={`flex items-center gap-1 px-4 py-2 rounded-md text-sm font-medium ${
                    hasBlocking
                      ? 'bg-text-muted text-white cursor-not-allowed'
                      : 'bg-accent text-white hover:opacity-90'
                  }`}
                >
                  <Check size={16} /> Approve
                </button>
                <button
                  onClick={() => setIsEditing(true)}
                  className="flex items-center gap-1 px-4 py-2 border border-border text-text-muted rounded-md text-sm hover:bg-surface-hover"
                >
                  <Edit size={16} /> Edit
                </button>
                <button
                  onClick={onReject}
                  className="flex items-center gap-1 px-4 py-2 border border-border text-text-muted rounded-md text-sm hover:bg-surface-hover"
                >
                  <X size={16} /> Reject
                </button>
              </>
            )}
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
  onToggleContextPanel,
  onToggleMobileSidebar,
}: ChatWindowProps) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

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

  const modeLabels: Record<ChatMode, { icon: string; label: string }> = {
    chat: { icon: '💬', label: 'Chat' },
    planning: { icon: '📋', label: 'Planning' },
    execute: { icon: '🚀', label: 'Execute' },
    brainstorm: { icon: '💡', label: 'Brainstorm' },
  };

  return (
    <div className="flex-1 flex flex-col min-h-screen bg-bg">
      {/* Header */}
      <header className="sticky top-0 z-30 px-6 py-4 bg-surface border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-3">
          {/* Mobile sidebar toggle */}
          <button
            onClick={onToggleMobileSidebar}
            className="md:hidden p-2 border border-border rounded hover:bg-surface-hover"
          >
            <Menu size={20} className="text-text-muted" />
          </button>

          {/* Mode indicator */}
          <h2 className="text-lg font-semibold text-text flex items-center gap-2 relative">
            <span className="text-accent">{modeLabels[mode].icon}</span>
            {modeLabels[mode].label} Mode
          </h2>
        </div>

        <div className="flex items-center gap-2">
          {isLoading && (
            <div className="flex items-center gap-2 text-text-muted">
              <Loader2 size={16} className="animate-spin" />
              <span className="text-sm">Thinking...</span>
            </div>
          )}

          {onToggleContextPanel && (
            <button
              onClick={onToggleContextPanel}
              className="p-2 border border-border rounded hover:bg-surface-hover"
              title="Toggle Context Panel"
            >
              <PanelRightClose size={20} className="text-text-muted" />
            </button>
          )}
        </div>
      </header>

      {/* Error display */}
      {error && (
        <div className="px-6 py-3 bg-red-50 border-b border-red-200 flex items-center justify-between">
          <span className="text-red-600 text-sm">{error}</span>
          <button onClick={onClearError} className="text-text-muted hover:text-text">
            <X size={16} />
          </button>
        </div>
      )}

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {messages.length === 0 && (
          <div className="text-center py-8 text-text-muted">
            <p className="text-lg text-text mb-2">Welcome to Sales AI Assistant! 👋</p>
            <p className="text-sm">I&apos;m your multi-agent sales assistant. How can I help you today?</p>
          </div>
        )}

        {messages.map((msg, index) => {
          const prevMsg = index > 0 ? messages[index - 1] : null;
          const isGrouped = prevMsg && prevMsg.role === msg.role && prevMsg.agent === msg.agent;
          return <MessageBubble key={index} message={msg} isGrouped={!!isGrouped} />;
        })}

        {/* Pending Questions */}
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
      <div className="px-6 py-4 bg-surface border-t border-border">
        <form onSubmit={handleSubmit} className="flex gap-3 items-end">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your message..."
            disabled={isLoading}
            rows={1}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(e);
              }
            }}
            className="flex-1 px-4 py-3 border border-border rounded-full text-sm resize-none min-h-[44px] max-h-[120px] bg-surface text-text focus:border-accent focus:ring-1 focus:ring-accent outline-none transition-colors"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className={`flex items-center gap-2 px-5 py-3 rounded-full text-sm font-medium ${
              input.trim() && !isLoading
                ? 'bg-accent text-white hover:opacity-90'
                : 'bg-text-muted text-white cursor-not-allowed'
            }`}
          >
            <Send size={18} />
            <span className="hidden sm:inline">Send</span>
          </button>
        </form>
      </div>
    </div>
  );
}