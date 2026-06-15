"""
LangGraph State Machine
=======================
Assembles the LangGraph StateGraph over SalesCaseState.

This implements the Supervisor/Router pattern (B.1) with:
- Orchestrator supervisor node
- One node per registered agent
- Conditional edges via Command(goto=...)
- Checkpointer for durability
- Anti-loop guard (visited + hop_depth)
"""

from typing import Optional, Callable
import asyncio
import os

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.runnables import RunnableConfig

from schemas.state import SalesCaseState
from agents.base import BaseAgent
from agents.registry import get_registry
from agents.orchestrator import get_orchestrator

# =============================================================================
# Graph Node Functions
# =============================================================================


async def orchestrator_node(state: SalesCaseState) -> dict:
    """
    Orchestrator supervisor node.

    Analyzes state, decides next action, returns updates via Command.
    """
    orchestrator = get_orchestrator()
    result = await orchestrator.run(state)

    # Update state with result
    updates = {"outputs": {**state.outputs, "orchestrator": result}}

    # Check what the result says to do next
    if result.status == "NEEDS_AGENT" and result.needs:
        # Need to dispatch to another agent (target stored in result.needs.agent)
        return {
            **updates,
            "visited": state.visited,
            "hop_depth": state.hop_depth,
        }

    return {
        **updates,
        "summary": state.summary + f" | Orchestrator: {result.summary[:50]}...",
    }


def agent_node(agent_name: str, agent: BaseAgent) -> Callable:
    """
    Create a LangGraph node function for a specific agent.

    Returns a ready-to-register async callable — NOT a coroutine.
    Previously this was `async def` which caused callers to receive a
    Coroutine[Callable] instead of the Callable itself.

    Args:
        agent_name: Name of the agent
        agent: Agent instance

    Returns:
        Async function that executes the agent and returns state-update dict
    """

    async def node(state: SalesCaseState) -> dict:
        # Day 4: Inject constraints if available in state
        constraints = getattr(state, "constraints", []) or []

        # Get constraints relevant to this agent
        from memory.constraint_injection import get_constraints_for_agent
        agent_constraints = get_constraints_for_agent(constraints, agent_name)

        # Store original prompt and inject constraints
        original_prompt = agent._base_prompt
        injected_prompt = agent.get_prompt_with_constraints(agent_constraints)
        agent._base_prompt = injected_prompt

        try:
            # Execute the agent
            result = await agent.run(state)
        finally:
            # Restore original prompt
            agent._base_prompt = original_prompt

        # Update outputs (use agent_name as key, not literal string)
        outputs = {**state.outputs, **{agent_name: result}}

        # Update summary
        summary = state.summary + f" | {agent_name}: {result.summary[:30]}..."

        return {
            "outputs": outputs,
            "summary": summary,
        }

    return node


def create_routing_function(agent_name: str) -> Callable:
    """
    Create a routing function that directs to a specific agent.

    Args:
        agent_name: Name of the agent to route to

    Returns:
        Function that returns the agent node name
    """

    def route(state: SalesCaseState) -> str:
        # Check if agent exists in outputs with NEEDS_AGENT
        if state.outputs:
            for name, output in state.outputs.items():
                if output.needs and output.needs.agent == agent_name:
                    return agent_name

        # Default: check orchestrator's last decision
        orch_output = state.outputs.get("orchestrator")
        if orch_output and orch_output.needs:
            if orch_output.needs.agent == agent_name:
                return agent_name

        return END

    return route


# =============================================================================
# Graph Builder
# =============================================================================


