/**
 * Context Panel Component
 * ========================
 * Right-side panel showing brief summary, active constraints,
 * and other context. Day 4 deliverable.
 */

import React, { useState, useEffect } from 'react';
import { ChevronRight, X, RefreshCw, Info, AlertCircle, Download, FileText, GitBranch, Image } from 'lucide-react';
import type { Brief, FeedbackRule as FeedbackRuleType, Checkpoint } from '../lib/types';

// Artifact types for Day 6
interface Artifact {
  id: string;
  type: 'pptx' | 'userflow' | 'quote' | 'wireframe';
  title: string;
  preview?: string;
  data?: string;  // For Mermaid code or download URL
}

interface ContextPanelProps {
  isOpen: boolean;
  onToggle: () => void;
  brief: Brief | null;
  constraints: FeedbackRuleType[];
  onRevokeConstraint: (ruleId: string) => void;
  isLoading?: boolean;
  // Day 6: Artifacts
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
  // Day 6: Artifacts
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

  if (!isOpen) {
    return (
      <button
        onClick={onToggle}
        style={{
          position: 'fixed',
          right: 0,
          top: '50%',
          transform: 'translateY(-50%)',
          backgroundColor: '#3b82f6',
          color: 'white',
          border: 'none',
          borderRadius: '4px 0 0 4px',
          padding: '1rem 0.5rem',
          cursor: 'pointer',
          writingMode: 'vertical-rl',
          textOrientation: 'mixed',
          fontSize: '0.75rem',
          fontWeight: '500',
          zIndex: 100,
        }}
      >
        Context
      </button>
    );
  }

