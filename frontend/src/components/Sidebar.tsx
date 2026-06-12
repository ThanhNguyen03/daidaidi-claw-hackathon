/**
 * Sidebar Component
 * =================
 * Left sidebar with mode switcher, new chat, and session history.
 */

import React, { useState } from "react";
import {
  MessageCircle,
  ClipboardList,
  Rocket,
  Lightbulb,
  Plus,
  Clock,
  Users,
  Database,
} from "lucide-react";
import type { ChatMode } from "../lib/types";

interface SidebarProps {
  currentMode: ChatMode;
  onModeChange: (mode: ChatMode) => void;
  onNewChat: () => void;
  sessionCount: number;
  isConnected: boolean;
}

const MODES: { id: ChatMode; label: string; icon: React.ReactNode; description: string }[] = [
  { id: "chat", label: "Chat", icon: <MessageCircle size={18} />, description: "Q&A & advisory" },
  { id: "planning", label: "Planning", icon: <ClipboardList size={18} />, description: "Sales planning" },
  { id: "execute", label: "Execute", icon: <Rocket size={18} />, description: "Generate proposals" },
  { id: "brainstorm", label: "Brainstorm", icon: <Lightbulb size={18} />, description: "Group discussion" },
];

export function Sidebar({
  currentMode,
  onModeChange,
  onNewChat,
  sessionCount,
  isConnected,
}: SidebarProps) {
  return (
    <div
      style={{
        width: "260px",
        height: "100vh",
        backgroundColor: "#ffffff",
        borderRight: "1px solid #e5e7eb",
        display: "flex",
        flexDirection: "column",
        padding: "1rem",
      }}
    >
      {/* Logo / Title */}
      <div style={{ marginBottom: "1.5rem" }}>
        <h1 style={{ fontSize: "1.25rem", fontWeight: "700", color: "#111827" }}>
          Sales AI
        </h1>
        <p style={{ fontSize: "0.75rem", color: "#6b7280" }}>
          Multi-Agent Assistant
        </p>
      </div>

      {/* New Chat Button */}
      <button
        onClick={onNewChat}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: "0.5rem",
          width: "100%",
          padding: "0.75rem",
          backgroundColor: "#3b82f6",
          color: "#ffffff",
          border: "none",
          borderRadius: "0.5rem",
          fontSize: "0.875rem",
          fontWeight: "500",
          cursor: "pointer",
          marginBottom: "1.5rem",
        }}
      >
        <Plus size={18} />
        New Chat
      </button>

      {/* Mode Switcher */}
      <div style={{ marginBottom: "1.5rem" }}>
        <h2
          style={{
            fontSize: "0.75rem",
            fontWeight: "600",
            color: "#6b7280",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
            marginBottom: "0.75rem",
          }}
        >
          Mode
        </h2>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
          {MODES.map((mode) => (
            <button
              key={mode.id}
              onClick={() => onModeChange(mode.id)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.75rem",
                padding: "0.625rem 0.75rem",
                backgroundColor: currentMode === mode.id ? "#eff6ff" : "transparent",
                color: currentMode === mode.id ? "#3b82f6" : "#374151",
                border: "none",
                borderRadius: "0.375rem",
                fontSize: "0.875rem",
                fontWeight: currentMode === mode.id ? "500" : "400",
                cursor: "pointer",
                textAlign: "left",
                transition: "all 0.15s ease",
              }}
            >
              <span style={{ color: currentMode === mode.id ? "#3b82f6" : "#6b7280" }}>
                {mode.icon}
              </span>
              {mode.label}
            </button>
          ))}
        </div>
      </div>

      {/* Active Agents */}
      <div style={{ marginBottom: "1.5rem" }}>
        <h2
          style={{
            fontSize: "0.75rem",
            fontWeight: "600",
            color: "#6b7280",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
            marginBottom: "0.75rem",
          }}
        >
          <span style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <Users size={14} />
            Active Agents
          </span>
        </h2>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
          {["Orchestrator", "Tech Solution", "Market Strategy", "Account"].map((agent) => (
            <div
              key={agent}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.5rem",
                padding: "0.5rem 0.75rem",
                fontSize: "0.8125rem",
                color: "#374151",
              }}
            >
              <span
                style={{
                  width: "8px",
                  height: "8px",
                  borderRadius: "50%",
                  backgroundColor: "#10b981", // Online/idle
                }}
              />
              {agent}
            </div>
          ))}
        </div>
      </div>

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* KB Status */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0.5rem",
          padding: "0.5rem 0.75rem",
          fontSize: "0.75rem",
          color: "#6b7280",
          borderTop: "1px solid #e5e7eb",
          marginTop: "0.5rem",
        }}
      >
        <Database size={14} />
        <span
          style={{
            width: "8px",
            height: "8px",
            borderRadius: "50%",
            backgroundColor: isConnected ? "#10b981" : "#ef4444",
          }}
        />
        {isConnected ? "KB Connected" : "KB Offline"}
      </div>

      {/* Session Count */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0.5rem",
          padding: "0.5rem 0.75rem",
          fontSize: "0.75rem",
          color: "#6b7280",
        }}
      >
        <Clock size={14} />
        {sessionCount} sessions
      </div>
    </div>
  );
}