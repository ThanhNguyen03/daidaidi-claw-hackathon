/**
 * Chat Window Component
 * =====================
 * Main chat interface with message list and input.
 * Uses Tailwind CSS for styling.
 */

import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2, PanelRightClose, Menu, AlertTriangle, Check, X, Edit, ArrowDown, Bot } from 'lucide-react';
import { MessageBubble } from './MessageBubble';
import { QuestionCard } from './QuestionCard';
import type { Message, Question, Checkpoint, Brief, ChatMode } from '../lib/types';

interface ChatWindowProps {
  messages: Message[];
  isLoading: boolean;
  isThinking: boolean;
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
                  <p className="text-[12px] font-medium">{finding.message}</p>
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
          <p className="text-[12px] text-accent-text mb-3">{checkpoint.action.description}</p>

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
                  className="flex items-center gap-1 px-4 py-2 bg-accent text-white rounded-md text-[12px] font-medium hover:opacity-90"
                >
                  <Check size={16} /> Re-preview
                </button>
                <button
                  onClick={() => setIsEditing(false)}
                  className="flex items-center gap-1 px-4 py-2 border border-border text-text-muted rounded-md text-[12px] hover:bg-surface-hover"
                >
                  <X size={16} /> Cancel
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={onApprove}
                  disabled={hasBlocking}
                  className={`flex items-center gap-1 px-4 py-2 rounded-md text-[12px] font-medium ${
                    hasBlocking
                      ? 'bg-text-muted text-white cursor-not-allowed'
                      : 'bg-accent text-white hover:opacity-90'
                  }`}
                >
                  <Check size={16} /> Approve
                </button>
                <button
                  onClick={() => setIsEditing(true)}
                  className="flex items-center gap-1 px-4 py-2 border border-border text-text-muted rounded-md text-[12px] hover:bg-surface-hover"
                >
                  <Edit size={16} /> Edit
                </button>
                <button
                  onClick={onReject}
                  className="flex items-center gap-1 px-4 py-2 border border-border text-text-muted rounded-md text-[12px] hover:bg-surface-hover"
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
  isThinking,
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
  const [showScrollButton, setShowScrollButton] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  // Track whether user is at the bottom so we only auto-scroll when appropriate
  const isAtBottomRef = useRef(true);

