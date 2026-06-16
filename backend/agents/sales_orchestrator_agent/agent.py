"""
Sales Orchestrator
==================
Primary control plane for the multi-agent sales workflow.

Responsibilities:
- Validate the brief without assuming missing context
- Ask targeted clarifying questions only when required
- Build the execution plan from the actual brief and desired output
- Dispatch to the best-fit specialist agents
- Preserve the anti-loop guard and session question stack

This module is the runtime source of truth for `sales_orchestrator`.
Legacy modules re-export from here for backward compatibility only.
"""

from __future__ import annotations

import uuid
from typing import Optional

from agents.registry import get_registry
from schemas.state import (
    AgentOutput,
    AgentTask,
    Brief,
    ExecutionPlan,
    NeedsRequest,
    Question,
    SalesCaseState,
)
from validation.question_stack import get_question_manager
from validation.validator import get_validation_service


DEFAULT_MAX_HOP_DEPTH = 4


class Orchestrator:
    """Central orchestrator for validation, planning, and routing."""

    def __init__(self, max_hop_depth: int = DEFAULT_MAX_HOP_DEPTH):
        self.max_hop_depth = max_hop_depth

    def _latest_user_message(self, state: SalesCaseState) -> str:
        for msg in reversed(state.messages):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return ""

    def _question_manager_for_state(self, state: SalesCaseState):
        question_manager = get_question_manager()
        question_manager.ensure_session(state.session_id)
        if state.question_stack:
            question_manager.restore_stack(state.question_stack)
        return question_manager

    async def validate_before_dispatch(
        self, state: SalesCaseState
    ) -> tuple[AgentOutput, bool]:
        """Validate the brief before dispatching any agent."""
        question_manager = self._question_manager_for_state(state)

        if not state.brief:
            # Seed raw user text as context instead of inventing structure.
            state.brief = Brief(additional_context=self._latest_user_message(state) or None)

        if question_manager.stack.has_mandatory_unanswered():
            state.validation_status = "PENDING"
            questions = question_manager.stack.next_batch()
            state.question_stack = question_manager.stack.items
            return (
                AgentOutput(
                    agent="sales_orchestrator",
                    status="NEEDS_INPUT",
                    payload={"validation_status": "PENDING", "question_count": len(questions)},
                    summary="Please answer the pending questions to proceed.",
                    confidence=1.0,
                    questions=questions,
                ),
                False,
            )

        validation_service = get_validation_service()
        validation_report = await validation_service.validate(
            brief=state.brief,
            profile=state.profile,
            mode=state.mode,
        )
        state.validation_report = validation_report
        state.validation_status = validation_report.status

        if validation_report.status == "BLOCKED":
            return (
                AgentOutput(
                    agent="sales_orchestrator",
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

        if validation_report.status == "PENDING":
            questions = question_manager.generate_questions_from_validation(
                brief=state.brief,
                mode=state.mode,
                validation_missing=validation_report.missing_required,
                validation_ambiguities=validation_report.ambiguities,
            )
            question_manager.stack.push(questions)
            state.question_stack = question_manager.stack.items
            batch = question_manager.stack.next_batch()
            return (
                AgentOutput(
                    agent="sales_orchestrator",
                    status="NEEDS_INPUT",
                    payload={"validation_status": "PENDING"},
                    summary="Please answer the following questions before proceeding.",
                    confidence=0.8,
                    questions=batch,
                ),
                False,
            )

        state.question_stack = question_manager.stack.items
        return (
            AgentOutput(
                agent="sales_orchestrator",
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
        """Apply user answers to the brief and revalidate."""
        question_manager = self._question_manager_for_state(state)
        if len(answers) == 1 and "free_text" in answers:
            state.brief = question_manager.map_free_text_answer(
                answers["free_text"], state.brief or Brief()
            )
        else:
            state.brief = question_manager.map_answers(answers, state.brief or Brief())

        validation_output, should_dispatch = await self.validate_before_dispatch(state)
        if should_dispatch:
            question_manager.stack.clear_answered()
            state.question_stack = question_manager.stack.items
        return validation_output

    async def handle_severity_gated_revalidation(
        self, state: SalesCaseState, old_brief: Brief
    ) -> tuple[AgentOutput, bool]:
        validation_service = get_validation_service()
        _report, should_revalidate = await validation_service.validate_with_severity(
            brief=state.brief,
            profile=state.profile,
            mode=state.mode,
            old_brief=old_brief,
        )

        if should_revalidate:
            return await self.validate_before_dispatch(state)

        return (
            AgentOutput(
                agent="sales_orchestrator",
                status="COMPLETE",
                payload={"revalidation": "skipped", "reason": "non-critical edit"},
                summary="Changes saved - no re-validation needed",
                confidence=1.0,
            ),
            True,
        )

    async def run(self, state: SalesCaseState) -> AgentOutput:
        """Validate, plan, and dispatch the next step."""
        validation_output, should_dispatch = await self.validate_before_dispatch(state)
        if not should_dispatch:
            return validation_output

        if not state.plan or not state.plan.tasks:
            state.plan = self._create_execution_plan(state)

        if not state.plan.tasks:
            return AgentOutput(
                agent="sales_orchestrator",
                status="COMPLETE",
                payload={"summary": "All tasks completed"},
                summary="All agents have completed their work. Here's the summary:",
                confidence=1.0,
            )

        next_task = self._get_next_task(state)
        if next_task is None:
            return AgentOutput(
                agent="sales_orchestrator",
                status="COMPLETE",
                payload={"summary": "No more tasks to execute"},
                summary="All planned tasks have been executed.",
                confidence=1.0,
            )

        if next_task.agent_name in state.visited:
            if state.hop_depth >= self.max_hop_depth:
                return AgentOutput(
                    agent="sales_orchestrator",
                    status="FAILED",
                    payload={
                        "error": "max_hop_depth_exceeded",
                        "message": f"Maximum hop depth ({self.max_hop_depth}) reached",
                    },
                    summary=f"Cannot dispatch to {next_task.agent_name} - would exceed maximum hop depth. Please rephrase your request.",
                    confidence=1.0,
                )

            return AgentOutput(
                agent="sales_orchestrator",
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
                        target_field="reuse_agent",
                    )
                ],
            )

        state.visited.append(next_task.agent_name)
        state.hop_depth += 1

        return AgentOutput(
            agent="sales_orchestrator",
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
        """Build a guarded execution plan from the current brief and desired outputs."""
        registry = get_registry()
        tasks: list[AgentTask] = []
        requested_outputs = set(state.desired_outputs or [])
        user_text = self._latest_user_message(state).lower()

        def _add(name: str, description: str, group: int, critical: bool = False):
            if registry.get(name) and not any(task.agent_name == name for task in tasks):
                tasks.append(
                    AgentTask(
                        agent_name=name,
                        task_description=description,
                        depends_on=[],
                        is_critical=critical,
                        parallel_group=group,
                    )
                )

        # Core chain: validate needs, map the opportunity, check risk, and produce the solution.
        _add(
            "requirement_elicitation",
            "Translate the brief into a structured requirement summary, surface unknowns, and request missing context only when needed",
            group=1,
            critical=True,
        )
        _add(
            "market_strategy",
            "Industry mapping, pain point framing, solution package selection, and case-study RAG",
            group=2,
            critical=True,
        )
        _add(
            "compliance",
            "PDPL check, consent language, data collection rules, and risk flags",
            group=2,
        )
        _add(
            "product_solution",
            "Merged product solution, pricing reference, integration fit, and solution packaging",
            group=2,
        )

        # Add artifact-producing agents when the request indicates output work.
        wants_artifacts = bool(requested_outputs) or any(
            keyword in user_text
            for keyword in [
                "proposal",
                "presentation",
                "pptx",
                "slide",
                "deck",
                "figma",
                "wireframe",
                "diagram",
                "userflow",
                "quotation",
                "quote",
                "pricing",
            ]
        )

        if wants_artifacts or not requested_outputs:
            _add(
                "design",
                "Wireframe and slide outline - deck structure, section order, visual hints",
                group=3,
            )
            _add(
                "client_simulator",
                "Simulate client pushback and flag weak points before AE review",
                group=4,
            )

        return ExecutionPlan(
            tasks=tasks,
            execution_mode="hybrid",
            estimated_duration_minutes=len(tasks) * 3,
        )

    def _get_next_task(self, state: SalesCaseState) -> Optional[AgentTask]:
        if not state.plan or not state.plan.tasks:
            return None
        for task in state.plan.tasks:
            if task.agent_name not in state.visited:
                return task
        return None

    def handle_agent_result(self, state: SalesCaseState, agent_output: AgentOutput) -> AgentOutput:
        state.outputs[agent_output.agent] = agent_output

        if agent_output.status == "FAILED":
            task = self._find_task_for_agent(state, agent_output.agent)
            if task and task.is_critical:
                return AgentOutput(
                    agent="sales_orchestrator",
                    status="FAILED",
                    payload={"failed_agent": agent_output.agent, "error": agent_output.summary},
                    summary=f"Critical agent {agent_output.agent} failed: {agent_output.summary}",
                    confidence=1.0,
                )

        if agent_output.status == "NEEDS_INPUT":
            return agent_output

        if agent_output.needs:
            if agent_output.needs.agent in state.visited:
                return AgentOutput(
                    agent="sales_orchestrator",
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
                            target_field="proceed_without_agent",
                        )
                    ],
                )
            state.visited.append(agent_output.needs.agent)

        return self.run(state)

    def _find_task_for_agent(self, state: SalesCaseState, agent_name: str) -> Optional[AgentTask]:
        if not state.plan:
            return None
        for task in state.plan.tasks:
            if task.agent_name == agent_name:
                return task
        return None


_sales_orchestrator: Optional[Orchestrator] = None


def get_sales_orchestrator() -> Orchestrator:
    global _sales_orchestrator
    if _sales_orchestrator is None:
        _sales_orchestrator = Orchestrator()
    return _sales_orchestrator


def get_orchestrator() -> Orchestrator:
    return get_sales_orchestrator()
