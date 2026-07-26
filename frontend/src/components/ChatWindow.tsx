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
  onAnswerAllQuestions: (answers: Record<string, string>) => void;
  onSkipQuestion?: (questionId: string) => void;
  onFreeTextAnswer?: (freeText: string) => void;
  onApproveCheckpoint: () => void;
  onRejectCheckpoint: () => void;
  onEditCheckpoint: (params: Record<string, unknown>) => void;
  onClearError: () => void;
  onToggleContextPanel?: () => void;
  onToggleMobileSidebar?: () => void;
}

// Openers for an empty chat. Written as briefs a rep would actually paste, not as
// feature names — "làm proposal" teaches nothing about what to put in one, whereas
// a filled-in example shows the shape of a brief that gets a good answer first try.
const SALES_STARTERS = [
  {
    icon: '🥤',
    label: 'Brief FMCG đầy đủ',
    prompt:
      'Brand nước giải khát FMCG, muốn tăng mua lại qua loyalty trên Zalo. Ngân sách 300 triệu, chạy Q4. Làm proposal giúp mình.',
  },
  {
    icon: '💊',
    label: 'Ngành dược, cần soát pháp lý',
    prompt:
      'Khách dược phẩm muốn làm chương trình tích điểm cho nhà thuốc. Kiểm giúp mình phần pháp lý và đề xuất giải pháp.',
  },
  {
    icon: '💰',
    label: 'Hỏi nhanh giá gói',
    prompt: 'Gói CShub Base 3 và Pro 1 khác nhau gì, giá 12 tháng bao nhiêu?',
  },
  {
    icon: '🛡️',
    label: 'Tập phản biện trước khi pitch',
    prompt:
      'Mai mình pitch cho khách FMCG đang so sánh với CNV Loyalty. Đóng vai khách và phản biện giúp mình.',
  },
];

