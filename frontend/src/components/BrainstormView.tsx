/**
 * Brainstorm View Component
 * ==========================
 * UI for brainstorm mode with group bubbles, add-members modal,
 * round/token meter, and ASK-LOCK state display.
 * Uses Tailwind CSS for styling.
 */

'use client';

import React, { useState, useEffect } from 'react';
import { Users, X, Plus, MessageCircle, Lock, Unlock, Clock, AlertCircle, Loader2 } from 'lucide-react';

interface BrainstormParticipant {
  agent_name: string;
  is_active: boolean;
  rounds_spoken: number;
}

interface BrainstormState {
  session_id: string;
  participants: BrainstormParticipant[];
  current_speaker: string | null;
  ask_lock_holder: string | null;
  round_count: number;
  max_rounds: number;
  is_frozen: boolean;
  is_ended: boolean;
}

interface BrainstormViewProps {
  brainState: BrainstormState | null;
  onAddParticipant?: (agentName: string) => void;
  onRemoveParticipant?: (agentName: string) => void;
  onRequestAskLock?: () => void;
  onReleaseAskLock?: () => void;
  onEndSession?: () => void;
}

// Add Member Modal - checkbox list from /debug/agents
function AddMemberModal({
  isOpen,
  onClose,
  onAdd,
}: {
  isOpen: boolean;
  onClose: () => void;
  onAdd: (agentName: string) => void;
}) {
  const [availableAgents, setAvailableAgents] = useState<{ name: string; display_name: string }[]>([]);
  const [selectedAgents, setSelectedAgents] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isOpen) return;

    const fetchAgents = async () => {
      setLoading(true);
      try {
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/debug/agents`
        );
        if (res.ok) {
          const data = await res.json();
          const agents = data.agents?.map((a: { name: string; display_name?: string }) => ({
            name: a.name,
            display_name: a.display_name || a.name,
          })) || [];
          setAvailableAgents(agents);
        }
      } catch (err) {
        console.error('Failed to fetch agents:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchAgents();
  }, [isOpen]);

  const toggleAgent = (name: string) => {
    setSelectedAgents(prev => {
      const newSet = new Set(prev);
      if (newSet.has(name)) {
        newSet.delete(name);
      } else {
        newSet.add(name);
      }
      return newSet;
    });
  };

  const handleAddSelected = () => {
    selectedAgents.forEach(agentName => onAdd(agentName));
    setSelectedAgents(new Set());
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        className="bg-surface rounded-lg p-6 w-full max-w-md shadow-lg border border-border"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-semibold text-text">Add Participants</h3>
          <button onClick={onClose} className="bg-transparent border-none cursor-pointer text-text-muted hover:text-text">
            <X size={20} />
          </button>
        </div>

        {loading ? (
          <div className="flex justify-center py-8">
            <Loader2 size={24} className="animate-spin text-text-muted" />
          </div>
        ) : (
          <>
            <p className="text-sm text-text-muted mb-4">Select agents to participate in the brainstorm:</p>

            <div className="mb-4 max-h-60 overflow-y-auto">
              {availableAgents.map(agent => (
                <label
                  key={agent.name}
                  className={`
                    flex items-center gap-3 p-3 rounded cursor-pointer transition-all
                    ${selectedAgents.has(agent.name)
                      ? 'bg-accent-soft border-accent'
                      : 'bg-transparent border-border hover:bg-surface-hover'
                    }
                    border mb-2
                  `}
                >
                  <input
                    type="checkbox"
                    checked={selectedAgents.has(agent.name)}
                    onChange={() => toggleAgent(agent.name)}
                    className="w-4 h-4 accent-accent"
                  />
                  <div className="flex-1">
                    <span className="text-sm font-medium text-text block">{agent.display_name}</span>
                    <span className="text-xs text-text-muted">{agent.name}</span>
                  </div>
                </label>
              ))}
            </div>

            <div className="flex gap-2 justify-end">
              <button
                onClick={onClose}
                className="px-4 py-2 border border-border rounded text-sm text-text hover:bg-surface-hover"
              >
                Cancel
              </button>
              <button
                onClick={handleAddSelected}
                disabled={selectedAgents.size === 0}
                className={`px-4 py-2 rounded text-sm ${
                  selectedAgents.size > 0
                    ? 'bg-accent text-white hover:opacity-90'
                    : 'bg-text-muted text-white cursor-not-allowed'
                }`}
              >
                Add Selected ({selectedAgents.size})
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// Participant Bubble
function ParticipantBubble({
  participant,
  isCurrentSpeaker,
  isAskLockHolder,
}: {
  participant: BrainstormParticipant;
  isCurrentSpeaker: boolean;
  isAskLockHolder: boolean;
}) {
  return (
    <div
      className={`
        flex flex-col items-center p-4 rounded-xl min-w-28 relative
        ${isCurrentSpeaker ? 'bg-accent-soft border-2 border-accent' : 'bg-surface-2 border border-border'}
      `}
    >
      {isCurrentSpeaker && (
        <div className="absolute -top-2 left-1/2 -translate-x-1/2 bg-accent text-white text-[10px] px-2 py-0.5 rounded-full font-medium">
          Speaking
        </div>
      )}

      {isAskLockHolder && (
        <div className="absolute top-2 right-2 text-status-thinking">
          <Lock size={14} />
        </div>
      )}

      <div className="w-10 h-10 rounded-full bg-accent text-white flex items-center justify-center font-semibold text-base mb-2">
        {participant.agent_name.charAt(0).toUpperCase()}
      </div>

      <span className="text-sm font-medium text-text">{participant.agent_name}</span>
      <span className="text-xs text-text-muted mt-1">{participant.rounds_spoken} rounds</span>
    </div>
  );
}

// Round Meter
function RoundMeter({ current, max }: { current: number; max: number }) {
  const percentage = Math.min((current / max) * 100, 100);

  return (
    <div className="mb-4">
      <div className="flex justify-between mb-1">
        <span className="text-sm font-medium">Round Progress</span>
        <span className="text-sm text-text-muted">{current} / {max}</span>
      </div>
      <div className="h-2 bg-surface-2 rounded-full overflow-hidden">
        <div
          className={`h-full transition-all duration-300 ${percentage >= 100 ? 'bg-status-completed' : 'bg-accent'}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

// ASK-LOCK Status
function AskLockStatus({
  holder,
  onRequest,
  onRelease,
  currentParticipant,
}: {
  holder: string | null;
  onRequest: () => void;
  onRelease: () => void;
  currentParticipant: string;
}) {
  const isHolder = holder === currentParticipant;
  const hasLock = holder !== null;

  return (
    <div
      className={`
        flex items-center justify-between p-3 rounded-lg mb-4
        ${hasLock ? 'bg-yellow-50 border border-yellow-200' : 'bg-surface-2 border border-border'}
      `}
    >
      <div className="flex items-center gap-2">
        {hasLock ? <Lock size={18} className="text-status-thinking" /> : <Unlock size={18} className="text-text-muted" />}
        <div>
          <span className="text-sm font-medium">ASK-LOCK: </span>
          <span className="text-sm text-text-muted">{hasLock ? `Held by ${holder}` : 'Available'}</span>
        </div>
      </div>

      {!isHolder && !hasLock && (
        <button
          onClick={onRequest}
          className="px-3 py-1 bg-accent text-white rounded text-xs cursor-pointer hover:opacity-90"
        >
          Request Lock
        </button>
      )}

      {isHolder && (
        <button
          onClick={onRelease}
          className="px-3 py-1 bg-text-muted text-white rounded text-xs cursor-pointer hover:opacity-90"
        >
          Release Lock
        </button>
      )}
    </div>
  );
}

export function BrainstormView({
  brainState,
  onAddParticipant,
  onRemoveParticipant,
  onRequestAskLock,
  onReleaseAskLock,
  onEndSession,
}: BrainstormViewProps) {
  const [showAddModal, setShowAddModal] = useState(false);

  const state = brainState || {
    session_id: '',
    participants: [],
    current_speaker: null,
    ask_lock_holder: null,
    round_count: 0,
    max_rounds: 8,
    is_frozen: false,
    is_ended: false,
  };

  if (state.is_ended) {
    return (
      <div className="p-8 text-center bg-surface rounded-lg">
        <AlertCircle size={48} className="text-status-completed mx-auto mb-4" />
        <h3 className="text-xl font-semibold mb-2">Brainstorm Session Ended</h3>
        <p className="text-sm text-text-muted">The session has reached its conclusion.</p>
        {onEndSession && (
          <button
            onClick={onEndSession}
            className="mt-4 px-4 py-2 bg-accent text-white rounded text-sm hover:opacity-90"
          >
            Start New Session
          </button>
        )}
      </div>
    );
  }

  if (state.is_frozen) {
    return (
      <div className="p-8 text-center bg-yellow-50 rounded-lg">
        <Clock size={48} className="text-status-thinking mx-auto mb-4" />
        <h3 className="text-xl font-semibold mb-2">Session Frozen</h3>
        <p className="text-sm text-yellow-800">The session has been frozen due to inactivity (15 minutes no response).</p>
      </div>
    );
  }

  return (
    <div className="p-4">
      {/* Header */}
      <div className="flex justify-between items-center mb-4">
        <div className="flex items-center gap-2">
          <MessageCircle size={20} className="text-accent" />
          <h3 className="text-base font-semibold">Brainstorm Mode</h3>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-1 px-3 py-1.5 bg-accent text-white rounded text-xs hover:opacity-90"
        >
          <Plus size={14} />
          Add Member
        </button>
      </div>

      {/* Round Meter */}
      <RoundMeter current={state.round_count} max={state.max_rounds} />

      {/* ASK-LOCK Status */}
      <div>
        <AskLockStatus
          holder={state.ask_lock_holder}
          onRequest={onRequestAskLock || (() => {})}
          onRelease={onReleaseAskLock || (() => {})}
          currentParticipant={state.current_speaker || ''}
        />
      </div>

      {/* Participants */}
      <div className="mb-4">
        <div className="flex items-center gap-2 mb-3">
          <Users size={16} className="text-text-muted" />
          <span className="text-sm font-medium text-text">Participants ({state.participants.length})</span>
        </div>

        {state.participants.length === 0 ? (
          <div className="p-8 text-center bg-surface-2 rounded-lg border border-dashed border-border">
            <p className="text-sm text-text-muted">No participants yet. Click &quot;Add Member&quot; to start.</p>
          </div>
        ) : (
          <div className="flex flex-wrap justify-center gap-4">
            {state.participants.map((participant) => (
              <ParticipantBubble
                key={participant.agent_name}
                participant={participant}
                isCurrentSpeaker={state.current_speaker === participant.agent_name}
                isAskLockHolder={state.ask_lock_holder === participant.agent_name}
              />
            ))}
          </div>
        )}
      </div>

      {/* Current Speaker */}
      {state.current_speaker && (
        <div className="p-3 bg-accent-soft rounded-lg text-center">
          <span className="text-sm text-text-muted">Current speaker: </span>
          <span className="text-sm font-semibold text-accent">{state.current_speaker}</span>
        </div>
      )}

      {/* Add Member Modal */}
      <AddMemberModal
        isOpen={showAddModal}
        onClose={() => setShowAddModal(false)}
        onAdd={onAddParticipant || (() => {})}
      />
    </div>
  );
}