/**
 * Question Card Component
 * =======================
 * Displays questions to the user in a distinct card.
 * Uses Tailwind CSS for styling.
 */

import React, { useState } from 'react';
import { HelpCircle, Check, SkipForward, Send } from 'lucide-react';
import type { Question } from '../lib/types';

interface QuestionCardProps {
  questions: Question[];
  onAnswer: (questionId: string, answer: string) => void;
  onSkip: (questionId: string) => void;
  onFreeTextAnswer: (freeText: string) => void;
  disabled?: boolean;
}

export function QuestionCard({
  questions,
  onAnswer,
  onSkip,
  onFreeTextAnswer,
  disabled = false,
}: QuestionCardProps) {
  const [freeText, setFreeText] = useState('');
  const [inlineAnswers, setInlineAnswers] = useState<Record<string, string>>({});

  const handleInlineAnswer = (questionId: string, answer: string) => {
    setInlineAnswers((prev) => ({ ...prev, [questionId]: answer }));
  };

  const submitInlineAnswer = (question: Question) => {
    const answer = inlineAnswers[question.id];
    if (answer?.trim()) {
      onAnswer(question.id, answer);
      setInlineAnswers((prev) => {
        const next = { ...prev };
        delete next[question.id];
        return next;
      });
    }
  };

  const handleFreeTextSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (freeText.trim()) {
      onFreeTextAnswer(freeText);
      setFreeText('');
    }
  };

  if (!questions || questions.length === 0) {
    return null;
  }

  return (
    <div className="bg-yellow-50 border-l-4 border-yellow-500 rounded-lg p-4 mb-4 shadow-sm">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4 text-amber-700">
        <HelpCircle size={20} />
        <span className="font-semibold text-sm">I need some information to proceed</span>
      </div>

      {/* Questions list */}
      <div className="flex flex-col gap-4">
        {questions.map((question, index) => (
          <div
            key={question.id}
            className="p-3 bg-white rounded border border-gray-100"
          >
            {/* Question number + text */}
            <div className="flex items-start gap-2 mb-2">
              <span className="flex items-center justify-center w-6 h-6 bg-yellow-500 text-white rounded-full text-xs font-semibold shrink-0">
                {index + 1}
              </span>
              <span className="text-sm text-gray-800 leading-relaxed">{question.text}</span>
            </div>

            {/* Tags */}
            <div className="ml-8 mb-3">
              {question.is_mandatory ? (
                <span className="inline-flex items-center px-2 py-0.5 bg-red-50 text-red-700 rounded text-[10px] font-semibold uppercase">
                  (required)
                </span>
              ) : (
                <span className="inline-flex items-center px-2 py-0.5 bg-yellow-100 text-amber-700 rounded text-[10px] font-medium">
                  (optional
                  {question.assumption && (
                    <span> — if skipped, I&apos;ll assume: {question.assumption}</span>
                  )}
                  )
                </span>
              )}
            </div>

            {/* Inline answer input */}
            <div className="ml-8">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={inlineAnswers[question.id] || ''}
                  onChange={(e) => handleInlineAnswer(question.id, e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      submitInlineAnswer(question);
                    }
                  }}
                  placeholder="Type your answer..."
                  disabled={disabled}
                  className="flex-1 px-3 py-2 border border-gray-300 rounded text-sm outline-none focus:border-yellow-500"
                />
                <button
                  onClick={() => submitInlineAnswer(question)}
                  disabled={disabled || !inlineAnswers[question.id]?.trim()}
                  className="p-2 bg-accent text-white rounded hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Check size={16} />
                </button>
                {!question.is_mandatory && (
                  <button
                    onClick={() => onSkip(question.id)}
                    disabled={disabled}
                    className="p-2 bg-gray-100 text-text-muted rounded hover:bg-gray-200 disabled:opacity-50"
                    title="Skip - use assumption"
                  >
                    <SkipForward size={16} />
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Free text answer */}
      <div className="mt-4 pt-4 border-t border-gray-100">
        <form onSubmit={handleFreeTextSubmit}>
          <div className="flex gap-2">
            <input
              type="text"
              value={freeText}
              onChange={(e) => setFreeText(e.target.value)}
              placeholder="Or answer everything in one message (e.g., 'F&B, 150 triệu, Q3 launch')"
              disabled={disabled}
              className="flex-1 px-3 py-2 border border-gray-300 rounded text-sm outline-none focus:border-green-500"
            />
            <button
              type="submit"
              disabled={disabled || !freeText.trim()}
              className="flex items-center gap-1 px-4 py-2 bg-green-500 text-white rounded text-sm hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Send size={16} />
              Send
            </button>
          </div>
          <p className="text-xs text-text-muted mt-2">
            I&apos;ll automatically map your answer to the right fields.
          </p>
        </form>
      </div>
    </div>
  );
}

export default QuestionCard;