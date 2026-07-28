/**
 * Sidebar Component
 * =================
 * Left sidebar with mode switcher, new chat, session history, agent status.
 * Uses Tailwind CSS for styling.
 */

import React, { useState, useEffect } from 'react';
import {
  MessageCircle,
  Headphones,
  Plus,
  Clock,
  Users,
  Cpu,
  Database,
  Sun,
  Moon,
  ChevronLeft,
  ChevronRight,
  LogOut,
  ShieldCheck,
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
}

interface AgentStatus {
  name: string;
  status: 'idle' | 'thinking' | 'waiting' | 'completed' | 'failed';
  /** The model that actually served this skill's last call. Not derivable from
   *  config: a quota fallback means it ran on something other than its MODEL_<NAME>. */
  model?: string | null;
}


const MODES: { id: ChatMode; label: string; icon: React.ReactNode; description: string }[] = [
  { id: 'chat', label: 'Chat', icon: <MessageCircle size={18} />, description: 'Q&A & advisory' },
  { id: 'cs', label: 'Customer Services', icon: <Headphones size={18} />, description: 'Customer Service' },
];

const SALE_AGENTS: { name: string; display_name: string }[] = [
  { name: 'market_strategy', display_name: 'Market Strategy' },
  { name: 'compliance', display_name: 'Compliance' },
  { name: 'product_solution', display_name: 'Product Solution' },
  { name: 'design', display_name: 'UX Design' },
  { name: 'client_simulator', display_name: 'Client Simulator' },
  { name: 'proposal_assembler', display_name: 'Proposal Assembler' },
  { name: 'wireframe_designer', display_name: 'Deck Generator' },
];

