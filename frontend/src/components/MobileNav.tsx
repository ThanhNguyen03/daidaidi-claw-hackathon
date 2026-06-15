/**
 * Mobile Navigation Component
 * ============================
 * Bottom navigation bar for mobile/tablet screens.
 * Replaces sidebar on small screens.
 */

import React from 'react';
import { MessageCircle, ClipboardList, Rocket, Lightbulb, Plus, Menu, X, PanelRightClose } from 'lucide-react';
import type { ChatMode } from '../lib/types';

interface MobileNavProps {
  currentMode: ChatMode;
  onModeChange: (mode: ChatMode) => void;
  onNewChat: () => void;
  isOpen: boolean;
  onToggle: () => void;
  onToggleContextPanel?: () => void;
}

const MODES: { id: ChatMode; icon: React.ReactNode; label: string }[] = [
  { id: 'chat', icon: <MessageCircle size={20} />, label: 'Chat' },
  { id: 'planning', icon: <ClipboardList size={20} />, label: 'Plan' },
  { id: 'execute', icon: <Rocket size={20} />, label: 'Execute' },
  { id: 'brainstorm', icon: <Lightbulb size={20} />, label: 'Brain' },
];

export function MobileNav({
  currentMode,
  onModeChange,
  onNewChat,
  isOpen,
  onToggle,
  onToggleContextPanel,
}: MobileNavProps) {
  return (
    <>
      {/* Mobile menu toggle - visible on small screens */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-3 py-2.5 bg-surface border-b border-border safe-area-inset-top">
        <button
          onClick={onToggle}
          className="p-2 -ml-1 border border-transparent hover:border-border hover:bg-surface-hover rounded-lg transition-all"
        >
          {isOpen ? <X size={22} /> : <Menu size={22} />}
        </button>
        <span className="text-sm font-semibold text-text">Sales AI</span>
        <div className="flex items-center gap-0.5">
          {onToggleContextPanel && (
            <button
              onClick={onToggleContextPanel}
              className="p-2.5 text-text-muted hover:text-text hover:bg-surface-hover rounded-lg transition-all"
              title="Context Panel"
            >
              <PanelRightClose size={20} />
            </button>
          )}
          <button
            onClick={onNewChat}
            className="p-2.5 text-accent hover:bg-accent/10 rounded-lg transition-all"
            title="New Chat"
          >
            <Plus size={22} />
          </button>
        </div>
      </div>

      {/* Mobile menu overlay */}
      {isOpen && (
        <div
          className="md:hidden fixed inset-0 top-[52px] bg-black/40 z-30"
          onClick={onToggle}
        />
      )}

      {/* Sidebar drawer on mobile */}
      <div
        className={`
          md:hidden fixed top-[52px] left-0 bottom-16 w-64 bg-surface border-r border-border z-40
          transform transition-transform duration-200 ease-out shadow-xl
          ${isOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        <div className="p-4 overflow-y-auto h-full">
          <div className="mb-6">
            <h1 className="text-[18px] font-bold text-text mb-1">Sales AI</h1>
            <p className="text-xs text-text-muted">Multi-Agent Assistant</p>
          </div>

          <div className="flex flex-col gap-1 mb-6">
            {MODES.map((mode) => (
              <button
                key={mode.id}
                onClick={() => {
                  onModeChange(mode.id);
                  onToggle();
                }}
                className={`
                  flex items-center gap-3 rounded-md py-2.5 px-3 cursor-pointer
                  text-sm transition-all duration-150
                  ${currentMode === mode.id
                    ? 'bg-accent-soft text-accent font-medium'
                    : 'text-text hover:bg-surface-hover'
                  }
                `}
              >
                <span className={currentMode === mode.id ? 'text-accent' : 'text-text-muted'}>
                  {mode.icon}
                </span>
                {mode.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Bottom navigation - visible on mobile only */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-surface border-t border-border safe-area-inset-bottom">
        <div className="flex items-center justify-around py-1.5 pb-safe">
          {MODES.map((mode) => (
            <button
              key={mode.id}
              onClick={() => onModeChange(mode.id)}
              className={`
                flex flex-col items-center gap-1 px-2 sm:px-3 py-2 rounded-lg transition-all
                ${currentMode === mode.id
                  ? 'text-accent bg-accent/10'
                  : 'text-text-muted hover:text-text'
                }
              `}
            >
              {mode.icon}
              <span className="text-[10px] sm:text-[11px]">{mode.label}</span>
            </button>
          ))}
        </div>
      </nav>

      {/* Spacer for fixed bottom nav */}
      <div className="md:hidden h-14 sm:h-16" />
    </>
  );
}