const CS_STARTERS = [
  {
    icon: '📖',
    label: 'Tra hướng dẫn',
    prompt: 'Khách hỏi tại sao không export được data thành viên, giải thích giúp mình.',
  },
  {
    icon: '🐞',
    label: 'Báo lỗi để tạo ticket',
    prompt: 'Khách báo voucher đã phát nhưng không thấy trong ví, mình cần tạo ticket.',
  },
];

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

  // Chốt 1 sends the brief split by where each item came from. Showing that split is
  // the whole value of the stop: a rep skims "inferred" and "assumed" for the one line
  // that is wrong, which is much faster than re-reading a brief they already wrote.
  const SOURCE_GROUPS: { key: string; label: string; hint: string; tone: string }[] = [
    { key: 'said', label: 'Bạn đã nói', hint: 'lấy nguyên từ tin nhắn của bạn', tone: 'text-text' },
    { key: 'inferred', label: 'Mình tự suy ra', hint: 'suy từ ngữ cảnh — kiểm giúp', tone: 'text-accent-text' },
    { key: 'assumed', label: 'Đang phỏng đoán', hint: 'chưa có dữ liệu, mình sẽ giả định', tone: 'text-amber-600' },
  ];

  const formatBriefGroups = (groups: Record<string, Array<Record<string, string>>>) => (
    <div className="space-y-3">
      {SOURCE_GROUPS.map(({ key, label, hint, tone }) => {
        const items = groups[key] || [];
        if (items.length === 0) return null;
        return (
          <div key={key} className="bg-surface rounded overflow-hidden">
            <div className="px-3 py-1.5 border-b border-border flex items-baseline gap-2">
              <span className={`text-[12px] font-semibold ${tone}`}>{label}</span>
              <span className="text-[11px] text-text-muted">{hint}</span>
            </div>
            <table className="w-full border-collapse text-xs">
              <tbody>
                {items.map((item) => (
                  <tr key={item.field} className="border-b border-border last:border-0">
                    <td className="py-2 px-3 font-medium text-text-muted w-2/5">{item.label}</td>
                    <td className="py-2 px-3 text-text">{item.value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}
    </div>
  );

  // Format preview as a table
  const formatPreview = (preview: unknown): React.ReactNode => {
    if (!preview) return null;

    if (typeof preview === 'object') {
      const asRecord = preview as Record<string, unknown>;
      if (asRecord.groups && typeof asRecord.groups === 'object') {
        return formatBriefGroups(
          asRecord.groups as Record<string, Array<Record<string, string>>>
        );
      }

      const entries = Object.entries(asRecord);
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

  // Chốt 1 exists so the rep can correct what we misread, which means Edit has to
  // actually edit. It used to open a panel reading "Edit functionality available"
  // and submit an empty object.
  const briefGroups = (checkpoint.action.preview as { groups?: Record<string, Array<Record<string, string>>> } | undefined)
    ?.groups;
  const editableFields = briefGroups
    ? ['said', 'inferred', 'assumed'].flatMap((k) => briefGroups[k] ?? [])
    : [];

  const [edits, setEdits] = useState<Record<string, string>>({});

  const startEditing = () => {
    // Seed from what is on screen so the rep changes one line instead of retyping
    // the brief. "(chưa có — sẽ phỏng đoán)" is a placeholder, not a value.
    setEdits(
      Object.fromEntries(
        editableFields.map((f) => [f.field, f.value.startsWith('(') ? '' : f.value])
      )
    );
    setIsEditing(true);
  };

  const handleEditSubmit = () => {
    const changed = Object.fromEntries(
      Object.entries(edits).filter(([field, value]) => {
        const original = editableFields.find((f) => f.field === field)?.value ?? '';
        return value.trim() && value.trim() !== original;
      })
    );
    onEdit(changed);
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
          <h3 className="font-semibold text-accent-text mb-2">
            {checkpoint.action.type === 'confirm_brief'
              ? 'Chốt 1 — Xác nhận cách hiểu brief'
              : checkpoint.action.type === 'confirm_solution'
                ? 'Chốt 2 — Duyệt hướng giải pháp'
                : 'Action Requires Approval'}
          </h3>
          <p className="text-[12px] text-accent-text mb-3">{checkpoint.action.description}</p>

          {/* Preview */}
          {checkpoint.action.preview && !isEditing && <div className="mb-4">{formatPreview(checkpoint.action.preview)}</div>}

          {/* Edit mode */}
          {isEditing && (
            <div className="mb-4 rounded-lg bg-surface p-3">
              {editableFields.length > 0 ? (
                <>
                  <p className="mb-3 text-[12px] text-text-muted">
                    Sửa dòng nào sai, để trống nghĩa là bỏ trường đó.
                  </p>
                  <div className="flex flex-col gap-2.5">
                    {editableFields.map((f) => (
                      <label key={f.field} className="flex flex-col gap-1">
                        <span className="text-[11px] font-medium text-text-muted">{f.label}</span>
                        <input
                          type="text"
                          value={edits[f.field] ?? ''}
                          onChange={(e) =>
                            setEdits((prev) => ({ ...prev, [f.field]: e.target.value }))
                          }
                          placeholder={
                            f.field === 'budget_vnd'
                              ? 'vd: 300 triệu, 200 - 500 triệu, 1.5 tỷ'
                              : 'Để trống nếu chưa có'
                          }
                          className="rounded-lg border border-border bg-surface-2 px-3 py-2 text-[13px] text-text outline-none transition-all focus:border-accent focus:ring-2 focus:ring-accent/20"
                        />
                      </label>
                    ))}
                  </div>
                </>
              ) : (
                <p className="text-xs text-text-muted">Không có trường nào để sửa ở bước này.</p>
              )}
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
                  <Check size={16} /> Lưu & xem lại
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
                  onClick={startEditing}
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
  onAnswerAllQuestions,
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

  // Streaming rewrites the last message on every token, so this effect fires dozens
  // of times a second. `behavior: 'smooth'` starts a new animation on each of those
  // and each one cancels the last mid-flight — that is the jitter at the end of a
  // long answer, and it is worst exactly when the message is tall and moving fast.
  //
  // While tokens are arriving, jump the container instantly and coalesce to one
  // adjustment per frame. Only the settled state, once loading stops, animates.
  const scrollRaf = useRef<number | null>(null);
  useEffect(() => {
    if (!isAtBottomRef.current) return;

    if (isLoading) {
      if (scrollRaf.current !== null) return;
      scrollRaf.current = requestAnimationFrame(() => {
        scrollRaf.current = null;
        const c = messagesContainerRef.current;
        if (c) c.scrollTop = c.scrollHeight;
      });
      return;
    }

    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  useEffect(
    () => () => {
      if (scrollRaf.current !== null) cancelAnimationFrame(scrollRaf.current);
    },
    []
  );

  // Return the caret to the composer once a turn finishes. Without this the rep has
  // to click back into the box after every single message.
  const wasLoading = useRef(false);
  useEffect(() => {
    if (wasLoading.current && !isLoading) {
      textareaRef.current?.focus();
    }
    wasLoading.current = isLoading;
  }, [isLoading]);

  // Handle scroll to show/hide scroll button
  const handleScroll = () => {
    const container = messagesContainerRef.current;
    if (!container) return;

    const { scrollTop, scrollHeight, clientHeight } = container;
    const distance = scrollHeight - scrollTop - clientHeight;

    // Asymmetric thresholds. Leaving the bottom is easy — any real scroll up hands
    // control back to the reader. Re-engaging needs them to come all the way down.
    // With one 150px threshold, scrolling down through a streaming answer crossed
    // back into "at bottom" early and the auto-scroll yanked them to the end.
    isAtBottomRef.current = isAtBottomRef.current ? distance < 220 : distance < 32;
    setShowScrollButton(distance > 220);
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
        // Keep the caret in the box on send, not just when the reply lands, so a
        // rep can fire several messages in a row without reaching for the mouse.
        textareaRef.current.focus();
      }
    }
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
              <span className="text-accent text-base sm:text-lg">💬</span>
              <span className="hidden sm:inline">Chat</span>
              <span className="sm:hidden">Chat</span>
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
      {/* overflow-anchor lets the browser hold the reader's position when content
          above them changes height — which is exactly what happens when a streamed
          block finishes and re-renders into a diagram or a table. */}
      <div
        className="flex-1 overflow-y-auto min-h-0 relative"
        style={{ overflowAnchor: 'auto' }}
        ref={messagesContainerRef}
        onScroll={handleScroll}
      >
        <div className="max-w-6xl mx-auto px-3 sm:px-4 md:px-8 py-3 md:py-4">
        {messages.length === 0 && (
          <div className="py-6 sm:py-10">
            <div className="mb-6 text-center text-text-muted">
              {mode === 'cs' ? (
                <>
                  <p className="mb-1.5 text-base text-text sm:text-[16px]">CSHub Support Assistant 🎧</p>
                  <p className="text-xs sm:text-[12px]">
                    Tra cứu hướng dẫn sử dụng CSHub, hoặc intake bug để tạo Jira ticket.
                  </p>
                </>
              ) : (
                <>
                  <p className="mb-1.5 text-base text-text sm:text-[16px]">
                    Chào bạn 👋 Mình là AdtimaBox Sales Agent
                  </p>
                  <p className="text-xs sm:text-[12px]">
                    Mô tả brief của khách, mình lo phần chiến lược, giải pháp, pháp lý và báo giá.
                  </p>
                </>
              )}
            </div>

            {/* An empty box with a blinking cursor tells a rep nothing about what this
                thing can do. These are real openers: one click sends, and the shape of
                the list doubles as the answer to "what am I supposed to type here". */}
            <div className="mx-auto grid max-w-3xl gap-2 sm:grid-cols-2">
              {(mode === 'cs' ? CS_STARTERS : SALES_STARTERS).map((s) => (
                <button
                  key={s.prompt}
                  type="button"
                  disabled={isLoading}
                  onClick={() => onSendMessage(s.prompt)}
                  className="group rounded-xl border border-border bg-surface/60 p-3.5 text-left transition-all hover:border-accent hover:bg-accent-soft/40 active:scale-[0.99] disabled:opacity-50"
                >
                  <div className="mb-1 flex items-center gap-2">
                    <span className="text-base">{s.icon}</span>
                    <span className="text-[13px] font-semibold text-text group-hover:text-accent-text">
                      {s.label}
                    </span>
                  </div>
                  <p className="text-[12px] leading-snug text-text-muted">{s.prompt}</p>
                </button>
              ))}
            </div>

            <p className="mt-4 text-center text-[11px] text-text-muted">
              Hoặc gõ brief của bạn bên dưới — thiếu gì mình sẽ hỏi lại.
            </p>
          </div>
        )}

        {messages.map((msg, index) => {
          const prevMsg = index > 0 ? messages[index - 1] : null;
          const isGrouped = prevMsg && prevMsg.role === msg.role && prevMsg.agent === msg.agent;
          const isLastMsg = index === messages.length - 1;
          return <MessageBubble key={index} message={msg} isGrouped={!!isGrouped} isStreaming={isLastMsg && isLoading && msg.role === 'assistant'} />;
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
            onAnswerAll={onAnswerAllQuestions}
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

        {/* The sentinel must opt out of scroll anchoring, or the browser picks this
            zero-height element at the very bottom as its anchor and cancels out the
            auto-scroll we do want while streaming. */}
        <div ref={messagesEndRef} style={{ overflowAnchor: 'none' }} />
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
        <div className="flex gap-2 items-end max-w-6xl mx-auto">
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
              placeholder={mode === 'cs' ? 'Hỏi về CSHub, hoặc mô tả bug...' : 'Message AdtimaBox Sales Agent...'}
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
