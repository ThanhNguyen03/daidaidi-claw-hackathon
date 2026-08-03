/**
 * ThinkingTrace Component
 * ======================
 * Displays detailed agent reasoning/thinking process in a collapsible card.
 * Inspired by Claude Desktop and Antigravity Desktop thinking UI.
 * 
 * Support rich step types:
 * - intent: Intent classification
 * - gate: Gate verdict & validation rules
 * - brief_extract: Brief field extraction details
 * - plan: Skill dispatch plan
 * - skill_start: Specialist agent launch & task prompt
 * - skill_done: Specialist output summary & key findings
 * - skill_failed: Specialist execution failure
 * - synthesis: Final answer assembly from specialists
 */

import React, { useState, useRef, useEffect } from 'react';
import {
  Brain,
  ChevronDown,
  ChevronUp,
  Check,
  Loader2,
  Zap,
  Shield,
  ListChecks,
  FileSearch,
  PlayCircle,
  CheckCircle2,
  AlertCircle,
  Layers,
} from 'lucide-react';
import type { ThinkingStep } from '../lib/types';

interface ThinkingTraceProps {
  steps: ThinkingStep[];
  /** True while the agent is still processing (steps may still arrive) */
  isActive: boolean;
}

// Each color pairs a darker light-mode shade with the lighter dark-mode shade —
// the -400 weight alone read fine on the near-black theme but was too pale for
// AA contrast on the light theme's white/near-white surfaces.
const STEP_CONFIG: Record<string, { icon: React.ReactNode; label: string; badgeColor: string }> = {
  intent: {
    icon: <Zap size={14} className="text-amber-600 dark:text-amber-400 shrink-0" />,
    label: 'Phân loại',
    badgeColor: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20',
  },
  gate: {
    icon: <Shield size={14} className="text-blue-600 dark:text-blue-400 shrink-0" />,
    label: 'Đánh giá Gate',
    badgeColor: 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20',
  },
  brief_extract: {
    icon: <FileSearch size={14} className="text-teal-600 dark:text-teal-400 shrink-0" />,
    label: 'Ghi nhận Brief',
    badgeColor: 'bg-teal-500/10 text-teal-600 dark:text-teal-400 border-teal-500/20',
  },
  plan: {
    icon: <ListChecks size={14} className="text-emerald-600 dark:text-emerald-400 shrink-0" />,
    label: 'Kế hoạch',
    badgeColor: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20',
  },
  skill_start: {
    icon: <PlayCircle size={14} className="text-indigo-600 dark:text-indigo-400 shrink-0" />,
    label: 'Chạy Specialist',
    badgeColor: 'bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border-indigo-500/20',
  },
  skill_done: {
    icon: <CheckCircle2 size={14} className="text-green-600 dark:text-green-400 shrink-0" />,
    label: 'Kết quả Specialist',
    badgeColor: 'bg-green-500/10 text-green-600 dark:text-green-400 border-green-500/20',
  },
  skill_failed: {
    icon: <AlertCircle size={14} className="text-rose-600 dark:text-rose-400 shrink-0" />,
    label: 'Lỗi Specialist',
    badgeColor: 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20',
  },
  synthesis: {
    icon: <Layers size={14} className="text-purple-600 dark:text-purple-400 shrink-0" />,
    label: 'Tổng hợp',
    badgeColor: 'bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20',
  },
};

const SKILL_NAMES_MAP: Record<string, string> = {
  market_strategy: 'Market Strategy',
  product_solution: 'Product Solution',
  compliance: 'Compliance',
  client_simulator: 'Client Simulator',
  proposal_assembler: 'Proposal Assembler',
  wireframe_designer: 'Deck Generator',
  cs_agent: 'CS Assistant',
};