  return (
    <div
      style={{
        width: '320px',
        backgroundColor: '#ffffff',
        borderLeft: '1px solid #e5e7eb',
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '1rem',
          borderBottom: '1px solid #e5e7eb',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <h3 style={{ fontSize: '1rem', fontWeight: '600', color: '#111827' }}>
          Context
        </h3>
        <button
          onClick={onToggle}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: '#6b7280',
            padding: '0.25rem',
          }}
        >
          <X size={18} />
        </button>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '1rem' }}>
        {/* Brief Summary Section */}
        <div style={{ marginBottom: '1.5rem' }}>
          <button
            onClick={() => toggleSection('brief')}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              width: '100%',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '0.5rem 0',
            }}
          >
            <span style={{ fontWeight: '600', color: '#374151', fontSize: '0.875rem' }}>
              Brief Summary
            </span>
            <ChevronRight
              size={16}
              style={{
                transform: expandedSections.brief ? 'rotate(90deg)' : 'rotate(0deg)',
                transition: 'transform 0.2s',
                color: '#9ca3af',
              }}
            />
          </button>

          {expandedSections.brief && (
            <div style={{ padding: '0.75rem', backgroundColor: '#f9fafb', borderRadius: '0.5rem' }}>
              {brief ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {brief.industry && (
                    <div>
                      <span style={{ fontSize: '0.75rem', color: '#6b7280' }}>Industry</span>
                      <p style={{ fontSize: '0.875rem', color: '#111827', margin: 0 }}>
                        {brief.industry}
                      </p>
                    </div>
                  )}
                  {brief.budget_vnd && (
                    <div>
                      <span style={{ fontSize: '0.75rem', color: '#6b7280' }}>Budget</span>
                      <p style={{ fontSize: '0.875rem', color: '#111827', margin: 0 }}>
                        {new Intl.NumberFormat('vi-VN', {
                          style: 'currency',
                          currency: 'VND',
                          maximumFractionDigits: 0,
                        }).format(brief.budget_vnd)}
                      </p>
                    </div>
                  )}
                  {brief.goal && (
                    <div>
                      <span style={{ fontSize: '0.75rem', color: '#6b7280' }}>Goal</span>
                      <p style={{ fontSize: '0.875rem', color: '#111827', margin: 0 }}>
                        {brief.goal}
                      </p>
                    </div>
                  )}
                  {!brief.industry && !brief.budget_vnd && !brief.goal && (
                    <p style={{ fontSize: '0.875rem', color: '#9ca3af', margin: 0 }}>
                      No brief information yet
                    </p>
                  )}
                </div>
              ) : (
                <p style={{ fontSize: '0.875rem', color: '#9ca3af', margin: 0 }}>
                  No brief information yet
                </p>
              )}
            </div>
          )}
        </div>

        {/* Active Constraints Section - Day 4 Key Feature */}
        <div style={{ marginBottom: '1.5rem' }}>
          <button
            onClick={() => toggleSection('constraints')}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              width: '100%',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '0.5rem 0',
            }}
          >
            <span style={{ fontWeight: '600', color: '#374151', fontSize: '0.875rem' }}>
              Active Constraints
            </span>
            <ChevronRight
              size={16}
              style={{
                transform: expandedSections.constraints ? 'rotate(90deg)' : 'rotate(0deg)',
                transition: 'transform 0.2s',
                color: '#9ca3af',
              }}
            />
          </button>

          {expandedSections.constraints && (
            <div style={{ padding: '0.75rem', backgroundColor: '#fef2f2', borderRadius: '0.5rem' }}>
              {isLoading ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#6b7280' }}>
                  <RefreshCw size={14} className="animate-spin" />
                  <span style={{ fontSize: '0.75rem' }}>Loading...</span>
                </div>
              ) : constraints.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {constraints.map((constraint) => (
                    <div
                      key={constraint.rule_id}
                      style={{
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: '0.5rem',
                        padding: '0.5rem',
                        backgroundColor: '#ffffff',
                        borderRadius: '0.375rem',
                        border: '1px solid #fee2e2',
                      }}
                    >
                      <AlertCircle
                        size={16}
                        style={{
                          color: constraint.type === 'NEGATIVE_CONSTRAINT' ? '#dc2626' : '#16a34a',
                          flexShrink: 0,
                          marginTop: '0.125rem',
                        }}
                      />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <p
                          style={{
                            fontSize: '0.8125rem',
                            color: '#111827',
                            margin: 0,
                            wordBreak: 'break-word',
                          }}
                        >
                          {constraint.rule}
                        </p>
                        <span
                          style={{
                            fontSize: '0.6875rem',
                            color: '#6b7280',
                            display: 'block',
                            marginTop: '0.25rem',
                          }}
                        >
                          {constraint.type === 'NEGATIVE_CONSTRAINT' ? '🔴 Never do this' : '🟢 Always do this'}
                        </span>
                      </div>
                      <button
                        onClick={() => onRevokeConstraint(constraint.rule_id)}
                        title="Revoke this constraint"
                        style={{
                          background: 'none',
                          border: 'none',
                          cursor: 'pointer',
                          color: '#9ca3af',
                          padding: '0.125rem',
                          flexShrink: 0,
                        }}
                      >
                        <X size={14} />
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ textAlign: 'center', padding: '1rem 0' }}>
                  <p style={{ fontSize: '0.875rem', color: '#6b7280', margin: 0 }}>
                    No active constraints
                  </p>
                  <p style={{ fontSize: '0.75rem', color: '#9ca3af', margin: '0.5rem 0 0' }}>
                    Tell the assistant "don't suggest X" to create one
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Preferences Section */}
        <div>
          <button
            onClick={() => toggleSection('preferences')}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              width: '100%',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '0.5rem 0',
            }}
          >
            <span style={{ fontWeight: '600', color: '#374151', fontSize: '0.875rem' }}>
              Preferences
            </span>
            <ChevronRight
              size={16}
              style={{
                transform: expandedSections.preferences ? 'rotate(90deg)' : 'rotate(0deg)',
                transition: 'transform 0.2s',
                color: '#9ca3af',
              }}
            />
          </button>

          {expandedSections.preferences && (
            <div style={{ padding: '0.75rem', backgroundColor: '#f9fafb', borderRadius: '0.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#6b7280' }}>
                <Info size={14} />
                <span style={{ fontSize: '0.8125rem' }}>
                  Learned from your interactions
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Artifacts Section - Day 6 Key Feature */}
        {artifacts && artifacts.length > 0 && (
          <div style={{ marginTop: '1.5rem' }}>
            <button
              onClick={() => toggleSection('artifacts')}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                width: '100%',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                padding: '0.5rem 0',
              }}
            >
              <span style={{ fontWeight: '600', color: '#374151', fontSize: '0.875rem' }}>
                Generated Artifacts
              </span>
              <ChevronRight
                size={16}
                style={{
                  transform: expandedSections.artifacts ? 'rotate(90deg)' : 'rotate(0deg)',
                  transition: 'transform 0.2s',
                  color: '#9ca3af',
                }}
              />
            </button>

            {expandedSections.artifacts && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {artifacts.map((artifact) => (
                  <div
                    key={artifact.id}
                    style={{
                      padding: '0.75rem',
                      backgroundColor: '#f0f9ff',
                      borderRadius: '0.5rem',
                      border: '1px solid #bae6fd',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                      {artifact.type === 'pptx' && <FileText size={16} style={{ color: '#0284c7' }} />}
                      {artifact.type === 'userflow' && <GitBranch size={16} style={{ color: '#7c3aed' }} />}
                      {artifact.type === 'wireframe' && <Image size={16} style={{ color: '#059669' }} />}
                      {artifact.type === 'quote' && <FileText size={16} style={{ color: '#dc2626' }} />}
                      <span style={{ fontSize: '0.8125rem', fontWeight: '500', color: '#0c4a6e' }}>
                        {artifact.title}
                      </span>
                    </div>

                    {/* Preview for userflow (Mermaid) */}
                    {artifact.type === 'userflow' && artifact.data && (
                      <div
                        style={{
                          backgroundColor: '#ffffff',
                          padding: '0.5rem',
                          borderRadius: '0.375rem',
                          marginBottom: '0.5rem',
                          fontSize: '0.6875rem',
                          fontFamily: 'monospace',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          maxHeight: '3rem',
                          color: '#4b5563',
                        }}
                      >
                        {artifact.data.substring(0, 200)}...
                      </div>
                    )}

                    {/* Preview text for other types */}
                    {artifact.preview && (
                      <p style={{ fontSize: '0.75rem', color: '#0369a1', margin: '0 0 0.5rem' }}>
                        {artifact.preview}
                      </p>
                    )}

                    {/* Download button */}
                    {onDownloadArtifact && (
                    <button
                      onClick={() => onDownloadArtifact(artifact)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.25rem',
                        backgroundColor: '#0284c7',
                        color: 'white',
                        border: 'none',
                        borderRadius: '0.25rem',
                        padding: '0.375rem 0.75rem',
                        fontSize: '0.75rem',
                        cursor: 'pointer',
                      }}
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
    </div>
  );
}

export default ContextPanel;