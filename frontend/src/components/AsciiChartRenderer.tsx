'use client';
/**
 * AsciiChartRenderer
 * ==================
 * Detects and renders ASCII bar-charts and timeline/Gantt diagrams
 * produced by the AI agent (Unicode box-drawing + block chars) into
 * proper CSS-based visualizations.
 *
 * Supports:
 *  - Budget / percentage bar charts  (█ ░ + % lines inside a ┌─┐ box)
 *  - Timeline / Gantt grids          (week columns with ─── separators)
 */

import React from 'react';

// ─── Color palette ────────────────────────────────────────────────────────────

const PALETTE = [
  { solid: '#4f46e5', light: '#e0e7ff', text: '#4338ca' }, // indigo
  { solid: '#7c3aed', light: '#ede9fe', text: '#6d28d9' }, // violet
  { solid: '#0891b2', light: '#cffafe', text: '#0e7490' }, // cyan
  { solid: '#059669', light: '#d1fae5', text: '#047857' }, // emerald
  { solid: '#d97706', light: '#fef3c7', text: '#b45309' }, // amber
  { solid: '#dc2626', light: '#fee2e2', text: '#b91c1c' }, // red
];

// ─── Types ────────────────────────────────────────────────────────────────────

interface BarItem {
  pct: number;
  label: string;
  detail: string;
}

interface TimelineColumn {
  header: string;
  active: boolean;
  phase: string;
  tasks: string[];
}

interface InfoLine {
  type: 'heading' | 'bullet' | 'checkbox' | 'text' | 'spacer';
  text: string;
}

// ─── Parsers ──────────────────────────────────────────────────────────────────

/** Return true if the content looks like a budget/bar chart. */
function isBarChart(content: string): boolean {
  const lines = content.split('\n');
  // Only count lines where NN% LEADS the content (after stripping box borders) — not inline prose like "giảm giá 20-50%"
  const leadingPctLines = lines.filter(l => {
    const inner = l.replace(/^[│┌└├─═\s]+/, '').trim();
    return /^\d{1,3}%\s+\S/.test(inner);
  }).length;
  const boxLines = lines.filter(l => l.includes('│') || l.includes('┌') || l.includes('└')).length;
  return leadingPctLines >= 2 && (content.includes('█') || boxLines >= 3);
}

/** Return true if the content looks like a timeline/Gantt. */
function isTimeline(content: string): boolean {
  return /─{5}/.test(content) && (content.includes('Tuần') || content.includes('Week') || content.includes('Phase') || content.includes('Giai đoạn'));
}

/** Return true if the content looks like a structured info/wireframe box (│ border + ═ separator). */
function isInfoBox(content: string): boolean {
  const hasBox = content.includes('│') && (content.includes('┌') || content.includes('└'));
  // Accept either double-line ══ or cross-bar ├──┤ as the title separator
  const hasSep = /═{3,}/.test(content) || (content.includes('├') && content.includes('┤'));
  // Bar charts have lines that START with "NN% label" after stripping box borders.
  const chartPctLines = content.split('\n').filter(l => {
    const inner = l.replace(/^[│┌└├─═\s]+/, '').trim();
    return /^\d{1,3}%\s+\S/.test(inner);
  }).length;

  const nonEmptyLines = content.split('\n').filter(l => l.trim());
  // Complex flow diagrams / user journeys are long — simple info boxes are short
  if (nonEmptyLines.length > 25) return false;
  // Multi-column layouts have multiple ┌ on the same line (e.g. 3-box row in a flow)
  if (nonEmptyLines.some(l => (l.match(/┌/g) || []).length > 1)) return false;

  return hasBox && hasSep && chartPctLines < 2;
}

function isEmojiLead(s: string): boolean {
  const cp = s.codePointAt(0) ?? 0;
  // Misc Symbols (⚡🎮), Dingbats (✓✗), and all Emoji blocks (U+1F000+)
  return (cp >= 0x2600 && cp <= 0x27BF) || cp >= 0x1F000;
}

function parseInfoBox(content: string): { title: string; lines: InfoLine[] } | null {
  const raw = content.split('\n');

  // Strip box-drawing border chars from each side, then trim
  const stripped = raw.map(l =>
    l.replace(/^[│┌└├┼╠╟╞─═┐┘]+/, '').replace(/[│┤┐┘─═╡╢╣]+$/, '').trim()
  );

  // Drop pure-border lines (only box-drawing chars remain after strip)
  const bodyLines = stripped.filter(l => l && !/^[═─┌└┤├┐┘╠╡]+$/.test(l));
  if (bodyLines.length < 2) return null;

  // Title = first content line; separator may appear right after as ══
  let title = '';
  let startIdx = 0;
  for (let i = 0; i < bodyLines.length; i++) {
    if (/═{3,}/.test(bodyLines[i])) { startIdx = i + 1; break; }
    if (!title && /[A-Za-zÀ-ỹ]/.test(bodyLines[i])) {
      title = bodyLines[i];
      startIdx = i + 1;
    }
  }

  const lines: InfoLine[] = [];
  for (const line of bodyLines.slice(startIdx)) {
    if (!line) { lines.push({ type: 'spacer', text: '' }); continue; }
    if (/^[□☐✓✗]/.test(line)) {
      lines.push({ type: 'checkbox', text: line.replace(/^[□☐✓✗]\s*/, '') });
    } else if (/^[•\-*▪◆►]/.test(line)) {
      lines.push({ type: 'bullet', text: line.replace(/^[•\-*▪◆►]\s*/, '') });
    } else if (isEmojiLead(line) || /^[A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝĐ\s]{5,}[:\-]?$/.test(line)) {
      lines.push({ type: 'heading', text: line });
    } else {
      lines.push({ type: 'text', text: line });
    }
  }

  return { title, lines };
}

