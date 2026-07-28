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
import { ModelPanel } from '../components/ModelPanel';
import { MobileNav } from '../components/MobileNav';
import { AttentionField } from '../components/AttentionField';
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
    setTimeout(() => setIsBooting(false), 950);
  };

  const handleLogout = () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_user');
    setCurrentUser(null);
    setSalespersonName('');
    window.location.reload();
  };

  // Mode state
  const [mode, setMode] = useState<ChatMode>('chat');

  // Theme state - persist to localStorage. Dark is the default: this is a tool
  // people sit in front of for a whole working session, and the product reads as
  // an instrument rather than a document.
  const [isDarkMode, setIsDarkMode] = useState(true);

  // Context panel state — open by default only on large screens
  const [contextPanelOpen, setContextPanelOpen] = useState(false);
  const [modelPanelOpen, setModelPanelOpen] = useState(false);

  // This only controls the mobile drawer (MobileNav) — the desktop/tablet
  // <Sidebar> is shown unconditionally above the md breakpoint by its own
  // wrapper, regardless of this flag. Defaulting to closed means the drawer
  // doesn't cover the chat the instant a phone opens the app.
  const [sidebarOpen, setSidebarOpen] = useState(false);

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
          <p className="tf-boot-line text-xs text-accent-text font-mono tracking-wide">
            ▸ 7 agents online · knowledge base linked
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
        isContextPanelOpen={contextPanelOpen}
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
          onOpenModelPanel={() => setModelPanelOpen(true)}
          currentUser={currentUser}
          onLogout={handleLogout}
          onOpenAdminPanel={() => setAdminPanelOpen(true)}
        />
      </div>

      <ModelPanel isOpen={modelPanelOpen} onClose={() => setModelPanelOpen(false)} />

      {currentUser && (
        <AdminPanel
          isOpen={adminPanelOpen}
          onClose={() => setAdminPanelOpen(false)}
          currentUser={currentUser}
        />
      )}

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
          onAnswerAllQuestions={answerAllQuestions}
          onSkipQuestion={skipQuestion}
          onFreeTextAnswer={freeTextAnswer}
          onApproveCheckpoint={approveCheckpoint}
          onRejectCheckpoint={rejectCheckpoint}
          onEditCheckpoint={editCheckpoint}
          onClearError={clearError}
          onToggleContextPanel={() => setContextPanelOpen(!contextPanelOpen)}
          isContextPanelOpen={contextPanelOpen}
          onToggleMobileSidebar={() => setSidebarOpen(!sidebarOpen)}
          thinkingSteps={thinkingSteps}
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
