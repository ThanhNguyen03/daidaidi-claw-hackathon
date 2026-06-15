# Brainstorm Mode Implementation (Day 7)
# =========================================
# Handles brainstorm sessions with moderator, turn selection, and convergence detection.

import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field


@dataclass
class BrainstormParticipant:
    """Represents an agent participating in brainstorm."""
    agent_name: str
    is_active: bool = False
    rounds_spoken: int = 0
    last_opinion: Optional[str] = None
    opinions: List[str] = field(default_factory=list)


@dataclass
class BrainstormMessage:
    """A message in the brainstorm transcript."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    speaker: str = ""  # agent name or "user"
    content: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    is_user: bool = False


@dataclass
class BrainstormState:
    """State for an active brainstorm session."""
    session_id: str
    participants: Dict[str, BrainstormParticipant] = field(default_factory=dict)
    transcript: List[BrainstormMessage] = field(default_factory=list)
    current_speaker: Optional[str] = None
    ask_lock_holder: Optional[str] = None  # Agent holding the ask-lock
    round_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    is_frozen: bool = False
    is_ended: bool = False

    # Configuration
    max_rounds: int = 8  # Hard cap on rounds
    repeat_threshold: int = 3  # Same opinion >3x → auto-stop
    freeze_timeout_minutes: int = 15  # 15 min no response → freeze
    end_timeout_hours: int = 1  # 1 hr total → auto-end

    def add_participant(self, agent_name: str) -> None:
        """Add an agent to the brainstorm."""
        if agent_name not in self.participants:
            self.participants[agent_name] = BrainstormParticipant(agent_name=agent_name)

    def remove_participant(self, agent_name: str) -> None:
        """Remove an agent from the brainstorm."""
        if agent_name in self.participants:
            del self.participants[agent_name]

    def select_next_speaker(self) -> Optional[str]:
        """Select next speaker using moderator-prioritized relevance."""
        # Get available participants (not current speaker)
        available = [
            p for name, p in self.participants.items()
            if name != self.current_speaker and p.is_active
        ]

        if not available:
            return None

        # Simple round-robin with preference for less-active agents
        # In production, this would use relevance scoring
        available.sort(key=lambda p: p.rounds_spoken)

        next_speaker = available[0].agent_name
        self.current_speaker = next_speaker
        self.participants[next_speaker].is_active = True
        self.participants[next_speaker].rounds_spoken += 1

        return next_speaker

    def add_message(self, speaker: str, content: str, is_user: bool = False) -> BrainstormMessage:
        """Add a message to the transcript."""
        msg = BrainstormMessage(
            speaker=speaker,
            content=content,
            is_user=is_user,
            timestamp=datetime.now()
        )
        self.transcript.append(msg)
        self.last_activity = datetime.now()

        # Track opinions for convergence detection
        if not is_user and speaker in self.participants:
            self.participants[speaker].opinions.append(content)
            self.participants[speaker].last_opinion = content

        return msg

    def check_convergence(self) -> bool:
        """Check if same opinion repeated >threshold times → auto-stop."""
        for participant in self.participants.values():
            if len(participant.opinions) >= self.repeat_threshold:
                # Check last N opinions for similarity
                recent = participant.opinions[-self.repeat_threshold:]
                if self._opinions_similar(recent):
                    return True
        return False

    def _opinions_similar(self, opinions: List[str]) -> bool:
        """Simple similarity check - in production use embeddings/cosine similarity."""
        if len(opinions) < 2:
            return False
        # Simple check: same first 50 chars
        base = opinions[0][:50].lower()
        return all(o[:50].lower() == base for o in opinions[1:])

    def request_ask_lock(self, agent_name: str) -> bool:
        """Request the ask-lock (one agent can ask at a time)."""
        if self.ask_lock_holder is None:
            self.ask_lock_holder = agent_name
            return True
        return False

    def release_ask_lock(self, agent_name: str) -> None:
        """Release the ask-lock."""
        if self.ask_lock_holder == agent_name:
            self.ask_lock_holder = None

    def check_timeouts(self) -> tuple[bool, str]:
        """Check for freeze/end timeouts. Returns (should_stop, reason)."""
        now = datetime.now()
        elapsed = now - self.last_activity

        # Check freeze timeout
        if elapsed > timedelta(minutes=self.freeze_timeout_minutes):
            self.is_frozen = True
            return True, "freeze"

        # Check end timeout
        if now - self.created_at > timedelta(hours=self.end_timeout_hours):
            self.is_ended = True
            return True, "timeout"

        # Check max rounds
        if self.round_count >= self.max_rounds:
            self.is_ended = True
            return True, "max_rounds"

        return False, ""

    def increment_round(self) -> None:
        """Increment round counter."""
        self.round_count += 1

    def get_summary(self) -> str:
        """Generate a summary of the brainstorm session."""
        if not self.transcript:
            return "No discussion occurred."

        summary_parts = [
            f"Brainstorm Session Summary",
            f"Duration: {datetime.now() - self.created_at}",
            f"Rounds: {self.round_count}",
            f"Participants: {', '.join(self.participants.keys())}",
            "",
            "Key Points:"
        ]

        # Extract unique viewpoints
        viewpoints = set()
        for msg in self.transcript:
            if not msg.is_user and msg.speaker in self.participants:
                viewpoints.add(f"{msg.speaker}: {msg.content[:100]}")

        for viewpoint in list(viewpoints)[:5]:  # Limit to 5 key points
            summary_parts.append(f"  • {viewpoint}")

        return "\n".join(summary_parts)


class BrainstormManager:
    """Manages brainstorm sessions."""

    def __init__(self):
        self._sessions: Dict[str, BrainstormState] = {}

    def create_session(
        self,
        session_id: str,
        participants: List[str],
        max_rounds: int = 8
    ) -> BrainstormState:
        """Create a new brainstorm session."""
        state = BrainstormState(
            session_id=session_id,
            max_rounds=max_rounds
        )

        for agent in participants:
            state.add_participant(agent)

        # Set up initial framing message
        state.add_message(
            speaker="moderator",
            content=f"Brainstorm started with: {', '.join(participants)}. "
                   f"Max {max_rounds} rounds. Please discuss the topic."
        )

        self._sessions[session_id] = state
        return state

    def get_session(self, session_id: str) -> Optional[BrainstormState]:
        """Get an existing brainstorm session."""
        return self._sessions.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        """Delete a brainstorm session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def get_active_sessions(self) -> List[str]:
        """Get list of active session IDs."""
        return [
            sid for sid, state in self._sessions.items()
            if not state.is_ended and not state.is_frozen
        ]


# Global instance
_brainstorm_manager: Optional[BrainstormManager] = None


def get_brainstorm_manager() -> BrainstormManager:
    """Get the global brainstorm manager instance."""
    global _brainstorm_manager
    if _brainstorm_manager is None:
        _brainstorm_manager = BrainstormManager()
    return _brainstorm_manager