function parseBarChart(content: string): { title: string; items: BarItem[] } | null {
  const lines = content.split('\n');

  // Title: first │-enclosed line that has letters but no ═, █, ░, ─, ┌, └
  let title = '';
  for (const line of lines) {
    if (line.includes('│') && !/[═█░─┌└]/.test(line)) {
      const inner = line.replace(/[│┌└─]/g, '').trim();
      if (inner.length > 4 && /[A-Za-zÀ-ỹ]/.test(inner)) {
        title = inner;
        break;
      }
    }
  }

  const items: BarItem[] = [];
  for (let i = 0; i < lines.length; i++) {
    // Strip │ borders and trim
    const inner = lines[i].replace(/[│┌└─]/g, '').trim();
    const m = inner.match(/^(\d{1,3})%\s+(.+)$/);
    if (m) {
      const pct = Math.min(100, parseInt(m[1], 10));
      const label = m[2].trim();
      // Look for (detail) in the next 1-3 lines
      let detail = '';
      for (let j = i + 1; j <= i + 3; j++) {
        const next = (lines[j] || '').replace(/[│┌└─]/g, '').trim();
        const dm = next.match(/^\((.+)\)$/);
        if (dm) { detail = dm[1].trim(); break; }
      }
      items.push({ pct, label, detail });
    }
  }

  return items.length > 0 ? { title, items } : null;
}

function parseTimeline(content: string): TimelineColumn[] | null {
  const lines = content.split('\n').filter(l => l.trim());
  if (lines.length < 4) return null;

  // Find separator line (─────)
  const sepIdx = lines.findIndex(l => /─{5}/.test(l));
  if (sepIdx < 1) return null;

  const headerLine = lines[sepIdx - 1];
  // Find bar line (█ or ░)
  const barIdx = lines.findIndex(l => l.includes('█') || l.includes('░'));
  if (barIdx < 0) return null;

  const phaseLine = lines[barIdx + 1] || '';
  const taskLines = lines.slice(barIdx + 2);

  // Split columns by 3+ spaces
  const split = (line: string) => line.split(/\s{3,}/).map(s => s.trim()).filter(Boolean);

  const headers = split(headerLine);
  const phases = split(phaseLine);
  const barCols = split(lines[barIdx]);
  const colCount = Math.max(headers.length, 1);

  const tasksByCols: string[][] = Array.from({ length: colCount }, () => []);
  for (const taskLine of taskLines) {
    const cols = taskLine.split(/\s{3,}/);
    cols.forEach((col, ci) => {
      const task = col.replace(/^[-*•]\s*/, '').trim();
      if (task && ci < colCount) tasksByCols[ci].push(task);
    });
  }

  return headers.map((header, i) => {
    const barContent = barCols[i] || '';
    const filledCount = (barContent.match(/█/g) || []).length;
    return {
      header,
      active: filledCount > 0,
      phase: phases[i] || '',
      tasks: tasksByCols[i] || [],
    };
  });
}

// ─── React components ─────────────────────────────────────────────────────────

