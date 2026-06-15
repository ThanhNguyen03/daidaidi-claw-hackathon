/**
 * Sidebar Component
 * =================
 * Left sidebar with mode switcher, new chat, session history, agent status.
 * Uses Tailwind CSS for styling.
 */

import React, { useState, useEffect } from 'react';
import {
  MessageCircle,
  ClipboardList,
  Rocket,
  Lightbulb,
  Plus,
  Clock,
  Users,
  Database,
  Sun,
  Moon,
  ChevronLeft,
  ChevronRight,
  Menu,
  X,
  Loader2,
} from 'lucide-react';
import type { ChatMode } from '../lib/types';

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
}

interface AgentStatus {
  name: string;
  status: 'idle' | 'thinking' | 'waiting' | 'completed' | 'failed';
}

interface AgentInfo {
  name: string;
  display_name: string;
}

const MODES: { id: ChatMode; label: string; icon: React.ReactNode; description: string }[] = [
  { id: 'chat', label: 'Chat', icon: <MessageCircle size={18} />, description: 'Q&A & advisory' },
  { id: 'planning', label: 'Planning', icon: <ClipboardList size={18} />, description: 'Sales planning' },
  { id: 'execute', label: 'Execute', icon: <Rocket size={18} />, description: 'Generate proposals' },
  { id: 'brainstorm', label: 'Brainstorm', icon: <Lightbulb size={18} />, description: 'Group discussion' },
];

// Map agent names to display names
const AGENT_DISPLAY_NAMES: Record<string, string> = {
  orchestrator: 'Orchestrator',
  tech_solution: 'Tech Solution',
  market_strategy: 'Market Strategy',
  account: 'Account',
  adtimabox: 'AdtimaBox',
  design: 'Design',
  compliance: 'Compliance',
};

// Status color classes
const getStatusColorClass = (status: AgentStatus['status']): string => {
  const classes: Record<AgentStatus['status'], string> = {
    idle: 'bg-status-idle',
    thinking: 'bg-status-thinking',
    waiting: 'bg-status-waiting',
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
  isOpen,
  isDarkMode,
  onToggleTheme,
}: SidebarProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [agentsList, setAgentsList] = useState<AgentInfo[]>([]);
  const [loadingAgents, setLoadingAgents] = useState(false);

  // Fetch agents from /debug/agents on mount
  useEffect(() => {
    const fetchAgents = async () => {
      setLoadingAgents(true);
      try {
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/debug/agents`
        );
        if (res.ok) {
          const data = await res.json();
          const agents = data.agents?.map((a: { name: string; display_name?: string }) => ({
            name: a.name,
            display_name: a.display_name || AGENT_DISPLAY_NAMES[a.name] || a.name,
          })) || [];
          setAgentsList(agents);
        }
      } catch (err) {
        console.error('Failed to fetch agents:', err);
      } finally {
        setLoadingAgents(false);
      }
    };

    fetchAgents();
  }, []);

  // Use fetched agents, fallback to defaults if empty
  const displayAgents = agentsList.length > 0 ? agentsList : [
    { name: 'orchestrator', display_name: 'Orchestrator' },
    { name: 'tech_solution', display_name: 'Tech Solution' },
    { name: 'market_strategy', display_name: 'Market Strategy' },
    { name: 'account', display_name: 'Account' },
    { name: 'adtimabox', display_name: 'AdtimaBox' },
    { name: 'design', display_name: 'Design' },
    { name: 'compliance', display_name: 'Compliance' },
  ];

  // Create a map of agent statuses
  const agentStatusMap = new Map<string, AgentStatus['status']>();
  activeAgents.forEach((agent) => {
    agentStatusMap.set(agent.name, agent.status);
  });

  const sidebarWidth = isCollapsed ? 'w-16' : 'w-64';

  return (
    <aside
      className={`${sidebarWidth} min-h-screen bg-surface border-r border-border flex flex-col p-4 transition-sidebar sticky top-0 z-40 shrink-0`}
    >
      {/* Logo / Title */}
      <div className="mb-6">
        {!isCollapsed && (
          <>
            <h1 className="text-xl font-bold text-text">Sales AI</h1>
            <p className="text-xs text-text-muted">Multi-Agent Assistant</p>
          </>
        )}
        {isCollapsed && (
          <div className="text-center text-xl font-bold text-accent">S</div>
        )}
      </div>

      {/* New Chat Button */}
      <button
        onClick={onNewChat}
        className={`
          flex items-center justify-center gap-2 w-full py-3 bg-accent text-white rounded-lg
          font-medium text-sm mb-6 hover:opacity-90 transition-opacity
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
                text-sm transition-all duration-150
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
              {!isCollapsed && mode.label}
            </button>
          ))}
        </div>
      </div>

      {/* Active Agents */}
      <div className="mb-6">
        {!isCollapsed && (
          <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3 flex items-center gap-2">
            <Users size={14} />
            Active Agents
          </h2>
        )}
        {loadingAgents ? (
          <div className="flex justify-center py-2">
            <Loader2 size={16} className="animate-spin text-text-muted" />
          </div>
        ) : (
          <div className="flex flex-col gap-1">
            {displayAgents.map((agent) => {
              const status = agentStatusMap.get(agent.name) || 'idle';
              const displayName = agent.display_name || AGENT_DISPLAY_NAMES[agent.name] || agent.name;

              return (
                <div
                  key={agent.name}
                  className={`
                    flex items-center gap-2 text-xs
                    ${isCollapsed ? 'justify-center py-2' : 'px-3 py-2'}
                  `}
                  title={displayName}
                >
                  <span
                    className={`w-2 h-2 rounded-full ${getStatusColorClass(status)}`}
                    style={{ backgroundColor: getStatusColorStyle(status) }}
                    title={status}
                  />
                  {!isCollapsed && (
                    <span className={getStatusTextClass(status)} style={{ color: getStatusColorStyle(status) }}>
                      {displayName}
                    </span>
                  )}
                  {status === 'thinking' && !isCollapsed && (
                    <span className="text-xs text-status-thinking">●</span>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Spacer */}
      <div className="flex-1" />

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

        {/* Collapse Toggle - desktop only */}
        {!isCollapsed && (
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="hidden md:flex items-center justify-center p-2 rounded-md border border-border text-text-muted hover:bg-surface-hover"
            title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            <ChevronLeft size={16} />
          </button>
        )}
      </div>

      {/* Expand button when collapsed */}
      {isCollapsed && (
        <button
          onClick={() => setIsCollapsed(false)}
          className="hidden md:flex items-center justify-center p-2 mt-2 rounded-md border border-border text-text-muted hover:bg-surface-hover"
          title="Expand sidebar"
        >
          <ChevronRight size={16} />
        </button>
      )}
    </aside>
  );
}