  useEffect(() => {
    if (isAtBottomRef.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  // Handle scroll to show/hide scroll button
  const handleScroll = () => {
    const container = messagesContainerRef.current;
    if (!container) return;

    const { scrollTop, scrollHeight, clientHeight } = container;
    const atBottom = scrollHeight - scrollTop - clientHeight < 150;
    isAtBottomRef.current = atBottom;
    setShowScrollButton(!atBottom);
  };

  const scrollToBottom = () => {
    isAtBottomRef.current = true;
    setShowScrollButton(false);
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      isAtBottomRef.current = true;
      onSendMessage(input);
      setInput('');
      if (textareaRef.current) {
        textareaRef.current.style.height = '';
      }
    }
  };

  const modeLabels: Record<ChatMode, { icon: string; label: string }> = {
    chat: { icon: '💬', label: 'Chat' },
    planning: { icon: '📋', label: 'Planning' },
    execute: { icon: '🚀', label: 'Execute' },
    brainstorm: { icon: '💡', label: 'Brainstorm' },
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-bg overflow-hidden">
      {/* Header - compact */}
      <header className="shrink-0 sticky top-0 z-30 px-3 sm:px-4 md:px-6 py-2.5 sm:py-3 bg-surface border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2 sm:gap-3">
          {/* Mobile sidebar toggle */}
          <button
            onClick={onToggleMobileSidebar}
            className="md:hidden p-1.5 sm:p-2 border border-border rounded-lg hover:bg-surface-hover transition-all"
          >
            <Menu size={18} className="w-4.5 h-4.5 sm:w-5 sm:h-5" />
          </button>

          {/* Mode indicator with per-mode accent underline */}
          <div className="relative">
            <h2 className="text-sm sm:text-base font-semibold text-text flex items-center gap-1.5 sm:gap-2">
              <span className="text-accent text-base sm:text-lg">{modeLabels[mode].icon}</span>
              <span className="hidden sm:inline">{modeLabels[mode].label}</span>
              <span className="sm:hidden">{modeLabels[mode].label === 'Brainstorm' ? 'Brain' : modeLabels[mode].label}</span>
              <span className="hidden sm:inline">Mode</span>
            </h2>
            {/* Per-mode accent underline */}
            <span className="absolute -bottom-1 left-0 right-0 h-0.5 bg-accent rounded" />
          </div>
        </div>

        <div className="flex items-center gap-1 sm:gap-2">
          {isLoading && (
            <div className="flex items-center gap-1.5 sm:gap-2 text-text-muted">
              <Loader2 size={14} className="animate-spin w-3.5 h-3.5 sm:w-4 sm:h-4" />
              <span className="text-[11px] sm:text-[12px] hidden sm:inline">Thinking...</span>
            </div>
          )}

          {onToggleContextPanel && (
            <button
              onClick={onToggleContextPanel}
              className="hidden md:flex p-2 border border-border rounded-lg hover:bg-surface-hover transition-all"
              title="Toggle Context Panel"
            >
              <PanelRightClose size={18} className="w-4.5 h-4.5 sm:w-5 sm:h-5" />
            </button>
          )}
        </div>
      </header>

      {/* Error display */}
      {error && (
        <div className="shrink-0 px-3 md:px-6 py-3 bg-red-50 border-b border-red-200 flex items-center justify-between">
          <span className="text-red-600 text-[12px]">{error}</span>
          <button onClick={onClearError} className="text-text-muted hover:text-text">
            <X size={16} />
          </button>
        </div>
      )}

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto min-h-0 relative" ref={messagesContainerRef} onScroll={handleScroll}>
        <div className="max-w-3xl mx-auto px-3 sm:px-4 md:px-6 py-3 md:py-4">
        {messages.length === 0 && (
          <div className="text-center py-6 sm:py-8 text-text-muted">
            <p className="text-base sm:text-[16px] text-text mb-1.5 sm:mb-2">Welcome to Sales AI Assistant! 👋</p>
            <p className="text-xs sm:text-[12px]">I&apos;m your multi-agent sales assistant. How can I help you today?</p>
          </div>
        )}

        {messages.map((msg, index) => {
          const prevMsg = index > 0 ? messages[index - 1] : null;
          const isGrouped = prevMsg && prevMsg.role === msg.role && prevMsg.agent === msg.agent;
          return <MessageBubble key={index} message={msg} isGrouped={!!isGrouped} />;
        })}

        {/* Thinking Indicator — shows while waiting for first content OR during <think> reasoning */}
        {isLoading && (
          isThinking ||
          (messages.length > 0 && messages[messages.length - 1].role === 'user')
        ) && (
          <div className="flex gap-3 mt-4">
            <div className="shrink-0 w-8 h-8 rounded-full flex items-center justify-center bg-accent">
              <Bot size={16} className="text-white" />
            </div>
            <div className="flex items-center gap-2 text-text-muted bg-surface border border-border rounded-xl px-3 py-2">
              <Loader2 size={14} className="animate-spin" />
              <span className="text-[12px]">{isThinking ? 'Reasoning...' : 'Thinking...'}</span>
            </div>
          </div>
        )}

        {/* Pending Questions */}
        {pendingQuestions.length > 0 && (
          <QuestionCard
            questions={pendingQuestions}
            onAnswer={onAnswerQuestion}
            onSkip={onSkipQuestion || (() => {})}
            onFreeTextAnswer={onFreeTextAnswer || ((_ft: string) => {})}
            isSubmitting={false}
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

        {/* Scroll to bottom button */}
        {showScrollButton && (
          <button
            onClick={scrollToBottom}
            className="absolute bottom-36 sm:bottom-32 md:bottom-4 right-3 sm:right-4 md:right-8 p-2.5 sm:p-2 bg-accent text-white rounded-full shadow-lg hover:opacity-90 transition-opacity z-10"
            title="Scroll to bottom"
          >
            <ArrowDown size={16} className="w-4 h-4 sm:w-[18px] sm:h-[18px]" />
          </button>
        )}
      </div>

      {/* Input area - refined composer */}
      <div className="px-3 sm:px-4 md:px-6 py-2 sm:py-3 bg-bg border-t border-border pb-safe">
        <div className="flex gap-2 items-end max-w-3xl mx-auto">
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                const t = e.currentTarget;
                t.style.height = 'auto';
                t.style.height = Math.min(t.scrollHeight, 120) + 'px';
              }}
              placeholder="Message Sales AI Assistant..."
              disabled={isLoading}
              rows={1}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(e);
                }
              }}
              className="w-full px-3 sm:px-4 py-2.5 sm:py-3 border border-border rounded-2xl text-sm sm:text-[13px] resize-none min-h-[44px] sm:min-h-[48px] bg-surface-2 text-text placeholder:text-text-muted/60 focus:border-accent focus:ring-2 focus:ring-accent/20 outline-none transition-all"
              style={{ lineHeight: '1.5' }}
            />
          </div>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!input.trim() || isLoading}
            className={`shrink-0 p-2.5 sm:p-3 rounded-2xl transition-all ${
              input.trim() && !isLoading
                ? 'bg-accent text-white hover:opacity-90 active:scale-95'
                : 'bg-surface-2 text-text-muted cursor-not-allowed'
            }`}
          >
            <Send size={16} className="w-4 h-4 sm:w-4.5 sm:h-4.5" />
          </button>
        </div>
      </div>
    </div>
  );
}