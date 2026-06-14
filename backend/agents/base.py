"""
Base Agent Contract
===================
Abstract base class for all agents in the system.
Every agent must implement this contract to be part of the agent workflow.
"""

from abc import ABC
from typing import Optional, TYPE_CHECKING
import os

from schemas.state import SalesCaseState, AgentOutput, FeedbackRule

if TYPE_CHECKING:
    from memory.constraint_injection import inject_constraints


class BaseAgent(ABC):
    """
    Base class for all agents.

    Each agent must:
    1. Have a unique name
    2. Define which model to use via MODEL_* env key
    3. Load system prompt from prompt.md
    4. Implement the run() method

    The run() method receives the current state and must return
    a standardized AgentOutput.

    D.2: Supports constraint injection from feedback rules.
    """

    def __init__(
        self,
        name: str,
        model_key: str,
        role_description: str,
        prompt_path: Optional[str] = None,
        knowledge_dir: Optional[str] = None,
        skills_dir: Optional[str] = None,
        enabled: bool = True,
        is_critical: bool = False,
        kind: str = "generator",
        hooks: Optional[list[str]] = None,
    ):
        """
        Initialize the agent.

        Args:
            name: Unique agent name (e.g., 'tech_solution')
            model_key: Environment variable key for model (e.g., 'MODEL_TECH_SOLUTION')
            role_description: One-line description for routing (e.g., 'Technical recommendations')
            prompt_path: Path to prompt.md file (optional)
            knowledge_dir: Path to knowledge folder (optional)
            skills_dir: Path to skills folder (optional)
            enabled: Whether this agent is enabled
            is_critical: B.5 failure policy - critical agents must succeed (default False)
            kind: How the orchestrator uses this agent - generator|advisory|reviewer (B.6)
            hooks: List of hook names this agent subscribes to (e.g., ['pre_checkpoint_review'])
        """
        self.name = name
        self.model_key = model_key
        self.role_description = role_description
        self.enabled = enabled
        self.is_critical = is_critical
        self.kind = kind
        self.hooks = hooks or []

        # Load system prompt
        self._base_prompt = self._load_prompt(
            prompt_path or f"agents/{name}/prompt.md"
        )

        # Store paths for knowledge/skills
        self.knowledge_dir = knowledge_dir
        self.skills_dir = skills_dir

    @property
    def system_prompt(self) -> str:
        """Get the base system prompt (without constraints)."""
        return self._base_prompt

    def get_prompt_with_constraints(
        self,
        constraints: list[FeedbackRule],
    ) -> str:
        """
        Get system prompt with constraints injected.

        D.2: Constraints are prepended to ensure they're followed.

        Args:
            constraints: Active feedback rules for this agent

        Returns:
            System prompt with constraints injected
        """
        from memory.constraint_injection import inject_constraints

        return inject_constraints(self._base_prompt, constraints, self.name)

    def _load_prompt(self, path: str) -> str:
        """Load system prompt from file."""
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                return f"Error loading prompt: {e}"

        # Default prompt if file doesn't exist
        return f"""You are {self.name}, a specialized agent.

Your role: {self.role_description}

Respond helpfully and professionally."""

    @property
    def model_path(self) -> str:
        """Get the model path from environment."""
        return os.getenv(self.model_key, "MiniMax-M2.5")

    async def run(self, state: SalesCaseState) -> AgentOutput:
        """
        Execute the agent's task.

        This is the main entry point for the agent. It receives the current
        state and must return a standardized AgentOutput.

        Args:
            state: The current SalesCaseState

        Returns:
            AgentOutput with the agent's result
        """
        raise NotImplementedError(f"Agent {self.name} must implement run()")

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name}, enabled={self.enabled})>"


class StubAgent(BaseAgent):
    """
    Stub implementation for agents that haven't been fully implemented.

    Returns a deterministic sample response for testing the routing.
    """

    def __init__(
        self,
        name: str,
        model_key: str,
        role_description: str,
        is_critical: bool = False,
        kind: str = "generator",
        hooks: Optional[list[str]] = None,
        **kwargs
    ):
        super().__init__(
            name,
            model_key,
            role_description,
            is_critical=is_critical,
            kind=kind,
            hooks=hooks,
            **kwargs
        )
        self._sample_responses = self._init_sample_responses()

    def _init_sample_responses(self) -> dict:
        """Initialize sample responses for each agent type."""
        return {
            "tech_solution": {
                "summary": "Analyzed requirements and provided technical recommendations",
                "payload": {
                    "recommendations": [
                        {
                            "category": "Infrastructure",
                            "item": "Cloud hosting with auto-scaling",
                        },
                        {
                            "category": "Integration",
                            "item": "REST API with WebSocket support",
                        },
                        {
                            "category": "Security",
                            "item": "OAuth 2.0 + JWT authentication",
                        },
                    ],
                    "estimated_complexity": "medium",
                    "timeline_weeks": 8,
                },
            },
            "market_strategy": {
                "summary": "Conducted market analysis and competitive research",
                "payload": {
                    "market_size": "~$50M USD annually",
                    "key_competitors": ["Competitor A", "Competitor B", "Competitor C"],
                    "target_segments": ["SMB", "Enterprise", "Government"],
                    "recommended_pricing": "Tiered: $99/mo, $299/mo, $999/mo",
                },
            },
            "account": {
                "summary": "Prepared pricing proposal and quotation",
                "payload": {
                    "quote_id": "Q-2026-001",
                    "items": [
                        {"name": "Platform License", "price": 50000000, "unit": "year"},
                        {
                            "name": "Implementation",
                            "price": 30000000,
                            "unit": "one-time",
                        },
                        {"name": "Support", "price": 12000000, "unit": "year"},
                    ],
                    "total_vnd": 92000000,
                    "valid_until": "2026-07-12",
                },
            },
            "adtimabox": {
                "summary": "Provided AdtimaBox integration options",
                "payload": {
                    "integration_type": "API + SDK",
                    "features": ["User sync", "Event tracking", "Push notifications"],
                    "setup_time": "3-5 business days",
                },
            },
            "design": {
                "summary": "Created wireframe recommendations",
                "payload": {
                    "deliverables": [
                        {"type": "User Flow", "description": "Main user journey"},
                        {"type": "Wireframe", "description": "Key screens (5 pages)"},
                        {"type": "Mockup", "description": "Visual design (optional)"},
                    ],
                    "estimated_hours": 40,
                },
            },
        }

    async def run(self, state: SalesCaseState) -> AgentOutput:
        """Return a deterministic sample response."""

        # Get sample response for this agent type
        sample = self._sample_responses.get(
            self.name,
            {
                "summary": f"{self.name} processed the request",
                "payload": {"message": f"This is a stub response from {self.name}"},
            },
        )

        return AgentOutput(
            agent=self.name,
            status="COMPLETE",
            payload=sample.get("payload", {}),
            summary=sample.get("summary", f"Agent {self.name} completed"),
            confidence=0.8,
            needs=None,
            questions=[],
        )


def create_agent(
    name: str, model_key: str, role_description: str, is_stub: bool = True, **kwargs
) -> BaseAgent:
    """
    Factory function to create an agent.

    Args:
        name: Agent name
        model_key: Model env key
        role_description: One-line role
        is_stub: If True, create a StubAgent (for Day 2)
        **kwargs: Additional arguments

    Returns:
        BaseAgent instance
    """
    if is_stub:
        return StubAgent(name, model_key, role_description, **kwargs)

    # For future: real agent implementation
    raise NotImplementedError("Real agent implementation coming in Day 5")
