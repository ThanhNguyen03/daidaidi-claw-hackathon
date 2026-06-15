/**
 * Question Card Component
 * =======================
 * Displays questions to the user in a distinct card.
 * Uses plain CSS values to avoid theme override issues.
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

  // Responsive styles
  const containerStyle: React.CSSProperties = {
    backgroundColor: '#ffffff',
    border: '1px solid #e5e7eb',
    borderRadius: '12px',
    padding: '16px',
    marginBottom: '16px',
    zIndex: 99999,
    position: 'relative',
  };

  const headerStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    marginBottom: '16px',
    color: '#4f46e5',
  };

  const questionItemStyle: React.CSSProperties = {
    padding: '14px',
    backgroundColor: '#f9fafb',
    border: '1px solid #e5e7eb',
    borderRadius: '8px',
  };

  const questionTextStyle: React.CSSProperties = {
    fontSize: '14px',
    color: '#374151',
    lineHeight: 1.6,
    wordBreak: 'break-word',
  };

  const inputStyle: React.CSSProperties = {
    flex: 1,
    padding: '10px 14px',
    borderRadius: '8px',
    border: '1px solid #d1d5db',
    backgroundColor: '#ffffff',
    color: '#374151',
    fontSize: '14px',
    cursor: 'text',
    width: '100%',
    pointerEvents: 'auto',
  };

  const buttonStyle: React.CSSProperties = {
    padding: '10px 14px',
    borderRadius: '8px',
    backgroundColor: '#4f46e5',
    color: '#ffffff',
    border: 'none',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    fontSize: '14px',
    fontWeight: 500,
    whiteSpace: 'nowrap',
  };

  return (
    <div
      className="question-card-container"
      style={containerStyle}
    >
      {/* Header */}
      <div style={headerStyle}>
        <HelpCircle size={18} />
        <span style={{ fontWeight: 600, fontSize: '14px' }}>Need some information to proceed</span>
      </div>

      {/* Questions list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {questions.map((question, index) => (
          <div key={question.id} style={questionItemStyle}>
            {/* Question number + text */}
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', marginBottom: '10px' }}>
              <span
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: '24px',
                  height: '24px',
                  borderRadius: '50%',
                  backgroundColor: '#4f46e5',
                  color: '#ffffff',
                  fontSize: '12px',
                  fontWeight: 600,
                  flexShrink: 0,
                }}
              >
                {index + 1}
              </span>
              <span style={questionTextStyle}>{question.text}</span>
            </div>

            {/* Tags */}
            <div style={{ marginLeft: '34px', marginBottom: '10px' }}>
              {question.is_mandatory ? (
                <span
                  style={{
                    display: 'inline-flex',
                    padding: '3px 8px',
                    borderRadius: '4px',
                    fontSize: '10px',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    backgroundColor: '#fee2e2',
                    color: '#dc2626',
                  }}
                >
                  Required
                </span>
              ) : (
                <span
                  style={{
                    display: 'inline-flex',
                    padding: '3px 8px',
                    borderRadius: '4px',
                    fontSize: '10px',
                    fontWeight: 500,
                    backgroundColor: '#e0e7ff',
                    color: '#4f46e5',
                    flexWrap: 'wrap',
                    gap: '4px',
                  }}
                >
                  Optional
                  {question.assumption && (
                    <span style={{ color: '#6b7280', marginLeft: '4px' }}>
                      — will assume: {question.assumption}
                    </span>
                  )}
                </span>
              )}
            </div>

            {/* Inline answer input */}
            <div style={{ marginLeft: '34px', position: 'relative', zIndex: 100 }}>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                <input
                  type="text"
                  id={`answer-${question.id}`}
                  name={`answer-${question.id}`}
                  value={inlineAnswers[question.id] || ''}
                  onChange={(e) => handleInlineAnswer(question.id, e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      submitInlineAnswer(question);
                    }
                  }}
                  placeholder="Type your answer..."
                  disabled={disabled}
                  autoComplete="off"
                  style={{
                    ...inputStyle,
                    cursor: disabled ? 'not-allowed' : 'text',
                    minWidth: '120px',
                    flex: '1 1 140px',
                  }}
                />
                <button
                  type="button"
                  aria-label="Send answer"
                  onClick={() => submitInlineAnswer(question)}
                  disabled={disabled || !inlineAnswers[question.id]?.trim()}
                  style={{
                    ...buttonStyle,
                    opacity: (disabled || !inlineAnswers[question.id]?.trim()) ? 0.5 : 1,
                    cursor: (disabled || !inlineAnswers[question.id]?.trim()) ? 'not-allowed' : 'pointer',
                  }}
                >
                  <Check size={16} />
                  <span className="hidden sm:inline">Send</span>
                </button>
                {!question.is_mandatory && (
                  <button
                    type="button"
                    aria-label="Skip this question"
                    onClick={() => onSkip(question.id)}
                    disabled={disabled}
                    style={{
                      padding: '10px',
                      borderRadius: '8px',
                      backgroundColor: '#f3f4f6',
                      color: '#6b7280',
                      border: '1px solid #d1d5db',
                      cursor: disabled ? 'not-allowed' : 'pointer',
                    }}
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
      <div style={{ marginTop: '16px', paddingTop: '14px', borderTop: '1px solid #e5e7eb' }}>
        <form onSubmit={handleFreeTextSubmit}>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <input
              type="text"
              id="free-text-answer"
              name="freeTextAnswer"
              value={freeText}
              onChange={(e) => setFreeText(e.target.value)}
              placeholder="Or answer everything in one message..."
              disabled={disabled}
              style={{
                ...inputStyle,
                flex: '1 1 180px',
                minWidth: '150px',
              }}
            />
            <button
              type="submit"
              aria-label="Send free text answer"
              disabled={disabled || !freeText.trim()}
              style={{
                ...buttonStyle,
                opacity: disabled ? 0.5 : 1,
                cursor: disabled ? 'not-allowed' : 'pointer',
              }}
            >
              <Send size={16} />
              <span className="hidden sm:inline">Send</span>
            </button>
          </div>
          <p style={{ fontSize: '12px', color: '#6b7280', marginTop: '8px' }}>
            I'll automatically map your answer to the right fields.
          </p>
        </form>
      </div>
    </div>
  );
}

export default QuestionCard;