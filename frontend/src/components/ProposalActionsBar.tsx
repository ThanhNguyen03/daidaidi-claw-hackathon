/**
 * ProposalActionsBar Component
 * ============================
 * View Deck / Download PPTX / Vẽ Wireframe trên Figma, in one place.
 *
 * Rendered twice per session, deliberately: once inline at the end of the assistant turn
 * that built the deck (`variant="inline"`), and once pinned above the composer
 * (`variant="pinned"`). The inline copy alone sat at the bottom of a 7-section proposal —
 * finding it meant scrolling past the whole document, so in practice the deliverables the
 * turn produced were invisible. The pinned copy is driven by session-level state, so it
 * stays reachable on every later turn too.
 *
 * Owning the Figma modal here rather than in either caller is what keeps the two copies from
 * drifting apart. Inline styles rather than Tailwind utilities, matching the block this
 * replaced — the surrounding file styles this way, and `border-accent/35` would depend on the
 * accent being registered as a Tailwind v4 @theme color, which is not worth verifying for a
 * border.
 */

'use client';

import React, { useState } from 'react';
import { FigmaWireframeModal } from './FigmaWireframeModal';

interface ProposalActionsBarProps {
  assets: { deck_url?: string; pptx_url?: string };
  sessionId?: string | null;
  variant?: 'inline' | 'pinned';
}

/** SSR renders a relative href; the browser resolves against the configured backend. */
function apiBase(): string {
  return typeof window !== 'undefined'
    ? process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    : '';
}

export function ProposalActionsBar({
  assets,
  sessionId = null,
  variant = 'inline',
}: ProposalActionsBarProps) {
  const [figmaOpen, setFigmaOpen] = useState(false);

  if (!assets.deck_url && !assets.pptx_url) return null;

  const pinned = variant === 'pinned';

  const wrapStyle: React.CSSProperties = pinned
    ? {
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        flexWrap: 'wrap',
        maxWidth: '72rem',
        margin: '0 auto',
        paddingBottom: '8px',
      }
    : {
        marginTop: '16px',
        padding: '14px 18px',
        borderRadius: '10px',
        border: '1.5px solid rgba(0,104,255,0.35)',
        background: 'var(--color-surface)',
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        flexWrap: 'wrap',
      };

  const pad = pinned ? '5px 12px' : '7px 16px';
  const fontSize = pinned ? '12px' : '13px';

  const base: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '6px',
    padding: pad,
    borderRadius: '6px',
    fontSize,
    fontWeight: 600,
    textDecoration: 'none',
    whiteSpace: 'nowrap',
  };

  return (
    <>
      <div style={wrapStyle}>
        <span
          style={{
            fontSize,
            fontWeight: 600,
            color: pinned ? 'var(--color-text-muted)' : 'var(--color-text)',
            flexShrink: 0,
          }}
        >
          📊 Proposal Deck
        </span>

        {assets.deck_url && (
          <a
            href={`${apiBase()}${assets.deck_url}`}
            target="_blank"
            rel="noopener noreferrer"
            style={{ ...base, background: '#0068ff', color: '#fff' }}
          >
            🖥️ View Deck
          </a>
        )}

        {assets.pptx_url && (
          <a
            href={`${apiBase()}${assets.pptx_url}`}
            download
            style={{
              ...base,
              background: 'transparent',
              border: '1.5px solid #0068ff',
              color: 'var(--color-accent)',
            }}
          >
            {pinned ? '⬇️ PPTX' : '⬇️ Download PPTX'}
          </a>
        )}

        {/* The wireframe spec is built on demand, not with the deck — most proposal turns
            never ask for one, and it is a serialised LLM call (LLM_MAX_CONCURRENCY=1). */}
        <button
          onClick={() => setFigmaOpen(true)}
          style={{
            ...base,
            background: 'transparent',
            border: '1.5px solid #f65009',
            color: '#f65009',
            cursor: 'pointer',
          }}
        >
          🎨 Vẽ Wireframe trên Figma
        </button>
      </div>

      <FigmaWireframeModal
        isOpen={figmaOpen}
        sessionId={sessionId}
        onClose={() => setFigmaOpen(false)}
      />
    </>
  );
}
