/**
 * Main Chat Page
 * ==============
 * Entry point for the AdtimaBox Sales Agent frontend.
 * Uses Tailwind CSS for styling.
 */

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Sidebar } from '../components/Sidebar';
import { ChatWindow } from '../components/ChatWindow';
import { ContextPanel } from '../components/ContextPanel';
import { ModelPanel } from '../components/ModelPanel';
import { AuthModal } from '../components/AuthModal';
import { AdminPanel } from '../components/AdminPanel';
import { useChat } from '../hooks/useChat';
import type { ChatMode, User } from '../lib/types';
import { getApiBaseUrl } from '../lib/api';

export default function Home() {
  // Auth state
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [adminPanelOpen, setAdminPanelOpen] = useState(false);

  // Identity state (for chat hook compatibility)
  const [salespersonName, setSalespersonName] = useState('');
  const [isBooting, setIsBooting] = useState(false);
  const isIdentified = !!currentUser;

  // Load persisted auth from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem('auth_user');
      if (stored) {
        const user = JSON.parse(stored) as User;
        setCurrentUser(user);
        setSalespersonName(user.full_name || user.username);
      }
    } catch { /* ignore */ }
    setAuthChecked(true);
  }, []);

  const handleAuthSuccess = (user: User) => {
    setCurrentUser(user);
    setSalespersonName(user.full_name || user.username);
    setIsBooting(true);
    setTimeout(() => setIsBooting(false), 1850);
  };

  const handleLogout = useCallback(() => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_user');
    setCurrentUser(null);
    setSalespersonName('');
    window.location.reload();
  }, []);

  // Mode state
  const [mode, setMode] = useState<ChatMode>('chat');

  // Theme state - persist to localStorage. Dark is the default: this is a tool
  // people sit in front of for a whole working session, and the product reads as
  // an instrument rather than a document.
  const [isDarkMode, setIsDarkMode] = useState(true);

  // Context panel state — open by default only on large screens
  const [contextPanelOpen, setContextPanelOpen] = useState(false);
  const [modelPanelOpen, setModelPanelOpen] = useState(false);

  // Sidebar drawer state — closed by default on mobile so the drawer does not
  // cover the chat on first paint. Desktop shows the sidebar unconditionally
  // via `md:translate-x-0`, so this only ever matters below the md breakpoint.
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Stable toggle/open/close callbacks — every content event re-renders this
  // component (messages lives in useChat, called from here), and an inline
  // `() => setX(!x)` arrow gets a fresh identity on every one of those
  // renders, which defeats React.memo on every child it's passed to
  // (Sidebar, ContextPanel). The functional-update form also means these
  // never need the current state value as a dependency.
  const toggleSidebar = useCallback(() => setSidebarOpen((v) => !v), []);
  const closeSidebar = useCallback(() => setSidebarOpen(false), []);
  const toggleContextPanel = useCallback(() => setContextPanelOpen((v) => !v), []);
  const openModelPanel = useCallback(() => setModelPanelOpen(true), []);
  const closeModelPanel = useCallback(() => setModelPanelOpen(false), []);
  const openAdminPanel = useCallback(() => setAdminPanelOpen(true), []);
  const closeAdminPanel = useCallback(() => setAdminPanelOpen(false), []);

  // Reads no component state — only the stable getApiBaseUrl import — so it
  // never needs to change identity across renders either.
  const handleDownloadArtifact = useCallback(
    (artifact: { download_url?: string; type?: string; data?: string; id?: string }) => {
      const backendUrl = getApiBaseUrl();

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
    },
    []
  );

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


  // Toggle theme function
  const toggleTheme = useCallback(() => {
    setIsDarkMode((prev) => {
      const newTheme = !prev;
      localStorage.setItem('theme', newTheme ? 'dark' : 'light');
      document.documentElement.classList.toggle('dark', newTheme);
      return newTheme;
    });
  }, []);

  // Apply mode to data attribute
  useEffect(() => {
    document.documentElement.setAttribute('data-mode', mode);
  }, [mode]);

  // Chat hook
  const {
    sessionId,
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
    answerAllQuestions,
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
    loadSession,
    thinkingSteps,
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


  // Handle new chat — clears all session data (both modes) and reloads
  const handleNewChat = useCallback(() => {
    if (typeof window !== 'undefined') {
      Object.keys(sessionStorage)
        .filter((k) => k.startsWith('chat_session_'))
        .forEach((k) => sessionStorage.removeItem(k));
      sessionStorage.removeItem('artifacts');
    }
    resetSession();
    window.location.reload();
  }, [resetSession]);

  // A deleted conversation must not stay on screen: the transcript is gone
  // server-side, so any further message would be answered against no history.
  const handleSessionDeleted = useCallback((deletedId: string) => {
    if (deletedId === sessionId) {
      resetSession();
    }
  }, [sessionId, resetSession]);

  // If auth not checked yet, show nothing (avoid flash)
  if (!authChecked) return null;

  // If not logged in, show Auth Modal
  if (!currentUser) {
    return (
      <div className={isDarkMode ? 'dark' : ''}>
        <AuthModal onSuccess={handleAuthSuccess} />
      </div>
    );
  }

  // If booting (just logged in), show boot animation briefly
  if (isBooting) {
    return (
      <div className={`tf-stage min-h-screen flex items-center justify-center bg-bg p-4 ${isDarkMode ? 'dark' : ''}`}>
        <span className="tf-ring" />
        <span className="tf-ring" />
        <span className="tf-ring" />
        <span className="tf-wipe" />
        <div className="tf-card p-8 rounded-2xl text-center">
          <p className="tf-boot-line text-sm text-accent-text font-mono tracking-wide">
            ▸ 7 Agents đã sẵn sàng · kho tri thức đã kết nối
          </p>
        </div>
      </div>
    );
  }
  // Main app layout
  return (
    <div className="flex flex-col md:flex-row h-dvh overflow-hidden">
      <Sidebar
        currentMode={mode}
        onModeChange={setMode}
        onNewChat={handleNewChat}
        sessionCount={sessionCount}
        isConnected={isConnected}
        activeAgents={activeAgents}
        isOpen={sidebarOpen}
        onToggle={toggleSidebar}
        isDarkMode={isDarkMode}
        onToggleTheme={toggleTheme}
        onOpenModelPanel={openModelPanel}
        currentUser={currentUser}
        onLogout={handleLogout}
        onOpenAdminPanel={openAdminPanel}
        onLoadSession={loadSession}
        onSessionDeleted={handleSessionDeleted}
        isBusy={isLoading}
      />

      {sidebarOpen && (
        <div
          className="md:hidden fixed inset-0 z-40 bg-black/50"
          onClick={closeSidebar}
          aria-hidden="true"
        />
      )}

      <ModelPanel isOpen={modelPanelOpen} onClose={closeModelPanel} />

      {currentUser && (
        <AdminPanel
          isOpen={adminPanelOpen}
          onClose={closeAdminPanel}
          currentUser={currentUser}
        />
      )}

      {/* Main chat area */}
      <main className="flex-1 min-h-0 min-w-0 flex flex-col overflow-hidden">
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
          onAnswerAllQuestions={answerAllQuestions}
          onSkipQuestion={skipQuestion}
          onFreeTextAnswer={freeTextAnswer}
          onApproveCheckpoint={approveCheckpoint}
          onRejectCheckpoint={rejectCheckpoint}
          onEditCheckpoint={editCheckpoint}
          onClearError={clearError}
          onToggleContextPanel={toggleContextPanel}
          isContextPanelOpen={contextPanelOpen}
          onToggleMobileSidebar={toggleSidebar}
          onModeChange={setMode}
          onNewChat={handleNewChat}
          thinkingSteps={thinkingSteps}
        />
      </main>

      {/* Context Panel */}
      <ContextPanel
        isOpen={contextPanelOpen}
        onToggle={toggleContextPanel}
        brief={brief}
        constraints={constraints}
        onRevokeConstraint={revokeConstraint}
        artifacts={artifacts}
        onDownloadArtifact={handleDownloadArtifact}
      />
    </div>
  );
}
