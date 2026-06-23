/**
 * Message Bubble Component
 * ========================
 * Renders individual chat messages with agent avatars.
 * Uses Tailwind CSS for styling.
 */

import React, { useMemo, useRef, useEffect, useState } from 'react';
import type { Message } from '../lib/types';
import { Bot, User, Sparkles, FileText, Users, Target, Clock, TrendingUp } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { tryRenderAsciiChart } from './AsciiChartRenderer';

// Mermaid diagram renderer — dynamically imports mermaid to avoid SSR issues
let _mermaidIdCounter = 0;

/** Fix common LLM-generated mermaid issues before handing to the renderer. */
function sanitizeMermaid(raw: string): string {
  let s = raw.trim();
  // Normalize line endings
  s = s.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
  // Normalize curly/smart quotes to straight quotes
  s = s.replace(/[""„‟]/g, '"');
  // Replace literal \n escape sequences inside labels with a space.
  s = s.replace(/\\n/g, ' ');
  // Strip markdown bold/italic inside labels
  s = s.replace(/\*\*([^*\n]+)\*\*/g, '$1');
  // Remove straight double-quotes inside square-bracket node labels.
  // e.g. A[say "hello"] confuses the mermaid parser in v11; becomes A[say hello]
  s = s.replace(/\[([^\[\]\n]*)\]/g, (_m, inner) => '[' + inner.replace(/"/g, '') + ']');
  return s;
}

/** Strip emoji from box-drawing ASCII art so column alignment is preserved.
 * Terminal emoji = 2 columns wide; browsers render them narrower → replace with 2 spaces. */
function sanitizeBoxArt(content: string): string {
  if (!/[┌┐└┘│─├┤┬┴┼═╔╗╚╝║]/.test(content)) return content;
  // Surrogate pairs = supplementary plane chars (emoji U+1F000+); BMP misc symbols U+2600-U+27BF
  return content
    .replace(/[\uD800-\uDBFF][\uDC00-\uDFFF]/g, '  ')
    .replace(/[☀-➿]/g, '  ');
}

/** Parse inline markdown (`**bold**`, `*italic*`, `` `code` ``) inside a plain string. */
function renderInlineMarkdown(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*\n]+\*\*|\*[^*\n]+\*|`[^`\n]+`)/);
  if (parts.length === 1) return text;
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**'))
      return <strong key={i} style={{ fontWeight: 700 }}>{part.slice(2, -2)}</strong>;
    if (part.startsWith('*') && part.endsWith('*'))
      return <em key={i}>{part.slice(1, -1)}</em>;
    if (part.startsWith('`') && part.endsWith('`'))
      return <code key={i} style={{ backgroundColor: 'var(--color-surface-2)', padding: '0.1rem 0.3rem', borderRadius: '3px', fontSize: '0.9em' }}>{part.slice(1, -1)}</code>;
    return part;
  });
}

function useDarkMode(): boolean {
  const [isDark, setIsDark] = useState(
    () => typeof document !== 'undefined' && document.documentElement.classList.contains('dark')
  );
  useEffect(() => {
    const observer = new MutationObserver(() => {
      setIsDark(document.documentElement.classList.contains('dark'));
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);
  return isDark;
}

function MermaidDiagram({ chart }: { chart: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const idRef = useRef(`mermaid-diag-${++_mermaidIdCounter}`);
  const isDarkMode = useDarkMode();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const cleaned = sanitizeMermaid(chart);
      try {
        const mermaid = (await import('mermaid')).default;
        mermaid.initialize({
          startOnLoad: false,
          theme: isDarkMode ? 'dark' : 'default',
          securityLevel: 'loose',
          fontSize: 14,
          flowchart: { useMaxWidth: true, diagramPadding: 8 },
          gantt: { fontSize: 13, barHeight: 28, barGap: 8, topPadding: 50, leftPadding: 140 },
        });

        // Parse first so we can distinguish syntax problems from render/runtime problems.
        await mermaid.parse(cleaned);

        const { svg } = await mermaid.render(idRef.current, cleaned);
        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML = svg;
          const svgEl = containerRef.current.querySelector('svg');
          if (svgEl) {
            svgEl.style.background = 'transparent';
            const isGantt = cleaned.trim().toLowerCase().startsWith('gantt');
            if (isGantt) {
              // Gantt charts need full width to be readable
              svgEl.style.width = '100%';
              svgEl.style.height = 'auto';
              svgEl.style.maxWidth = 'none';
            } else {
              // Flowcharts/sequence diagrams: natural size, never stretch beyond container
              svgEl.removeAttribute('width');
              svgEl.removeAttribute('height');
              svgEl.style.maxWidth = '100%';
              svgEl.style.height = 'auto';
              svgEl.style.display = 'block';
              svgEl.style.margin = '0 auto';
            }
          }
        }
      } catch (error) {
        console.error('[MermaidDiagram] render failed', { error, cleaned });
        if (!cancelled && containerRef.current) {
          const escaped = cleaned.replace(/</g, '&lt;');
          containerRef.current.innerHTML = `
            <div style="font-size:0.85em;margin:8px 0;padding:8px;border:1px solid var(--color-border);border-radius:8px;background:var(--color-surface-2);color:var(--color-text)">
              <div style="font-weight:600;margin-bottom:4px">Mermaid render failed</div>
              <pre style="margin:0;overflow:auto;white-space:pre-wrap;text-align:left">${escaped}</pre>
            </div>`;
        }
      }
    })();
    return () => { cancelled = true; };
  }, [chart, isDarkMode]);

  return (
    <div
      ref={containerRef}
      className="mermaid-diagram my-4 flex justify-center overflow-x-auto"
      style={{ minHeight: '80px', background: 'var(--color-surface-2)', borderRadius: '8px', padding: '8px' }}
    />
  );
}

// Detect and fix tables that have header + data but NO delimiter row
// Example: "| A | B |" + "| X | Y |" (missing |---|---|)
// Skips content inside fenced code blocks (``` ... ```)
function fixMissingDelimiterTables(content: string): string {
  const lines = content.split('\n');
  const result: string[] = [];
  let addedDelimiterThisBlock = false;
  let inCodeBlock = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    // Track fenced code blocks
    if (trimmed.startsWith('```')) {
      inCodeBlock = !inCodeBlock;
      result.push(line);
      addedDelimiterThisBlock = false;
      continue;
    }

    // Never touch content inside code blocks
    if (inCodeBlock) {
      result.push(line);
      continue;
    }

    const pipeCount = (trimmed.match(/\|/g) || []).length;

    // Check if this is a table row (has 3+ pipes)
    if (pipeCount < 3) {
      result.push(line);
      addedDelimiterThisBlock = false;
      continue;
    }

    // Check if previous line was also a table row (no delimiter between them)
    if (i > 0 && !addedDelimiterThisBlock) {
      const prevLine = lines[i - 1].trim();
      const prevPipeCount = (prevLine.match(/\|/g) || []).length;

      // Previous line is table row, current is table row, no delimiter between
      if (prevPipeCount >= 3 && !prevLine.includes('---')) {
        const cols = pipeCount - 1;
        const delimiter = '| ' + Array(cols).fill('---').join(' | ') + ' |';
        result.push(delimiter);
        addedDelimiterThisBlock = true;
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

type ContentBlock =
  | { kind: 'markdown'; content: string }
  | { kind: 'table'; headers: string[]; rows: string[][] };

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

// Format structured table output from agent into proper markdown
// Detects patterns with numbered sections, headers, and content
function formatStructuredAgentTables(content: string): string {
  const lines = content.split('\n');
  const result: string[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    // Look for section headers like "1.1. Section Name" followed by table
    const sectionMatch = trimmed.match(/^(\d+(?:\.\d+)?)\.\s+([^:]+)(?::\s*)?$/);
    if (sectionMatch && i + 1 < lines.length) {
      const nextLine = lines[i + 1].trim();
      // Check if next few lines look like a table structure
      if (nextLine.includes('|') && nextLine.includes('-')) {
        // This is a section header before a table - add it and continue
        result.push(line);
        i++;
        continue;
      }
    }

    result.push(line);
    i++;
  }

  return result.join('\n');
}

function splitTableRow(line: string): string[] {
  const trimmed = line.trim();
  const raw = trimmed.startsWith('|') ? trimmed.slice(1) : trimmed;
  const parts = raw.endsWith('|') ? raw.slice(0, -1).split('|') : raw.split('|');
  return parts.map(cell => cell.trim());
}

function isDelimiterCells(cells: string[]): boolean {
  return cells.length > 0 && cells.every(cell => cell === '' || /^[:\-]+$/.test(cell));
}

function isTableCandidateLine(line: string): boolean {
  const trimmed = line.trim();
  return trimmed.includes('|') && !trimmed.startsWith('```');
}

function parseTableBlock(lines: string[]): { headers: string[]; rows: string[][] } | null {
  const rows: string[][] = [];

  for (const line of lines) {
    if (/^[┌┐└┘├┤┬┴┼─═\s]+$/.test(line.trim())) {
      continue;
    }
    const cells = splitTableRow(line);
    if (cells.length < 2) return null;

    if (isDelimiterCells(cells)) {
      continue;
    }

    rows.push(cells);
  }

  if (rows.length < 2) return null;

  const headers = rows[0];
  const dataRows = rows.slice(1);
  const width = Math.max(headers.length, ...dataRows.map(row => row.length));

  const normalizeRow = (row: string[]) => {
    const copy = row.slice();
    while (copy.length < width) copy.push('');
    return copy;
  };

  return {
    headers: normalizeRow(headers),
    rows: dataRows.map(normalizeRow),
  };
}

function tryRenderPipeTable(content: string): React.ReactElement | null {
  const lines = content
    .split('\n')
    .map(line => line.trim())
    .filter(line => line.length > 0);

  const candidateLines = lines.filter(line => isTableCandidateLine(line) || /^[┌┐└┘├┤┬┴┼─═\s]+$/.test(line));
  if (candidateLines.length < 2) {
    return null;
  }

  const parsed = parseTableBlock(candidateLines);
  if (!parsed) {
    return null;
  }

  return <TableBlock headers={parsed.headers} rows={parsed.rows} />;
}

function splitContentIntoBlocks(content: string): ContentBlock[] {
  const normalized = fixMalformedTables(formatStructuredAgentTables(content));
  const lines = normalized.split('\n');
  const blocks: ContentBlock[] = [];
  const proseBuffer: string[] = [];
  let inCodeBlock = false;

  const flushProse = () => {
    if (proseBuffer.length === 0) return;
    blocks.push({ kind: 'markdown', content: proseBuffer.join('\n') });
    proseBuffer.length = 0;
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    if (trimmed.startsWith('```')) {
      inCodeBlock = !inCodeBlock;
      proseBuffer.push(line);
      continue;
    }

    if (inCodeBlock) {
      proseBuffer.push(line);
      continue;
    }

    if (!trimmed) {
      proseBuffer.push(line);
      continue;
    }

    if (isTableCandidateLine(line)) {
      const tableLines = [line];
      let j = i + 1;

      while (j < lines.length && isTableCandidateLine(lines[j])) {
        tableLines.push(lines[j]);
        j++;
      }

      const parsed = parseTableBlock(tableLines);
      if (parsed) {
        flushProse();
        blocks.push({ kind: 'table', headers: parsed.headers, rows: parsed.rows });
        i = j - 1;
        continue;
      }
    }

    proseBuffer.push(line);
  }

  flushProse();
  return blocks;
}

function TableBlock({
  headers,
  rows,
}: {
  headers: string[];
  rows: string[][];
}) {
  return (
    <div className="overflow-x-auto my-5 rounded-xl border border-border shadow-md" style={{ backgroundColor: 'var(--color-surface)' }}>
      <table className="agent-output-table" style={{ borderCollapse: 'collapse', width: '100%', fontSize: '0.875em', tableLayout: 'fixed' }}>
        <thead>
          <tr>
            {headers.map((header, index) => (
              <th
                key={index}
                style={{
                  padding: '1rem 1.25rem',
                  textAlign: 'left',
                  fontWeight: 700,
                  fontSize: '0.75em',
                  color: '#ffffff',
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                  backgroundColor: 'var(--color-accent)',
                  borderBottom: '3px solid color-mix(in srgb, var(--color-accent) 85%, black)',
                  whiteSpace: 'normal',
                  wordWrap: 'break-word',
                }}
              >
                {renderInlineMarkdown(header)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) => (
                <td
                  key={cellIndex}
                  style={{
                    padding: '1rem 1.25rem',
                    fontSize: '0.875em',
                    color: 'var(--color-text)',
                    lineHeight: 1.6,
                    borderBottom: '1px solid var(--color-border)',
                    wordWrap: 'break-word',
                    maxWidth: '500px',
                  }}
                >
                  {renderInlineMarkdown(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Parse a single-line concatenated table like:
// "| H1 | H2 | H3 | | --- | --- | --- | |---|---|---| | D1 | D2 | D3 | | D4 | | D5 |"
// into proper multi-line markdown table rows, preserving empty cells.
function tryFixConcatenatedTable(line: string): string[] | null {
  // Quick reject: no "| |" row boundary means nothing to split
  if (!/\|\s*\|/.test(line)) return null;

  // Split by | to get all raw cells (preserves empty cells)
  const raw = line.split('|');
  if (raw[0].trim() === '') raw.shift();
  if (raw.length > 0 && raw[raw.length - 1].trim() === '') raw.pop();
  const cells = raw.map(c => c.trim());
  if (cells.length < 4) return null;

  // A cell is a delimiter (only dashes/colons, non-empty)
  const isDelim = (c: string) => c.length > 0 && /^[:\-]+$/.test(c);

  // Determine N: count consecutive non-delim, non-empty cells at the start
  let N = 0;
  for (const c of cells) {
    if (isDelim(c) || c === '') break;
    N++;
  }
  if (N < 1) return null;

  // Verify there's a delimiter region after the header
  const sepIdx = cells[N] === '' ? N + 1 : N; // skip optional row-boundary empty
  if (sepIdx >= cells.length || !isDelim(cells[sepIdx])) return null;

  // Build output rows
  const rows: string[] = [];

  // Header row
  rows.push('| ' + cells.slice(0, N).join(' | ') + ' |');
  // Normalized delimiter
  rows.push('| ' + Array(N).fill('---').join(' | ') + ' |');

  // Skip all delimiter and separator cells to find first data cell
  let i = N;
  while (i < cells.length && (isDelim(cells[i]) || cells[i] === '')) i++;

  // Parse data rows: collect exactly N cells per row
  while (i < cells.length) {
    const rowCells: string[] = [];
    for (let j = 0; j < N && i < cells.length; j++, i++) {
      rowCells.push(cells[i]); // include empty cells (they're valid data)
    }
    // Skip trailing row-separator empty cells between rows
    while (i < cells.length && cells[i] === '') i++;

    if (rowCells.some(c => c !== '')) {
      while (rowCells.length < N) rowCells.push('');
      rows.push('| ' + rowCells.join(' | ') + ' |');
    }
  }

  return rows.length > 2 ? rows : null;
}

// Fix malformed markdown tables that are concatenated onto a single line.
// Also tracks fenced code blocks and skips content inside them.
function fixMalformedTables(content: string): string {
  const lines = content.split('\n');
  const result: string[] = [];
  let inCodeBlock = false;

  for (const line of lines) {
    const trimmed = line.trim();

    if (trimmed.startsWith('```')) {
      inCodeBlock = !inCodeBlock;
      result.push(line);
      continue;
    }

    if (!trimmed || inCodeBlock) {
      result.push(line);
      continue;
    }

    if (trimmed.startsWith('|')) {
      const fixed = tryFixConcatenatedTable(trimmed);
      if (fixed && fixed.length > 2) {
        result.push(...fixed);
        continue;
      }
    }

    result.push(line);
  }

  return result.join('\n');
}


interface MessageBubbleProps {
  message: Message;
  isGrouped?: boolean;
  isStreaming?: boolean;
}

const AGENT_COLORS: Record<string, string> = {
  central_agent: '#6366f1',
  market_strategy: '#ec4899',
  compliance: '#f97316',
  product_solution: '#10b981',
  design: '#3b82f6',
  client_simulator: '#06b6d4',
  proposal_assembler: '#8b5cf6',
  system: '#6b7280',
};

const AGENT_NAMES: Record<string, string> = {
  central_agent: 'Sales AI',
  market_strategy: 'Strategy',
  compliance: 'Compliance',
  product_solution: 'Product Solution',
  design: 'Slide Designer',
  client_simulator: 'Client Simulator',
  proposal_assembler: 'Proposal Assembler',
  system: 'System',
};

export function MessageBubble({ message, isGrouped = false, isStreaming = false }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';
  const agentName = message.agent ? AGENT_NAMES[message.agent] || message.agent : null;
  const agentColor = message.agent ? AGENT_COLORS[message.agent] || '#6b7280' : undefined;

  const showHeader = !isGrouped && !isUser && !isSystem && agentName;
  const isAI = !isUser && !isSystem;
  const processedContent = fixMissingDelimiterTables(formatStructuredAgentTables(fixMalformedTables(message.content)));
  const contentBlocks = useMemo(() => splitContentIntoBlocks(processedContent), [processedContent]);
  const markdownComponents: any = {
    p: ({ children }: { children: React.ReactNode }) => <p style={{ margin: '0.5rem 0', lineHeight: 1.7 }}>{children}</p>,
    h1: ({ children }: { children: React.ReactNode }) => (
      <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: '1.5rem 0 0.75rem', color: 'var(--color-text)' }}>
        {children}
      </h1>
    ),
    h2: ({ children }: { children: React.ReactNode }) => (
      <h2 style={{ fontSize: '1.25rem', fontWeight: 600, margin: '1.25rem 0 0.5rem', color: 'var(--color-text)' }}>
        {children}
      </h2>
    ),
    h3: ({ children }: { children: React.ReactNode }) => (
      <h3 style={{ fontSize: '1.1rem', fontWeight: 600, margin: '1rem 0 0.5rem', color: 'var(--color-text)' }}>
        {children}
      </h3>
    ),
    h4: ({ children }: { children: React.ReactNode }) => (
      <h4 style={{ fontSize: '1rem', fontWeight: 600, margin: '1rem 0 0.5rem', color: 'var(--color-text)' }}>
        {children}
      </h4>
    ),
    ul: ({ children }: { children: React.ReactNode }) => <ul style={{ margin: '0.5rem 0', paddingLeft: '1.5rem', lineHeight: 1.8 }}>{children}</ul>,
    ol: ({ children }: { children: React.ReactNode }) => <ol style={{ margin: '0.5rem 0', paddingLeft: '1.5rem', lineHeight: 1.8 }}>{children}</ol>,
    li: ({ children }: { children: React.ReactNode }) => <li style={{ margin: '0.35rem 0', lineHeight: 1.7 }}>{children}</li>,
    strong: ({ children }: { children: React.ReactNode }) => <strong style={{ fontWeight: 600, color: 'var(--color-text)' }}>{children}</strong>,
    em: ({ children }: { children: React.ReactNode }) => <em style={{ fontStyle: 'italic' }}>{children}</em>,
    a: ({ href, children }: { href?: string; children: React.ReactNode }) => (
      <a href={href} style={{ color: 'var(--color-accent)', textDecoration: 'underline' }} target="_blank" rel="noopener noreferrer">
        {children}
      </a>
    ),
    table: ({ children }: { children: React.ReactNode }) => (
      <div className="overflow-x-auto my-5 rounded-xl border border-border shadow-md" style={{ backgroundColor: 'var(--color-surface)' }}>
        <style>{`
          .agent-output-table tbody tr:nth-child(odd) {
            background-color: color-mix(in srgb, var(--color-accent) 4%, transparent);
          }
          .agent-output-table tbody tr:hover {
            background-color: color-mix(in srgb, var(--color-accent) 8%, transparent);
            transition: background-color 0.2s;
          }
        `}</style>
        <table className="agent-output-table" style={{ borderCollapse: 'collapse', width: '100%', fontSize: '0.875em', tableLayout: 'fixed' }}>
          {children}
        </table>
      </div>
    ),
    thead: ({ children }: { children: React.ReactNode }) => <thead>{children}</thead>,
    tbody: ({ children }: { children: React.ReactNode }) => <tbody>{children}</tbody>,
    tr: ({ children }: { children: React.ReactNode }) => <tr>{children}</tr>,
    th: ({ children }: { children: React.ReactNode }) => (
      <th style={{
        padding: '1rem 1.25rem',
        textAlign: 'left',
        fontWeight: 700,
        fontSize: '0.75em',
        color: '#ffffff',
        textTransform: 'uppercase',
        letterSpacing: '0.08em',
        backgroundColor: 'var(--color-accent)',
        borderBottom: '3px solid color-mix(in srgb, var(--color-accent) 85%, black)',
        whiteSpace: 'normal',
        wordWrap: 'break-word',
      }}>
        {children}
      </th>
    ),
    td: ({ children }: { children: React.ReactNode }) => (
      <td style={{
        padding: '1rem 1.25rem',
        fontSize: '0.875em',
        color: 'var(--color-text)',
        lineHeight: 1.6,
        borderBottom: '1px solid var(--color-border)',
        wordWrap: 'break-word',
        maxWidth: '500px',
      }}>
        {children}
      </td>
    ),
    code: ({ children, className }: { children: React.ReactNode; className?: string }) => {
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
    pre: ({ children }: { children: React.ReactNode }) => {
      const child = React.Children.toArray(children)[0];
      if (React.isValidElement(child)) {
        const el = child as React.ReactElement<{ className?: string; children?: React.ReactNode }>;
        const rawContent = String(el.props.children ?? '').replace(/\n$/, '');

        // Mermaid diagrams
        if (el.props.className === 'language-mermaid') {
          if (isStreaming) {
            return (
              <pre style={{ backgroundColor: 'var(--color-surface-2)', padding: '1rem', borderRadius: '8px', overflow: 'auto', fontSize: '0.85em', fontFamily: 'monospace', margin: '1rem 0', whiteSpace: 'pre', overflowX: 'auto' }}>
                <code>{rawContent}</code>
              </pre>
            );
          }
          return <MermaidDiagram chart={rawContent} />;
        }

        // ASCII charts (bar chart, timeline) — skip during streaming to avoid flicker
        if (!isStreaming && !el.props.className) {
          const chart = tryRenderAsciiChart(rawContent);
          if (chart) return chart;
          const table = tryRenderPipeTable(rawContent);
          if (table) return table;
        }

        // Box-drawing ASCII art: strip emoji to fix column alignment.
        if (!el.props.className) {
          const sanitized = sanitizeBoxArt(rawContent);
          if (sanitized !== rawContent) {
            return (
              <pre style={{ backgroundColor: 'var(--color-surface-2)', padding: '1rem', borderRadius: '8px', overflowX: 'auto', fontSize: '0.85em', fontFamily: 'monospace', margin: '1rem 0', whiteSpace: 'pre' }}>
                <code>{sanitized}</code>
              </pre>
            );
          }
        }
      }
      return (
        <pre style={{ backgroundColor: 'var(--color-surface-2)', padding: '1rem', borderRadius: '8px', overflowX: 'auto', fontSize: '0.85em', fontFamily: 'monospace', margin: '1rem 0', whiteSpace: 'pre' }}>
          {children}
        </pre>
      );
    },
    hr: () => <hr style={{ border: 'none', borderTop: '1px solid var(--color-border)', margin: '1.5rem 0' }} />,
    blockquote: ({ children }: { children: React.ReactNode }) => (
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
  };

  // System messages render as a thin centered divider
  if (isSystem) {
    return (
      <div className="flex items-center gap-3 my-4">
        <div className="flex-1 h-px bg-border" />
        <span className="text-[13px] text-text-muted whitespace-nowrap">{message.content}</span>
        <div className="flex-1 h-px bg-border" />
      </div>
    );
  }

  // User messages: show in chat bubble (like now)
  if (isUser) {
    return (
      <div className={`flex w-full flex-row-reverse gap-2 sm:gap-3 ${isGrouped ? 'mt-1' : 'mt-3 sm:mt-4'}`}>
        {/* Avatar */}
        {!isGrouped && (
          <div className="shrink-0 w-8 h-8 sm:w-10 sm:h-10 rounded-full flex items-center justify-center bg-border text-[#374151]">
            <User size={16} className="w-4 h-4 sm:w-5 sm:h-5" />
          </div>
        )}

        {/* Spacer for grouped user messages */}
        {isGrouped && <div className="w-8 sm:w-10" />}

        {/* Message content */}
        <div className="ml-auto flex flex-col items-end" style={{ maxWidth: '85%' }}>
          {/* Message bubble */}
          <div
            className="px-3 sm:px-4 py-2 sm:py-3 wrap-break-word"
            style={{
              backgroundColor: 'var(--color-accent)',
              color: '#ffffff',
              borderRadius: '1rem 1rem 0.25rem 1rem',
              boxShadow: 'var(--shadow-sm)',
              fontSize: '15px',
              lineHeight: 1.6,
            }}
          >
            <p className="whitespace-pre-wrap" style={{ margin: 0 }}>{message.content}</p>
          </div>

          {/* Timestamp */}
          {!isGrouped && (
            <span className="text-[12px] sm:text-sm text-gray-400 mt-1 mr-1">
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
          {message.agent === 'central_agent' ? (
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
          <span className="text-[12px] sm:text-sm font-medium mb-1.5 sm:mb-2 ml-1" style={{ color: agentColor }}>
            {agentName}
          </span>
        )}

        <div
          className="w-full"
          style={{
            color: 'var(--color-text)',
            fontSize: '16px',
            lineHeight: 1.7,
          }}
        >
          {contentBlocks.map((block, index) => {
            if (block.kind === 'table') {
              return <TableBlock key={`table-${index}`} headers={block.headers} rows={block.rows} />;
            }

            return (
              <ReactMarkdown key={`markdown-${index}`} components={markdownComponents} remarkPlugins={[remarkGfm]}>
                {block.content}
              </ReactMarkdown>
            );
          })}
        </div>

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
           
