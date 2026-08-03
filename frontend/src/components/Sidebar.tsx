/**
 * Sidebar Component
 * =================
 * Left sidebar with mode switcher, new chat, session history, agent status.
 * Uses Tailwind CSS for styling.
 */

import React, { useState, useEffect, useRef } from 'react';
import {
  MessageCircle,
  Plus,
  Clock,
  Users,
  Cpu,
  Database,
  Sun,
  Moon,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  LogOut,
  ShieldCheck,
  Trash2,
  Check,
  X,
  Loader2,
  Bot,
} from 'lucide-react';
import type { ChatMode, User } from '../lib/types';

interface SidebarProps {
  currentMode: ChatMode;
  onModeChange: (mode: ChatMode) => void;
  onNewChat: () => void;
  sessionCount: number;
  isConnected: boolean;
  activeAgents?: AgentStatus[];
  isOpen: boolean;
  onToggle: () => void;
  isDarkMode: boolean;
  onToggleTheme: () => void;
  onOpenModelPanel?: () => void;
  currentUser?: User | null;
  onLogout?: () => void;
  onOpenAdminPanel?: () => void;
  onLoadSession?: (sessionId: string) => void;
  /** Called after a conversation is deleted, so the open chat can reset if it was the one removed. */
  onSessionDeleted?: (sessionId: string) => void;
  /** True while a turn is streaming — history refreshes pause so a poll cannot compete with it. */
  isBusy?: boolean;
}

/** NEXT_PUBLIC_API_URL already ends in /api; strip it before adding our own. */
function apiBase(): string {
  const raw =
    process.env.NEXT_PUBLIC_API_URL ||
    (typeof window !== 'undefined' && window.location.hostname !== 'localhost'
      ? ''
      : 'http://localhost:8000');
  return raw.endsWith('/api') ? raw.slice(0, -4) : raw;
}

function authHeaders(): Record<string, string> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// Revealed on hover on desktop, always visible below md — the sidebar is reachable
// on mobile once opened, and a hover-only control cannot be tapped there at all.
const DELETE_BTN_CLASS =
  'p-1 mr-1.5 rounded-sm text-text-muted opacity-60 md:opacity-0 md:group-hover:opacity-100 ' +
  'focus:opacity-100 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-500/10 transition-all shrink-0';

interface AgentStatus {
  name: string;
  status: 'idle' | 'thinking' | 'waiting' | 'completed' | 'failed';
  /** The model that actually served this skill's last call. Not derivable from
   *  config: a quota fallback means it ran on something other than its MODEL_<NAME>. */
  model?: string | null;
}


// CS mode is hidden from the switcher (not removed — 'cs' stays a valid
// ChatMode and the rest of the app still branches on it) — add the entry
// back here to re-expose it.
const MODES: { id: ChatMode; label: string; icon: React.ReactNode; description: string }[] = [
  { id: 'chat', label: 'PreSales', icon: <MessageCircle size={18} />, description: 'Q&A & advisory' },
];

const SALE_AGENTS: { name: string; display_name: string }[] = [
  { name: 'market_strategy', display_name: 'Orchestrator' },
  { name: 'compliance', display_name: 'Requirement Elicitor' },
  { name: 'product_solution', display_name: 'Strategy Analyst' },
  { name: 'design', display_name: 'Solution Designer' },
  { name: 'client_simulator', display_name: 'Compliance Checker' },
  { name: 'proposal_assembler', display_name: 'Client Debater' },
  { name: 'wireframe_designer', display_name: 'Proposal Builder' },
];

// Status color classes
const getStatusColorClass = (status: AgentStatus['status']): string => {
  const classes: Record<AgentStatus['status'], string> = {
    idle: 'bg-status-idle',
    // Only the two live states pulse. Animating everything would make the panel
    // busy without telling anyone anything; animating just these makes the list a
    // genuine progress readout during the minute a proposal takes to build.
    thinking: 'bg-status-thinking agent-active',
    waiting: 'bg-status-waiting agent-active',
    completed: 'bg-status-completed',
    failed: 'bg-status-failed',
  };
  return classes[status] || classes.idle;
};

