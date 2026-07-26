/**
 * ModelPanel Component
 * ====================
 * Which model each skill is on, how much of each model's allowance this app has
 * spent, and a picker to move a skill — or everything — onto a different one.
 *
 * The usage figures are counted by the backend, not reported by Google: there is no
 * API that returns remaining quota for a key. So the panel shows the backend's own
 * caveat verbatim instead of presenting the numbers as authoritative. The one figure
 * that is authoritative is the "hết quota hôm nay" state, which comes straight out of
 * a 429 that named a per-day limit.
 */

'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, Check, Cpu, Info, RefreshCw, X } from 'lucide-react';
import { getApiBaseUrl } from '../lib/api';
import type { ModelInfo, ModelsResponse, SkillModel } from '../lib/types';

interface ModelPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

const STATE_LABEL: Record<string, string> = {
  ok: 'Sẵn sàng',
  unused: 'Chưa dùng',
  rate_limited: 'Đang bị giới hạn/phút',
  out_of_quota_today: 'Hết quota hôm nay',
};

const STATE_COLOR: Record<string, string> = {
  ok: 'var(--color-status-completed)',
  unused: 'var(--color-status-idle)',
  rate_limited: 'var(--color-status-waiting)',
  out_of_quota_today: 'var(--color-status-failed)',
};

/** Percentage of an allowance used, or null when no ceiling is declared for it. */
function pct(used: number, limit: number | null): number | null {
  if (!limit || limit <= 0) return null;
  return Math.min(100, Math.round((used / limit) * 100));
}

function UsageBar({ used, limit, label }: { used: number; limit: number | null; label: string }) {
  const p = pct(used, limit);
  return (
    <div className="flex items-center gap-2 text-[11px]">
      <span className="w-8 text-text-muted">{label}</span>
      <div className="flex-1 h-1.5 rounded-full bg-border overflow-hidden">
        {p !== null && (
          <div
            className="h-full rounded-full transition-all"
            style={{
              width: `${p}%`,
              // Red once the allowance is effectively gone — the number itself is
              // easy to skim past when it is one row of nine.
              backgroundColor:
                p >= 100
                  ? 'var(--color-status-failed)'
                  : p >= 70
                    ? 'var(--color-status-waiting)'
                    : 'var(--color-status-completed)',
            }}
          />
        )}
      </div>
      <span className="w-16 text-right tabular-nums text-text-muted">
        {used}
        {limit ? ` / ${limit}` : ''}
      </span>
    </div>
  );
}

