/**
 * Main Chat Page
 * ==============
 * Entry point for the Sales AI Assistant frontend.
 */

'use client';

import React, { useState, useEffect } from 'react';
import { Sidebar } from '../components/Sidebar';
import { ChatWindow } from '../components/ChatWindow';
import { useChat } from '../hooks/useChat';
import type { ChatMode, Brief } from '../lib/types';

export default function Home() {
  // Identity state (demo mode - simple name input)
  const [isIdentified, setIsIdentified] = useState(false);
  const [salespersonName, setSalespersonName] = useState('');

  // Mode state
  const [mode, setMode] = useState<ChatMode>('chat');

  // KB connection status
  const [isConnected, setIsConnected] = useState(false);
  const [sessionCount, setSessionCount] = useState(1);

  // Chat hook
  const {
    sessionId,
    messages,
    isLoading,
    error,
    pendingQuestions,
    activeCheckpoint,
    activeAgents,
    sendMessage,
    answerQuestion,
    skipQuestion,
    freeTextAnswer,
    approveCheckpoint,
    rejectCheckpoint,
    editCheckpoint,
    clearError,
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
        setIsConnected(data.llm_configured || false);
      } catch {
        setIsConnected(false);
      }
    };

    checkConnection();
    // Check periodically
    const interval = setInterval(checkConnection, 30000);
    return () => clearInterval(interval);
  }, []);

  // Handle identity submission
  const handleIdentify = (e: React.FormEvent) => {
    e.preventDefault();
    if (salespersonName.trim()) {
      setIsIdentified(true);
    }
  };

  // Handle new chat
  const handleNewChat = () => {
    // Reset messages - in real app would create new session
    window.location.reload();
  };

  // If not identified, show welcome screen
  if (!isIdentified) {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: '#f9fafb',
        }}
      >
        <div
          style={{
            backgroundColor: '#ffffff',
            padding: '2rem',
            borderRadius: '1rem',
            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
            maxWidth: '400px',
            width: '100%',
          }}
        >
          <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
            <h1
              style={{
                fontSize: '1.5rem',
                fontWeight: '700',
                color: '#111827',
                marginBottom: '0.5rem',
              }}
            >
              Sales AI Assistant
            </h1>
            <p style={{ color: '#6b7280', fontSize: '0.875rem' }}>Multi-Agent AI for Sales Teams</p>
          </div>

          <form onSubmit={handleIdentify}>
            <div style={{ marginBottom: '1rem' }}>
              <label
                htmlFor="name"
                style={{
                  display: 'block',
                  fontSize: '0.875rem',
                  fontWeight: '500',
                  color: '#374151',
                  marginBottom: '0.5rem',
                }}
              >
                Your Name
              </label>
              <input
                type="text"
                id="name"
                value={salespersonName}
                onChange={(e) => setSalespersonName(e.target.value)}
                placeholder="Enter your name..."
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  border: '1px solid #d1d5db',
                  borderRadius: '0.5rem',
                  fontSize: '1rem',
                  outline: 'none',
                }}
              />
            </div>

            <button
              type="submit"
              disabled={!salespersonName.trim()}
              style={{
                width: '100%',
                padding: '0.75rem',
                backgroundColor: salespersonName.trim() ? '#3b82f6' : '#9ca3af',
                color: '#ffffff',
                border: 'none',
                borderRadius: '0.5rem',
                fontSize: '1rem',
                fontWeight: '500',
                cursor: salespersonName.trim() ? 'pointer' : 'not-allowed',
              }}
            >
              Start Chatting
            </button>
          </form>

          <p
            style={{
              marginTop: '1rem',
              fontSize: '0.75rem',
              color: '#9ca3af',
              textAlign: 'center',
            }}
          >
            Demo mode - no authentication required
          </p>
        </div>
      </div>
    );
  }

  // Main app layout
  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* Sidebar */}
      <Sidebar
        currentMode={mode}
        onModeChange={setMode}
        onNewChat={handleNewChat}
        sessionCount={sessionCount}
        isConnected={isConnected}
        activeAgents={activeAgents}
      />

      {/* Main chat area */}
      <ChatWindow
        messages={messages}
        isLoading={isLoading}
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
      />
    </div>
  );
}