class AgentGraph:
    """
    LangGraph state machine for the multi-agent system.
    """

    def __init__(self):
        self.graph: Optional[StateGraph] = None

        # Day 4: Use in-memory checkpointer for now (SQLite interface has issues)
        # The session persistence happens via memory_repo.save_session() in main.py
        # This enables graph checkpointing for anti-loop within a session
        self.checkpointer = MemorySaver()

        self._build_graph()

    def _build_graph(self) -> None:
        """Build the LangGraph state machine."""
        # Create the state graph
        workflow = StateGraph(SalesCaseState)

        # Add orchestrator node (supervisor)
        workflow.add_node("orchestrator", orchestrator_node)

        # Get all registered agents
        registry = get_registry()
        all_agents = [a for a in registry.all() if a.name != "orchestrator"]

        # First, add all agent nodes
        # agent_node() is a sync factory — call it immediately to capture the loop
        # variable and register the resulting async callable with LangGraph.
        for agent in all_agents:
            workflow.add_node(agent.name, agent_node(agent.name, agent))

        # Then, add conditional edges - each needs unique routing function
        for idx, agent in enumerate(all_agents):
            # Add conditional edge: orchestrator -> agent
            # Use partial to make routing function unique per agent
            from functools import partial
            route_fn = partial(create_routing_function(agent.name))
            route_fn.__name__ = f"route_{agent.name}"
            workflow.add_conditional_edges(
                "orchestrator",
                route_fn,
                [agent.name, END]
            )

            # Add edge: agent -> orchestrator (to aggregate results)
            workflow.add_edge(agent.name, "orchestrator")

        # Set entry point
        workflow.set_entry_point("orchestrator")

        # Compile with checkpointer
        self.graph = workflow.compile(
            checkpointer=self.checkpointer,
            interrupt_before=[],  # Could add checkpoints here for HITL
        )

    def get_graph(self) -> StateGraph:
        """Get the compiled graph."""
        if self.graph is None:
            self._build_graph()
        return self.graph

    async def run(
        self, state: SalesCaseState, config: Optional[RunnableConfig] = None
    ) -> SalesCaseState:
        """
        Run the graph with the given state.

        Args:
            state: Initial SalesCaseState
            config: Optional LangGraph config (thread_id, etc.)

        Returns:
            Updated state after graph execution
        """
        graph = self.get_graph()

        # Run the graph
        result = await graph.ainvoke(state, config=config)

        return result

    async def run_stream(
        self, state: SalesCaseState, config: Optional[RunnableConfig] = None
    ):
        """
        Run the graph with streaming events.

        Yields state updates and agent status events.

        Args:
            state: Initial SalesCaseState
            config: Optional LangGraph config

        Yields:
            Dict with event type and data
        """
        graph = self.get_graph()

        async for event in graph.astream(state, config=config):
            for node_name, node_output in event.items():
                if node_name == "orchestrator":
                    yield {
                        "type": "agent_status",
                        "agent": "orchestrator",
                        "status": "thinking",
                        "message": node_output.get("summary", ""),
                    }
                else:
                    # Agent completed
                    output = node_output.get("outputs", {}).get(node_name)
                    if output:
                        yield {
                            "type": "agent_status",
                            "agent": node_name,
                            "status": "completed",
                            "summary": (
                                output.summary if hasattr(output, "summary") else ""
                            ),
                        }

        yield {"type": "done"}


def awaitable(func):
    """Decorator to make a sync function return an awaitable."""

    async def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


# =============================================================================
# Global Graph Instance
# =============================================================================

_graph: Optional[AgentGraph] = None


def get_graph() -> AgentGraph:
    """Get the global agent graph instance."""
    global _graph
    if _graph is None:
        _graph = AgentGraph()
    return _graph


def rebuild_graph() -> AgentGraph:
    """Rebuild the graph (useful after config changes)."""
    global _graph
    _graph = AgentGraph()
    return _graph


# =============================================================================
# Simple Wrapper for Day 2 (without full LangGraph)
# =============================================================================


