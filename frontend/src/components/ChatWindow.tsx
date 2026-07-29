/**
 * Chat Window Component
 * =====================
 * Main chat interface with message list and input.
 * Uses Tailwind CSS for styling.
 */

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Loader2, PanelRightClose, Menu, AlertTriangle, Check, X, Edit, ArrowDown, Bot, MessageCircle, Headphones, Plus } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { MessageBubble } from './MessageBubble';
import { QuestionCard } from './QuestionCard';
import { ThinkingTrace } from './ThinkingTrace';
import type { Message, Question, Checkpoint, Brief, ChatMode, ThinkingStep } from '../lib/types';

// Render-invariant — see the same constant in MessageBubble.tsx.
const REMARK_PLUGINS = [remarkGfm];

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
  onModeChange?: (mode: ChatMode) => void;
  onNewChat?: () => void;
  thinkingSteps?: ThinkingStep[];
}

const HEADER_MODES: { id: ChatMode; label: string; icon: React.ReactNode }[] = [
  { id: 'chat', label: 'Chat', icon: <MessageCircle size={16} /> },
  { id: 'cs', label: 'CS', icon: <Headphones size={16} /> },
];

// Openers for an empty chat, each scoped to ONE specialist rather than a full
// brief — "làm proposal" as the only entry point taught every rep to open with
// a proposal request, which is why every first message used to build a full
// pptx whether that's what they needed or not. `prompt` is what actually gets
// sent; `description` is the friendlier one-line gloss shown next to it.
const SALES_STARTERS = [
  {
    icon: '💰',
    label: 'Giá gói bao nhiêu?',
    description: 'So sánh tính năng và giá các gói CShub theo nhu cầu cụ thể.',
    prompt: 'Gói CShub Base 3 và Pro 1 khác nhau gì, giá 12 tháng bao nhiêu?',
  },
  {
    icon: '📖',
    label: 'Vẽ user flow',
    description: 'Thiết kế hành trình người dùng trên Zalo MiniApp theo brief của khách.',
    prompt:
      'Vẽ giúp mình user flow cho chương trình tích điểm trên Zalo Mini App — khách FMCG, cơ chế quét mã trên bao bì để tích điểm.',
  },
  {
    icon: '📊',
    label: 'Phân tích chiến lược',
    description: 'Tại sao khách cần loyalty? Insight ngành + đề xuất giải pháp tổng thể.',
    prompt:
      'Khách FMCG muốn triển khai loyalty trên Zalo nhưng chưa rõ vì sao cần. Phân tích giúp mình insight ngành và định hướng giải pháp.',
  },
  {
    icon: '🛡️',
    label: 'Đối thủ hỏi khó',
    description: 'Khách đang so sánh với CNV / Pango / Mmenu — giúp mình trả lời.',
    prompt:
      'Khách đang so sánh AdtimaBox với CNV Loyalty. Đóng vai khách và đưa ra phản biện giúp mình luyện tập trả lời.',
  },
];

