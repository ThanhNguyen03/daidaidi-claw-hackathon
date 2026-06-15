"""
Orchestrator Supervisor Node
============================
The orchestrator is the supervisor node in the LangGraph workflow.
It owns the execution plan, makes routing decisions, handles validation gate, and manages the anti-loop guard.

Implements C.5 §3: Orchestrator gate with validation states (BLOCKED/PENDING/READY).
"""

from typing import Optional
import uuid

from schemas.state import (
    SalesCaseState,
    AgentOutput,
    ExecutionPlan,
    AgentTask,
    NeedsRequest,
    Question,
    Brief,
)
from agents.registry import get_registry

# Import validation (Day 3)
from validation.validator import get_validation_service
from validation.question_stack import get_question_manager

# =============================================================================
# Constants
# =============================================================================

# Maximum hop depth to prevent infinite loops (A.1 / B.4)
DEFAULT_MAX_HOP_DEPTH = 4


# =============================================================================
# Orchestrator Functions
# =============================================================================


class Orchestrator:
    """
    Orchestrator supervisor node.

    This is NOT a separate service - it's a node function re-entered at
    each routing point in the LangGraph workflow (A.3 Q3).
    """

    def __init__(self, max_hop_depth: int = DEFAULT_MAX_HOP_DEPTH):
        self.max_hop_depth = max_hop_depth

    async def validate_before_dispatch(
        self, state: SalesCaseState
    ) -> tuple[AgentOutput, bool]:
        """
        C.5 §3: Validation gate - runs before any agent dispatch.

        Returns (agent_output, should_dispatch):
        - BLOCKED: returns error output, should_dispatch = False
        - PENDING: returns question output, should_dispatch = False
        - READY: returns continue output, should_dispatch = True
        """
        # If no brief, can't validate - proceed to dispatch
        if not state.brief:
            state.validation_status = "READY"
            return (
                AgentOutput(
                    agent="orchestrator",
                    status="COMPLETE",
                    payload={"validation_status": "READY"},
                    summary="No brief to validate - proceeding",
                    confidence=1.0,
                ),
                True,
            )

        # Check if we have questions already pending
        question_manager = get_question_manager()
        if question_manager.stack.has_mandatory_unanswered():
            # There are pending questions - don't dispatch
            state.validation_status = "PENDING"
            questions = question_manager.stack.next_batch()

            return (
                AgentOutput(
                    agent="orchestrator",
                    status="NEEDS_INPUT",
                    payload={
                        "validation_status": "PENDING",
                        "question_count": len(questions),
                    },
                    summary="Please answer the pending questions to proceed.",
                    confidence=1.0,
                    questions=questions,
                ),
                False,
            )

        # Run validation
        validation_service = get_validation_service()
        validation_report = await validation_service.validate(
            brief=state.brief,
            profile=state.profile,
            mode=state.mode,
        )

        state.validation_report = validation_report
        state.validation_status = validation_report.status

        # Handle different statuses
        if validation_report.status == "BLOCKED":
            # Out-of-scope or truly unrecoverable — hard stop
            return (
                AgentOutput(
                    agent="orchestrator",
                    status="FAILED",
                    payload={
                        "validation_status": "BLOCKED",
                        "missing_required": validation_report.missing_required,
                    },
                    summary="This request is out of scope. Please provide a valid sales brief.",
                    confidence=1.0,
                ),
                False,
            )

        elif validation_report.status == "PENDING":
            # Missing some fields — generate questions but STILL allow dispatch.
            # Agents are smart enough to work with partial info.
            question_manager = get_question_manager()
            questions = question_manager.generate_questions_from_validation(
                brief=state.brief,
                mode=state.mode,
                validation_missing=validation_report.missing_required,
                validation_ambiguities=validation_report.ambiguities,
            )
            question_manager.stack.push(questions)
            state.question_stack = question_manager.stack.items
            batch = question_manager.stack.next_batch()

            # Return NEEDS_INPUT but with should_dispatch=True so agents still run
            return (
                AgentOutput(
                    agent="orchestrator",
                    status="NEEDS_INPUT",
                    payload={"validation_status": "PENDING"},
                    summary="Proceeding with available information. Some details can be refined later.",
                    confidence=0.8,
                    questions=batch,
                ),
                True,  # still dispatch agents
            )

        else:
            # READY - can proceed
            return (
                AgentOutput(
                    agent="orchestrator",
                    status="COMPLETE",
                    payload={"validation_status": "READY"},
                    summary="Validation passed - proceeding with agent dispatch",
                    confidence=1.0,
                ),
                True,
            )

    async def handle_validation_response(
        self, state: SalesCaseState, answers: dict[str, str]
    ) -> AgentOutput:
        """
        C.5 §3: Handle user's answers to validation questions.
        Maps answers to brief, re-validates, and decides next action.
        """
        question_manager = get_question_manager()

        # Check if this is a free-text answer (contains multiple field answers)
        if len(answers) == 1 and "free_text" in answers:
            # Map free text to brief fields
            state.brief = question_manager.map_free_text_answer(
                answers["free_text"], state.brief or Brief()
            )
        else:
            # Map individual answers to brief
            state.brief = question_manager.map_answers(answers, state.brief or Brief())

        # Re-validate
        validation_output, should_dispatch = await self.validate_before_dispatch(state)

        if should_dispatch:
            # Clear the question stack
            question_manager.stack.clear_answered()
            state.question_stack = []

        return validation_output

    async def handle_severity_gated_revalidation(
        self, state: SalesCaseState, old_brief: Brief
    ) -> tuple[AgentOutput, bool]:
        """
        C.5 §6: Severity-gated re-validation.
        Non-critical edits (budget) skip re-validation.
        Critical edits (industry) trigger re-validation.
        """
        validation_service = get_validation_service()
        report, should_revalidate = await validation_service.validate_with_severity(
            brief=state.brief,
            profile=state.profile,
            mode=state.mode,
            old_brief=old_brief,
        )

        if should_revalidate:
            # Re-run full validation
            return await self.validate_before_dispatch(state)
        else:
            # No re-validation needed
            return (
                AgentOutput(
                    agent="orchestrator",
                    status="COMPLETE",
                    payload={"revalidation": "skipped", "reason": "non-critical edit"},
                    summary="Changes saved - no re-validation needed",
                    confidence=1.0,
                ),
                True,
            )

    async def run(self, state: SalesCaseState) -> AgentOutput:
        """
        Execute the orchestrator logic.

        This is called when the graph enters the orchestrator node.
        It analyzes the current state and decides what to do next.

        C.5 §3: First validates the brief before dispatching to agents.

        Args:
            state: Current SalesCaseState

        Returns:
            AgentOutput with routing decision
        """
        # C.5 §3: Validation gate - MUST pass before any dispatch
        validation_output, should_dispatch = await self.validate_before_dispatch(state)

        if not should_dispatch:
            # BLOCKED or PENDING - return validation output
            return validation_output

        # Validation passed - proceed to dispatch
        # Step 1: Analyze the request and build execution plan
        if not state.plan or not state.plan.tasks:
            # No plan yet, create one based on mode and brief
            plan = self._create_execution_plan(state)
            state.plan = plan

        # Step 2: Check if there are pending tasks
        if not state.plan.tasks:
            # No more tasks, return completion
            return AgentOutput(
                agent="orchestrator",
                status="COMPLETE",
                payload={"summary": "All tasks completed"},
                summary="All agents have completed their work. Here's the summary:",
                confidence=1.0,
            )

        # Step 3: Determine next task
        next_task = self._get_next_task(state)

        if next_task is None:
            # No eligible tasks
            return AgentOutput(
                agent="orchestrator",
                status="COMPLETE",
                payload={"summary": "No more tasks to execute"},
                summary="All planned tasks have been executed.",
                confidence=1.0,
            )

        # Step 4: Check anti-loop guard
        if next_task.agent_name in state.visited:
            # Agent already visited - check if we can proceed
            if state.hop_depth >= self.max_hop_depth:
                return AgentOutput(
                    agent="orchestrator",
                    status="FAILED",
                    payload={
                        "error": "max_hop_depth_exceeded",
                        "message": f"Maximum hop depth ({self.max_hop_depth}) reached",
                    },
                    summary=f"Cannot dispatch to {next_task.agent_name} - would exceed maximum hop depth. Please rephrase your request.",
                    confidence=1.0,
                )

            # Ask user if they want to proceed
            return AgentOutput(
                agent="orchestrator",
                status="NEEDS_INPUT",
                payload={
                    "agent_requested": next_task.agent_name,
                    "already_visited": state.visited,
                },
                summary=f"You've already consulted {next_task.agent_name} in this session. Do you want to consult them again for updated insights?",
                confidence=0.9,
                questions=[
                    Question(
                        id=str(uuid.uuid4()),
                        text=f"Would you like to consult {next_task.agent_name} again?",
                        priority=1,
                        is_mandatory=False,
                        assumption="Continue without re-consulting",
                        target_field="reuse_agent",
                    )
                ],
            )

        # Step 5: Mark agent as visited and increment hop depth
        state.visited.append(next_task.agent_name)
        state.hop_depth += 1

        # Return the routing decision
        return AgentOutput(
            agent="orchestrator",
            status="NEEDS_AGENT",
            payload={
                "next_task": next_task.model_dump(),
                "visited": state.visited,
                "hop_depth": state.hop_depth,
            },
            summary=f"Dispatching to {next_task.agent_name}...",
            confidence=0.9,
            needs=NeedsRequest(
                agent=next_task.agent_name,
                reason=next_task.task_description,
                context={"task": next_task.model_dump()},
            ),
        )

    def _create_execution_plan(self, state: SalesCaseState) -> ExecutionPlan:
        """
        Build the execution plan for the current mode.

        Architecture (matches workflow diagram):
          Group 1 (parallel)  — A3 Strategy, A4 Compliance, A5 Product-expert
          Group 2 (sequential)— A6 Content-generator   (reads Group-1 outputs)
          Group 3 (sequential)— A7 Budget/pricing (account), A8 Design (slide outline)

        planning mode → Group 1 only.
        execute mode  → Groups 1 + 2 + 3.
        """
        registry = get_registry()
        tasks: list[AgentTask] = []

        def _add(name: str, description: str, group: int, critical: bool = False):
            if registry.get(name):
                tasks.append(AgentTask(
                    agent_name=name,
                    task_description=description,
                    depends_on=[],
                    is_critical=critical,
                    parallel_group=group,
                ))

        if state.mode == "chat":
            # Chat mode: orchestrator + process_simple handles this directly
            pass

        elif state.mode == "planning":
            # ── Group 1: parallel analysis (tech team + business team) ───────
            _add("market_strategy",
                 "Industry mapping, pain point, solution package selection & case study RAG",
                 group=1, critical=True)
            _add("tech_solution",
                 "Technical feasibility check: platform stack, Zalo integration options, system architecture",
                 group=1, critical=False)
            _add("compliance",
                 "PDPL check, pharma ad rules, consent language, flag risks early",
                 group=1, critical=False)
            _add("adtimabox",
                 "AdtimaBox features, ZNS / Mini App / OA specs, pricing tier reference",
                 group=1, critical=False)

        elif state.mode == "execute":
            # ── Group 1: parallel analysis (tech team + business team) ───────
            _add("market_strategy",
                 "Industry mapping, pain point, solution package selection & case study RAG",
                 group=1, critical=True)
            _add("tech_solution",
                 "Technical feasibility check: platform stack, Zalo integration options, system architecture & workflow diagram",
                 group=1, critical=False)
            _add("compliance",
                 "PDPL check, consent language, data collection rules for Zalo / offline activation",
                 group=1, critical=False)
            _add("adtimabox",
                 "AdtimaBox features, ZNS / Mini App / OA specs, pricing tier reference",
                 group=1, critical=False)

            # ── Group 2: content creation (reads Group-1 outputs) ───────────
            _add("content_generator",
                 "Write full proposal: insight narrative, solution overview, user journey & earn/burn model",
                 group=2, critical=True)

            # ── Group 3: budget, pricing & visual design ──────────────────────
            _add("account",
                 "Package fee, timeline estimate, ROI projection — detailed pricing table",
                 group=3, critical=True)
            _add("design",
                 "Wireframe & slide outline — deck structure, section order, visual hints",
                 group=3, critical=False)

            # ── Group 4: adversarial review before AE checkpoint ─────────────
            # A9 — Client simulator: stress-tests the proposal, flags weak points
            _add("client_simulator",
                 "Simulate client pushback: identify objections, weak points, and deal-kill risks in the proposal before AE review",
                 group=4, critical=False)

        elif state.mode == "brainstorm":
            participants = getattr(state, "participants", []) or ["orchestrator"]
            for i, agent_name in enumerate(participants):
                if registry.get(agent_name):
                    tasks.append(AgentTask(
                        agent_name=agent_name,
                        task_description=f"Brainstorm contribution {i + 1}",
                        depends_on=[] if i == 0 else [participants[i - 1]],
                        is_critical=False,
                        parallel_group=i,  # each turn is its own group (sequential)
                    ))

        return ExecutionPlan(
            tasks=tasks,
            execution_mode="hybrid",
            estimated_duration_minutes=len(tasks) * 3,
        )

    def _get_next_task(self, state: SalesCaseState) -> Optional[AgentTask]:
        """
        Get the next eligible task to execute.

        Args:
            state: Current state

        Returns:
            Next AgentTask or None
        """
        if not state.plan or not state.plan.tasks:
            return None

        # For sequential execution, return the first task
        # For parallel, would return all eligible tasks
        for task in state.plan.tasks:
            if task.agent_name not in state.visited:
                return task

        return None

    def handle_agent_result(
        self, state: SalesCaseState, agent_output: AgentOutput
    ) -> AgentOutput:
        """
        Handle the result from an agent.

        This is called after an agent completes to determine next steps.

        Args:
            state: Current state
            agent_output: The output from the agent

        Returns:
            Next action to take
        """
        # Store the output
        state.outputs[agent_output.agent] = agent_output

        # Check agent status
        if agent_output.status == "FAILED":
            # Check if this was a critical agent
            task = self._find_task_for_agent(state, agent_output.agent)
            if task and task.is_critical:
                return AgentOutput(
                    agent="orchestrator",
                    status="FAILED",
                    payload={
                        "failed_agent": agent_output.agent,
                        "error": agent_output.summary,
                    },
                    summary=f"Critical agent {agent_output.agent} failed: {agent_output.summary}",
                    confidence=1.0,
                )

        if agent_output.status == "NEEDS_INPUT":
            # Agent needs more info from user
            return agent_output

        if agent_output.needs:
            # Agent is requesting another agent
            # Check anti-loop guard
            if agent_output.needs.agent in state.visited:
                return AgentOutput(
                    agent="orchestrator",
                    status="NEEDS_INPUT",
                    payload={
                        "original_request": agent_output.needs.model_dump(),
                        "already_visited": state.visited,
                    },
                    summary=f"Cannot fulfill request to consult {agent_output.needs.agent} - this agent has already been consulted in this session. Would you like to continue without additional input from them?",
                    confidence=0.9,
                    questions=[
                        Question(
                            id=str(uuid.uuid4()),
                            text=f"Should I proceed without consulting {agent_output.needs.agent} again?",
                            priority=1,
                            is_mandatory=False,
                            assumption="Proceed without the agent",
                            target_field="proceed_without_agent",
                        )
                    ],
                )

            # Add the requested agent to visited
            state.visited.append(agent_output.needs.agent)

        # Continue with next task
        return self.run(state)

    def _find_task_for_agent(
        self, state: SalesCaseState, agent_name: str
    ) -> Optional[AgentTask]:
        """Find the task for a specific agent."""
        if not state.plan:
            return None
        for task in state.plan.tasks:
            if task.agent_name == agent_name:
                return task
        return None


# =============================================================================
# Global Orchestrator Instance
# =============================================================================

_orchestrator: Optional[Orchestrator] = None


def get_orchestrator() -> Orchestrator:
    """Get the global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
