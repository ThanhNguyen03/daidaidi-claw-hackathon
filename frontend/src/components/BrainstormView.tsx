/**
 * Brainstorm View Component
 * ==========================
 * UI for brainstorm mode with group bubbles, add-members modal,
 * round/token meter, and ASK-LOCK state display.
 */

'use client';

import React, { useState, useEffect } from 'react';
import { Users, X, Plus, MessageCircle, Lock, Unlock, Clock, AlertCircle } from 'lucide-react';

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

// Add Member Modal Component
function AddMemberModal({
  isOpen,
  onClose,
  onAdd,
}: {
  isOpen: boolean;
  onClose: () => void;
  onAdd: (agentName: string) => void;
}) {
  const [agentName, setAgentName] = useState('');

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (agentName.trim()) {
      onAdd(agentName.trim());
      setAgentName('');
      onClose();
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
      }}
      onClick={onClose}
    >
      <div
        style={{
          backgroundColor: 'white',
          borderRadius: '0.5rem',
          padding: '1.5rem',
          width: '100%',
          maxWidth: '400px',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
          <h3 style={{ fontSize: '1.125rem', fontWeight: '600' }}>Add Participant</h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer' }}>
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '1rem' }}>
            <label
              htmlFor="agentName"
              style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', marginBottom: '0.5rem' }}
            >
              Agent Name
            </label>
            <input
              type="text"
              id="agentName"
              value={agentName}
              onChange={(e) => setAgentName(e.target.value)}
              placeholder="Enter agent name..."
              style={{
                width: '100%',
                padding: '0.5rem',
                border: '1px solid #d1d5db',
                borderRadius: '0.375rem',
                fontSize: '0.875rem',
              }}
            />
          </div>

          <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                padding: '0.5rem 1rem',
                border: '1px solid #d1d5db',
                borderRadius: '0.375rem',
                backgroundColor: 'white',
                fontSize: '0.875rem',
                cursor: 'pointer',
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!agentName.trim()}
              style={{
                padding: '0.5rem 1rem',
                backgroundColor: agentName.trim() ? '#3b82f6' : '#9ca3af',
                color: 'white',
                border: 'none',
                borderRadius: '0.375rem',
                fontSize: '0.875rem',
                cursor: agentName.trim() ? 'pointer' : 'not-allowed',
              }}
            >
              Add
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// Participant Bubble Component
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
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: '1rem',
        backgroundColor: isCurrentSpeaker ? '#eff6ff' : '#f9fafb',
        border: isCurrentSpeaker ? '2px solid #3b82f6' : '1px solid #e5e7eb',
        borderRadius: '0.75rem',
        minWidth: '120px',
        position: 'relative',
      }}
    >
      {/* Current speaker indicator */}
      {isCurrentSpeaker && (
        <div
          style={{
            position: 'absolute',
            top: '-8px',
            left: '50%',
            transform: 'translateX(-50%)',
            backgroundColor: '#3b82f6',
            color: 'white',
            fontSize: '0.625rem',
            padding: '0.125rem 0.5rem',
            borderRadius: '9999px',
            fontWeight: '500',
          }}
        >
          Speaking
        </div>
      )}

      {/* Ask lock indicator */}
      {isAskLockHolder && (
        <div style={{ position: 'absolute', top: '0.5rem', right: '0.5rem', color: '#f59e0b' }}>
          <Lock size={14} />
        </div>
      )}

      <div
        style={{
          width: '40px',
          height: '40px',
          borderRadius: '50%',
          backgroundColor: '#3b82f6',
          color: 'white',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontWeight: '600',
          fontSize: '1rem',
          marginBottom: '0.5rem',
        }}
      >
        {participant.agent_name.charAt(0).toUpperCase()}
      </div>

      <span style={{ fontSize: '0.875rem', fontWeight: '500', color: '#111827' }}>
        {participant.agent_name}
      </span>

      <span style={{ fontSize: '0.75rem', color: '#6b7280', marginTop: '0.25rem' }}>
        {participant.rounds_spoken} rounds
      </span>
    </div>
  );
}

