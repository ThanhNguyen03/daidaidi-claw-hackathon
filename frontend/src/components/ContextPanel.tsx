/**
 * Context Panel Component
 * ========================
 * Right-side panel showing brief summary, active constraints, and artifacts.
 * Uses Tailwind CSS for styling. Drawer overlay on mobile.
 */

import React, { useState } from 'react';
import { ChevronRight, X, RefreshCw, Info, AlertCircle, Download, ExternalLink, FileText, GitBranch, Image, PanelRightClose, PanelRightOpen } from 'lucide-react';
import type { Brief, FeedbackRule as FeedbackRuleType } from '../lib/types';

// Artifact types
interface Artifact {
  id: string;
  type: 'pptx' | 'userflow' | 'quote' | 'wireframe';
  title: string;
  preview?: string;
  data?: string;
  download_url?: string;   // backend-relative URL for binary file download
  artifact_id?: string;
}

interface ContextPanelProps {
  isOpen: boolean;
  onToggle: () => void;
  brief: Brief | null;
  constraints: FeedbackRuleType[];
  onRevokeConstraint: (ruleId: string) => void;
  isLoading?: boolean;
  artifacts?: Artifact[];
  onDownloadArtifact?: (artifact: Artifact) => void;
}

function ContextPanelInner({
  isOpen,
  onToggle,
  brief,
  constraints,
  onRevokeConstraint,
  isLoading = false,
  artifacts = [],
  onDownloadArtifact,
}: ContextPanelProps) {
  const [expandedSections, setExpandedSections] = useState({
    brief: true,
    constraints: true,
    preferences: false,
    artifacts: true,
  });

  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections((prev) => ({ ...prev, [section]: !prev[section] }));
  };

  // Opening/closing is driven by the single toggle button in the chat header
  // (and, below md, the sidebar's own mobile bar) — this panel does not also
  // render its own close/open control, so there is only ever one place that
  // does this job. It stays mounted at all times (rather than returning null
  // or a standalone floating tab when closed) so the slide/width transitions
  // below actually have something to animate between open and closed.

  return (
    <>
      {/* Backdrop for mobile and tablet (below lg) */}
      {isOpen && (
        <div
          onClick={onToggle}
          className="lg:hidden fixed inset-0 bg-black/40 z-40"
        />
      )}

      {/* Drawer panel — slides in as a fixed overlay on mobile/tablet, and
          widens/narrows in place as a docked column on lg+. Both are
          animated so open/close always has motion, not a hard cut. */}
      <aside
        aria-hidden={!isOpen}
        className={`
          glass-panel border-l border-border flex flex-col
          fixed right-0 top-0 bottom-0 z-50 shrink-0
          w-[min(20rem,88vw)]
          transform transition-transform duration-300 ease-out
          ${isOpen ? 'translate-x-0' : 'translate-x-full pointer-events-none'}
          lg:translate-x-0 lg:pointer-events-auto
          lg:sticky lg:top-0 lg:bottom-auto lg:h-full lg:overflow-hidden
          lg:transition-[width] lg:duration-300 lg:ease-out
          ${isOpen ? 'lg:w-80' : 'lg:w-0 lg:border-l-0'}
          pb-4 lg:pb-0
        `}
      >
        {/* Header — no close button here; the single toggle in the chat
            header (or the backdrop tap on mobile/tablet) closes this panel. */}
        <div className="h-14 px-4 border-b border-border flex items-center">
          <h3 className="text-sm sm:text-base font-semibold text-gradient-tech">Context</h3>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-3 sm:px-4 py-3 sm:py-4">
          {/* Brief Summary */}
          <div className="mb-4 sm:mb-6">
            <button
              onClick={() => toggleSection('brief')}
              className="flex items-center justify-between w-full bg-transparent border-none cursor-pointer py-1.5 sm:py-2"
            >
              <span className="font-semibold text-xs sm:text-[12px] text-text">Brief Summary</span>
              <ChevronRight
                size={14} className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-text-muted transition-transform"
              />
            </button>

            {expandedSections.brief && (
              <div className="p-3 bg-surface-2 rounded-lg">
                {brief ? (
                  <div className="flex flex-col gap-2">
                    {brief.industry && (
                      <div>
                        <span className="text-xs text-text-muted">Industry</span>
                        <p className="text-[12px] text-text">{brief.industry}</p>
                      </div>
                    )}
                    {brief.budget_vnd && (
                      <div>
                        <span className="text-xs text-text-muted">Budget</span>
                        <p className="text-[12px] text-text">
                          {new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 }).format(Number(brief.budget_vnd))}
                        </p>
                      </div>
                    )}
                    {brief.goal && (
                      <div>
                        <span className="text-xs text-text-muted">Goal</span>
                        <p className="text-[12px] text-text">{brief.goal}</p>
                      </div>
                    )}
                    {!brief.industry && !brief.budget_vnd && !brief.goal && (
                      <p className="text-[12px] text-text-muted">No brief information yet</p>
                    )}
                  </div>
                ) : (
                  <p className="text-[12px] text-text-muted">No brief information yet</p>
                )}
              </div>
            )}
          </div>

          {/* Active Constraints */}
          <div className="mb-4 sm:mb-6">
            <button
              onClick={() => toggleSection('constraints')}
              className="flex items-center justify-between w-full bg-transparent border-none cursor-pointer py-1.5 sm:py-2"
            >
              <span className="font-semibold text-xs sm:text-[12px] text-text">Active Constraints</span>
              <ChevronRight
                size={14} className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-text-muted transition-transform"
              />
            </button>

            {expandedSections.constraints && (
              <div className="p-3 bg-red-500/10 border border-red-500/25 rounded-lg">
                {isLoading ? (
                  <div className="flex items-center gap-2 text-text-muted">
                    <RefreshCw size={14} className="animate-spin" />
                    <span className="text-xs">Loading...</span>
                  </div>
                ) : constraints.length > 0 ? (
                  <div className="flex flex-col gap-3">
                    {constraints.map((constraint) => (
                      <div
                        key={constraint.rule_id}
                        className="flex items-start gap-2 p-2 bg-surface-2 rounded-sm border border-border"
                      >
                        <AlertCircle
                          size={16}
                          className={constraint.type === 'NEGATIVE_CONSTRAINT' ? 'text-red-600 dark:text-red-400 shrink-0' : 'text-green-600 dark:text-green-400 shrink-0'}
                        />
                        <div className="flex-1 min-w-0">
                          <p className="text-xs text-text wrap-break-word">{constraint.rule}</p>
                          <span className="text-[10px] text-text-muted block mt-1">
                            {constraint.type === 'NEGATIVE_CONSTRAINT' ? '🔴 Never do this' : '🟢 Always do this'}
                          </span>
                        </div>
                        <button
                          onClick={() => onRevokeConstraint(constraint.rule_id)}
                          title="Revoke this constraint"
                          className="bg-transparent border-none cursor-pointer text-text-muted hover:text-text p-0.5 shrink-0"
                        >
                          <X size={14} />
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-4">
                    <p className="text-[12px] text-text-muted">No active constraints</p>
                    <p className="text-xs text-text-muted mt-1">Tell the assistant &quot;don&apos;t suggest X&quot; to create one</p>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Preferences */}
          <div>
            <button
              onClick={() => toggleSection('preferences')}
              className="flex items-center justify-between w-full bg-transparent border-none cursor-pointer py-1.5 sm:py-2"
            >
              <span className="font-semibold text-xs sm:text-[12px] text-text">Preferences</span>
              <ChevronRight
                size={14} className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-text-muted transition-transform"
              />
            </button>

            {expandedSections.preferences && (
              <div className="p-3 bg-surface-2 rounded-lg">
                <div className="flex items-center gap-2 text-text-muted">
                  <Info size={14} />
                  <span className="text-xs">Learned from your interactions</span>
                </div>
              </div>
            )}
          </div>

          {/* Artifacts */}
          {artifacts && artifacts.length > 0 && (
            <div className="mt-6">
              <button
                onClick={() => toggleSection('artifacts')}
                className="flex items-center justify-between w-full bg-transparent border-none cursor-pointer py-2"
              >
                <span className="font-semibold text-[12px] text-text">Generated Artifacts</span>
                <ChevronRight
                  size={16}
                  className={`text-text-muted transition-transform ${expandedSections.artifacts ? 'rotate-90' : ''}`}
                />
              </button>

              {expandedSections.artifacts && (
                <div className="flex flex-col gap-3">
                  {artifacts.map((artifact) => (
                    <div
                      key={artifact.id}
                      className="p-3 bg-accent-soft rounded-lg border border-accent/25"
                    >
                      <div className="flex items-center gap-2 mb-2">
                        {artifact.type === 'pptx' && <FileText size={16} className="text-accent" />}
                        {artifact.type === 'userflow' && <GitBranch size={16} className="text-violet-600 dark:text-violet-400" />}
                        {artifact.type === 'wireframe' && <ImageIcon size={16} className="text-emerald-600 dark:text-emerald-400" />}
                        {artifact.type === 'quote' && <FileText size={16} className="text-red-600 dark:text-red-400" />}
                        <span className="text-xs font-medium text-text">{artifact.title}</span>
                      </div>

                      {artifact.type === 'userflow' && artifact.data && (
                        <div className="bg-surface-2 p-2 rounded-sm text-[10px] font-mono text-text-muted overflow-hidden text-ellipsis max-h-12 mb-2">
                          {artifact.data.substring(0, 200)}...
                        </div>
                      )}

                      {artifact.preview && (
                        <p className="text-xs text-text-muted mb-2">{artifact.preview}</p>
                      )}

                      {onDownloadArtifact && (
                        <button
                          onClick={() => onDownloadArtifact(artifact)}
                          className="flex items-center gap-1 bg-accent text-white border-none rounded-sm py-1.5 px-3 text-xs cursor-pointer hover:opacity-90"
                        >
                          {/* The HTML deck opens in a new tab — it does not save a
                              file to disk — so labelling it "Download" like the
                              PPTX (which genuinely does) promised behavior it
                              didn't deliver. */}
                          {artifact.type === 'wireframe' ? (
                            <>
                              <ExternalLink size={12} />
                              Xem
                            </>
                          ) : (
                            <>
                              <Download size={12} />
                              Download
                            </>
                          )}
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </aside>
    </>
  );
}

// Memoized for the same reason as Sidebar: page.tsx re-renders on every
// streamed token, and this panel's callbacks are now stable (see page.tsx).
export const ContextPanel = React.memo(ContextPanelInner);
ContextPanel.displayName = 'ContextPanel';
export default ContextPanel;