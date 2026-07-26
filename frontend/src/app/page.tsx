/**
 * Main Chat Page
 * ==============
 * Entry point for the AdtimaBox Sales Agent frontend.
 * Uses Tailwind CSS for styling.
 */

'use client';

import React, { useState, useEffect } from 'react';
import { Sidebar } from '../components/Sidebar';
import { ChatWindow } from '../components/ChatWindow';
import { ContextPanel } from '../components/ContextPanel';
import { MobileNav } from '../components/MobileNav';
import { AttentionField } from '../components/AttentionField';
import { useChat } from '../hooks/useChat';
import type { ChatMode } from '../lib/types';
import { getApiBaseUrl } from '../lib/api';

export default function Home() {
  // Identity state (demo mode - simple name input)
  const [isIdentified, setIsIdentified] = useState(false);
  const [salespersonName, setSalespersonName] = useState('');
  const [isBooting, setIsBooting] = useState(false);

  // Mode state
  const [mode, setMode] = useState<ChatMode>('chat');

  // Theme state - persist to localStorage. Dark is the default: this is a tool
  // people sit in front of for a whole working session, and the product reads as
  // an instrument rather than a document.
  const [isDarkMode, setIsDarkMode] = useState(true);

  // Context panel state — open by default only on large screens
  const [contextPanelOpen, setContextPanelOpen] = useState(false);

  // Sidebar state for responsive
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // KB connection status
  const [isConnected, setIsConnected] = useState(false);
  const [sessionCount, setSessionCount] = useState(1);

  // Load theme from localStorage on mount. Only an explicit "light" overrides the
  // dark default — the previous version could only ever turn dark ON, so a first
  // visit always rendered light no matter what the default said.
  useEffect(() => {
    const savedTheme = localStorage.getItem('theme');
    const dark = savedTheme !== 'light';
    setIsDarkMode(dark);
    document.documentElement.classList.toggle('dark', dark);
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
    resetSession,
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
          `${getApiBaseUrl()}/health`
        );
        const data = await res.json();
        setIsConnected(data.kb_configured || data.llm_configured || false);
      } catch {
        setIsConnected(false);
      }
    };

    checkConnection();
    const interval = setInterval(checkConnection, 300000);
    return () => clearInterval(interval);
  }, []);

  // Load constraints and profile when identified
  useEffect(() => {
    if (isIdentified && salespersonName) {
      loadConstraints();
      loadProfile();
    }
  }, [isIdentified, salespersonName, loadConstraints, loadProfile]);

  // Handle identity submission. The boot animation runs first, then the app
  // mounts — 950ms, matched to the CSS keyframes in globals.css (.tf-lock).
  const handleIdentify = (e: React.FormEvent) => {
    e.preventDefault();
    if (salespersonName.trim() && !isBooting) {
      setIsBooting(true);
      setTimeout(() => setIsIdentified(true), 950);
    }
  };

  // Handle new chat — clears all session data (both modes) and reloads
  const handleNewChat = () => {
    if (typeof window !== 'undefined') {
      Object.keys(sessionStorage)
        .filter((k) => k.startsWith('chat_session_'))
        .forEach((k) => sessionStorage.removeItem(k));
      sessionStorage.removeItem('artifacts');
    }
    resetSession();
    window.location.reload();
  };

  // If not identified, show welcome screen
  if (!isIdentified) {
    return (
      <div
        className={`tf-stage min-h-screen flex items-center justify-center bg-bg p-4 md:p-6 ${
          isBooting ? 'tf-booting' : ''
        }`}
      >
        <AttentionField />

        {/* Boot overlay: three rings propagating outward, then a horizontal wipe. */}
        {isBooting && (
          <>
            <span className="tf-ring" />
            <span className="tf-ring" />
            <span className="tf-ring" />
            <span className="tf-wipe" />
          </>
        )}

        <div className="tf-card p-5 sm:p-6 md:p-8 rounded-2xl max-w-sm sm:max-w-md w-full mx-2 sm:mx-4">
          <div className="text-center mb-5 sm:mb-6">
            <div className="tf-mark w-16 h-16 sm:w-20 sm:h-20 mx-auto mb-3 sm:mb-4 bg-accent rounded-2xl flex items-center justify-center">
              <span className="text-3xl sm:text-4xl">🤖</span>
            </div>
            <h1 className="text-xl sm:text-[22px] font-bold text-text mb-1.5 sm:mb-2">AdtimaBox Sales Agent</h1>
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
                autoFocus
                disabled={isBooting}
                className="w-full px-4 py-3 sm:py-3.5 border border-border rounded-lg text-sm sm:text-[13px] bg-surface/60 text-text outline-none focus:border-accent focus:ring-2 focus:ring-accent/20 transition-all"
                autoComplete="off"
              />
            </div>

            <button
              type="submit"
              disabled={!salespersonName.trim() || isBooting}
              className={`w-full py-3 sm:py-3.5 rounded-lg font-medium text-sm ${
                salespersonName.trim() && !isBooting
                  ? 'bg-accent text-white hover:opacity-90 active:scale-[0.98] transition-all'
                  : 'bg-text-muted/50 text-white/70 cursor-not-allowed'
              }`}
            >
              {isBooting ? 'Initializing…' : 'Start Chatting'}
            </button>
          </form>

          {isBooting ? (
            <p className="tf-boot-line text-[11px] sm:text-xs text-accent-text text-center mt-4 font-mono tracking-wide">
              ▸ 7 agents online · knowledge base linked
            </p>
          ) : (
            <p className="text-[11px] sm:text-xs text-text-muted text-center mt-4">
              Demo mode — no authentication required
            </p>
          )}
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
          const backendUrl =
            getApiBaseUrl();

          // Binary artifacts served directly by the backend (PPTX, quote, etc.)
          if (artifact.download_url) {
            const a = document.createElement('a');
            a.href = `${backendUrl}${artifact.download_url}`;
            a.target = '_blank';
            a.rel = 'noopener noreferrer';
            // Let the browser use the Content-Disposition filename from the server
            a.click();
            return;
          }

          // Text artifacts stored in-browser (fallback / Mermaid / HTML)
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
          } else if (artifact.type === 'pptx') {
            alert('PPTX file not available — please approve the checkpoint to generate it.');
          }
        }}
      />
    </div>
  );
}
