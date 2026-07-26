"""
Sales Assistant Core Schemas
=============================
Core data models for the multi-agent sales assistant.
All schemas are defined using Pydantic for validation and serialization.
"""

from typing import Optional, Literal, Any
from datetime import datetime
from pydantic import BaseModel, Field

# =============================================================================
# Brief Schema - User's request/input
# =============================================================================


class Brief(BaseModel):
    """
    User's initial brief or request.
    Captures all the essential information from the user's message.
    """

    industry: Optional[str] = Field(
        None, description="Industry sector (e.g., F&B, Retail, Tech)"
    )
    budget_vnd: Optional[int] = Field(None, description="Budget in VND")
    goal: Optional[str] = Field(None, description="Core objective or goal")
    timeline: Optional[str] = Field(None, description="Timeline/deadline")
    target_audience: Optional[str] = Field(None, description="Target customers/users")
    specific_requirements: Optional[list[str]] = Field(
        default_factory=list, description="Specific requirements"
    )
    constraints: Optional[list[str]] = Field(
        default_factory=list, description="Known constraints"
    )
    additional_context: Optional[str] = Field(
        None, description="Any additional context"
    )

    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# =============================================================================
# Question Schema - For active questioning mechanism
# =============================================================================


class Question(BaseModel):
    """
    Represents a question asked to the user.
    Used in the QuestionStack mechanism for gathering missing information.
    """

    id: str = Field(..., description="Unique identifier for the question")
    text: str = Field(..., description="The question text to display to user")
    priority: int = Field(1, ge=1, le=5, description="Priority: 1 = highest")
    is_mandatory: bool = Field(
        False, description="Whether this question must be answered to proceed"
    )
    assumption: Optional[str] = Field(
        None, description="Optional context associated with the question"
    )
    target_field: str = Field(
        ..., description="Which brief field this question populates"
    )
    asked_count: int = Field(
        0, description="Number of times this question has been asked"
    )
    last_asked_at: Optional[datetime] = Field(
        None, description="Last time this question was asked"
    )
    options: Optional[list[str]] = Field(
        None, description="Predefined choices for multi-select questions; None = free text"
    )
    answered: bool = Field(False, description="Whether the question has been answered")
    answer: Optional[str] = Field(None, description="The user's answer")
    was_helpful: Optional[bool] = Field(
        None, description="Feedback: was this question helpful"
    )

    def mark_answered(self, answer: str) -> None:
        """Mark the question as answered with the given answer."""
        self.answer = answer
        self.answered = True
        self.asked_count += 1


# =============================================================================
# Agent Output Schema - Standardized output from each agent
# =============================================================================


class NeedsRequest(BaseModel):
    """
    Signal that an agent needs information from another agent.
    Used for the anti-loop mechanism - agent requests sales_orchestrator to invoke another agent.
    """

    agent: str = Field(..., description="Agent name that is needed")
    reason: str = Field(..., description="Why this agent is needed")
    context: dict[str, Any] = Field(
        default_factory=dict, description="Context to pass to the requested agent"
    )


class AgentOutput(BaseModel):
    """
    Standardized output from any agent.
    All agents must return this structure for consistent state management.
    """

    agent: str = Field(..., description="Name of the agent that produced this output")
    status: Literal["COMPLETE", "NEEDS_INPUT", "NEEDS_AGENT", "FAILED"] = Field(
        ..., description="Status of the agent's work"
    )
    payload: dict[str, Any] = Field(
        default_factory=dict, description="The actual result data"
    )
    summary: str = Field(..., description="Short summary for UI/transcript")
    content: str = Field(
        "", description="Full user-facing text for synthesis and transcript rendering"
    )
    confidence: float = Field(0.5, ge=0.0, le=1.0, description="Confidence score 0-1")
    needs: Optional[NeedsRequest] = Field(None, description="Request for another agent")
    questions: list[Question] = Field(
        default_factory=list, description="Questions to ask user"
    )

    def is_complete(self) -> bool:
        return self.status == "COMPLETE"

    def needs_input(self) -> bool:
        return self.status == "NEEDS_INPUT"

    def needs_agent(self) -> bool:
        return self.status == "NEEDS_AGENT"


# =============================================================================
# Validation Report Schema - Output from validation gate
# =============================================================================


class Ambiguity(BaseModel):
    """Represents an ambiguous field in the brief."""

    field: str = Field(..., description="The field with ambiguity")
    interpretations: list[str] = Field(..., description="Possible interpretations")
    why: str = Field(..., description="Why this is ambiguous")


