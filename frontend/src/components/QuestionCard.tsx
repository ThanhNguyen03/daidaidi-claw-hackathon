/**
 * Question Card
 * =============
 * What the agent shows when the gate is blocking on a missing field.
 *
 * Each question carries suggested answers as chips plus a free-text box. The
 * chips are there because typing "FMCG - Thực phẩm & Đồ uống" costs a rep far
 * more than tapping it, and because free text arrives in a dozen spellings that
 * extraction then has to normalise. The free-text box is there because a closed
 * list would quietly steer every brief toward whatever options we guessed.
 *
 * Colours come from theme variables. The previous version hardcoded a white card
 * with dark grey text, which is invisible against the dark theme.
 */

import React, { useState } from 'react';
import { HelpCircle, Check, SkipForward, Send, Pencil } from 'lucide-react';
import type { Question } from '../lib/types';

interface QuestionCardProps {
  questions: Question[];
  onAnswerAll: (answers: Record<string, string>) => void;
  onSkip: (questionId: string) => void;
  onFreeTextAnswer: (freeText: string) => void;
  disabled?: boolean;
  isSubmitting?: boolean;
}

export function QuestionCard({
  questions,
  onAnswerAll,
  onSkip,
  onFreeTextAnswer,
  disabled = false,
  isSubmitting = false,
}: QuestionCardProps) {
  const [freeText, setFreeText] = useState('');
  // Picks are held locally until the rep submits. Sending on click meant the very
  // first chip advanced the pipeline and the remaining questions were thrown away —
  // the card asks four things, so it has to collect four before it commits.
  const [selected, setSelected] = useState<Record<string, string>>({});
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  // Which questions have had "Khác" opened. Tracked separately from the draft
  // text so the box stays open while it is still empty.
  const [customOpen, setCustomOpen] = useState<Record<string, boolean>>({});

  const busy = disabled || isSubmitting;

  const pick = (question: Question, answer: string) => {
    if (busy) return;
    setSelected((prev) =>
      // Tapping the chosen chip again clears it, so a misclick is one click to undo.
      prev[question.id] === answer
        ? Object.fromEntries(Object.entries(prev).filter(([k]) => k !== question.id))
        : { ...prev, [question.id]: answer }
    );
    setCustomOpen((prev) => ({ ...prev, [question.id]: false }));
  };

  if (!questions || questions.length === 0) return null;

  const mandatory = questions.filter((q) => q.is_mandatory);
  const answeredMandatory = mandatory.filter((q) => selected[q.id]?.trim()).length;
  const totalPicked = Object.values(selected).filter((v) => v.trim()).length;
  const canSubmit = !busy && answeredMandatory === mandatory.length && totalPicked > 0;
  const blocking = mandatory.length;

  return (
    <div className="relative mb-4 rounded-xl border border-accent/35 bg-surface/70 p-4 shadow-card backdrop-blur-sm">
      <div className="mb-1 flex items-center gap-2 text-accent-text">
        <HelpCircle size={18} />
        <span className="text-sm font-semibold">Chọn nhanh hoặc tự nhập</span>
      </div>
      <p className="mb-4 text-[12px] text-text-muted">
        {blocking > 0
          ? `${blocking} thông tin bắt buộc còn thiếu — có cái này mình mới chạy phân tích được.`
          : 'Trả lời giúp mình mấy ý sau để đề xuất sát hơn.'}
      </p>

      <div className="flex flex-col gap-3">
        {questions.map((question, index) => {
          const isCustom = customOpen[question.id];
          const draft = drafts[question.id] ?? '';
          const options = question.options ?? [];

          return (
            <div
              key={question.id}
              className="rounded-lg border border-border bg-surface-2/60 p-3.5"
            >
              <div className="mb-2.5 flex items-start gap-2.5">
                <span
                  className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-bold ${
                    question.is_mandatory
                      ? 'bg-accent text-white'
                      : 'bg-surface-hover text-text-muted'
                  }`}
                >
                  {index + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm leading-snug text-text">{question.text}</p>
                  {!question.is_mandatory && (
                    <span className="text-[11px] text-text-muted">không bắt buộc</span>
                  )}
                </div>
              </div>

              {/* Suggested answers */}
              {options.length > 0 && (
                <div className="mb-2 flex flex-wrap gap-1.5">
                  {options.map((option) => {
                    const isPicked = selected[question.id] === option;
                    return (
                      <button
                        key={option}
                        type="button"
                        disabled={busy}
                        onClick={() => pick(question, option)}
                        className={`flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[12px] transition-all active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-50 ${
                          isPicked
                            ? 'border-accent bg-accent text-white'
                            : 'border-border bg-surface text-text hover:border-accent hover:bg-accent-soft hover:text-accent-text'
                        }`}
                      >
                        {isPicked && <Check size={12} />}
                        {option}
                      </button>
                    );
                  })}

                  <button
                    type="button"
                    disabled={busy}
                    onClick={() =>
                      setCustomOpen((prev) => ({ ...prev, [question.id]: !prev[question.id] }))
                    }
                    className={`flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[12px] transition-all active:scale-[0.97] disabled:opacity-50 ${
                      isCustom
                        ? 'border-accent bg-accent-soft text-accent-text'
                        : 'border-dashed border-border-strong text-text-muted hover:border-accent hover:text-accent-text'
                    }`}
                  >
                    <Pencil size={12} />
                    Khác…
                  </button>
                </div>
              )}

              {/* Free text — always reachable, either as the "Khác" box or as the
                  only input when a question ships without suggestions. */}
              {(isCustom || options.length === 0) && (
                <input
                  type="text"
                  autoFocus={isCustom}
                  value={draft}
                  disabled={busy}
                  onChange={(e) => {
                    const value = e.target.value;
                    setDrafts((prev) => ({ ...prev, [question.id]: value }));
                    // Typing IS the selection — no separate confirm step per question,
                    // since the whole card is submitted together at the end.
                    setSelected((prev) => ({ ...prev, [question.id]: value }));
                  }}
                  placeholder="Nhập câu trả lời của bạn…"
                  className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-[13px] text-text outline-hidden transition-all focus:border-accent focus:ring-2 focus:ring-accent/20"
                />
              )}

              {/* Show what is currently chosen for questions answered via a chip,
                  so a long card stays readable without scrolling back. */}
              {selected[question.id] && !isCustom && options.length > 0 && (
                <p className="mt-1.5 text-[11px] text-accent-text">
                  Đã chọn: {selected[question.id]}
                </p>
              )}

              {!question.is_mandatory && (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => onSkip(question.id)}
                  className="mt-2 flex items-center gap-1 text-[11px] text-text-muted transition-colors hover:text-text disabled:opacity-50"
                >
                  <SkipForward size={11} />
                  Bỏ qua câu này
                </button>
              )}
            </div>
          );
        })}
      </div>

      {/* The single commit point for everything picked above. */}
      <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-border pt-3">
        <button
          type="button"
          disabled={!canSubmit}
          onClick={() => {
            const payload = Object.fromEntries(
              Object.entries(selected).filter(([, v]) => v.trim())
            );
            if (Object.keys(payload).length === 0) return;
            onAnswerAll(payload);
            setSelected({});
            setDrafts({});
            setCustomOpen({});
          }}
          className="flex items-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-[13px] font-semibold text-white transition-all hover:opacity-90 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Check size={15} />
          {isSubmitting ? 'Đang gửi…' : `Gửi ${totalPicked > 0 ? `(${totalPicked})` : ''}`}
        </button>

        <span className="text-[12px] text-text-muted">
          {answeredMandatory < mandatory.length
            ? `Còn ${mandatory.length - answeredMandatory} câu bắt buộc chưa chọn`
            : 'Đã đủ thông tin bắt buộc — bấm Gửi là mình chạy phân tích.'}
        </span>
      </div>

      {/* Escape hatch for reps who would rather type a sentence than work the card. */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!freeText.trim() || busy) return;
          onFreeTextAnswer(freeText.trim());
          setFreeText('');
        }}
        className="mt-3"
      >
        <div className="flex gap-2">
          <input
            type="text"
            value={freeText}
            disabled={busy}
            onChange={(e) => setFreeText(e.target.value)}
            placeholder="Hoặc trả lời tất cả trong một câu…"
            className="min-w-0 flex-1 rounded-lg border border-border bg-surface px-3 py-2 text-[13px] text-text outline-hidden transition-all focus:border-accent focus:ring-2 focus:ring-accent/20"
          />
          <button
            type="submit"
            disabled={busy || !freeText.trim()}
            className="flex shrink-0 items-center gap-1.5 rounded-lg border border-border bg-surface px-3 py-2 text-[13px] font-medium text-text transition-all hover:border-accent hover:text-accent-text active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Send size={14} />
            Gửi
          </button>
        </div>
      </form>
    </div>
  );
}

export default QuestionCard;
