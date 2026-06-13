/**
 * Sidebar Component
 * =================
 * Left sidebar with mode switcher, new chat, and session history.
 */

import React from 'react';
import {
  MessageCircle,
  ClipboardList,
  Rocket,
  Lightbulb,
  Plus,
  Clock,
  Users,
  Database,
} from 'lucide-react';
import type { ChatMode } from '../lib/types';

interface SidebarProps {
  currentMode: ChatMode;
  onModeChange: (mode: ChatMode) => void;
  onNewChat: () => void;
  sessionCount: number;
  isConnected: boolean;
  activeAgents?: AgentStatus[];
}

interface AgentStatus {
  name: string;
  status: 'idle' | 'thinking' | 'waiting' | 'completed' | 'failed';
}

const MODES: { id: ChatMode; label: string; icon: React.ReactNode; description: string }[] = [
  { id: 'chat', label: 'Chat', icon: <MessageCircle size={18} />, description: 'Q&A & advisory' },
  {
    id: 'planning',
    label: 'Planning',
    icon: <ClipboardList size={18} />,
    description: 'Sales planning',
  },
  {
    id: 'execute',
    label: 'Execute',
    icon: <Rocket size={18} />,
    description: 'Generate proposals',
  },
  {
    id: 'brainstorm',
    label: 'Brainstorm',
    icon: <Lightbulb size={18} />,
    description: 'Group discussion',
  },
];

// Default agents to show
const DEFAULT_AGENTS = ['orchestrator', 'tech_solution', 'market_strategy', 'account'];

// Map agent names to display names
const AGENT_DISPLAY_NAMES: Record<string, string> = {
  orchestrator: 'Orchestrator',
  tech_solution: 'Tech Solution',
  market_strategy: 'Market Strategy',
  account: 'Account',
  adtimabox: 'AdtimaBox',
  design: 'Design',
};

// Get status color
function getStatusColor(status: AgentStatus['status']): string {
  switch (status) {
    case 'thinking':
      return '#f59e0b'; // Amber - processing
    case 'waiting':
      return '#8b5cf6'; // Violet - waiting for user
    case 'completed':
      return '#10b981'; // Green - done
    case 'failed':
      return '#ef4444'; // Red - error
    default:
      return '#6b7280'; // Gray - idle
  }
}

export function Sidebar({
  currentMode,
  onModeChange,
  onNewChat,
  sessionCount,
  isConnected,
  activeAgents = [],
}: SidebarProps) {
  // Create a map of agent statuses
  const agentStatusMap = new Map<string, AgentStatus['status']>();
  activeAgents.forEach((agent) => {
    agentStatusMap.set(agent.name, agent.status);
  });

  return (
    <div
      style={{
        width: '260px',
        height: '100vh',
        backgroundColor: '#ffffff',
        borderRight: '1px solid #e5e7eb',
        display: 'flex',
        flexDirection: 'column',
        padding: '1rem',
      }}
    >
      {/* Logo / Title */}
      <div style={{ marginBottom: '1.5rem' }}>
        <h1 style={{ fontSize: '1.25rem', fontWeight: '700', color: '#111827' }}>Sales AI</h1>
        <p style={{ fontSize: '0.75rem', color: '#6b7280' }}>Multi-Agent Assistant</p>
      </div>

      {/* New Chat Button */}
      <button
        onClick={onNewChat}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '0.5rem',
          width: '100%',
          padding: '0.75rem',
          backgroundColor: '#3b82f6',
          color: '#ffffff',
          border: 'none',
          borderRadius: '0.5rem',
          fontSize: '0.875rem',
          fontWeight: '500',
          cursor: 'pointer',
          marginBottom: '1.5rem',
        }}
      >
        <Plus size={18} />
        New Chat
      </button>

      {/* Mode Switcher */}
      <div style={{ marginBottom: '1.5rem' }}>
        <h2
          style={{
            fontSize: '0.75rem',
            fontWeight: '600',
            color: '#6b7280',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            marginBottom: '0.75rem',
          }}
        >
          Mode
        </h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          {MODES.map((mode) => (
            <button
              key={mode.id}
              onClick={() => onModeChange(mode.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                padding: '0.625rem 0.75rem',
                backgroundColor: currentMode === mode.id ? '#eff6ff' : 'transparent',
                color: currentMode === mode.id ? '#3b82f6' : '#374151',
                border: 'none',
                borderRadius: '0.375rem',
                fontSize: '0.875rem',
                fontWeight: currentMode === mode.id ? '500' : '400',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all 0.15s ease',
              }}
            >
              <span style={{ color: currentMode === mode.id ? '#3b82f6' : '#6b7280' }}>
                {mode.icon}
              </span>
              {mode.label}
            </button>
          ))}
        </div>
      </div>

      {/* Active Agents */}
      <div style={{ marginBottom: '1.5rem' }}>
        <h2
          style={{
            fontSize: '0.75rem',
            fontWeight: '600',
            color: '#6b7280',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            marginBottom: '0.75rem',
          }}
        >
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Users size={14} />
            Active Agents
          </span>
        </h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          {DEFAULT_AGENTS.map((agentName) => {
            const status = agentStatusMap.get(agentName) || 'idle';
            const displayName = AGENT_DISPLAY_NAMES[agentName] || agentName;

            return (
              <div
                key={agentName}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  padding: '0.5rem 0.75rem',
                  fontSize: '0.8125rem',
                  color: '#374151',
                }}
              >
                <span
                  style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    backgroundColor: getStatusColor(status),
                    transition: 'background-color 0.2s ease',
                  }}
                  title={status}
                />
                <span
                  style={{
                    color:
                      status === 'thinking'
                        ? '#f59e0b'
                        : status === 'failed'
                          ? '#ef4444'
                          : '#374151',
                  }}
                >
                  {displayName}
                </span>
                {status === 'thinking' && (
                  <span style={{ fontSize: '0.625rem', color: '#f59e0b' }}>●</span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* KB Status */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          padding: '0.5rem 0.75rem',
          fontSize: '0.75rem',
          color: '#6b7280',
          borderTop: '1px solid #e5e7eb',
          marginTop: '0.5rem',
        }}
      >
        <Database size={14} />
        <span
          style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            backgroundColor: isConnected ? '#10b981' : '#ef4444',
          }}
        />
        {isConnected ? 'KB Connected' : 'KB Offline'}
      </div>

      {/* Session Count */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          padding: '0.5rem 0.75rem',
          fontSize: '0.75rem',
          color: '#6b7280',
        }}
      >
        <Clock size={14} />
        {sessionCount} sessions
      </div>
    </div>
  );
}
