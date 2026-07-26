/**
 * Sidebar Component
 * =================
 * Left sidebar with mode switcher, new chat, session history, agent status.
 * Uses Tailwind CSS for styling.
 */

import React, { useState } from 'react';
import {
  MessageCircle,
  ClipboardList,
  Rocket,
  Lightbulb,
  Headphones,
  Plus,
  Clock,
  Users,
  Database,
  Sun,
  Moon,
  ChevronLeft,
  ChevronRight,
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


const MODES: { id: ChatMode; label: string; icon: React.ReactNode; description: string; comingSoon?: boolean }[] = [
  { id: 'chat', label: 'Chat', icon: <MessageCircle size={18} />, description: 'Q&A & advisory' },
  { id: 'cs', label: 'Customer Services', icon: <Headphones size={18} />, description: 'Customer Service' },
  { id: 'planning', label: 'Planning', icon: <ClipboardList size={18} />, description: 'Coming soon', comingSoon: true },
  { id: 'execute', label: 'Execute', icon: <Rocket size={18} />, description: 'Coming soon', comingSoon: true },
  { id: 'brainstorm', label: 'Brainstorm', icon: <Lightbulb size={18} />, description: 'Coming soon', comingSoon: true },
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
  isOpen = true,
  isDarkMode,
  onToggleTheme,
}: SidebarProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);

  const displayAgents = currentMode === 'cs' ? CS_AGENTS : SALE_AGENTS;

  // Create a map of agent statuses
  const agentStatusMap = new Map<string, AgentStatus['status']>();
  activeAgents.forEach((agent) => {
    agentStatusMap.set(agent.name, agent.status);
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
              onClick={() => {
                if (!mode.comingSoon) {
                  onModeChange(mode.id);
                }
              }}
              disabled={mode.comingSoon}
              className={`
                flex items-center gap-3 rounded-md py-2.5 cursor-pointer
                text-[12px] transition-all duration-150
                ${currentMode === mode.id
                  ? 'bg-accent-soft text-accent font-medium'
                  : 'text-text hover:bg-surface-hover'
                }
                ${mode.comingSoon ? 'opacity-60 cursor-not-allowed' : ''}
                ${isCollapsed ? 'justify-center px-2' : 'px-3 justify-start'}
              `}
              title={mode.description}
            >
              <span className={currentMode === mode.id ? 'text-accent' : 'text-text-muted'}>
                {mode.icon}
              </span>
              {!isCollapsed && (
                <span className="flex items-center gap-2">
                  {mode.label}
                  {mode.comingSoon && (
                    <span className="text-[10px] uppercase tracking-wide text-orange-500 font-medium border border-neutral-800/10 rounded-full px-2 py-0.5">
                      Soon
                    </span>
                  )}
                </span>
              )}
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
        <div className="flex flex-col gap-1">
          {displayAgents.map((agent) => {
            const status = agentStatusMap.get(agent.name) || 'idle';

            return (
              <div
                key={agent.name}
                className={`
                  flex items-center gap-2 text-xs
                  ${isCollapsed ? 'justify-center py-2' : 'px-3 py-2'}
                `}
                title={agent.display_name}
              >
                <span
                  className={`w-2 h-2 rounded-full ${getStatusColorClass(status)}`}
                  style={{ backgroundColor: getStatusColorStyle(status) }}
                  title={status}
                />
                {!isCollapsed && (
                  <span className={getStatusTextClass(status)} style={{ color: getStatusColorStyle(status) }}>
                    {agent.display_name}
                  </span>
                )}
                {status === 'thinking' && !isCollapsed && (
                  <span className="text-xs text-status-thinking">●</span>
                )}
              </div>
            );
          })}
        </div>
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
