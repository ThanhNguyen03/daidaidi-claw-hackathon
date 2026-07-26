"""
Checkpoint Manager
==================
Manages human-in-the-loop checkpoints for side-effecting actions.

Implements the state machine:
- PREVIEW_BUILT → AWAITING_DECISION → {EXECUTING | RECOMPUTING | REJECTED} → COMPLETED/FAILED

Key features:
- Session-scoped auto-approve (per action type)
- External actions (send_external) always require checkpoint
- No hard timeout - checkpoint persists via checkpointer
- Generic pre_checkpoint_review hook execution
"""

import uuid
from datetime import datetime
from typing import Optional, Any, Callable, Awaitable
from enum import Enum

from schemas.state import Checkpoint, CheckpointAction
from checkpoint.state import CheckpointState, CheckpointTransition, can_auto_approve
from checkpoint.compliance import CompliancePayload, ComplianceFinding


# Type for checkpoint handlers (the actual side-effecting tools)
CheckpointHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class CheckpointManager:
    """
    Manages checkpoint lifecycle and execution.

    Handles:
    - Creating checkpoints with previews
    - Processing user decisions (approve/edit/reject)
    - Running pre_checkpoint_review hooks
    - Session-scoped auto-approve
    """

    def __init__(self):
        self._handlers: dict[str, CheckpointHandler] = {}
        self._auto_approve_session: dict[str, set[str]] = {}  # session_id -> set of action types

    def register_handler(self, action_type: str, handler: CheckpointHandler) -> None:
        """
        Register a handler for an action type.

        Args:
            action_type: The type of action (e.g., "generate_pptx")
            handler: Async function that executes the action
        """
        self._handlers[action_type] = handler

    def set_auto_approve(
        self, session_id: str, action_type: str, enabled: bool = True
    ) -> None:
        """
        Set session-scoped auto-approve for an action type.

        Args:
            session_id: The session ID
            action_type: The type of action
            enabled: Whether to enable auto-approve
        """
        if session_id not in self._auto_approve_session:
            self._auto_approve_session[session_id] = set()

        if enabled:
            # Only allow auto-approve for non-external actions
            if can_auto_approve(action_type):
                self._auto_approve_session[session_id].add(action_type)
        else:
            self._auto_approve_session[session_id].discard(action_type)

    def is_auto_approved(self, session_id: str, action_type: str) -> bool:
        """
        Check if an action type is auto-approved for this session.

        Args:
            session_id: The session ID
            action_type: The type of action

        Returns:
            True if auto-approved for this session
        """
        # External actions are never auto-approved
        if not can_auto_approve(action_type):
            return False

        return action_type in self._auto_approve_session.get(session_id, set())

    def clear_session_auto_approve(self, session_id: str) -> None:
        """
        Clear all auto-approvals for a session.
        Called when a new session starts.

        Args:
            session_id: The session ID
        """
        self._auto_approve_session.pop(session_id, None)

    async def create_checkpoint(
        self,
        session_id: str,
        action: CheckpointAction,
        preview: dict[str, Any],
        compliance_findings: Optional[list[ComplianceFinding]] = None,
    ) -> Checkpoint:
        """
        Create a new checkpoint with preview.

        Args:
            session_id: The session ID
            action: The action requiring approval
            preview: Preview data (quote, plan, etc.)
            compliance_findings: Optional compliance findings from review

        Returns:
            The created Checkpoint
        """
        # Check for session auto-approve
        if self.is_auto_approved(session_id, action.type):
            # Auto-approve: execute immediately without showing checkpoint
            return await self._execute_auto_approved(
                session_id, action, preview, compliance_findings
            )

        # Create checkpoint
        checkpoint = Checkpoint(
            id=f"cp_{uuid.uuid4().hex[:12]}",
            action=action,
            status="AWAITING",
            preview=preview,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        # Attach compliance findings if any
        if compliance_findings:
            # Store findings in checkpoint metadata
            checkpoint.compliance_findings = compliance_findings

            # If there's a blocking finding, disable auto-approve for this checkpoint
            if any(f.severity == "block" for f in compliance_findings):
                checkpoint.auto_approve_session = False

        return checkpoint

    async def _execute_auto_approved(
        self,
        session_id: str,
        action: CheckpointAction,
        preview: dict[str, Any],
        compliance_findings: Optional[list[ComplianceFinding]] = None,
    ) -> Checkpoint:
        """
        Execute an auto-approved action without showing checkpoint.
        """
        handler = self._handlers.get(action.type)
        if not handler:
            raise ValueError(f"No handler registered for action type: {action.type}")

        # Create checkpoint in EXECUTING state
        checkpoint = Checkpoint(
            id=f"cp_{uuid.uuid4().hex[:12]}",
            action=action,
            status="AWAITING",  # Will be updated after execution
            preview=preview,
            auto_approve_session=True,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        try:
            # Execute the handler
            result = await handler(action.parameters)

            # Update checkpoint to completed
            checkpoint.status = "APPROVED"
            checkpoint.result = result
            checkpoint.decided_at = datetime.now()
        except Exception as e:
            checkpoint.status = "REJECTED"
            checkpoint.error = str(e)

        checkpoint.updated_at = datetime.now()
        return checkpoint

    async def process_decision(
        self,
        checkpoint: Checkpoint,
        decision: str,
        params: Optional[dict[str, Any]] = None,
    ) -> Checkpoint:
        """
        Process a user decision on a checkpoint.

        Args:
            checkpoint: The checkpoint to decide on
            decision: One of "approve", "edit", "reject"
            params: Optional parameters for edit decision

        Returns:
            Updated checkpoint
        """
        params = params or {}

        if decision == "approve":
            return await self._approve(checkpoint)
        elif decision == "edit":
            return await self._edit(checkpoint, params)
        elif decision == "reject":
            return await self._reject(checkpoint)
        else:
            raise ValueError(f"Invalid decision: {decision}")

    async def _approve(self, checkpoint: Checkpoint) -> Checkpoint:
        """
        Process APPROVE decision.
        Executes the side-effecting action.
        """
        handler = self._handlers.get(checkpoint.action.type)
        if not handler:
            raise ValueError(f"No handler registered for: {checkpoint.action.type}")

        checkpoint.status = "AWAITING"  # Temporarily await during execution
        checkpoint.updated_at = datetime.now()

        try:
            result = await handler(checkpoint.action.parameters)
            checkpoint.status = "APPROVED"
            checkpoint.result = result
        except Exception as e:
            checkpoint.status = "FAILED"
            checkpoint.error = str(e)

        checkpoint.decided_at = datetime.now()
        checkpoint.updated_at = datetime.now()
        return checkpoint

    async def _edit(
        self, checkpoint: Checkpoint, params: dict[str, Any]
    ) -> Checkpoint:
        """
        Process EDIT decision.
        Re-runs preview computation, does NOT auto-execute.
        """
        # Update action parameters with new values
        checkpoint.action.parameters.update(params)

        # Set status to recompute - caller should regenerate preview
        checkpoint.status = "AWAITING"
        checkpoint.updated_at = datetime.now()

        # Clear any previous result
        checkpoint.result = None
        checkpoint.decided_at = None

        return checkpoint

    async def _reject(self, checkpoint: Checkpoint) -> Checkpoint:
        """
        Process REJECT decision.
        Does NOT execute the action. Returns clarifying question.
        """
        checkpoint.status = "REJECTED"
        checkpoint.decided_at = datetime.now()
        checkpoint.updated_at = datetime.now()

        return checkpoint

    def get_clarifying_question(self, checkpoint: Checkpoint) -> str:
        """
        Get the clarifying question after rejection.

        Returns:
            A single clarifying question
        """
        return (
            f"Action '{checkpoint.action.description}' was rejected. "
            "How would you like to adjust?"
        )


# =============================================================================
# Hook System for Pre-Checkpoint Review
# =============================================================================

class ReviewHook:
    """Base class for pre-checkpoint review hooks."""

    async def run(
        self, state: Any, checkpoint: Checkpoint
    ) -> CompliancePayload:
        """
        Run the review hook.

        Args:
            state: Current SalesCaseState
            checkpoint: The checkpoint being reviewed

        Returns:
            CompliancePayload with findings
        """
        raise NotImplementedError


class ComplianceReviewHook(ReviewHook):
    """Compliance agent review hook."""

    def __init__(self, compliance_agent: Any):
        self.compliance_agent = compliance_agent

    async def run(
        self, state: Any, checkpoint: Checkpoint
    ) -> CompliancePayload:
        """Run compliance review on the pending action."""
        # Get the pending plan/quote from state
        # The compliance agent will analyze and return findings
        # Note: review_checkpoint takes (state, checkpoint)
        return await self.compliance_agent.review_checkpoint(state, checkpoint)


class CheckpointManagerWithHooks(CheckpointManager):
    """
    Extended checkpoint manager with pre-checkpoint review hooks.
    """

    def __init__(self):
        super().__init__()
        self._review_hooks: list[ReviewHook] = []

    def register_review_hook(self, hook: ReviewHook) -> None:
        """
        Register a review hook to run before showing checkpoint.

        Args:
            hook: A ReviewHook instance
        """
        self._review_hooks.append(hook)

    async def run_review_hooks(
        self, state: Any, checkpoint: Checkpoint
    ) -> list[ComplianceFinding]:
        """
        Run all registered review hooks.

        Args:
            state: Current state
            checkpoint: The checkpoint to review

        Returns:
            Combined list of findings from all hooks
        """
        all_findings = []

        for hook in self._review_hooks:
            result = await hook.run(state, checkpoint)
            # Result is an AgentOutput, findings are in payload
            # Extract findings from payload and rebuild ComplianceFinding objects
            findings_data = result.payload.get("findings", []) if result.payload else []
            for f in findings_data:
                if isinstance(f, dict):
                    all_findings.append(ComplianceFinding(**f))
                elif isinstance(f, ComplianceFinding):
                    all_findings.append(f)

        return all_findings


# =============================================================================
# Global Instance
# =============================================================================

_manager: Optional[CheckpointManagerWithHooks] = None


def get_checkpoint_manager() -> CheckpointManagerWithHooks:
    """Get the global checkpoint manager instance."""
    global _manager
    if _manager is None:
        _manager = CheckpointManagerWithHooks()
    return _manager


def set_checkpoint_manager(manager: CheckpointManagerWithHooks) -> None:
    """Set the global checkpoint manager."""
    global _manager
    _manager = manager