// Memoized: one of these is mounted per historical assistant message in
// ChatWindow's message list, and that list re-renders on every streamed
// token of whichever message is currently live. `steps` keeps its array
// identity once attached to a message (set once at message creation, never
// mutated afterward), so a completed trace now skips re-rendering — including
// its own scrollHeight read in the effect below, which forces a layout.
function ThinkingTraceInner({ steps, isActive }: ThinkingTraceProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const contentRef = useRef<HTMLDivElement>(null);
  const [contentHeight, setContentHeight] = useState<number>(0);
  const userToggledRef = useRef(false);

  // Expand when active, stay open when completed unless user manually toggles
  useEffect(() => {
    if (isActive) {
      setIsExpanded(true);
      userToggledRef.current = false;
    }
  }, [isActive]);

  useEffect(() => {
    if (contentRef.current) {
      setContentHeight(contentRef.current.scrollHeight);
    }
  }, [steps, isExpanded]);

  if (steps.length === 0) return null;

  const handleToggle = () => {
    userToggledRef.current = true;
    setIsExpanded((prev) => !prev);
  };

  const summaryText = isActive
    ? `Đang suy nghĩ (${steps.length} bước)...`
    : `Đã suy nghĩ qua ${steps.length} bước chi tiết`;

  return (
    <div className="thinking-trace-container mt-3 sm:mt-4 mb-3">
      {/* Header */}
      <button
        onClick={handleToggle}
        className="thinking-trace-header group"
        aria-expanded={isExpanded}
        aria-label={isExpanded ? 'Thu gọn luồng suy nghĩ' : 'Mở rộng luồng suy nghĩ'}
      >
        <div className="flex items-center gap-2">
          <span className="thinking-trace-icon">
            {isActive ? (
              <Loader2 size={14} className="animate-spin text-accent" />
            ) : (
              <Brain size={14} className="text-accent" />
            )}
          </span>
          <span className="thinking-trace-summary">{summaryText}</span>
        </div>
        <span className="thinking-trace-chevron">
          {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </span>
      </button>

      {/* Body content */}
      <div
        className="thinking-trace-body"
        style={{
          maxHeight: isExpanded ? `${contentHeight + 32}px` : '0px',
          opacity: isExpanded ? 1 : 0,
        }}
      >
        <div ref={contentRef} className="thinking-trace-steps space-y-2 py-2">
          {steps.map((step, index) => {
            const isLast = index === steps.length - 1;
            const config = STEP_CONFIG[step.step] || {
              icon: <Zap size={14} className="text-text-muted shrink-0" />,
              label: step.step,
              badgeColor: 'bg-surface-2 text-text-muted border-border',
            };

            const agentDisplayName = step.agent
              ? SKILL_NAMES_MAP[step.agent] || step.agent
              : null;

            return (
              <div
                key={index}
                className="thinking-trace-step flex items-start gap-2 text-xs leading-relaxed group/step rounded-lg p-1.5 transition-colors hover:bg-surface-2/40"
              >
                <div className="thinking-trace-step-indicator shrink-0 mt-0.5">
                  {isActive && isLast ? (
                    <Loader2 size={12} className="animate-spin text-accent" />
                  ) : step.step === 'skill_failed' ? (
                    <AlertCircle size={12} className="text-rose-600 dark:text-rose-400" />
                  ) : (
                    <Check size={12} className="text-emerald-600 dark:text-emerald-400" />
                  )}
                </div>

                <div className="thinking-trace-step-content flex-1 min-w-0">
                  <div className="flex items-center gap-1.5 flex-wrap mb-0.5">
                    {config.icon}
                    <span className={`inline-flex items-center px-1.5 py-0.5 rounded-sm border text-[10px] font-semibold ${config.badgeColor}`}>
                      {config.label}
                    </span>
                    {agentDisplayName && (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded-sm border border-border bg-surface text-[10px] text-text-muted">
                        {agentDisplayName}
                      </span>
                    )}
                  </div>
                  <p className="thinking-trace-step-text text-text-muted text-[11px] wrap-break-word">
                    {step.content}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export const ThinkingTrace = React.memo(ThinkingTraceInner);
ThinkingTrace.displayName = 'ThinkingTrace';
