/**
 * Message Bubble Component
 * ========================
 * Renders individual chat messages with agent avatars.
 * Uses Tailwind CSS for styling.
 */

import React, { useMemo } from 'react';
import type { Message } from '../lib/types';
import { Bot, User, Sparkles, FileText, Users, Target, Clock, TrendingUp } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

// Detect and fix tables that have header + data but NO delimiter row
// Example: "| A | B | C |" + "| X | Y | Z |" (missing |---|---|)
function fixMissingDelimiterTables(content: string): string {
  const lines = content.split('\n');
  const result: string[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();

    // Check if this is a table row (has 3+ pipes)
    const pipeCount = (line.match(/\|/g) || []).length;
    if (pipeCount < 3) {
      result.push(line);
      continue;
    }

    // Check if previous line was also a table row (no delimiter between them)
    if (i > 0) {
      const prevLine = lines[i - 1].trim();
      const prevPipeCount = (prevLine.match(/\|/g) || []).length;

      if (prevPipeCount >= 3 && !prevLine.includes('---')) {
        // Need to insert delimiter row between them
        // Generate |---|---|---| based on column count
        const cols = pipeCount - 1;
        const delimiter = '| ' + Array(cols).fill('---').join(' | ') + ' |';
        result.push(delimiter);
      }
    }

    result.push(line);
  }

  return result.join('\n');
}

// Detect if content is a brief document (has tables with specific structure)
function isBriefDocument(content: string): boolean {
  const hasBriefHeader = /📋|BRIEF|Chương trình|TỔNG QUAN/i.test(content);
  const hasTable = /\|.+\|/.test(content);
  const hasProjectInfo = /Client|Mục tiêu|TA|Kênh|Timeline/i.test(content);
  return hasBriefHeader && hasTable && hasProjectInfo;
}

// Extract brief info for custom rendering
interface BriefInfo {
  title: string;
  sections: Array<{ key: string; value: string }>;
}

function parseBriefContent(content: string): BriefInfo | null {
  if (!isBriefDocument(content)) return null;

  const lines = content.split('\n');
  let title = '';
  const sections: Array<{ key: string; value: string }> = [];

  for (const line of lines) {
    const trimmed = line.trim();
    // Match lines like: | Client | [Tên brand sẽ được điền] |
    const tableMatch = trimmed.match(/^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|$/);
    if (tableMatch) {
      const key = tableMatch[1].trim();
      const value = tableMatch[2].trim();
      // Check if it's a header row (no dashes)
      if (!key.includes('-') && !value.includes('-') && key && value) {
        if (!title && /📋|BRIEF/i.test(key)) {
          title = value;
        } else if (key && value) {
          sections.push({ key, value });
        }
      }
    }
  }

  return sections.length > 0 ? { title, sections } : null;
}

// Icon mapping for brief sections
const sectionIcons: Record<string, React.ReactNode> = {
  'client': <Users size={16} />,
  'mục tiêu': <Target size={16} />,
  'ta': <Users size={16} />,
  'target audience': <Users size={16} />,
  'kênh': <FileText size={16} />,
  'channel': <FileText size={16} />,
  'timeline': <Clock size={16} />,
  'budget': <TrendingUp size={16} />,
  'ngân sách': <TrendingUp size={16} />,
};

