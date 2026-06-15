/**
 * Main Chat Page
 * ==============
 * Entry point for the Sales AI Assistant frontend.
 * Uses Tailwind CSS for styling.
 */

'use client';

import React, { useState, useEffect } from 'react';
import { Sidebar } from '../components/Sidebar';
import { ChatWindow } from '../components/ChatWindow';
import { ContextPanel } from '../components/ContextPanel';
import { BrainstormView } from '../components/BrainstormView';
import { MobileNav } from '../components/MobileNav';
import { useChat } from '../hooks/useChat';
import type { ChatMode } from '../lib/types';

export default function Home() {
  // Identity state (demo mode - simple name input)
  const [isIdentified, setIsIdentified] = useState(false);
  const [salespersonName, setSalespersonName] = useState('');

  // Mode state
  const [mode, setMode] = useState<ChatMode>('chat');

  // Theme state - persist to localStorage
  const [isDarkMode, setIsDarkMode] = useState(false);

  // Context panel state — open by default only on large screens
  const [contextPanelOpen, setContextPanelOpen] = useState(false);

  // Sidebar state for responsive
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // KB connection status
  const [isConnected, setIsConnected] = useState(false);
  const [sessionCount, setSessionCount] = useState(1);

  // Load theme from localStorage on mount
  useEffect(() => {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
      setIsDarkMode(true);
      document.documentElement.classList.add('dark');
    }
  }, []);

  // Open context panel by default on large screens only
  useEffect(() => {
    if (window.innerWidth >= 1024) {
      setContextPanelOpen(true);
    }
  }, []);

  // Toggle theme function
  const toggleTheme = () => {
    const newTheme = !isDarkMode;
    setIsDarkMode(newTheme);
    localStorage.setItem('theme', newTheme ? 'dark' : 'light');
    if (newTheme) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  };

  // Apply mode to data attribute
  useEffect(() => {
    document.documentElement.setAttribute('data-mode', mode);
  }, [mode]);

  // Chat hook
  const {
    messages,
    isLoading,
    isThinking,
    error,
    pendingQuestions,
    activeCheckpoint,
    activeAgents,
    constraints,
    brief,
    artifacts,
    brainState,
    sendMessage,
    answerQuestion,
    skipQuestion,
    freeTextAnswer,
    revokeConstraint,
    loadConstraints,
    loadProfile,
    approveCheckpoint,
    rejectCheckpoint,
    editCheckpoint,
    clearError,
    addParticipant,
    removeParticipant,
    requestAskLock,
    releaseAskLock,
  } = useChat({
    salespersonId: salespersonName || 'demo_user',
    displayName: salespersonName,
    mode,
  });

  // Check backend connection on mount
  useEffect(() => {
    const checkConnection = async () => {
      try {
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/health`
        );
        const data = await res.json();
        setIsConnected(data.kb_configured || data.llm_configured || false);
      } catch {
        setIsConnected(false);
      }
    };

    checkConnection();
    const interval = setInterval(checkConnection, 30000);
    return () => clearInterval(interval);
  }, []);

  // Load constraints and profile when identified
  useEffect(() => {
    if (isIdentified && salespersonName) {
      loadConstraints();
      loadProfile();
    }
  }, [isIdentified, salespersonName, loadConstraints, loadProfile]);

  // Handle identity submission
  const handleIdentify = (e: React.FormEvent) => {
    e.preventDefault();
    if (salespersonName.trim()) {
      setIsIdentified(true);
    }
  };

  // Handle new chat
  const handleNewChat = () => {
    window.location.reload();
  };

  // If not identified, show welcome screen
  if (!isIdentified) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-bg p-4 md:p-6">
        <div className="bg-surface p-5 sm:p-6 md:p-8 rounded-lg shadow-card max-w-sm sm:max-w-md w-full border border-border mx-2 sm:mx-4">
          <div className="text-center mb-5 sm:mb-6">
            <div className="w-16 h-16 sm:w-20 sm:h-20 mx-auto mb-3 sm:mb-4 bg-accent rounded-2xl flex items-center justify-center">
              <span className="text-3xl sm:text-4xl">🤖</span>
            </div>
            <h1 className="text-xl sm:text-[22px] font-bold text-text mb-1.5 sm:mb-2">Sales AI Assistant</h1>
            <p className="text-xs sm:text-[12px] text-text-muted">Multi-Agent AI for Sales Teams</p>
          </div>

          <form onSubmit={handleIdentify}>
            <div className="mb-4 sm:mb-5">
              <label htmlFor="name" className="block text-xs sm:text-[12px] font-medium text-text mb-2">
                Your Name
              </label>
              <input
                type="text"
                id="name"
                value={salespersonName}
                onChange={(e) => setSalespersonName(e.target.value)}
                placeholder="Enter your name..."
                className="w-full px-4 py-3 sm:py-3.5 border border-border rounded-lg text-sm sm:text-[13px] bg-surface text-text outline-none focus:border-accent focus:ring-2 focus:ring-accent/20 transition-all"
                autoComplete="off"
              />
            </div>

            <button
              type="submit"
              disabled={!salespersonName.trim()}
              className={`w-full py-3 sm:py-3.5 rounded-lg font-medium text-sm ${
                salespersonName.trim()
                  ? 'bg-accent text-white hover:opacity-90 active:scale-[0.98] transition-all'
                  : 'bg-text-muted/50 text-white/70 cursor-not-allowed'
              }`}
            >
              Start Chatting
            </button>
          </form>

          <p className="text-[11px] sm:text-xs text-text-muted text-center mt-4">
            Demo mode — no authentication required
          </p>
        </div>
      </div>
    );
  }

  // Main app layout
  return (
    <div className="flex h-dvh overflow-hidden">
      {/* Mobile Navigation - visible on mobile only */}
      <MobileNav
        currentMode={mode}
        onModeChange={setMode}
        onNewChat={handleNewChat}
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        onToggleContextPanel={() => setContextPanelOpen(!contextPanelOpen)}
      />

      {/* Sidebar - hidden on mobile, shown on desktop */}
      <div className="hidden md:block h-full overflow-y-auto">
        <Sidebar
          currentMode={mode}
          onModeChange={setMode}
          onNewChat={handleNewChat}
          sessionCount={sessionCount}
          isConnected={isConnected}
          activeAgents={activeAgents}
          isOpen={sidebarOpen}
          onToggle={() => setSidebarOpen(!sidebarOpen)}
          isDarkMode={isDarkMode}
          onToggleTheme={toggleTheme}
        />
      </div>

      {/* Main chat area */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden pt-14 md:pt-0 pb-16 md:pb-0">
        {mode === 'brainstorm' ? (
          <BrainstormView
            key={mode}
            brainState={brainState}
            onAddParticipant={addParticipant}
            onRemoveParticipant={removeParticipant}
            onRequestAskLock={requestAskLock}
            onReleaseAskLock={releaseAskLock}
          />
        ) : (
          <ChatWindow
            key={mode}
            messages={messages}
            isLoading={isLoading}
            isThinking={isThinking}
            error={error}
            pendingQuestions={pendingQuestions}
            activeCheckpoint={activeCheckpoint}
            mode={mode}
            onSendMessage={sendMessage}
            onAnswerQuestion={answerQuestion}
            onSkipQuestion={skipQuestion}
            onFreeTextAnswer={freeTextAnswer}
            onApproveCheckpoint={approveCheckpoint}
            onRejectCheckpoint={rejectCheckpoint}
            onEditCheckpoint={editCheckpoint}
            onClearError={clearError}
            onToggleContextPanel={() => setContextPanelOpen(!contextPanelOpen)}
            onToggleMobileSidebar={() => setSidebarOpen(!sidebarOpen)}
          />
        )}
      </main>

      {/* Context Panel */}
      <ContextPanel
        isOpen={contextPanelOpen}
        onToggle={() => setContextPanelOpen(!contextPanelOpen)}
        brief={brief}
        constraints={constraints}
        onRevokeConstraint={revokeConstraint}
        artifacts={artifacts}
        onDownloadArtifact={(artifact) => {
          if (artifact.type === 'userflow' && artifact.data) {
            const blob = new Blob([artifact.data], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${artifact.id || 'userflow'}.mmd`;
            a.click();
            URL.revokeObjectURL(url);
          } else if (artifact.type === 'wireframe' && artifact.data) {
            const blob = new Blob([artifact.data], { type: 'text/html' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${artifact.id || 'wireframe'}.html`;
            a.click();
            URL.revokeObjectURL(url);
          } else {
            console.log('Download not implemented for:', artifact.type);
          }
        }}
      />
    </div>
  );
}