const getStatusTextClass = (status: AgentStatus['status']): string => {
  const classes: Record<AgentStatus['status'], string> = {
    idle: 'text-text',
    thinking: 'text-status-thinking',
    waiting: 'text-status-waiting',
    completed: 'text-status-completed',
    failed: 'text-status-failed',
  };
  return classes[status] || classes.idle;
};

const getStatusColorStyle = (status: AgentStatus['status']): string => {
  const colors: Record<AgentStatus['status'], string> = {
    idle: 'var(--color-status-idle)',
    thinking: 'var(--color-status-thinking)',
    waiting: 'var(--color-status-waiting)',
    completed: 'var(--color-status-completed)',
    failed: 'var(--color-status-failed)',
  };
  return colors[status] || colors.idle;
};

function SidebarInner({
  currentMode,
  onModeChange,
  onNewChat,
  sessionCount,
  isConnected,
  activeAgents = [],
  isOpen = true,
  isDarkMode,
  onToggleTheme,
  onOpenModelPanel,
  currentUser,
  onLogout,
  onOpenAdminPanel,
  onLoadSession,
  onSessionDeleted,
  isBusy = false,
}: SidebarProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [sessions, setSessions] = useState<Array<{ session_id: string; title: string; updated_at: string }>>([]);
  // Which row is asking "are you sure?" — deleting a rep's conversation is not undoable.
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [confirmingClearAll, setConfirmingClearAll] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  // Closed by default — the per-agent list (name + model, one row each) can run
  // to 7 rows, which used to be a fixed chunk of the sidebar whether or not
  // anything was actually running.
  const [agentsExpanded, setAgentsExpanded] = useState(false);

  // Reads the latest isBusy without making it an effect dependency — changing it
  // must not tear down and rebuild the refresh timer on every turn.
  const isBusyRef = useRef(isBusy);
  useEffect(() => { isBusyRef.current = isBusy; }, [isBusy]);

  // Fetch session history (both logged in users and guests)
  useEffect(() => {
    const fetchSessions = async (force = false) => {
      // The backend reads SQLite for this. While a turn is streaming, that read
      // competes with the response the rep is waiting on — and `session_updated`
      // already fires the moment anything changes, so a poll mid-turn buys nothing.
      if (!force && isBusyRef.current) return;
      try {
        const res = await fetch(`${apiBase()}/api/user/sessions`, { headers: authHeaders() });
        if (res.ok) {
          const data = await res.json();
          setSessions(data.sessions || []);
        }
      } catch { /* ignore */ }
    };
    const refreshNow = () => { void fetchSessions(true); };

    void fetchSessions(true);
    // A slow fallback only. The list is event-driven: the chat hook fires
    // `session_updated` at the start and end of every turn. The old 5s interval
    // meant 12 requests a minute per open tab, each one a blocking SQLite read
    // on the same event loop that serves the SSE stream.
    const interval = setInterval(() => { void fetchSessions(); }, 60000);
    window.addEventListener('session_updated', refreshNow);
    window.addEventListener('focus', refreshNow);
    return () => {
      clearInterval(interval);
      window.removeEventListener('session_updated', refreshNow);
      window.removeEventListener('focus', refreshNow);
    };
  }, [currentUser]);

  const handleDelete = async (sessionId: string) => {
    setDeletingId(sessionId);
    try {
      const res = await fetch(`${apiBase()}/api/user/sessions/${sessionId}`, {
        method: 'DELETE',
        headers: authHeaders(),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setSessions((prev) => prev.filter((s) => s.session_id !== sessionId));
      onSessionDeleted?.(sessionId);
    } catch (e) {
      console.error('Failed to delete session:', e);
    } finally {
      setDeletingId(null);
      setConfirmingId(null);
    }
  };

  const handleClearAll = async () => {
    const removed = sessions.map((s) => s.session_id);
    setDeletingId('__all__');
    try {
      const res = await fetch(`${apiBase()}/api/user/sessions`, {
        method: 'DELETE',
        headers: authHeaders(),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setSessions([]);
      removed.forEach((id) => onSessionDeleted?.(id));
    } catch (e) {
      console.error('Failed to clear history:', e);
    } finally {
      setDeletingId(null);
      setConfirmingClearAll(false);
    }
  };

  const displayAgents = SALE_AGENTS;

  // Create a map of agent statuses
  const agentStatusMap = new Map<string, AgentStatus['status']>();
  const agentModelMap = new Map<string, string>();
  activeAgents.forEach((agent) => {
    agentStatusMap.set(agent.name, agent.status);
    if (agent.model) agentModelMap.set(agent.name, agent.model);
  });

  return (
    <aside
      className={`
        w-72 max-w-[85vw] flex flex-col glass-panel border-r border-border-strong
        fixed inset-y-0 left-0 z-50 transition-transform duration-200 ease-out
        md:static md:z-auto md:h-full md:translate-x-0 md:transition-none
        ${isOpen ? 'translate-x-0' : '-translate-x-full'}
        ${isCollapsed ? 'md:w-16' : 'md:w-64'}
      `}
    >
      <div className="shrink-0 sticky top-0 z-10 bg-surface-solid border-b border-border/50 p-4">
        {/* Logo / Title */}
        <div className="mb-3">
          {!isCollapsed && (
            <>
              <h1 className="text-[18px] font-bold text-gradient-tech">Z-PreSales Agent</h1>
              <p className="text-xs text-text-muted">Multi-Agent Assistant</p>
            </>
          )}
          {isCollapsed && (
            <div className="w-8 h-8 mx-auto rounded-lg bg-accent flex items-center justify-center">
              <Bot size={18} className="text-white" />
            </div>
          )}
        </div>
        {/* New Chat Button */}
        <button
          onClick={onNewChat}
          className={`
            flex items-center justify-center gap-2 bg-accent text-white rounded-lg
            font-medium text-[12px] hover:opacity-90 transition-opacity
            ${isCollapsed ? 'w-8 h-8 mx-auto' : 'w-full px-4 py-3'}
          `}
        >
          <Plus size={18} />
          {!isCollapsed && 'New Chat'}
        </button>
      </div>

      <div className='p-2 md:p-4 flex flex-col justify-between items-center overflow-y-auto overflow-x-hidden flex-1 min-h-0 relative' >
        <div className='w-full flex flex-col'>
          {/* Mode Switcher — hidden while CS mode is hidden and MODES has only
              one entry (a single always-active pill isn't a switcher, it's
              clutter). Reappears on its own once a second mode is added back
              to MODES above. */}
          {MODES.length > 1 && (
            <>
              {!isCollapsed && (
                <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">
                  Mode
                </h2>
              )}
              <div className="flex flex-col gap-1">
                {MODES.map((mode) => (
                  <button
                    key={mode.id}
                    onClick={() => onModeChange(mode.id)}
                    className={`
                      flex items-center gap-3 rounded-md cursor-pointer
                      text-[12px] transition-all duration-150
                      ${currentMode === mode.id
                        ? 'bg-accent-soft text-accent font-medium'
                        : 'text-text hover:bg-surface-hover'
                      }
                      ${isCollapsed ? 'w-8 h-8 mx-auto justify-center' : 'py-2.5 px-3 justify-start'}
                    `}
                    title={mode.description}
                  >
                    <span className={currentMode === mode.id ? 'text-accent' : 'text-text-muted'}>
                      {mode.icon}
                    </span>
                    {!isCollapsed && <span className="flex items-center gap-2">{mode.label}</span>}
                  </button>
                ))}
              </div>
            </>
          )}

          {!isCollapsed && (
            <div className="mt-4 pt-3 border-t border-border/50">
              <div className="flex items-center justify-between px-1 mb-2">
                <p className="text-[10px] uppercase tracking-wider text-text-muted font-bold flex items-center gap-1">
                  <Clock size={11} className="text-accent" /> Lịch sử hội thoại
                </p>
                <div className="flex items-center gap-1">
                  {sessions.length > 0 && (
                    <span className="text-[9px] bg-accent/10 text-accent font-medium px-1.5 py-0.5 rounded-full">
                      {sessions.length}
                    </span>
                  )}
                  {sessions.length > 0 && !confirmingClearAll && (
                    <button
                      onClick={() => { setConfirmingClearAll(true); setConfirmingId(null); }}
                      className="p-1 rounded-sm text-text-muted hover:text-red-600 dark:hover:text-red-400 hover:bg-red-500/10 transition-colors"
                      title="Xoá toàn bộ lịch sử"
                      aria-label="Xoá toàn bộ lịch sử"
                    >
                      <Trash2 size={11} />
                    </button>
                  )}
                </div>
              </div>

              {confirmingClearAll && (
                <div className="mb-2 px-2 py-2 rounded-lg border border-red-500/30 bg-red-500/5">
                  <p className="text-[11px] text-text mb-2">
                    Xoá {sessions.length} cuộc trò chuyện? Không thể hoàn tác.
                  </p>
                  <div className="flex gap-1">
                    <button
                      onClick={handleClearAll}
                      disabled={deletingId === '__all__'}
                      className="flex-1 flex items-center justify-center gap-1 py-1 rounded-sm text-[11px] font-medium bg-red-500/15 text-red-600 dark:text-red-400 hover:bg-red-500/25 transition-colors disabled:opacity-50"
                    >
                      {deletingId === '__all__'
                        ? <Loader2 size={11} className="animate-spin" />
                        : <Trash2 size={11} />}
                      Xoá hết
                    </button>
                    <button
                      onClick={() => setConfirmingClearAll(false)}
                      className="flex-1 py-1 rounded-sm text-[11px] text-text-muted border border-border hover:bg-surface-hover transition-colors"
                    >
                      Huỷ
                    </button>
                  </div>
                </div>
              )}

              {sessions.length > 0 ? (
                <div className="flex flex-col gap-1 max-h-48 overflow-y-auto pr-1 text-xs">
                  {sessions.slice(0, 15).map((s) => (
                    <div
                      key={s.session_id}
                      className="w-full flex items-center gap-1 rounded-lg group border border-transparent hover:border-border/60 hover:bg-surface-2 transition-all"
                    >
                      <button
                        onClick={() => onLoadSession?.(s.session_id)}
                        title={s.title}
                        className="min-w-0 flex-1 text-left pl-2.5 py-2 text-[12px] text-text-muted group-hover:text-text transition-colors flex items-center gap-2"
                      >
                        <MessageCircle size={13} className="shrink-0 text-accent/60 group-hover:text-accent transition-colors" />
                        <span className="truncate font-medium">{s.title}</span>
                      </button>
                      {confirmingId === s.session_id ? (
                        // Two taps to delete, and the confirm lives on the row itself:
                        // a window.confirm() is blocked in some embedded webviews, which
                        // would make the button look broken rather than cautious.
                        <span className="flex items-center gap-0.5 pr-1.5 shrink-0">
                          <button
                            onClick={() => handleDelete(s.session_id)}
                            disabled={deletingId === s.session_id}
                            className="p-1 rounded-sm text-red-600 dark:text-red-400 hover:bg-red-500/15 transition-colors disabled:opacity-50"
                            title="Xác nhận xoá"
                            aria-label="Xác nhận xoá"
                          >
                            {deletingId === s.session_id
                              ? <Loader2 size={12} className="animate-spin" />
                              : <Check size={12} />}
                          </button>
                          <button
                            onClick={() => setConfirmingId(null)}
                            className="p-1 rounded-sm text-text-muted hover:bg-surface-hover transition-colors"
                            title="Huỷ"
                            aria-label="Huỷ xoá"
                          >
                            <X size={12} />
                          </button>
                        </span>
                      ) : (
                        <button
                          onClick={() => { setConfirmingId(s.session_id); setConfirmingClearAll(false); }}
                          className={DELETE_BTN_CLASS}
                          title="Xoá cuộc trò chuyện"
                          aria-label={`Xoá cuộc trò chuyện ${s.title}`}
                        >
                          <Trash2 size={12} />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="px-2 py-1.5 text-[11px] text-text-muted italic opacity-75">
                  Chưa có cuộc trò chuyện nào. Hãy bắt đầu chat để tự động lưu!
                </p>
              )}
            </div>
          )}

          {currentMode !== 'cs' && (
          <div className="mb-6 mt-4">
            {!isCollapsed && (
              <div
                role="button"
                tabIndex={0}
                onClick={() => setAgentsExpanded((v) => !v)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setAgentsExpanded((v) => !v); }
                }}
                className="w-full text-xs font-semibold text-text-muted uppercase tracking-wider mb-3 flex items-center justify-between gap-2 cursor-pointer hover:text-text transition-colors select-none"
                aria-expanded={agentsExpanded}
              >
                <span className="flex items-center gap-2">
                  <Users size={14} />
                  Active Agents
                </span>
                <span className="flex items-center gap-1">
                  {onOpenModelPanel && (
                    <button
                      onClick={(e) => { e.stopPropagation(); onOpenModelPanel(); }}
                      className="p-1 rounded-sm hover:bg-bg text-text-muted normal-case tracking-normal"
                      title="Model & quota"
                      aria-label="Model & quota"
                    >
                      <Cpu size={14} />
                    </button>
                  )}
                  <ChevronDown
                    size={14}
                    className={`transition-transform duration-150 ${agentsExpanded ? 'rotate-180' : ''}`}
                  />
                </span>
              </div>
            )}
            {(isCollapsed || agentsExpanded) && (
            <div className="flex flex-col gap-1">
              {displayAgents.map((agent) => {
                const status = agentStatusMap.get(agent.name) || 'idle';
                const model = agentModelMap.get(agent.name);

                return (
                  <div
                    key={agent.name}
                    className={`
                      flex items-center gap-2 text-xs
                      ${isCollapsed ? 'justify-center py-2' : 'px-3 py-1.5'}
                    `}
                    title={agent.display_name}
                  >
                    <span
                      className={`w-2 h-2 rounded-full shrink-0 ${getStatusColorClass(status)}`}
                      style={{ backgroundColor: getStatusColorStyle(status) }}
                      title={status}
                    />
                    {!isCollapsed && (
                      <span className="min-w-0 flex flex-col leading-tight">
                        <span
                          className={getStatusTextClass(status)}
                          style={{ color: getStatusColorStyle(status) }}
                        >
                          {agent.display_name}
                          {status === 'thinking' && (
                            <span className="ml-1 text-status-thinking">●</span>
                          )}
                        </span>
                        {/* The model it actually ran on. Shown only once it has run,
                            because before that it is a guess the fallback can overrule. */}
                        {model && (
                          <span className="text-[10px] text-text-muted truncate" title={model}>
                            {model}
                          </span>
                        )}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
            )}
          </div>
          )}
        </div>

        <div className='w-full flex flex-col'>
          {/* User Info + Admin/Logout */}
          {currentUser && !isCollapsed && (
            <div className="mt-2 mb-2 flex flex-col gap-2">
              <div className="flex items-stretch gap-2">
                <div className="sidebar-user-block flex-1 min-w-0" title={currentUser.full_name}>
                  <div className="sidebar-user-avatar">
                    {currentUser.full_name?.[0]?.toUpperCase() ?? '?'}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-text truncate">{currentUser.full_name}</p>
                    <p className="text-[10px] text-text-muted truncate">
                      {currentUser.role === 'admin' ? '🛡️ Admin' : currentUser.role === 'account_manager' ? '💼 AM' : '🎯 Sales'}
                    </p>
                  </div>
                  {onLogout && (
                    <button
                      onClick={onLogout}
                      className="p-2 flex items-center justify-center aspect-square shrink-0 rounded-lg text-text-muted hover:text-red-600 dark:hover:text-red-400 hover:bg-red-500/10 transition-colors"
                      title="Đăng xuất"
                    >
                      <LogOut size={16} />
                    </button>
                  )}
                </div>
              </div>
              {currentUser.role === 'admin' && onOpenAdminPanel && (
                <button
                  onClick={onOpenAdminPanel}
                  className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-[11px] font-medium bg-accent/10 hover:bg-accent/20 text-accent transition-colors border border-accent/20"
                  title="Admin Panel"
                >
                  <ShieldCheck size={11} />
                  Admin Panel
                </button>
              )}
            </div>
          )}

          {/* Collapsed user info — just the avatar (as a tooltip identity cue)
              plus a reachable logout button; the full name/role card and admin
              shortcut only make sense at full width. */}
          {currentUser && isCollapsed && (
            <div className="mt-2 mb-2 flex flex-col items-center gap-2">
              <div className="sidebar-user-avatar" title={currentUser.full_name}>
                {currentUser.full_name?.[0]?.toUpperCase() ?? '?'}
              </div>
              {onLogout && (
                <button
                  onClick={onLogout}
                  className="flex items-center justify-center w-8 h-8 rounded-lg text-text-muted hover:text-red-600 dark:hover:text-red-400 hover:bg-red-500/10 transition-colors border border-border"
                  title="Đăng xuất"
                >
                  <LogOut size={16} />
                </button>
              )}
            </div>
          )}

          {/* KB/Backend Status */}
          <div
            className={`
              flex items-center gap-2 text-xs text-text-muted border-t border-border pt-2 mt-2
              ${isCollapsed ? 'justify-center' : 'px-3'}
            `}
            title={isConnected ? 'Backend connected and ready' : 'Backend offline or not configured'}
          >
            <Database size={14} />
            {!isCollapsed && (
              <div className='flex items-center justify-between w-full'>
                {isConnected ? 'Backend Ready' : 'Backend Offline'}
                <span
                  className={`w-2 h-2 rounded-full ${isConnected ? 'bg-status-completed' : 'bg-status-failed'}`}
                  style={{ backgroundColor: isConnected ? 'var(--color-status-completed)' : 'var(--color-status-failed)' }}
                />
              </div>
            )}
          </div>

          {/* Session Count */}
          {!isCollapsed && (
            <div className="flex items-center gap-2 text-xs text-text-muted px-3">
              <Clock size={14} />
              {sessionCount} sessions
            </div>
          )}

          <div className={`
            flex items-center gap-2 mt-2 pt-2 border-t border-border
            ${isCollapsed ? 'flex-col justify-center' : 'flex-row justify-between'}
          `}>
            {/* Theme Toggle */}
            <button
              onClick={onToggleTheme}
              className={`
                flex items-center justify-center gap-2 rounded-md shrink-0
                border border-border text-text-muted hover:bg-surface-hover transition-colors
                ${isCollapsed ? 'w-8 h-8' : 'flex-1 h-9'}
              `}
              title={isDarkMode ? 'Switch to Light mode' : 'Switch to Dark mode'}
            >
              {isDarkMode ? <Sun size={16} /> : <Moon size={16} />}
              {!isCollapsed && (isDarkMode ? 'Light' : 'Dark')}
            </button>

            {/* Collapse/Expand — desktop only. The aside is off-canvas on mobile
                (full width when open, translated away when closed), so "collapsed"
                has no meaning there; the icon-only layout it produces would just
                be a full-width drawer showing icons with no labels. */}
            <button
              onClick={() => setIsCollapsed(!isCollapsed)}
              className={`hidden md:flex items-center justify-center rounded-md border border-border text-text-muted hover:bg-surface-hover shrink-0 ${isCollapsed ? 'size-8' : 'h-full aspect-square p-2'}`}
              title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              {isCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
            </button>
          </div>
        </div>
      </div>
    </aside>
  );
}

// Memoized: this component re-renders on every streamed token otherwise
// (page.tsx re-renders on every content event, and an unmemoized Sidebar
// re-renders with it) — the callbacks it receives are now stable identities
// (see page.tsx's useCallback wrappers), so the memo actually holds.
export const Sidebar = React.memo(SidebarInner);
Sidebar.displayName = 'Sidebar';