export function ModelPanel({ isOpen, onClose }: ModelPanelProps) {
  const [data, setData] = useState<ModelsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busySkill, setBusySkill] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${getApiBaseUrl()}/models`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData((await res.json()) as ModelsResponse);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Không đọc được trạng thái model');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    load();
    // Usage moves only when a turn runs, so a slow poll is enough to keep the panel
    // honest without adding traffic of its own during a demo.
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [isOpen, load]);

  const select = async (agent: string, model: string | null) => {
    setBusySkill(agent);
    try {
      const res = await fetch(`${getApiBaseUrl()}/models/select`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent, model }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Không đổi được model');
    } finally {
      setBusySkill(null);
    }
  };

  if (!isOpen) return null;

  const models: ModelInfo[] = data?.models ?? [];
  const skills: SkillModel[] = data?.skills ?? [];
  // Only offer models that can actually serve a request. A zero allowance in the
  // limits file means "known not to work on this tier" — offering it as a choice
  // would be offering a way to break the demo.
  const selectable = models.filter((m) => (m.limit_rpd ?? 0) > 0).map((m) => m.model);
  const globalOverride = data?.overrides?.['*'] ?? '';

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 p-4 overflow-y-auto">
      <div className="w-full max-w-2xl bg-surface border border-border rounded-xl shadow-xl my-8">
        <header className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-text">
            <Cpu size={16} />
            Model &amp; Quota
          </h2>
          <div className="flex items-center gap-2">
            <button
              onClick={load}
              className="p-1.5 rounded-lg hover:bg-bg text-text-muted"
              title="Cập nhật"
              aria-label="Cập nhật"
            >
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg hover:bg-bg text-text-muted"
              aria-label="Đóng"
            >
              <X size={16} />
            </button>
          </div>
        </header>

        {error && (
          <div className="mx-5 mt-4 flex items-start gap-2 text-xs text-status-failed">
            <AlertTriangle size={14} className="mt-0.5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <section className="px-5 py-4">
          <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">
            Hạn mức theo model
          </h3>
          <div className="flex flex-col gap-3">
            {models.map((m) => (
              <div key={m.model} className="border border-border rounded-lg p-3">
                <div className="flex items-center justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <span
                      className="w-2 h-2 rounded-full flex-shrink-0"
                      style={{ backgroundColor: STATE_COLOR[m.state] ?? STATE_COLOR.unused }}
                    />
                    <span className="text-xs font-medium text-text truncate">{m.model}</span>
                  </div>
                  <span
                    className="text-[11px] flex-shrink-0"
                    style={{ color: STATE_COLOR[m.state] ?? STATE_COLOR.unused }}
                  >
                    {STATE_LABEL[m.state] ?? m.state}
                  </span>
                </div>
                <div className="flex flex-col gap-1.5">
                  <UsageBar used={m.used_rpm} limit={m.limit_rpm} label="phút" />
                  <UsageBar used={m.used_rpd} limit={m.limit_rpd} label="ngày" />
                </div>
                {(m.rate_limits > 0 || m.note) && (
                  <p className="mt-2 text-[11px] text-text-muted">
                    {m.rate_limits > 0 && <>429: {m.rate_limits} lần. </>}
                    {m.note}
                  </p>
                )}
              </div>
            ))}
          </div>
        </section>

        <section className="px-5 pb-4">
          <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">
            Model theo từng skill
          </h3>

          <div className="flex items-center gap-2 mb-3 text-xs">
            <span className="text-text-muted">Đổi tất cả:</span>
            <select
              value={globalOverride}
              disabled={busySkill === '*'}
              onChange={(e) => select('*', e.target.value || null)}
              className="flex-1 bg-bg border border-border rounded-lg px-2 py-1.5 text-text"
            >
              <option value="">— theo cấu hình —</option>
              {selectable.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            {skills.map((s) => (
              <div key={s.skill} className="flex items-center gap-2 text-xs py-1">
                <span className="w-40 truncate text-text" title={s.skill}>
                  {s.skill}
                </span>
                <select
                  value={data?.overrides?.[s.skill] ?? ''}
                  disabled={busySkill === s.skill}
                  onChange={(e) => select(s.skill, e.target.value || null)}
                  className="flex-1 min-w-0 bg-bg border border-border rounded-lg px-2 py-1 text-text"
                >
                  <option value="">
                    {s.overridden && !data?.overrides?.[s.skill]
                      ? `${s.model} (đổi tất cả)`
                      : `${s.configured ?? s.model} (mặc định)`}
                  </option>
                  {selectable.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
                {/* What ran last, which is the only way to see a fallback having
                    fired — it differs from the configured model precisely then. */}
                <span
                  className="w-44 text-[11px] text-right truncate text-text-muted"
                  title={s.last_used ? `Lượt gần nhất chạy trên ${s.last_used}` : 'Chưa chạy lượt nào'}
                >
                  {s.last_used ? (
                    <>
                      {s.last_used === s.model ? (
                        <Check size={11} className="inline mb-0.5 mr-1" />
                      ) : (
                        <AlertTriangle size={11} className="inline mb-0.5 mr-1" />
                      )}
                      {s.last_used}
                    </>
                  ) : (
                    '—'
                  )}
                </span>
              </div>
            ))}
          </div>

          {data?.fallback_chain?.length ? (
            <p className="mt-3 text-[11px] text-text-muted">
              Hết quota thì tự chuyển sang: {data.fallback_chain.join(' → ')}
            </p>
          ) : null}
        </section>

        {data?.caveat && (
          <footer className="flex items-start gap-2 px-5 py-3 border-t border-border text-[11px] text-text-muted">
            <Info size={13} className="mt-0.5 flex-shrink-0" />
            <span>{data.caveat}</span>
          </footer>
        )}
      </div>
    </div>
  );
}