// Custom Brief Document Renderer
function BriefDocument({ content }: { content: string }) {
  const briefInfo = useMemo(() => parseBriefContent(content), [content]);

  if (!briefInfo) return null;

  return (
    <div className="w-full my-4">
      {/* Header Card */}
      {briefInfo.title && (
        <div
          className="rounded-t-xl px-6 py-4"
          style={{
            background: 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
          }}
        >
          <h2 className="text-white text-lg font-semibold m-0 flex items-center gap-2">
            <FileText size={20} />
            {briefInfo.title}
          </h2>
        </div>
      )}

      {/* Info Cards Grid */}
      <div
        className="rounded-b-xl overflow-hidden"
        style={{
          backgroundColor: 'var(--color-surface)',
          boxShadow: '0 10px 40px -10px rgba(0,0,0,0.15)',
        }}
      >
        <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))' }}>
          {briefInfo.sections.map((section, index) => {
            const iconKey = Object.keys(sectionIcons).find(k =>
              section.key.toLowerCase().includes(k)
            );
            const icon = iconKey ? sectionIcons[iconKey] : <FileText size={16} />;

            return (
              <div
                key={index}
                className="p-4 flex items-start gap-3"
                style={{
                  borderBottom: '1px solid var(--color-border)',
                  borderRight: index % 2 === 0 ? '1px solid var(--color-border)' : 'none',
                }}
              >
                <div
                  className="shrink-0 w-9 h-9 rounded-lg flex items-center justify-center"
                  style={{
                    backgroundColor: 'rgba(79, 70, 229, 0.1)',
                    color: '#4f46e5',
                  }}
                >
                  {icon}
                </div>
                <div className="flex-1 min-w-0">
                  <p
                    className="text-xs font-medium m-0 mb-1"
                    style={{
                      color: 'var(--color-text-muted)',
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em',
                    }}
                  >
                    {section.key}
                  </p>
                  <p
                    className="text-sm m-0"
                    style={{
                      color: 'var(--color-text)',
                      lineHeight: 1.5,
                    }}
                  >
                    {section.value}
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

// Helper to fix malformed markdown tables (all on one line)
// Handles cases like: "| H1 | H2 | |----|----|----| | C1 | C2 |"
function fixMalformedTables(content: string): string {
  const lines = content.split('\n');
  const result: string[] = [];

  for (const line of lines) {
    const trimmed = line.trim();

    // Skip empty lines and code blocks
    if (!trimmed || trimmed.startsWith('```')) {
      result.push(line);
      continue;
    }

    // Check if line contains a table delimiter pattern like |----| or |:----:|
    if (trimmed.includes('|---') || trimmed.includes('|:--')) {
      // This line likely contains header + delimiter + data all on one line
      // Split by | but keep the delimiters
      const parts = trimmed.split('|').filter(p => p !== '');

      if (parts.length >= 3) {
        // Find the delimiter part (contains only - or :)
        const partsWithDelim: string[] = [];
        let currentPart = '';

        for (const part of parts) {
          const p = part.trim();

          if (p.match(/^[:\-\s]+$/)) {
            // This is a delimiter
            if (currentPart) {
              partsWithDelim.push(currentPart.trim());
              currentPart = '';
            }
            partsWithDelim.push(p);
          } else {
            currentPart += (currentPart ? '|' : '') + p;
          }
        }
        if (currentPart) {
          partsWithDelim.push(currentPart.trim());
        }

        // If we have at least 3 parts (header, delimiter, data), split into lines
        if (partsWithDelim.length >= 3) {
          // More precise: find the index of the delimiter
          let headerEnd = -1;
          let delimiterIdx = -1;

          for (let i = 0; i < parts.length; i++) {
            const p = parts[i].trim();
            if (p.match(/^[:\-\s]+$/)) {
              delimiterIdx = i;
              break;
            }
          }

          if (delimiterIdx > 0) {
            // Build header row
            const headerParts = parts.slice(0, delimiterIdx);
            if (headerParts.length > 0) {
              result.push('| ' + headerParts.join(' | ') + ' |');
            }

            // Build delimiter row
            const delimParts = parts.slice(delimiterIdx, delimiterIdx + 1);
            result.push('| ' + delimParts.join(' | ').replace(/:/g, '-') + ' |');

            // Build data row
            const dataParts = parts.slice(delimiterIdx + 1);
            if (dataParts.length > 0) {
              result.push('| ' + dataParts.join(' | ') + ' |');
            }
            continue;
          }
        }
      }
    }

    // Default: keep line as is
    result.push(line);
  }

  return result.join('\n');
}


interface MessageBubbleProps {
  message: Message;
  isGrouped?: boolean;
}

const AGENT_COLORS: Record<string, string> = {
  orchestrator: '#6366f1',
  scoping: '#64748b',
  market_strategy: '#ec4899',
  compliance: '#f97316',
  adtimabox: '#10b981',
  content_generator: '#06b6d4',
  account: '#f59e0b',
  design: '#3b82f6',
  tech_solution: '#8b5cf6',
  system: '#6b7280',
};

const AGENT_NAMES: Record<string, string> = {
  orchestrator: 'Orchestrator',
  scoping: 'Scoping',
  market_strategy: 'Strategy',
  compliance: 'Compliance',
  adtimabox: 'Product Expert',
  content_generator: 'Content Generator',
  account: 'Budget & Pricing',
  design: 'Slide Designer',
  tech_solution: 'Tech Solution',
  system: 'System',
};

export function MessageBubble({ message, isGrouped = false }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';
  const agentName = message.agent ? AGENT_NAMES[message.agent] || message.agent : null;
  const agentColor = message.agent ? AGENT_COLORS[message.agent] || '#6b7280' : undefined;

  const showHeader = !isGrouped && !isUser && !isSystem && agentName;
  const isAI = !isUser && !isSystem;

  // System messages render as a thin centered divider
  if (isSystem) {
    return (
      <div className="flex items-center gap-3 my-4">
        <div className="flex-1 h-px bg-border" />
        <span className="text-[11px] text-text-muted whitespace-nowrap">{message.content}</span>
        <div className="flex-1 h-px bg-border" />
      </div>
    );
  }

  // User messages: show in chat bubble (like now)
  if (isUser) {
    return (
      <div className={`flex gap-2 sm:gap-3 ${isGrouped ? 'mt-1' : 'mt-3 sm:mt-4'}`}>
        {/* Avatar */}
        {!isGrouped && (
          <div className="shrink-0 w-7 h-7 sm:w-8 sm:h-8 rounded-full flex items-center justify-center bg-[#e5e7eb] text-[#374151]">
            <User size={14} className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
          </div>
        )}

        {/* Spacer for grouped user messages */}
        {isGrouped && <div className="w-7 sm:w-8" />}

        {/* Message content */}
        <div className="flex flex-col items-end" style={{ maxWidth: '85%' }}>
          {/* Message bubble */}
          <div
            className="px-3 sm:px-4 py-2 sm:py-3 wrap-break-word"
            style={{
              backgroundColor: 'var(--color-accent)',
              color: '#ffffff',
              borderRadius: '1rem 1rem 0.25rem 1rem',
              boxShadow: 'var(--shadow-sm)',
              fontSize: '13px',
              lineHeight: 1.6,
            }}
          >
            <p className="whitespace-pre-wrap" style={{ margin: 0 }}>{message.content}</p>
          </div>

          {/* Timestamp */}
          {!isGrouped && (
            <span className="text-[10px] sm:text-xs text-gray-400 mt-1 mr-1">
              {new Date(message.timestamp).toLocaleTimeString()}
            </span>
          )}
        </div>
      </div>
    );
  }

  // AI messages: render without bubble (document-style like ChatGPT/Claude)
  return (
    <div className={`flex gap-2 sm:gap-3 ${isGrouped ? 'mt-1' : 'mt-3 sm:mt-4'}`}>
      {/* Avatar */}
      {!isGrouped && (
        <div
          className="shrink-0 w-7 h-7 sm:w-8 sm:h-8 rounded-full flex items-center justify-center"
          style={{
            backgroundColor: agentColor || '#6366f1',
            color: '#ffffff',
          }}
        >
          {message.agent === 'orchestrator' ? (
            <Sparkles size={14} className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
          ) : (
            <Bot size={14} className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
          )}
        </div>
      )}

      {/* Spacer for grouped AI messages */}
      {isGrouped && <div className="w-7 sm:w-8" />}

      {/* Message content - document style (no bubble) */}
      <div className="flex flex-col items-start flex-1" style={{ maxWidth: '100%' }}>
        {/* Agent name */}
        {showHeader && (
          <span className="text-[10px] sm:text-xs font-medium mb-1.5 sm:mb-2 ml-1" style={{ color: agentColor }}>
            {agentName}
          </span>
        )}

        {/* Check if this is a brief document - render custom UI */}
        {isBriefDocument(message.content) ? (
          <BriefDocument content={message.content} />
        ) : (
        <div
          className="w-full"
          style={{
            color: 'var(--color-text)',
            fontSize: '14px',
            lineHeight: 1.7,
          }}
        >
          {/* Preprocess content to fix malformed tables */}
          <ReactMarkdown
            components={{
              p: ({ children }) => <p style={{ margin: '0.5rem 0', lineHeight: 1.7 }}>{children}</p>,
              h1: ({ children }) => (
                <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: '1.5rem 0 0.75rem', color: 'var(--color-text)' }}>
                  {children}
                </h1>
              ),
              h2: ({ children }) => (
                <h2 style={{ fontSize: '1.25rem', fontWeight: 600, margin: '1.25rem 0 0.5rem', color: 'var(--color-text)' }}>
                  {children}
                </h2>
              ),
              h3: ({ children }) => (
                <h3 style={{ fontSize: '1.1rem', fontWeight: 600, margin: '1rem 0 0.5rem', color: 'var(--color-text)' }}>
                  {children}
                </h3>
              ),
              h4: ({ children }) => (
                <h4 style={{ fontSize: '1rem', fontWeight: 600, margin: '1rem 0 0.5rem', color: 'var(--color-text)' }}>
                  {children}
                </h4>
              ),
              ul: ({ children }) => <ul style={{ margin: '0.5rem 0', paddingLeft: '1.5rem', lineHeight: 1.8 }}>{children}</ul>,
              ol: ({ children }) => <ol style={{ margin: '0.5rem 0', paddingLeft: '1.5rem', lineHeight: 1.8 }}>{children}</ol>,
              li: ({ children }) => <li style={{ margin: '0.35rem 0', lineHeight: 1.7 }}>{children}</li>,
              strong: ({ children }) => <strong style={{ fontWeight: 600, color: 'var(--color-text)' }}>{children}</strong>,
              em: ({ children }) => <em style={{ fontStyle: 'italic' }}>{children}</em>,
              a: ({ href, children }) => (
                <a href={href} style={{ color: 'var(--color-accent)', textDecoration: 'underline' }} target="_blank" rel="noopener noreferrer">
                  {children}
                </a>
              ),
              table: ({ children }) => (
                <div className="overflow-x-auto my-5 rounded-xl border-0 shadow-lg" style={{ backgroundColor: 'var(--color-surface)' }}>
                  <table style={{ borderCollapse: 'separate', borderSpacing: 0, width: '100%', fontSize: '0.875em' }}>
                    {children}
                  </table>
                </div>
              ),
              thead: ({ children }) => (
                <thead>
                  {children}
                </thead>
              ),
              tbody: ({ children }) => <tbody>{children}</tbody>,
              tr: ({ children }) => (
                <tr>
                  {children}
                </tr>
              ),
              th: ({ children }) => (
                <th style={{
                  padding: '0.875rem 1.25rem',
                  textAlign: 'left',
                  fontWeight: 600,
                  fontSize: '0.75em',
                  color: '#ffffff',
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  backgroundColor: '#4f46e5',
                  borderRadius: '0',
                  whiteSpace: 'nowrap',
                }}>
                  {children}
                </th>
              ),
              td: ({ children }) => (
                <td style={{
                  padding: '0.875rem 1.25rem',
                  fontSize: '0.875em',
                  color: 'var(--color-text)',
                  lineHeight: 1.6,
                  borderBottom: '1px solid var(--color-border)',
                }}>
                  {children}
                </td>
              ),
              code: ({ children, className }) => {
                const isInline = !className;
                if (isInline) {
                  return (
                    <code style={{ backgroundColor: 'var(--color-surface-2)', padding: '0.2rem 0.4rem', borderRadius: '4px', fontSize: '0.85em', fontFamily: 'monospace' }}>
                      {children}
                    </code>
                  );
                }
                return (
                  <code className={className}>
                    {children}
                  </code>
                );
              },
              pre: ({ children }) => (
                <pre style={{ backgroundColor: 'var(--color-surface-2)', padding: '1rem', borderRadius: '8px', overflow: 'auto', fontSize: '0.85em', fontFamily: 'monospace', margin: '1rem 0' }}>
                  {children}
                </pre>
              ),
              hr: () => <hr style={{ border: 'none', borderTop: '1px solid var(--color-border)', margin: '1.5rem 0' }} />,
              blockquote: ({ children }) => (
                <blockquote style={{
                  borderLeft: '4px solid var(--color-accent)',
                  paddingLeft: '1rem',
                  margin: '1rem 0',
                  fontStyle: 'italic',
                  color: 'var(--color-text-muted)',
                  backgroundColor: 'var(--color-surface-2)',
                  padding: '0.75rem 1rem',
                  borderRadius: '0 8px 8px 0',
                }}>
                  {children}
                </blockquote>
              ),
            }}
          >
            {fixMissingDelimiterTables(message.content)}
          </ReactMarkdown>
        </div>
        )}

        {/* Timestamp */}
        {!isGrouped && (
          <span className="text-xs text-gray-400 mt-3 ml-1">
            {new Date(message.timestamp).toLocaleTimeString()}
          </span>
        )}
      </div>
    </div>
  );
}
           