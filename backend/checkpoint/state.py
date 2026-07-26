"""
Checkpoint State Machine
=========================
Defines the checkpoint states and transitions.

States:
- PREVIEW_BUILT: Preview computed, waiting for user decision
- AWAITING_DECISION: Checkpoint card shown to user
- EXECUTING: User approved, action is running
- RECOMPUTING: User edited, re-computing preview
- REJECTED: User rejected, waiting for clarification
- COMPLETED: Action finished successfully
- FAILED: Action failed
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class CheckpointState(str, Enum):
    """Checkpoint state enumeration."""

    PREVIEW_BUILT = "PREVIEW_BUILT"
    AWAITING_DECISION = "AWAITING_DECISION"
    EXECUTING = "EXECUTING"
    RECOMPUTING = "RECOMPUTING"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class CheckpointTransition(BaseModel):
    """Records a state transition for audit."""

    from_state: CheckpointState
    to_state: CheckpointState
    timestamp: datetime = Field(default_factory=datetime.now)
    reason: Optional[str] = None
    actor: Optional[str] = None  # "user", "system", "auto_approve"


# External actions that always require checkpoint (never auto-approve)
EXTERNAL_ACTION_TYPES = {"send_external", "email", "webhook"}


def can_auto_approve(action_type: str) -> bool:
    """
    Check if an action type can be auto-approved.
    External actions are excluded from auto-approve.

    Args:
        action_type: The type of action

    Returns:
        True if auto-approve is allowed for this action type
    """
    return action_type not in EXTERNAL_ACTION_TYPES