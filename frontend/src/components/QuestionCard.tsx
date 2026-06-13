/**
 * Question Card Component
 * =======================
 * Displays questions to the user in a distinct card.
 * C.5 §5: Yellow left-border + ? icon, numbered list.
 * Mandatory tagged (required), optional tagged (optional — assume: ...).
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
    <div
      style={{
        backgroundColor: '#fffbeb', // Light yellow background
        borderLeft: '4px solid #f59e0b', // Yellow left border - C.5-UI note
        borderRadius: '0.5rem',
        padding: '1rem',
        marginBottom: '1rem',
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)',
      }}
    >
      {/* Header with ? icon */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          marginBottom: '1rem',
          color: '#b45309',
        }}
      >
        <HelpCircle size={20} />
        <span style={{ fontWeight: '600', fontSize: '0.9375rem' }}>
          I need some information to proceed
        </span>
      </div>

      {/* Questions list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {questions.map((question, index) => (
          <div
            key={question.id}
            style={{
              padding: '0.75rem',
              backgroundColor: '#ffffff',
              borderRadius: '0.375rem',
              border: '1px solid #f3f4f6',
            }}
          >
            {/* Question number + mandatory tag */}
            <div
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '0.5rem',
                marginBottom: '0.5rem',
              }}
            >
              <span
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: '1.5rem',
                  height: '1.5rem',
                  backgroundColor: '#f59e0b',
                  color: '#ffffff',
                  borderRadius: '50%',
                  fontSize: '0.75rem',
                  fontWeight: '600',
                  flexShrink: 0,
                }}
              >
                {index + 1}
              </span>
              <span style={{ fontSize: '0.9375rem', color: '#1f2937', lineHeight: '1.5' }}>
                {question.text}
              </span>
            </div>

            {/* Tags: required / optional */}
            <div style={{ marginLeft: '2rem', marginBottom: '0.75rem' }}>
              {question.is_mandatory ? (
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    padding: '0.125rem 0.5rem',
                    backgroundColor: '#fef2f2',
                    color: '#dc2626',
                    borderRadius: '0.25rem',
                    fontSize: '0.6875rem',
                    fontWeight: '600',
                    textTransform: 'uppercase',
                  }}
                >
                  (required)
                </span>
              ) : (
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    padding: '0.125rem 0.5rem',
                    backgroundColor: '#fef3c7',
                    color: '#b45309',
                    borderRadius: '0.25rem',
                    fontSize: '0.6875rem',
                    fontWeight: '600',
                  }}
                >
                  (optional
                  {question.assumption && (
                    <span> — if skipped, I'll assume: {question.assumption}</span>
                  )}
                  )
                </span>
              )}
            </div>

            {/* Inline answer input */}
            {!question.is_mandatory && (
              <div style={{ marginLeft: '2rem' }}>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
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
                    style={{
                      flex: 1,
                      padding: '0.5rem 0.75rem',
                      border: '1px solid #d1d5db',
                      borderRadius: '0.375rem',
                      fontSize: '0.875rem',
                      outline: 'none',
                    }}
                  />
                  {/* Submit button */}
                  <button
                    onClick={() => submitInlineAnswer(question)}
                    disabled={disabled || !inlineAnswers[question.id]?.trim()}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      padding: '0.5rem',
                      backgroundColor: '#3b82f6',
                      color: '#ffffff',
                      border: 'none',
                      borderRadius: '0.375rem',
                      cursor:
                        disabled || !inlineAnswers[question.id]?.trim() ? 'not-allowed' : 'pointer',
                      opacity: disabled || !inlineAnswers[question.id]?.trim() ? 0.5 : 1,
                    }}
                  >
                    <Check size={16} />
                  </button>
                  {/* Skip button for optional */}
                  <button
                    onClick={() => onSkip(question.id)}
                    disabled={disabled}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      padding: '0.5rem',
                      backgroundColor: '#f3f4f6',
                      color: '#6b7280',
                      border: 'none',
                      borderRadius: '0.375rem',
                      cursor: disabled ? 'not-allowed' : 'pointer',
                    }}
                    title="Skip - use assumption"
                  >
                    <SkipForward size={16} />
                  </button>
                </div>
              </div>
            )}

            {/* For mandatory questions, show simple input too */}
            {question.is_mandatory && (
              <div style={{ marginLeft: '2rem' }}>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
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
                    required
                    style={{
                      flex: 1,
                      padding: '0.5rem 0.75rem',
                      border: '1px solid #d1d5db',
                      borderRadius: '0.375rem',
                      fontSize: '0.875rem',
                      outline: 'none',
                    }}
                  />
                  <button
                    onClick={() => submitInlineAnswer(question)}
                    disabled={disabled || !inlineAnswers[question.id]?.trim()}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      padding: '0.5rem',
                      backgroundColor: '#3b82f6',
                      color: '#ffffff',
                      border: 'none',
                      borderRadius: '0.375rem',
                      cursor:
                        disabled || !inlineAnswers[question.id]?.trim() ? 'not-allowed' : 'pointer',
                      opacity: disabled || !inlineAnswers[question.id]?.trim() ? 0.5 : 1,
                    }}
                  >
                    <Check size={16} />
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Free text answer path - C.5 §5 */}
      <div
        style={{
          marginTop: '1rem',
          paddingTop: '1rem',
          borderTop: '1px solid #f3f4f6',
        }}
      >
        <form onSubmit={handleFreeTextSubmit}>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <input
              type="text"
              value={freeText}
              onChange={(e) => setFreeText(e.target.value)}
              placeholder="Or answer everything in one message (e.g., 'F&B, 150 triệu, Q3 launch')"
              disabled={disabled}
              style={{
                flex: 1,
                padding: '0.5rem 0.75rem',
                border: '1px solid #d1d5db',
                borderRadius: '0.375rem',
                fontSize: '0.875rem',
                outline: 'none',
              }}
            />
            <button
              type="submit"
              disabled={disabled || !freeText.trim()}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '0.5rem 1rem',
                backgroundColor: '#10b981',
                color: '#ffffff',
                border: 'none',
                borderRadius: '0.375rem',
                fontSize: '0.875rem',
                cursor: disabled || !freeText.trim() ? 'not-allowed' : 'pointer',
                opacity: disabled || !freeText.trim() ? 0.5 : 1,
              }}
            >
              <Send size={16} style={{ marginRight: '0.25rem' }} />
              Send
            </button>
          </div>
          <p
            style={{
              marginTop: '0.5rem',
              fontSize: '0.75rem',
              color: '#6b7280',
            }}
          >
            I'll automatically map your answer to the right fields.
          </p>
        </form>
      </div>
    </div>
  );
}

export default QuestionCard;
