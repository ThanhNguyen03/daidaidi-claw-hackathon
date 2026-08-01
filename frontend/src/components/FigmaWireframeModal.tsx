/**
 * FigmaWireframeModal Component
 * =============================
 * The rep presses "Vẽ Wireframe trên Figma" on a finished proposal; this asks the backend to
 * build a wireframe spec, then shows the job code they paste into the AdtimaBox Figma plugin.
 *
 * Why a code and not a redirect into Figma: Figma exposes no REST API for creating nodes, and
 * OAuth grants no Plugin-API access, so nothing server-side can draw into the rep's file
 * however they authorise us. Drawing only happens from inside a running Figma session, which
 * means the plugin has to pull. The code is what connects the two halves.
 */

'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, Check, Copy, Loader2, X } from 'lucide-react';
import { getApiBaseUrl } from '../lib/api';

interface FigmaWireframeModalProps {
  isOpen: boolean;
  sessionId: string | null;
  onClose: () => void;
}

interface JobResult {
  job_code: string;
  screen_count: number;
  reused: boolean;
}

export function FigmaWireframeModal({ isOpen, sessionId, onClose }: FigmaWireframeModalProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<JobResult | null>(null);
  const [copied, setCopied] = useState(false);

  const build = useCallback(async () => {
    if (!sessionId) {
      setError('Chưa có hội thoại nào đang mở.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const base = getApiBaseUrl();
      const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
      const res = await fetch(`${base}/figma/wireframe`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ session_id: sessionId }),
      });
      if (!res.ok) {
        // The backend's 422 detail is the skill's own Vietnamese explanation of which
        // failure this was (thin proposal, no drawable screens, model truncated) — showing
        // it beats collapsing every cause into one generic message.
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail || `Không dựng được wireframe (HTTP ${res.status})`);
      }
      setResult(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Không dựng được wireframe');
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  // Build on open rather than behind a second click: the rep already expressed the intent by
  // pressing the CTA, and the call takes long enough that an extra confirm step reads as a
  // stall. Reopening a modal that already has a result must not spend another LLM call —
  // the backend is idempotent per proposal, but not re-requesting is cheaper still.
  useEffect(() => {
    if (isOpen && !result && !loading && !error) build();
  }, [isOpen, result, loading, error, build]);

  useEffect(() => {
    if (!copied) return;
    const t = setTimeout(() => setCopied(false), 2000);
    return () => clearTimeout(t);
  }, [copied]);

  if (!isOpen) return null;

  const copyCode = async () => {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(result.job_code);
      setCopied(true);
    } catch {
      // Clipboard is blocked in some embedded contexts; the code is on screen to retype.
    }
  };

  return (
    <div className="modal-scrim items-start p-4">
      <div className="w-full max-w-lg rounded-xl my-8 modal-card">
        <header className="shrink-0 flex items-center justify-between px-5 py-4 border-b border-border">
          <h2 className="text-sm font-semibold text-text">🎨 Vẽ Wireframe trên Figma</h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-surface-2 text-text-muted"
            aria-label="Đóng"
          >
            <X size={16} />
          </button>
        </header>

        <div className="modal-card-body px-5 py-4">
          {loading && (
            <div className="flex items-center gap-2 text-sm text-text-muted py-6">
              <Loader2 size={16} className="animate-spin" />
              Đang dựng wireframe từ proposal…
            </div>
          )}

          {error && !loading && (
            <div className="py-2">
              <div className="flex items-start gap-2 text-sm text-status-failed mb-4">
                <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                <span>{error}</span>
              </div>
              <button
                onClick={build}
                className="px-4 py-2 rounded-lg text-sm font-semibold bg-accent text-white"
              >
                Thử lại
              </button>
            </div>
          )}

          {result && !loading && !error && (
            <>
              <p className="text-sm text-text-muted mb-4">
                Đã dựng <strong className="text-text">{result.screen_count} màn hình</strong>. Mở
                plugin <strong className="text-text">AdtimaBox Wireframe</strong> trong file Figma
                của bạn và dán mã dưới đây:
              </p>

              <div className="flex items-center gap-2 mb-5">
                <code className="flex-1 px-4 py-3 rounded-lg bg-surface-2 text-text text-xl font-bold tracking-[0.3em] text-center tabular-nums">
                  {result.job_code}
                </code>
                <button
                  onClick={copyCode}
                  className="p-3 rounded-lg hover:bg-surface-2 text-text-muted shrink-0"
                  title="Sao chép mã"
                  aria-label="Sao chép mã"
                >
                  {copied ? <Check size={18} className="text-status-completed" /> : <Copy size={18} />}
                </button>
              </div>

              <ol className="text-xs text-text-muted space-y-2 list-decimal list-inside">
                <li>Mở file Figma bất kỳ của bạn (Figma desktop app).</li>
                <li>
                  Menu <strong className="text-text">Plugins → Development → AdtimaBox Wireframe</strong>.
                  Lần đầu cần Import plugin from manifest, chọn file{' '}
                  <code className="text-text">figma-plugin/manifest.json</code>.
                </li>
                <li>Dán mã ở trên vào plugin rồi bấm <strong className="text-text">Vẽ Wireframe</strong>.</li>
              </ol>

              <p className="text-[11px] text-text-muted mt-4 pt-3 border-t border-border">
                Mã có hiệu lực trong 24 giờ. Figma không cho phép hệ thống bên ngoài tự vẽ vào file
                của bạn, nên plugin phải chạy từ trong Figma — đây là cách duy nhất nền tảng hỗ trợ.
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
