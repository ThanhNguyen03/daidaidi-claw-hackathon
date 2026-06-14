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


async def agent_node(agent_name: str, agent: BaseAgent) -> Callable:
    """
    Create a node function for a specific agent.

    Args:
        agent_name: Name of the agent
        agent: Agent instance

    Returns:
        Async function that executes the agent
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

        # Add nodes for each agent
        for agent in registry.all():
            if agent.name == "orchestrator":
                continue

            # Create agent node function - use default arg to capture loop variable
            def make_node(a=agent):
                async def node_inner(state: SalesCaseState) -> dict:
                    return await agent_node(a.name, a)

                return node_inner

            workflow.add_node(agent.name, make_node())

            # Add conditional edge: orchestrator -> agent
            workflow.add_conditional_edges(
                "orchestrator", create_routing_function(agent.name), [agent.name, END]
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
    Simple agent runner for Day 2 (without full LangGraph complexity).

    This provides the core orchestration logic without the full
    LangGraph state machine. Will be replaced by AgentGraph in later days.

    Day 4: Loads constraints and injects them into agent prompts.
    """

    def __init__(self):
        self.orchestrator = get_orchestrator()

    async def run(self, state: SalesCaseState) -> tuple[SalesCaseState, list[dict]]:
        """
        Run the orchestration.

        Args:
            state: Initial state

        Returns:
            Tuple of (final_state, stream_events)
        """
        stream_events = []
        state.outputs = {}

        # Day 4: Load active constraints and inject into state
        from repos.memory_repo import get_memory_repo
        from memory.constraint_injection import get_constraints_for_agent

        memory_repo = get_memory_repo()
        constraints = await memory_repo.load_feedback_rules(
            state.salesperson_id, active_only=True
        )
        state.constraints = constraints  # Populate constraints in state

        # Initial status
        stream_events.append(
            {
                "type": "agent_status",
                "agent": "orchestrator",
                "status": "thinking",
                "message": "Analyzing request...",
            }
        )

        # Run orchestrator to get first decision
        orch_result = await self.orchestrator.run(state)
        state.outputs["orchestrator"] = orch_result

        stream_events.append(
            {
                "type": "agent_status",
                "agent": "orchestrator",
                "status": "completed",
                "message": orch_result.summary,
            }
        )

        # If needs an agent, dispatch
        while orch_result.needs:
            target_agent = orch_result.needs.agent
            stream_events.append(
                {
                    "type": "agent_status",
                    "agent": target_agent,
                    "status": "thinking",
                    "message": f"Executing {target_agent}...",
                }
            )

            # Get the agent from registry
            from agents.registry import get_agent

            agent = get_agent(target_agent)

            if agent is None:
                stream_events.append(
                    {
                        "type": "agent_status",
                        "agent": target_agent,
                        "status": "failed",
                        "message": f"Agent {target_agent} not found",
                    }
                )
                break

            # Day 4: Get constraints for this specific agent
            agent_constraints = get_constraints_for_agent(constraints, target_agent)

            # Run the agent with constraint-injected prompt
            # Store the original prompt, inject constraints, run, restore
            original_prompt = agent._base_prompt
            injected_prompt = agent.get_prompt_with_constraints(agent_constraints)

            # Temporarily set the injected prompt
            agent._base_prompt = injected_prompt

            try:
                agent_result = await agent.run(state)
            finally:
                # Restore original prompt
                agent._base_prompt = original_prompt

            state.outputs[target_agent] = agent_result

            stream_events.append(
                {
                    "type": "agent_status",
                    "agent": target_agent,
                    "status": "completed",
                    "message": agent_result.summary,
                }
            )

            # Handle agent result
            orch_result = self.orchestrator.handle_agent_result(state, agent_result)
            state.outputs["orchestrator"] = orch_result

            # Check if orchestrator wants to continue
            # Only continue if status is NEEDS_AGENT (needs another agent)
            # If COMPLETE, FAILED, NEEDS_INPUT - break
            if orch_result.status != "NEEDS_AGENT":
                break

        # Final status
        stream_events.append(
            {
                "type": "done",
            }
        )

        return state, stream_events


# Global simple runner
_simple_runner: Optional[SimpleAgentRunner] = None


def get_simple_runner() -> SimpleAgentRunner:
    """Get the simple agent runner."""
    global _simple_runner
    if _simple_runner is None:
        _simple_runner = SimpleAgentRunner()
    return _simple_runner