function BarChartCard({ title, items }: { title: string; items: BarItem[] }) {
  return (
    <div style={{
      background: 'linear-gradient(135deg, #f8f7ff 0%, #f0f0ff 100%)',
      border: '1px solid #e0e7ff',
      borderRadius: '12px',
      padding: '1.25rem 1.5rem',
      margin: '1rem 0',
    }}>
      {title && (
        <div style={{
          fontSize: '0.875rem',
          fontWeight: 700,
          color: '#1e1b4b',
          marginBottom: '1.25rem',
          paddingBottom: '0.75rem',
          borderBottom: '2px solid #e0e7ff',
          letterSpacing: '0.01em',
        }}>
          {title}
        </div>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>
        {items.map((item, i) => {
          const color = PALETTE[i % PALETTE.length];
          return (
            <div key={i}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '0.3rem' }}>
                <span style={{ fontSize: '0.875rem', fontWeight: 600, color: '#1f2937' }}>{item.label}</span>
                <span style={{ fontSize: '0.875rem', fontWeight: 700, color: color.text, marginLeft: '0.75rem', flexShrink: 0 }}>
                  {item.pct}%
                </span>
              </div>
              <div style={{ background: '#e5e7eb', borderRadius: '100px', height: '10px', overflow: 'hidden' }}>
                <div style={{
                  width: `${item.pct}%`,
                  height: '100%',
                  background: `linear-gradient(90deg, ${color.solid}, ${color.solid}bb)`,
                  borderRadius: '100px',
                }} />
              </div>
              {item.detail && (
                <div style={{ fontSize: '0.775rem', color: '#6b7280', marginTop: '0.3rem' }}>
                  {item.detail}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function TimelineCard({ columns }: { columns: TimelineColumn[] }) {
  return (
    <div style={{
      background: '#f8f7ff',
      border: '1px solid #e0e7ff',
      borderRadius: '12px',
      padding: '1.25rem',
      margin: '1rem 0',
      overflowX: 'auto',
    }}>
      <div style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${columns.length}, minmax(120px, 1fr))`,
        gap: '0.75rem',
      }}>
        {columns.map((col, i) => (
          <div key={i} style={{
            background: col.active
              ? 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)'
              : '#e5e7eb',
            borderRadius: '10px',
            padding: '0.875rem 1rem',
            color: col.active ? '#fff' : '#6b7280',
          }}>
            <div style={{
              fontSize: '0.7rem',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              opacity: 0.75,
              marginBottom: '0.4rem',
            }}>
              {col.header}
            </div>
            {col.phase && (
              <div style={{ fontSize: '0.875rem', fontWeight: 700, marginBottom: '0.5rem', lineHeight: 1.3 }}>
                {col.phase}
              </div>
            )}
            <div style={{ fontSize: '0.775rem', lineHeight: 1.65, opacity: col.active ? 0.9 : 0.65 }}>
              {col.tasks.map((t, j) => (
                <div key={j} style={{ display: 'flex', gap: '0.3rem' }}>
                  <span style={{ flexShrink: 0, opacity: 0.6 }}>•</span>
                  <span>{t}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function InfoBoxCard({ title, lines }: { title: string; lines: InfoLine[] }) {
  return (
    <div style={{
      background: 'linear-gradient(135deg, #f0f4ff 0%, #f8f0ff 100%)',
      border: '1px solid #c7d2fe',
      borderRadius: '12px',
      padding: '1.25rem 1.5rem',
      margin: '1rem 0',
    }}>
      {title && (
        <div style={{
          fontSize: '0.875rem',
          fontWeight: 700,
          color: '#1e1b4b',
          marginBottom: '1rem',
          paddingBottom: '0.6rem',
          borderBottom: '2px solid #c7d2fe',
          letterSpacing: '0.02em',
        }}>
          {title}
        </div>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
        {lines.map((line, i) => {
          if (line.type === 'spacer') return <div key={i} style={{ height: '0.5rem' }} />;
          if (line.type === 'heading') return (
            <div key={i} style={{
              fontSize: '0.85rem',
              fontWeight: 700,
              color: '#4338ca',
              marginTop: '0.6rem',
              marginBottom: '0.2rem',
            }}>
              {line.text}
            </div>
          );
          if (line.type === 'bullet') return (
            <div key={i} style={{ display: 'flex', gap: '0.5rem', fontSize: '0.825rem', color: '#374151', paddingLeft: '0.5rem' }}>
              <span style={{ color: '#6366f1', flexShrink: 0 }}>•</span>
              <span>{line.text}</span>
            </div>
          );
          if (line.type === 'checkbox') return (
            <div key={i} style={{ display: 'flex', gap: '0.6rem', fontSize: '0.825rem', color: '#374151', paddingLeft: '0.5rem', alignItems: 'flex-start' }}>
              <span style={{
                width: '14px', height: '14px', border: '2px solid #6366f1',
                borderRadius: '3px', flexShrink: 0, marginTop: '1px', display: 'inline-block',
              }} />
              <span>{line.text}</span>
            </div>
          );
          return (
            <div key={i} style={{ fontSize: '0.825rem', color: '#4b5563', lineHeight: 1.6 }}>
              {line.text}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Public API ───────────────────────────────────────────────────────────────

/**
 * Try to render `content` as an ASCII chart.
 * Returns a React element if recognized, or null if not a chart.
 */
export function tryRenderAsciiChart(content: string): React.ReactElement | null {
  if (isBarChart(content)) {
    const data = parseBarChart(content);
    if (data) return <BarChartCard {...data} />;
  }
  if (isTimeline(content)) {
    const cols = parseTimeline(content);
    if (cols && cols.length > 1) return <TimelineCard columns={cols} />;
  }
  if (isInfoBox(content)) {
    const data = parseInfoBox(content);
    if (data) return <InfoBoxCard {...data} />;
  }
  return null;
}
