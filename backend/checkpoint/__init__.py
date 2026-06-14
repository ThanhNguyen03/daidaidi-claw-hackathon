"""
Checkpoint Package
==================
Manages human-in-the-loop checkpoints for side-effecting actions.
"""

from checkpoint.manager import get_checkpoint_manager, CheckpointManagerWithHooks
from checkpoint.state import CheckpointState, CheckpointTransition, can_auto_approve
from checkpoint.compliance import CompliancePayload, ComplianceFinding

__all__ = [
    "get_checkpoint_manager",
    "CheckpointManagerWithHooks",
    "CheckpointState",
    "CheckpointTransition",
    "can_auto_approve",
    "CompliancePayload",
    "ComplianceFinding",
]