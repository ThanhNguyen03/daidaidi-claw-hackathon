/**
 * Context Panel Component
 * ========================
 * Right-side panel showing brief summary, active constraints, and artifacts.
 * Uses Tailwind CSS for styling. Drawer overlay on mobile.
 */

import React, { useState } from 'react';
import { ChevronRight, X, RefreshCw, Info, AlertCircle, Download, FileText, GitBranch, Image, PanelRightClose, PanelRightOpen } from 'lucide-react';
import type { Brief, FeedbackRule as FeedbackRuleType } from '../lib/types';

// Artifact types
interface Artifact {
  id: string;
  type: 'pptx' | 'userflow' | 'quote' | 'wireframe';
  title: string;
  preview?: string;
  data?: string;
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

export function ContextPanel({
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

  // Toggle button when closed
  if (!isOpen) {
    return (
      <button
        onClick={onToggle}
        className="fixed right-0 top-1/2 -translate-y-1/2 bg-accent text-white border-none py-3 sm:py-4 px-1.5 sm:px-2 rounded-l-lg cursor-pointer text-xs font-medium z-50 flex items-center gap-1 shadow-card hover:opacity-90 transition-all"
        title="Open Context Panel"
      >
        <PanelRightOpen size={14} className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
        <span className="hidden sm:inline text-[11px] sm:text-xs">Context</span>
      </button>
    );
  }

  return (
    <>
      {/* Backdrop for mobile and tablet (below lg) */}
      <div
        onClick={onToggle}
        className="lg:hidden fixed inset-0 bg-black/40 z-40"
      />

      {/* Drawer panel - overlay on mobile/tablet, in-flow sticky panel on lg+ */}
      <aside className="
        bg-surface border-l border-border flex flex-col
        fixed right-0 top-0 bottom-0 z-50 shrink-0
        w-80 sm:w-80
        lg:sticky lg:top-0 lg:bottom-auto lg:h-screen lg:w-80
        transform transition-transform duration-300 ease-out
        lg:transform-none
        pb-20 lg:pb-0
      ">
        {/* Header */}
        <div className="px-4 py-3 sm:py-4 border-b border-border flex items-center justify-between">
          <h3 className="text-sm sm:text-base font-semibold text-text">Context</h3>
          <button
            onClick={onToggle}
            className="flex items-center gap-1.5 bg-transparent border-none cursor-pointer text-text-muted hover:text-text p-1.5 sm:p-0 rounded-lg sm:rounded-none hover:bg-surface-hover sm:bg-transparent transition-all"
            title="Close Context Panel"
          >
            <span className="hidden lg:inline text-[12px]">Close</span>
            <PanelRightClose size={18} />
          </button>
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
                          {new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 }).format(brief.budget_vnd)}
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
              <div className="p-3 bg-red-50 rounded-lg">
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
                        className="flex items-start gap-2 p-2 bg-white rounded border border-red-100"
                      >
                        <AlertCircle
                          size={16}
                          className={constraint.type === 'NEGATIVE_CONSTRAINT' ? 'text-red-600' : 'text-green-600'}
                          style={{ color: constraint.type === 'NEGATIVE_CONSTRAINT' ? '#dc2626' : '#16a34a' }}
                        />
                        <div className="flex-1 min-w-0">
                          <p className="text-xs text-text break-words">{constraint.rule}</p>
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
                      className="p-3 bg-sky-50 rounded-lg border border-sky-200"
                    >
                      <div className="flex items-center gap-2 mb-2">
                        {artifact.type === 'pptx' && <FileText size={16} className="text-sky-600" />}
                        {artifact.type === 'userflow' && <GitBranch size={16} className="text-violet-600" />}
                        {artifact.type === 'wireframe' && <Image size={16} className="text-emerald-600" />}
                        {artifact.type === 'quote' && <FileText size={16} className="text-red-600" />}
                        <span className="text-xs font-medium text-sky-900">{artifact.title}</span>
                      </div>

                      {artifact.type === 'userflow' && artifact.data && (
                        <div className="bg-white p-2 rounded text-[10px] font-mono text-gray-600 overflow-hidden text-ellipsis max-h-12 mb-2">
                          {artifact.data.substring(0, 200)}...
                        </div>
                      )}

                      {artifact.preview && (
                        <p className="text-xs text-sky-700 mb-2">{artifact.preview}</p>
                      )}

                      {onDownloadArtifact && (
                        <button
                          onClick={() => onDownloadArtifact(artifact)}
                          className="flex items-center gap-1 bg-sky-600 text-white border-none rounded py-1.5 px-3 text-xs cursor-pointer hover:bg-sky-700"
                        >
                          <Download size={12} />
                          Download
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

export default ContextPanel;