class ValidationReport(BaseModel):
    """
    Output from the validation gate.
    Determines whether the brief is ready for agent dispatch.
    """

    missing_required: list[str] = Field(
        default_factory=list, description="Required fields that are missing"
    )
    ambiguities: list[Ambiguity] = Field(
        default_factory=list, description="Fields with ambiguous values"
    )
    kb_confidence: float = Field(
        1.0, ge=0.0, le=1.0, description="Knowledge base retrieval confidence"
    )
    out_of_scope: bool = Field(False, description="Whether request is out of scope")
    status: Literal["READY", "PENDING", "BLOCKED"] = Field(
        ..., description="Overall validation status"
    )
    severity: Literal["critical", "major", "minor"] = Field(
        "minor", description="Severity of issues found"
    )

    def is_ready(self) -> bool:
        return self.status == "READY"

    def is_blocked(self) -> bool:
        return self.status == "BLOCKED"

    def is_pending(self) -> bool:
        return self.status == "PENDING"


# =============================================================================
# Execution Plan - Agent dispatch plan
# =============================================================================


class AgentTask(BaseModel):
    """A single task to be executed by an agent."""

    agent_name: str = Field(..., description="Name of the agent to invoke")
    task_description: str = Field(..., description="What the agent should do")
    depends_on: list[str] = Field(
        default_factory=list, description="Agent names this depends on"
    )
    is_critical: bool = Field(
        True, description="Whether failure should halt the pipeline"
    )
    parallel_group: int = Field(
        0,
        description=(
            "Execution group. Tasks with the same group number run in parallel. "
            "Groups are executed in ascending order (0 first). "
            "Group 0 = sequential before any parallel groups."
        ),
    )


class ExecutionPlan(BaseModel):
    """Plan for executing agents based on the user's brief."""

    tasks: list[AgentTask] = Field(default_factory=list, description="Tasks to execute")
    execution_mode: Literal["sequential", "parallel", "hybrid"] = Field(
        "sequential", description="How tasks should be executed"
    )
    estimated_duration_minutes: Optional[int] = Field(
        None, description="Estimated completion time"
    )


# =============================================================================
# Checkpoint Schema - Human approval checkpoint
# =============================================================================


class CheckpointAction(BaseModel):
    """An action that requires human approval."""

    type: Literal[
        "generate_pptx",
        "generate_wireframe",
        "generate_userflow",
        "generate_quote",
        "send_external",
        "other",
    ] = Field(..., description="Type of action")
    description: str = Field(..., description="Human-readable description")
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="Action parameters"
    )
    preview: Optional[dict[str, Any]] = Field(
        None, description="Preview of what will be generated"
    )


class Checkpoint(BaseModel):
    """
    Represents a human approval checkpoint.
    The system halts here until user approves, edits, or rejects.
    """

    id: str = Field(..., description="Unique checkpoint ID")
    action: CheckpointAction = Field(..., description="The action requiring approval")
    status: Literal["AWAITING", "APPROVED", "EDITED", "REJECTED", "FAILED"] = Field(
        "AWAITING", description="Current checkpoint status"
    )
    auto_approve_session: bool = Field(
        False,
        description="If true, auto-approve this action type for remainder of session",
    )
    # Preview data (quote, plan, etc.)
    preview: Optional[dict[str, Any]] = Field(
        None, description="Preview data for the checkpoint card"
    )
    # Result after execution
    result: Optional[dict[str, Any]] = Field(
        None, description="Result after action execution"
    )
    # Error if failed
    error: Optional[str] = Field(
        None, description="Error message if action failed"
    )
    # Compliance findings
    compliance_findings: Optional[list[dict[str, Any]]] = Field(
        None, description="Compliance review findings"
    )
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    decided_at: Optional[datetime] = Field(
        None, description="When user made a decision"
    )


# =============================================================================
# Feedback Rules - For memory/learning mechanism
# =============================================================================