class SimpleAgentRunner:
    """
    Multi-group agent runner implementing the A1→A2→Group1∥→Group2→… pipeline.

    Architecture (matches workflow diagram):
      A1  Scoping agent   — validates brief, asks missing fields
      A2  Orchestrator    — pure router: creates plan, never executes tasks
      G1  Parallel group  — strategy, compliance, product_expert run simultaneously
      G2  Sequential      — content_generator synthesises G1 outputs
      G3  Sequential      — account (budget/pricing), design (slide outline)

    Constraints are injected per-agent from the salesperson's feedback rules.
    """

    def __init__(self):
        self.orchestrator = get_orchestrator()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run_agent(
        self,
        agent_name: str,
        task_description: str,
        state: SalesCaseState,
        constraints: list,
    ):
        """Run one agent with constraint injection. Returns AgentOutput."""
        from agents.registry import get_agent
        from memory.constraint_injection import get_constraints_for_agent
        from schemas.state import AgentOutput

        agent = get_agent(agent_name)
        if agent is None:
            return AgentOutput(
                agent=agent_name,
                status="FAILED",
                payload={},
                summary=f"Agent '{agent_name}' not found in registry",
                confidence=0.0,
                needs=None,
                questions=[],
            )

        agent_constraints = get_constraints_for_agent(constraints, agent_name)
        original_prompt = agent._base_prompt
        agent._base_prompt = agent.get_prompt_with_constraints(agent_constraints)

        try:
            result = await agent.run(state)
        except Exception as exc:
            result = AgentOutput(
                agent=agent_name,
                status="FAILED",
                payload={"error": str(exc)},
                summary=f"Agent error: {exc}",
                confidence=0.0,
                needs=None,
                questions=[],
            )
        finally:
            agent._base_prompt = original_prompt

        return result

    # ------------------------------------------------------------------
    # Main run loop
    # ------------------------------------------------------------------

    async def run(self, state: SalesCaseState) -> tuple[SalesCaseState, list[dict]]:
        from repos.memory_repo import get_memory_repo
        from memory.constraint_injection import get_constraints_for_agent
        from schemas.state import AgentOutput

        stream_events: list[dict] = []
        state.outputs = {}

        # Load per-salesperson feedback rules for constraint injection
        memory_repo = get_memory_repo()
        constraints = await memory_repo.load_feedback_rules(
            state.salesperson_id, active_only=True
        )
        state.constraints = constraints

        # ── A1: Scoping & validation ──────────────────────────────────────
        stream_events.append({
            "type": "agent_status", "agent": "scoping",
            "status": "thinking", "message": "Validating brief…",
        })

        # Skip LLM validation if chat_stream already ran it (READY or PENDING both proceed).
        # This avoids double-calling the validation model on every request.
        if state.validation_status not in ("READY", "PENDING"):
            validation_output, should_dispatch = await self.orchestrator.validate_before_dispatch(state)
            if not should_dispatch:
                state.outputs["orchestrator"] = validation_output
                stream_events.append({
                    "type": "agent_status", "agent": "scoping",
                    "status": "completed" if validation_output.status == "NEEDS_INPUT" else "failed",
                    "message": validation_output.summary,
                })
                stream_events.append({"type": "done"})
                return state, stream_events

        stream_events.append({
            "type": "agent_status", "agent": "scoping",
            "status": "completed", "message": "Brief validated ✓",
        })

        # ── A2: Orchestrator — pure routing, no execution ─────────────────
        stream_events.append({
            "type": "agent_status", "agent": "orchestrator",
            "status": "thinking", "message": "Building execution plan…",
        })

        if not state.plan or not state.plan.tasks:
            state.plan = self.orchestrator._create_execution_plan(state)

        task_names = [t.agent_name for t in state.plan.tasks]
        stream_events.append({
            "type": "agent_status", "agent": "orchestrator",
            "status": "completed",
            "message": f"Plan ready → {', '.join(task_names)}",
        })

        # ── Execute tasks grouped by parallel_group ───────────────────────
        group_map: dict[int, list] = {}
        for task in state.plan.tasks:
            g = getattr(task, "parallel_group", 0)
            group_map.setdefault(g, []).append(task)

        for group_num in sorted(group_map.keys()):
            eligible = [t for t in group_map[group_num] if t.agent_name not in state.visited]
            if not eligible:
                continue

            # Mark all agents in this group as visited before execution
            for task in eligible:
                state.visited.append(task.agent_name)
                state.hop_depth += 1
                stream_events.append({
                    "type": "agent_status", "agent": task.agent_name,
                    "status": "thinking",
                    "message": task.task_description
                    + (" [parallel]" if len(eligible) > 1 else ""),
                })

            if len(eligible) == 1:
                # Sequential — single agent
                task = eligible[0]
                result = await self._run_agent(
                    task.agent_name, task.task_description, state, constraints
                )
                state.outputs[task.agent_name] = result
                stream_events.append({
                    "type": "agent_status", "agent": task.agent_name,
                    "status": "completed" if result.status == "COMPLETE" else "failed",
                    "message": result.summary,
                })
            else:
                # Parallel — asyncio.gather across the whole group
                results = await asyncio.gather(
                    *[
                        self._run_agent(t.agent_name, t.task_description, state, constraints)
                        for t in eligible
                    ],
                    return_exceptions=True,
                )
                for task, result in zip(eligible, results):
                    if isinstance(result, Exception):
                        err = AgentOutput(
                            agent=task.agent_name, status="FAILED",
                            payload={"error": str(result)}, summary=str(result),
                            confidence=0.0, needs=None, questions=[],
                        )
                        state.outputs[task.agent_name] = err
                        stream_events.append({
                            "type": "agent_status", "agent": task.agent_name,
                            "status": "failed", "message": str(result),
                        })
                    else:
                        state.outputs[task.agent_name] = result
                        stream_events.append({
                            "type": "agent_status", "agent": task.agent_name,
                            "status": "completed" if result.status == "COMPLETE" else "failed",
                            "message": result.summary,
                        })

        stream_events.append({"type": "done"})
        return state, stream_events


# Global simple runner
_simple_runner: Optional[SimpleAgentRunner] = None


def get_simple_runner() -> SimpleAgentRunner:
    """Get the simple agent runner."""
    global _simple_runner
    if _simple_runner is None:
        _simple_runner = SimpleAgentRunner()
    return _simple_runner