const CS_STARTERS = [
  {
    icon: '📖',
    label: 'Tra hướng dẫn',
    description: 'Tìm câu trả lời trong tài liệu hướng dẫn sử dụng CSHub.',
    prompt: 'Khách hỏi tại sao không export được data thành viên, giải thích giúp mình.',
  },
  {
    icon: '🐞',
    label: 'Báo lỗi để tạo ticket',
    description: 'Ghi nhận lỗi khách báo và tạo Jira ticket.',
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

  function cleanAndTranslateCheckpointText(text: string): string {
    if (!text) return '';
    let s = text
      .replace(/\$*\\+rightarrow\$*/gi, ' → ')
      .replace(/\$*\\+Rightarrow\$*/gi, ' ⇒ ')
      .replace(/\$*\\+leftarrow\$*/gi, ' ← ')
      .replace(/\$*\\+Leftarrow\$*/gi, ' ⇐ ');

    // Strip ASCII banners & double horizontal lines
    s = s.replace(/^[-=]{3,}\s*[A-Z0-9_\s—\-]*\s*[-=]*$/gm, '');
    s = s.replace(/^([=]{3,}|-{3,})$/gm, '');

    // Translate common English headers & jargon to clean Vietnamese
    s = s
      .replace(/OVERALL VERDICT:\s*⚠️?\s*PROCEED WITH CONDITIONS/gi, '📌 Kết luận: ĐƯỢC TRIỂN KHAI CÓ ĐIỀU KIỆN ⚠️')
      .replace(/OVERALL VERDICT:\s*PROCEED/gi, '📌 Kết luận: ĐƯỢC PHÉP TRIỂN KHAI 🟢')
      .replace(/OVERALL VERDICT:\s*BLOCK/gi, '📌 Kết luận: CẦN TẠM DỪNG / CHẶN 🔴')
      .replace(/Risk summary:\s*(\d+)\s*High\s*\|\s*(\d+)\s*Medium\s*\|\s*(\d+)\s*Note/gi, '📊 Mức độ rủi ro: $1 Cao | $2 Vừa | $3 Lưu ý')
      .replace(/EXPLICIT ASSUMPTIONS/gi, 'Giả định triển khai chính')
      .replace(/\(Provisional\s*[\-–—]\s*pending client confirmation\)/gi, '(Tạm thời — chờ khách hàng xác nhận)')
      .replace(/ASSUMPTIONS STATEMENT/gi, 'Giả định triển khai')
      .replace(/RUNNING WITH ASSUMPTIONS/gi, 'Giả định thực thi')
      .replace(/A4 COMPLIANCE REPORT/gi, 'Báo cáo tuân thủ & Pháp lý')
      .replace(/PROPOSAL:\s*/gi, 'Đề xuất: ')
      .replace(/SOLUTION ARCHITECTURE & PACKAGE MAPPING/gi, 'Kiến trúc giải pháp & Gói dịch vụ')
      .replace(/SPECIFIC REQUIREMENTS:/gi, 'Yêu cầu cụ thể:')
      .replace(/CONSTRAINTS:/gi, 'Ràng buộc & Hạn chế:')
      .replace(/STRATEGIC DIAGNOSIS/gi, 'Chẩn đoán chiến lược')
      .replace(/Campaign Scale:/gi, 'Quy mô chiến dịch:')
      .replace(/Database Scale:/gi, 'Quy mô cơ sở dữ liệu:')
      .replace(/Database Size:/gi, 'Dung lượng dữ liệu:')
      .replace(/Acquisition & Loyalty Mechanic:/gi, 'Cơ chế Thu hút & Tích điểm Loyalty:')
      .replace(/Timeline Duration:/gi, 'Thời gian chiến dịch:')
      .replace(/Primary Objective:/gi, 'Mục tiêu chính:')
      .replace(/Objective:/gi, 'Mục tiêu:')
      .replace(/Total Provisional Budget:/gi, 'Tổng ngân sách dự kiến:')
      .replace(/Total Budget:/gi, 'Tổng ngân sách:')
      .replace(/Timeline:/gi, 'Thời gian triển khai:')
      .replace(/Client:/gi, 'Khách hàng:')
      .replace(/Industry:/gi, 'Ngành hàng:')
      .replace(/Assumption (\d+)/gi, 'Giả định $1')
      .replace(/Assumptions made:/gi, 'Giả định được đưa ra:')
      .replace(/High reliance on mass media/gi, 'Phụ thuộc lớn vào truyền thông đại chúng');

    return s.trim();
  }

  // Parse raw JSON objects/strings into clean human-readable Vietnamese text
  function formatValueHumanReadable(val: unknown): string {
    if (!val) return '';
    let obj: Record<string, unknown> | null = null;

    if (typeof val === 'object' && val !== null) {
      obj = val as Record<string, unknown>;
    } else if (typeof val === 'string') {
      let rawStr = val.trim();
      // Strip markdown code fences if present e.g. ```json { ... } ```
      if (rawStr.startsWith('```')) {
        rawStr = rawStr.replace(/^```[a-z]*\n?/i, '').replace(/\n?```$/i, '').trim();
      }
      // If contains a JSON object pattern
      const jsonMatch = rawStr.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        try {
          obj = JSON.parse(jsonMatch[0]);
        } catch {
          obj = null;
        }
      }
    }

    if (obj) {
      const lines: string[] = [];
      // Extract key fields into friendly format
      if (obj.problem_statement) lines.push(`**Mục tiêu bài toán:** ${cleanAndTranslateCheckpointText(String(obj.problem_statement))}`);
      if (obj.confidence_notes) lines.push(`**Ghi chú giả định:** ${cleanAndTranslateCheckpointText(String(obj.confidence_notes))}`);
      if (obj.summary) lines.push(`**Tóm tắt:** ${cleanAndTranslateCheckpointText(String(obj.summary))}`);
      if (obj.verdict) lines.push(`**Kết luận:** ${cleanAndTranslateCheckpointText(String(obj.verdict))}`);

      // Handle gap analysis if present
      if (obj.gap_analysis && typeof obj.gap_analysis === 'object') {
        const gap = obj.gap_analysis as Record<string, unknown>;
        if (gap.current_state) lines.push(`**Hiện trạng:** ${cleanAndTranslateCheckpointText(String(gap.current_state))}`);
        if (gap.desired_state) lines.push(`**Mục tiêu hướng tới:** ${cleanAndTranslateCheckpointText(String(gap.desired_state))}`);
      }

      // Fallback for other keys if no standard field matched
      if (lines.length === 0) {
        Object.entries(obj).forEach(([k, v]) => {
          if (['skill', 'status', 'agent', 'model'].includes(k)) return; // Skip internal dev fields
          const label = k.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
          const displayVal = typeof v === 'object' ? JSON.stringify(v) : String(v);
          lines.push(`**${label}:** ${cleanAndTranslateCheckpointText(displayVal)}`);
        });
      }

      return lines.join('\n\n');
    }

    let finalStr = cleanAndTranslateCheckpointText(String(val));
    // If text still contains raw JSON snippet (e.g. {"skill": ...}), clean it completely
    if (finalStr.includes('"skill":') || finalStr.includes('"status":')) {
      finalStr = finalStr.replace(/\{[\s\S]*?\}/g, (match) => {
        try {
          const parsed = JSON.parse(match);
          const parts = [];
          if (parsed.problem_statement) parts.push(`**Bài toán:** ${parsed.problem_statement}`);
          if (parsed.confidence_notes) parts.push(`**Ghi chú:** ${parsed.confidence_notes}`);
          return parts.join('\n\n');
        } catch {
          return '';
        }
      });
    }

    return finalStr.trim();
  }

  const formatBriefGroups = (groups: Record<string, Array<Record<string, string>>>) => (
    <div className="space-y-3 max-w-full overflow-hidden">
      {SOURCE_GROUPS.map(({ key, label, hint, tone }) => {
        const items = groups[key] || [];
        if (items.length === 0) return null;
        return (
          <div key={key} className="bg-surface rounded-xl border border-border overflow-hidden shadow-sm">
            <div className="px-3 py-2 bg-surface-2 border-b border-border flex items-baseline gap-2">
              <span className={`text-[12px] font-semibold ${tone}`}>{label}</span>
              <span className="text-[11px] text-text-muted">{hint}</span>
            </div>
            <div className="divide-y divide-border/50 text-xs">
              {items.map((item) => (
                <div key={item.field} className="p-3 flex flex-col sm:flex-row gap-1 sm:gap-4">
                  <span className="font-medium text-text-muted shrink-0 sm:w-1/3">{item.label}</span>
                  <span className="text-text break-words flex-1 min-w-0">{formatValueHumanReadable(item.value)}</span>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );

  // Friendly Vietnamese Section Labels
  const SECTION_LABELS: Record<string, { label: string; bg: string; border: string }> = {
    compliance: { label: '⚖️ Đánh giá Pháp lý & Tuân thủ (Compliance)', bg: 'bg-amber-500/10 dark:bg-amber-900/20', border: 'border-amber-500/30' },
    strategy: { label: '🎯 Định hình Chiến lược (Market Strategy)', bg: 'bg-blue-500/10 dark:bg-blue-900/20', border: 'border-blue-500/30' },
    solution: { label: '💡 Đề xuất Giải pháp & Gói sản phẩm (Product Solution)', bg: 'bg-purple-500/10 dark:bg-purple-900/20', border: 'border-purple-500/30' },
  };

  // Format preview with clear cards and Vietnamese labels
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

      // Re-order entries so compliance/verdict is ALWAYS ON TOP!
      const sortedEntries = [...entries].sort(([a], [b]) => {
        if (a === 'compliance') return -1;
        if (b === 'compliance') return 1;
        if (a === 'strategy') return -1;
        if (b === 'strategy') return 1;
        return 0;
      });

      return (
        <div className="space-y-3 my-2 max-w-full overflow-hidden">
          {sortedEntries.map(([key, value]) => {
            const secInfo = SECTION_LABELS[key] || {
              label: key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
              bg: 'bg-surface-2',
              border: 'border-border',
            };

            const cleanedText = formatValueHumanReadable(value);

            return (
              <div
                key={key}
                className={`rounded-xl border ${secInfo.border} ${secInfo.bg} p-3.5 shadow-sm transition-all max-w-full`}
              >
                <div className="flex items-center justify-between pb-2 mb-2 border-b border-border/40">
                  <span className="text-[13px] font-bold text-text flex items-center gap-1.5 truncate">
                    {secInfo.label}
                  </span>
                </div>
                <div className="text-sm text-text leading-relaxed max-w-full break-words">
                  <ReactMarkdown remarkPlugins={REMARK_PLUGINS}>{cleanedText}</ReactMarkdown>
                </div>
              </div>
            );
          })}
        </div>
      );
    }

    return (
      <div className="p-3 bg-surface-2 rounded-xl text-xs text-text leading-relaxed break-words overflow-hidden">
        <ReactMarkdown remarkPlugins={REMARK_PLUGINS}>{formatValueHumanReadable(preview)}</ReactMarkdown>
      </div>
    );
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
    <div className="border-2 border-accent bg-accent-soft rounded-2xl p-4 mb-4 max-w-full overflow-hidden shadow-md">
      {/* Compliance Findings */}
      {checkpoint.compliance_findings && checkpoint.compliance_findings.length > 0 && (
        <div className="mb-4 max-w-full overflow-hidden">
          {checkpoint.compliance_findings.map((finding, idx) => (
            <div
              key={idx}
              className={`
                p-3 rounded-xl mb-2 max-w-full overflow-hidden
                ${finding.severity === 'block' ? 'bg-red-500/10 border border-red-500/25 text-red-400' : ''}
                ${finding.severity === 'warn' ? 'bg-amber-500/10 border border-amber-500/25 text-amber-300' : ''}
                ${finding.severity === 'info' ? 'bg-blue-500/10 border border-blue-500/25 text-blue-300' : ''}
              `}
            >
              <div className="flex items-start gap-2">
                <span>{finding.severity === 'block' ? '🔴' : finding.severity === 'warn' ? '⚠️' : 'ℹ️'}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-[12px] font-medium break-words">{finding.message}</p>
                  {finding.suggestion && (
                    <p className="text-xs opacity-80 mt-1 break-words">Gợi ý: {finding.suggestion}</p>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="flex items-start gap-3 max-w-full overflow-hidden">
        <AlertTriangle size={24} className="text-accent shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0 max-w-full overflow-hidden">
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
            <label className="flex items-center gap-2 mb-3 text-xs text-text-muted cursor-pointer hover:text-text transition-colors">
              <input
                type="checkbox"
                checked={autoApprove}
                onChange={(e) => setAutoApprove(e.target.checked)}
                className="rounded border-border text-accent focus:ring-accent"
              />
              Tự động duyệt bước này trong các lần tiếp theo của phiên
            </label>
          )}

          {/* Action buttons */}
          <div className="flex gap-2 flex-wrap">
            {isEditing ? (
              <>
                <button
                  onClick={handleEditSubmit}
                  className="flex items-center gap-1.5 px-4 py-2 bg-accent text-white rounded-xl text-xs font-semibold hover:opacity-90 transition-all shadow-sm active:scale-95"
                >
                  <Check size={16} /> Lưu & Xem lại
                </button>
                <button
                  onClick={() => setIsEditing(false)}
                  className="flex items-center gap-1.5 px-3 py-2 bg-surface-2 text-text-muted rounded-xl text-xs font-medium hover:text-text hover:bg-surface-hover transition-all"
                >
                  Hủy
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={onApprove}
                  disabled={hasBlocking}
                  className={`flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold transition-all shadow-sm active:scale-95 ${
                    hasBlocking
                      ? 'bg-red-500/20 text-red-400 cursor-not-allowed'
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
  onModeChange,
  onNewChat,
  thinkingSteps = [],
}: ChatWindowProps) {
  const [input, setInput] = useState('');
  const [showScrollButton, setShowScrollButton] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
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
      <header className="app-chrome shrink-0 sticky top-0 z-20 safe-area-inset-top px-3 sm:px-4 md:px-6 py-1.5 sm:py-3 bg-surface border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2 sm:gap-3 min-w-0">
          {/* Mobile sidebar toggle — the only hamburger now that the drawer lives
              directly on the Sidebar component, off-canvas. */}
          <button
            onClick={onToggleMobileSidebar}
            className="md:hidden p-1.5 sm:p-2 border border-border rounded-lg hover:bg-surface-hover transition-all"
            aria-label="Mở menu"
          >
            <Menu size={18} className="w-4.5 h-4.5 sm:w-5 sm:h-5" />
          </button>

          {/* Mobile: a compact 2-segment mode switcher — the bottom nav that used
              to hold this is gone, and this is the only mode control left once
              the drawer is closed. */}
          {onModeChange && (
            <div className="md:hidden flex items-center gap-0.5 p-0.5 rounded-lg bg-surface-2 border border-border">
              {HEADER_MODES.map((m) => (
                <button
                  key={m.id}
                  onClick={() => onModeChange(m.id)}
                  aria-pressed={mode === m.id}
                  className={`flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium transition-colors ${
                    mode === m.id ? 'bg-accent text-white' : 'text-text-muted'
                  }`}
                >
                  {m.icon}
                  {m.label}
                </button>
              ))}
            </div>
          )}

          {/* Desktop: the mode indicator with per-mode accent underline. Reads
              `mode` now — it used to hardcode "Chat Mode" even while in CS mode. */}
          <div className="relative hidden md:block">
            <h2 className="text-sm sm:text-base font-semibold text-text flex items-center gap-1.5 sm:gap-2">
              <span className="text-accent text-base sm:text-lg">{mode === 'cs' ? '🎧' : '💬'}</span>
              <span>{mode === 'cs' ? 'CS Mode' : 'Chat Mode'}</span>
            </h2>
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

          {/* Mobile: new chat — the drawer's own New Chat button is gone now that
              the drawer is the full Sidebar, whose New Chat button sits above the
              history list rather than in the header. Keeping one reachable
              without opening the drawer first. */}
          {onNewChat && (
            <button
              onClick={onNewChat}
              className="md:hidden p-1.5 sm:p-2 text-accent hover:bg-accent/10 rounded-lg transition-all"
              title="Cuộc trò chuyện mới"
              aria-label="Cuộc trò chuyện mới"
            >
              <Plus size={20} />
            </button>
          )}
        </div>
      </header>

      {/* Error display */}
      {error && (
        <div className="shrink-0 px-3 md:px-6 py-3 bg-red-500/10 border-b border-red-500/25 flex items-center justify-between">
          <span className="text-red-400 text-[12px]">{error}</span>
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
                thing can do. These are real openers, laid out as a two-column table
                (name | suggested description) rather than cards — one click sends the
                underlying `prompt`, and each row is scoped to one specialist so the
                list itself demonstrates that this isn't "type a brief, get a pptx". */}
            <div className="mx-auto max-w-2xl overflow-hidden rounded-xl border border-border divide-y divide-border">
              {(mode === 'cs' ? CS_STARTERS : SALES_STARTERS).map((s) => (
                <button
                  key={s.prompt}
                  type="button"
                  disabled={isLoading}
                  onClick={() => onSendMessage(s.prompt)}
                  className="group flex w-full flex-col gap-1 bg-surface/60 p-3.5 text-left transition-colors hover:bg-accent-soft/40 disabled:opacity-50 sm:flex-row sm:items-center sm:gap-4"
                >
                  <span className="flex shrink-0 items-center gap-2 sm:w-[190px]">
                    <span className="text-base">{s.icon}</span>
                    <span className="text-[13px] font-semibold text-text group-hover:text-accent-text">
                      {s.label}
                    </span>
                  </span>
                  <span className="text-[12px] leading-snug text-text-muted">{s.description}</span>
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
          return (
            <React.Fragment key={index}>
              {/* Render attached thinking trace above each assistant message that has steps */}
              {msg.role === 'assistant' && msg.thinkingSteps && msg.thinkingSteps.length > 0 && (
                <ThinkingTrace steps={msg.thinkingSteps} isActive={false} />
              )}
              <MessageBubble message={msg} isGrouped={!!isGrouped} isStreaming={isLastMsg && isLoading && msg.role === 'assistant'} />
            </React.Fragment>
          );
        })}

        {/* Live Thinking Trace — shows during processing before first content arrives */}
        {isLoading && thinkingSteps.length > 0 && (
          messages.length === 0 || messages[messages.length - 1].role === 'user'
        ) && (
          <ThinkingTrace steps={thinkingSteps} isActive={true} />
        )}

        {/* Thinking Indicator — shows while waiting for first content OR during <think> reasoning */}
        {isLoading && thinkingSteps.length === 0 && (
          isThinking ||
          (messages.length > 0 && messages[messages.length - 1].role === 'user')
        ) && (
          <div className="flex gap-3 mt-4 animate-fade-in-up">
            <div className="shrink-0 w-8 h-8 rounded-full flex items-center justify-center bg-accent animate-pulse-glow glow-border">
              <Bot size={16} className="text-white" />
            </div>
            <div className="flex items-center gap-2 text-text-muted glass-panel border border-border rounded-xl px-4 py-2" style={{boxShadow: '0 4px 10px rgba(0,0,0,0.1)'}}>
              <Loader2 size={14} className="animate-spin text-accent" />
              <span className="text-[12px] font-medium bg-clip-text text-transparent bg-gradient-to-r from-accent to-[#38bdf8] animate-pulse">
                {isThinking ? 'Analyzing data...' : 'Processing...'}
              </span>
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
            className="absolute bottom-4 right-3 sm:right-4 md:right-8 p-2.5 sm:p-2 bg-accent text-white rounded-full shadow-lg hover:opacity-90 transition-opacity z-10"
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