class FeedbackRule(BaseModel):
    """
    A rule learned from user feedback.
    Injected into agent prompts to constrain behavior.
    """

    rule_id: str = Field(..., description="Unique rule identifier")
    salesperson_id: str = Field(..., description="Which salesperson this applies to")
    type: Literal["NEGATIVE_CONSTRAINT", "POSITIVE_CONSTRAINT", "PREFERENCE"] = Field(
        ..., description="Type of feedback"
    )
    scope: list[str] = Field(
        ...,
        description="Which agents this applies to (e.g., ['product_solution', 'sales_orchestrator'])",
    )
    rule: str = Field(..., description="The actual rule text")
    source_quote: str = Field(
        ..., description="What the user said that triggered this rule"
    )
    created_at: datetime = Field(default_factory=datetime.now)
    active: bool = Field(True, description="Whether this rule is currently active")


# =============================================================================
# Salesperson Profile - User profile for personalization
# =============================================================================


class ProfileHistoryItem(BaseModel):
    """
    A past case in the salesperson's history.
    Extended for Day 4 to include question/answer tracking.
    """

    case_id: str = Field(..., description="Unique case identifier")
    summary: str = Field(..., description="Brief summary of the case")
    # Day 4: Extended fields for learning
    question: Optional[str] = Field(None, description="Question that was asked")
    answer: Optional[str] = Field(None, description="User's answer")
    helpful: Optional[bool] = Field(None, description="Was the answer helpful")
    timestamp: Optional[str] = Field(None, description="ISO timestamp of the interaction")
    # Legacy fields
    chosen_solution: Optional[str] = Field(None, description="Solution that was chosen")
    outcome: Optional[Literal["won", "lost", "pending"]] = Field(
        None, description="Case outcome"
    )


class SalespersonProfile(BaseModel):
    """
    Profile for a salesperson - stores preferences and learning.
    """

    salesperson_id: str = Field(..., description="Unique identifier")
    display_name: str = Field(..., description="Display name")
    style: Literal["terse", "balanced", "detailed"] = Field(
        "balanced", description="Preferred communication style"
    )
    question_frequency: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description="Ratio of useful question answers to total questions",
    )
    preferences: dict[str, Any] = Field(
        default_factory=dict,
        description="Other preferences (currency, favored solutions, etc.)",
    )
    constraints: list[str] = Field(
        default_factory=list, description="Active feedback rule IDs"
    )
    history: list[ProfileHistoryItem] = Field(
        default_factory=list, description="Past cases"
    )
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# =============================================================================
# Session State - The main state object for LangGraph
# =============================================================================


class SalesCaseState(BaseModel):
    """
    The main state object passed through the LangGraph workflow.
    This is the core state that all agents read from and write to.
    """

    # Core identifiers
    session_id: str = Field(..., description="Unique session identifier")
    salesperson_id: str = Field(..., description="Salesperson identifier")
    participants: list[str] = Field(
        default_factory=list,
        description="Optional brainstorm participants for moderated discussions",
    )

    # Mode and workflow
    mode: str = Field("chat", description="Current runtime mode; normalized to chat")
    brief: Optional[Brief] = Field(None, description="User's brief/request")

    # Validation
    validation_status: Literal["PENDING", "READY", "BLOCKED"] = Field(
        "PENDING", description="Whether brief is ready for agent dispatch"
    )
    validation_report: Optional[ValidationReport] = Field(
        None, description="Latest validation report"
    )

    # Question handling
    question_stack: list[Question] = Field(
        default_factory=list, description="Stack of questions to ask user"
    )

    # Execution
    plan: Optional[ExecutionPlan] = Field(None, description="Execution plan for agents")
    outputs: dict[str, AgentOutput] = Field(
        default_factory=dict, description="Agent outputs keyed by agent name"
    )

    # Anti-loop guard
    visited: list[str] = Field(
        default_factory=list, description="Agents already visited in this workflow"
    )
    hop_depth: int = Field(0, description="Current depth in the agent workflow")

    # Memory & learning
    profile: Optional[SalespersonProfile] = Field(
        None, description="Salesperson profile"
    )
    constraints: list[FeedbackRule] = Field(
        default_factory=list, description="Active feedback rules"
    )

    # Desired output formats requested by the user, if any.
    desired_outputs: list[str] = Field(
        default_factory=list,
        description="Output types requested by the user: pptx, figma, userflow, quote",
    )

    # Checkpoint
    checkpoint: Optional[Checkpoint] = Field(
        None, description="Current checkpoint if any"
    )

    # Messages/transcript
    messages: list[dict[str, Any]] = Field(
        default_factory=list, description="Message history for this session"
    )
    summary: str = Field("", description="Rolling summary of the conversation")

    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Config:
        arbitrary_types_allowed = True
