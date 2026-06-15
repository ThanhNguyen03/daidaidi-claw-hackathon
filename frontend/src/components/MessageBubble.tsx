/**
 * Message Bubble Component
 * ========================
 * Renders individual chat messages with agent avatars.
 * Uses Tailwind CSS for styling.
 */

import React from 'react';
import type { Message } from '../lib/types';
import { Bot, User, Sparkles } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

interface MessageBubbleProps {
  message: Message;
  isGrouped?: boolean;
}

const AGENT_COLORS: Record<string, string> = {
  orchestrator: '#6366f1',
  tech_solution: '#8b5cf6',
  market_strategy: '#ec4899',
  account: '#f59e0b',
  adtimabox: '#10b981',
  design: '#3b82f6',
  system: '#6b7280',
};

const AGENT_NAMES: Record<string, string> = {
  orchestrator: 'Orchestrator',
  tech_solution: 'Tech Solution',
  market_strategy: 'Market Strategy',
  account: 'Account',
  adtimabox: 'AdtimaBox',
  design: 'Design',
  compliance: 'Compliance',
  system: 'System',
};

export function MessageBubble({ message, isGrouped = false }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const agentName = message.agent ? AGENT_NAMES[message.agent] || message.agent : null;
  const agentColor = message.agent ? AGENT_COLORS[message.agent] || '#6b7280' : undefined;

  const showHeader = !isGrouped && !isUser && agentName;

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'} ${isGrouped ? 'mt-1' : 'mt-4'}`}>
      {/* Avatar */}
      {!isGrouped && (
        <div
          className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center"
          style={{
            backgroundColor: isUser ? '#e5e7eb' : agentColor || '#6366f1',
            color: isUser ? '#374151' : '#ffffff',
          }}
        >
          {isUser ? (
            <User size={16} />
          ) : message.agent === 'orchestrator' ? (
            <Sparkles size={16} />
          ) : (
            <Bot size={16} />
          )}
        </div>
      )}

      {/* Spacer for grouped user messages */}
      {isGrouped && isUser && <div className="w-8" />}

      {/* Message content */}
      <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'}`} style={{ maxWidth: '70%' }}>
        {/* Agent name */}
        {showHeader && (
          <span className="text-xs font-medium mb-1 ml-1" style={{ color: agentColor }}>
            {agentName}
          </span>
        )}

        {/* Message bubble */}
        <div
          className="px-4 py-3"
          style={{
            backgroundColor: isUser ? 'var(--color-accent)' : 'var(--color-surface)',
            color: isUser ? '#ffffff' : 'var(--color-text)',
            borderRadius: isUser ? '1rem 1rem 0.25rem 1rem' : '1rem 1rem 1rem 0.25rem',
            boxShadow: 'var(--shadow-sm)',
            border: isUser ? 'none' : '1px solid var(--color-border)',
          }}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap" style={{ lineHeight: 1.6, margin: 0 }}>{message.content}</p>
          ) : (
            <ReactMarkdown
              components={{
                p: ({ children }) => <p style={{ margin: 0, lineHeight: 1.6 }}>{children}</p>,
                ul: ({ children }) => <ul style={{ margin: '0.5rem 0', paddingLeft: '1.25rem' }}>{children}</ul>,
                ol: ({ children }) => <ol style={{ margin: '0.5rem 0', paddingLeft: '1.25rem' }}>{children}</ol>,
                li: ({ children }) => <li style={{ margin: '0.25rem 0' }}>{children}</li>,
                strong: ({ children }) => <strong style={{ fontWeight: 600 }}>{children}</strong>,
                code: ({ children }) => (
                  <code className="bg-surface-2 px-1 py-0.5 rounded text-xs font-mono">
                    {children}
                  </code>
                ),
                pre: ({ children }) => (
                  <pre className="bg-surface-2 p-2 rounded overflow-x-auto text-xs font-mono my-2">
                    {children}
                  </pre>
                ),
              }}
            >
              {message.content}
            </ReactMarkdown>
          )}
        </div>

        {/* Timestamp */}
        {!isGrouped && (
          <span className="text-xs text-gray-400 mt-1 ml-1">
            {new Date(message.timestamp).toLocaleTimeString()}
          </span>
        )}
      </div>
    </div>
  );
}