const CS_AGENTS: { name: string; display_name: string }[] = [
  { name: 'cs_agent', display_name: 'CS Assistant' },
  { name: 'predict_agent', display_name: 'Tarot & Fortune' },
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

export function Sidebar({
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
}: SidebarProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [sessions, setSessions] = useState<Array<{ session_id: string; title: string; updated_at: string }>>([]); 

  // Fetch session history (both logged in users and guests)
  useEffect(() => {
    const fetchSessions = async () => {
      try {
        const token = localStorage.getItem('auth_token');
        const headers: Record<string, string> = {};
        if (token) headers['Authorization'] = `Bearer ${token}`;

        const apiBase = process.env.NEXT_PUBLIC_API_URL ||
          (typeof window !== 'undefined' && window.location.hostname !== 'localhost'
            ? '' : 'http://localhost:8000');
        const res = await fetch(`${apiBase}/api/user/sessions`, { headers });
        if (res.ok) {
          const data = await res.json();
          setSessions(data.sessions || []);
        }
      } catch { /* ignore */ }
    };
    fetchSessions();
    const interval = setInterval(fetchSessions, 10000);
    return () => clearInterval(interval);
  }, [currentUser]);

  const displayAgents = currentMode === 'cs' ? CS_AGENTS : SALE_AGENTS;

  // Create a map of agent statuses
  const agentStatusMap = new Map<string, AgentStatus['status']>();
  const agentModelMap = new Map<string, string>();
  activeAgents.forEach((agent) => {
    agentStatusMap.set(agent.name, agent.status);
    if (agent.model) agentModelMap.set(agent.name, agent.model);
  });

  const sidebarWidth = isCollapsed ? 'w-16' : 'w-64';

  return (
    <aside
      className={`
        ${sidebarWidth} min-h-screen bg-surface border-r border-border overflow-y-auto
        flex flex-col p-4 transition-sidebar sticky top-0 z-40 shrink-0
        ${!isOpen ? 'hidden md:flex' : 'flex'}
      `}
    >
      {/* Logo / Title */}
      <div className="mb-6">
        {!isCollapsed && (
          <>
            <h1 className="text-[18px] font-bold text-text">AdtimaBox Sales Agent</h1>
            <p className="text-xs text-text-muted">Multi-Agent Assistant</p>
          </>
        )}
        {isCollapsed && (
          <div className="text-center text-[18px] font-bold text-accent">S</div>
        )}
      </div>

      {/* New Chat Button */}
      <button
        onClick={onNewChat}
        className={`
          flex items-center justify-center gap-2 w-full py-3 bg-accent text-white rounded-lg
          font-medium text-[12px] mb-6 hover:opacity-90 transition-opacity
          ${isCollapsed ? 'px-2' : 'px-4'}
        `}
      >
        <Plus size={18} />
        {!isCollapsed && 'New Chat'}
      </button>

      {/* Mode Switcher */}
      <div className="mb-6">
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
                flex items-center gap-3 rounded-md py-2.5 cursor-pointer
                text-[12px] transition-all duration-150
                ${currentMode === mode.id
                  ? 'bg-accent-soft text-accent font-medium'
                  : 'text-text hover:bg-surface-hover'
                }
                ${isCollapsed ? 'justify-center px-2' : 'px-3 justify-start'}
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
      </div>

      {/* Active Agents */}
      <div className="mb-6">
        {!isCollapsed && (
          <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3 flex items-center justify-between gap-2">
            <span className="flex items-center gap-2">
              <Users size={14} />
              Active Agents
            </span>
            {onOpenModelPanel && (
              <button
                onClick={onOpenModelPanel}
                className="p-1 rounded hover:bg-bg text-text-muted normal-case tracking-normal"
                title="Model & quota"
                aria-label="Model & quota"
              >
                <Cpu size={14} />
              </button>
            )}
          </h2>
        )}
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
                  className={`w-2 h-2 rounded-full flex-shrink-0 ${getStatusColorClass(status)}`}
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
      </div>

      {/* Session History */}
      {!isCollapsed && sessions.length > 0 && (
        <div className="mt-4 pt-3 border-t border-border/50">
          <div className="flex items-center justify-between px-1 mb-2">
            <p className="text-[10px] uppercase tracking-wider text-text-muted font-bold flex items-center gap-1">
              <Clock size={11} className="text-accent" /> Lịch sử hội thoại
            </p>
            <span className="text-[9px] bg-accent/10 text-accent font-medium px-1.5 py-0.5 rounded-full">
              {sessions.length}
            </span>
          </div>
          <div className="flex flex-col gap-1 max-h-48 overflow-y-auto pr-1 text-xs">
            {sessions.slice(0, 15).map((s) => (
              <button
                key={s.session_id}
                onClick={() => onLoadSession?.(s.session_id)}
                title={s.title}
                className="w-full text-left px-2.5 py-2 rounded-lg text-[12px] text-text-muted hover:bg-surface-2 hover:text-text transition-all flex items-center gap-2 group border border-transparent hover:border-border/60"
              >
                <MessageCircle size={13} className="shrink-0 text-accent/60 group-hover:text-accent transition-colors" />
                <span className="truncate flex-1 font-medium">{s.title}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Spacer */}
      <div className="flex-1" />

      {/* User Info + Admin/Logout */}
      {currentUser && !isCollapsed && (
        <div className="px-2 mt-2 mb-2">
          <div className="sidebar-user-block" title={currentUser.full_name}>
            <div className="sidebar-user-avatar">
              {currentUser.full_name?.[0]?.toUpperCase() ?? '?'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-text truncate">{currentUser.full_name}</p>
              <p className="text-[10px] text-text-muted truncate">
                {currentUser.role === 'admin' ? '🛡️ Admin' : currentUser.role === 'account_manager' ? '💼 AM' : '🎯 Sales'}
              </p>
            </div>
          </div>
          <div className="flex gap-1">
            {currentUser.role === 'admin' && onOpenAdminPanel && (
              <button
                onClick={onOpenAdminPanel}
                className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-[11px] font-medium bg-accent/10 hover:bg-accent/20 text-accent transition-colors border border-accent/20"
                title="Admin Panel"
              >
                <ShieldCheck size={11} />
                Admin Panel
              </button>
            )}
            {onLogout && (
              <button
                onClick={onLogout}
                className="flex items-center justify-center gap-1 p-1.5 rounded-lg text-[11px] text-text-muted hover:text-red-400 hover:bg-red-500/10 transition-colors border border-border"
                title="Đăng xuất"
              >
                <LogOut size={12} />
              </button>
            )}
          </div>
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
          <>
            <span
              className={`w-2 h-2 rounded-full ${isConnected ? 'bg-status-completed' : 'bg-status-failed'}`}
              style={{ backgroundColor: isConnected ? 'var(--color-status-completed)' : 'var(--color-status-failed)' }}
            />
            {isConnected ? 'Backend Ready' : 'Backend Offline'}
          </>
        )}
      </div>

      {/* Session Count */}
      {!isCollapsed && (
        <div className="flex items-center gap-2 text-xs text-text-muted px-3">
          <Clock size={14} />
          {sessionCount} sessions
        </div>
      )}

      {/* Bottom controls: Theme toggle + Collapse */}
      <div className={`
        flex items-center gap-2 mt-2 pt-2 border-t border-border
        ${isCollapsed ? 'justify-center' : 'justify-between'}
      `}>
        {/* Theme Toggle */}
        <button
          onClick={onToggleTheme}
          className={`
            flex items-center justify-center gap-2 p-2 rounded-md
            border border-border text-text-muted hover:bg-surface-hover transition-colors
            ${isCollapsed ? 'w-full' : 'flex-1'}
          `}
          title={isDarkMode ? 'Switch to Light mode' : 'Switch to Dark mode'}
        >
          {isDarkMode ? <Sun size={16} /> : <Moon size={16} />}
          {!isCollapsed && (isDarkMode ? 'Light' : 'Dark')}
        </button>

        {/* Collapse/Expand Toggle - always visible on larger screens when needed */}
        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="flex items-center justify-center p-2 rounded-md border border-border text-text-muted hover:bg-surface-hover"
          title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {isCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>
    </aside>
  );
}
