/**
 * Message Bubble Component
 * ========================
 * Renders individual chat messages with agent avatars.
 */

import React from "react";
import type { Message } from "../lib/types";
import { Bot, User, Sparkles } from "lucide-react";

interface MessageBubbleProps {
  message: Message;
}

const AGENT_COLORS: Record<string, string> = {
  orchestrator: "#6366f1",    // Indigo
  tech_solution: "#8b5cf6",  // Violet
  market_strategy: "#ec4899", // Pink
  account: "#f59e0b",          // Amber
  adtimabox: "#10b981",       // Emerald
  design: "#3b82f6",          // Blue
  system: "#6b7280",          // Gray
};

const AGENT_NAMES: Record<string, string> = {
  orchestrator: "Orchestrator",
  tech_solution: "Tech Solution",
  market_strategy: "Market Strategy",
  account: "Account",
  adtimabox: "AdtimaBox",
  design: "Design",
  system: "System",
};

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const agentName = message.agent ? AGENT_NAMES[message.agent] || message.agent : null;
  const agentColor = message.agent ? AGENT_COLORS[message.agent] || "#6b7280" : null;

  return (
    <div
      className={`flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}
      style={{ marginBottom: "1rem" }}
    >
      {/* Avatar */}
      <div
        className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center"
        style={{
          backgroundColor: isUser ? "#e5e7eb" : agentColor || "#6366f1",
          color: isUser ? "#374151" : "#ffffff",
        }}
      >
        {isUser ? (
          <User size={16} />
        ) : message.agent === "orchestrator" ? (
          <Sparkles size={16} />
        ) : (
          <Bot size={16} />
        )}
      </div>

      {/* Message content */}
      <div
        className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}
        style={{ maxWidth: "70%" }}
      >
        {/* Agent name (for non-user messages) */}
        {!isUser && agentName && (
          <span
            className="text-xs font-medium mb-1"
            style={{ color: agentColor }}
          >
            {agentName}
          </span>
        )}

        {/* Message bubble */}
        <div
          className="px-4 py-2 rounded-lg"
          style={{
            backgroundColor: isUser ? "#3b82f6" : "#f3f4f6",
            color: isUser ? "#ffffff" : "#111827",
            borderRadius: isUser ? "1rem 1rem 0.25rem 1rem" : "1rem 1rem 1rem 0.25rem",
          }}
        >
          <p style={{ whiteSpace: "pre-wrap", lineHeight: 1.6 }}>
            {message.content}
          </p>
        </div>

        {/* Timestamp */}
        <span className="text-xs text-gray-400 mt-1">
          {new Date(message.timestamp).toLocaleTimeString()}
        </span>
      </div>
    </div>
  );
}