// Round Meter Component
function RoundMeter({ current, max }: { current: number; max: number }) {
  const percentage = Math.min((current / max) * 100, 100);

  return (
    <div style={{ marginBottom: '1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
        <span style={{ fontSize: '0.875rem', fontWeight: '500' }}>Round Progress</span>
        <span style={{ fontSize: '0.875rem', color: '#6b7280' }}>
          {current} / {max}
        </span>
      </div>
      <div
        style={{
          height: '8px',
          backgroundColor: '#e5e7eb',
          borderRadius: '9999px',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            height: '100%',
            backgroundColor: percentage >= 100 ? '#10b981' : '#3b82f6',
            width: `${percentage}%`,
            transition: 'width 0.3s ease',
          }}
        />
      </div>
    </div>
  );
}

// ASK-LOCK Status Component
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
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0.75rem',
        backgroundColor: hasLock ? '#fef3c7' : '#f9fafb',
        border: '1px solid',
        borderColor: hasLock ? '#fcd34d' : '#e5e7eb',
        borderRadius: '0.5rem',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        {hasLock ? <Lock size={18} color="#f59e0b" /> : <Unlock size={18} color="#6b7280" />}
        <div>
          <span style={{ fontSize: '0.875rem', fontWeight: '500' }}>ASK-LOCK: </span>
          <span style={{ fontSize: '0.875rem', color: '#6b7280' }}>
            {hasLock ? `Held by ${holder}` : 'Available'}
          </span>
        </div>
      </div>

      {!isHolder && !hasLock && (
        <button
          onClick={onRequest}
          style={{
            padding: '0.25rem 0.75rem',
            backgroundColor: '#3b82f6',
            color: 'white',
            border: 'none',
            borderRadius: '0.375rem',
            fontSize: '0.75rem',
            cursor: 'pointer',
          }}
        >
          Request Lock
        </button>
      )}

      {isHolder && (
        <button
          onClick={onRelease}
          style={{
            padding: '0.25rem 0.75rem',
            backgroundColor: '#6b7280',
            color: 'white',
            border: 'none',
            borderRadius: '0.375rem',
            fontSize: '0.75rem',
            cursor: 'pointer',
          }}
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

  // Default state when no session exists
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
      <div
        style={{
          padding: '2rem',
          textAlign: 'center',
          backgroundColor: '#f9fafb',
          borderRadius: '0.5rem',
        }}
      >
        <AlertCircle size={48} color="#10b981" style={{ marginBottom: '1rem', margin: '0 auto' }} />
        <h3 style={{ fontSize: '1.25rem', fontWeight: '600', marginBottom: '0.5rem' }}>
          Brainstorm Session Ended
        </h3>
        <p style={{ color: '#6b7280', fontSize: '0.875rem' }}>
          The session has reached its conclusion.
        </p>
        {onEndSession && (
          <button
            onClick={onEndSession}
            style={{
              marginTop: '1rem',
              padding: '0.5rem 1rem',
              backgroundColor: '#3b82f6',
              color: 'white',
              border: 'none',
              borderRadius: '0.375rem',
              fontSize: '0.875rem',
              cursor: 'pointer',
            }}
          >
            Start New Session
          </button>
        )}
      </div>
    );
  }

  if (state.is_frozen) {
    return (
      <div
        style={{
          padding: '2rem',
          textAlign: 'center',
          backgroundColor: '#fef3c7',
          borderRadius: '0.5rem',
        }}
      >
        <Clock size={48} color="#f59e0b" style={{ marginBottom: '1rem', margin: '0 auto' }} />
        <h3 style={{ fontSize: '1.25rem', fontWeight: '600', marginBottom: '0.5rem' }}>
          Session Frozen
        </h3>
        <p style={{ color: '#92400e', fontSize: '0.875rem' }}>
          The session has been frozen due to inactivity (15 minutes no response).
        </p>
      </div>
    );
  }

  return (
    <div style={{ padding: '1rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <MessageCircle size={20} color="#3b82f6" />
          <h3 style={{ fontSize: '1rem', fontWeight: '600' }}>Brainstorm Mode</h3>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.25rem',
            padding: '0.25rem 0.75rem',
            backgroundColor: '#3b82f6',
            color: 'white',
            border: 'none',
            borderRadius: '0.375rem',
            fontSize: '0.75rem',
            cursor: 'pointer',
          }}
        >
          <Plus size={14} />
          Add Member
        </button>
      </div>

      {/* Round Meter */}
      <RoundMeter current={state.round_count} max={state.max_rounds} />

      {/* ASK-LOCK Status */}
      <div style={{ marginBottom: '1rem' }}>
        <AskLockStatus
          holder={state.ask_lock_holder}
          onRequest={onRequestAskLock || (() => {})}
          onRelease={onReleaseAskLock || (() => {})}
          currentParticipant={state.current_speaker || ''}
        />
      </div>

      {/* Participant Bubbles */}
      <div style={{ marginBottom: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
          <Users size={16} color="#6b7280" />
          <span style={{ fontSize: '0.875rem', fontWeight: '500', color: '#374151' }}>
            Participants ({state.participants.length})
          </span>
        </div>

        {state.participants.length === 0 ? (
          <div
            style={{
              padding: '2rem',
              textAlign: 'center',
              backgroundColor: '#f9fafb',
              borderRadius: '0.5rem',
              border: '1px dashed #d1d5db',
            }}
          >
            <p style={{ color: '#6b7280', fontSize: '0.875rem' }}>
              No participants yet. Click "Add Member" to start.
            </p>
          </div>
        ) : (
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: '1rem',
              justifyContent: 'center',
            }}
          >
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

      {/* Current Speaker Indicator */}
      {state.current_speaker && (
        <div
          style={{
            padding: '0.75rem',
            backgroundColor: '#eff6ff',
            borderRadius: '0.5rem',
            textAlign: 'center',
          }}
        >
          <span style={{ fontSize: '0.875rem', color: '#6b7280' }}>Current speaker: </span>
          <span style={{ fontSize: '0.875rem', fontWeight: '600', color: '#3b82f6' }}>
            {state.current_speaker}
          </span>
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