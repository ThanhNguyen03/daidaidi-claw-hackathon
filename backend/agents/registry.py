"""
Agent Registry
==============
Config-driven agent registry that loads agents from config/agents.yaml.
Adding/removing agents = editing the config file, never the code.
"""

import os
import yaml
from typing import Optional

from agents.base import BaseAgent, create_agent


class AgentRegistry:
    """
    Config-driven agent registry.

    Loads agent configuration from YAML and instantiates agents.
    Supports dynamic enable/disable without code changes.
    """

    def __init__(self, config_path: str = "backend/config/agents.yaml"):
        """
        Initialize the registry.

        Args:
            config_path: Path to the agents.yaml config file
        """
        self.config_path = config_path
        self._agents: dict[str, BaseAgent] = {}
        self._load_agents()

    def _load_agents(self) -> None:
        """Load agents from config file."""
        if not os.path.exists(self.config_path):
            print(f"Warning: Config file {self.config_path} not found")
            return

        with open(self.config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not config or "agents" not in config:
            print("Warning: No 'agents' key in config")
            return

        agents_config = config["agents"]

        for name, agent_config in agents_config.items():
            if not agent_config.get("enabled", True):
                print(f"Agent '{name}' is disabled, skipping")
                continue

            # Read agent metadata (DAY_2 §4 + B.6)
            # Note: is_critical is read but not yet propagated to AgentTask (see CHECK.md issue #2)
            model_key = agent_config.get("model", agent_config.get("model_env", f"MODEL_{name.upper()}"))
            role_description = agent_config.get("role", agent_config.get("description", ""))
            is_critical = agent_config.get("critical", False)
            kind = agent_config.get("kind", "generator")
            hooks = agent_config.get("hooks", [])

            # Day 5: Try to use real agent implementations first, fall back to stub
            try:
                agent = self._create_real_agent(name, model_key, role_description, is_critical, kind, hooks)
            except Exception as e:
                print(f"Real agent '{name}' failed to load: {e}, using stub")
                # Use paths relative to this file so they resolve correctly
                # regardless of the working directory the server starts from.
                _here = os.path.dirname(os.path.abspath(__file__))
                agent = create_agent(
                    name=name,
                    model_key=model_key,
                    role_description=role_description,
                    is_stub=True,
                    prompt_path=os.path.join(_here, name, "prompt.md"),
                    knowledge_dir=os.path.join(_here, name, "knowledge"),
                    skills_dir=os.path.join(_here, name, "skills"),
                    is_critical=is_critical,
                    kind=kind,
                    hooks=hooks,
                )

            if agent:
                self._agents[name] = agent
                # Determine agent type for logging
                stub_class = type(create_agent('temp', 'MODEL_TEMP', 'desc', is_stub=True))
                agent_type = 'stub' if isinstance(agent, stub_class) else 'real'
                print(f"Loaded agent: {name} (kind={kind}, critical={is_critical}, type={agent_type})")

    def _create_real_agent(self, name: str, model_key: str, role_description: str, is_critical: bool, kind: str, hooks: list) -> Optional[BaseAgent]:
        """Try to create a real agent implementation if available."""

        # Map agent names to their real implementations
        real_agent_map = {
            "account": ("agents.account.agent", "get_account_agent"),
            "compliance": ("agents.compliance.agent", "get_compliance_agent"),
            # Add more agents as they're implemented
        }

        if name in real_agent_map:
            module_path, getter_name = real_agent_map[name]
            try:
                module = __import__(module_path, fromlist=[getter_name])
                getter = getattr(module, getter_name)
                return getter()
            except Exception as e:
                raise RuntimeError(f"Failed to load real agent: {e}")

        # No real implementation available
        return None

    def get(self, name: str) -> Optional[BaseAgent]:
        """
        Get an agent by name.

        Args:
            name: Agent name

        Returns:
            BaseAgent instance or None if not found
        """
        return self._agents.get(name)

    def all(self) -> list[BaseAgent]:
        """
        Get all enabled agents.

        Returns:
            List of all BaseAgent instances
        """
        return list(self._agents.values())

    def all_names(self) -> list[str]:
        """Get all agent names."""
        return list(self._agents.keys())

    def routing_descriptions(self) -> dict[str, str]:
        """
        Get routing descriptions for all agents.

        Returns:
            Dict mapping agent name to role description
        """
        return {name: agent.role_description for name, agent in self._agents.items()}

    def get_model_for_agent(self, name: str) -> str:
        """Get the model path for a specific agent."""
        agent = self.get(name)
        if agent:
            return agent.model_path
        return "MiniMax-M2.5"  # Default

    def reload(self) -> None:
        """Reload agents from config (useful after config changes)."""
        self._agents.clear()
        self._load_agents()

    def __repr__(self) -> str:
        return f"<AgentRegistry(agents={list(self._agents.keys())})>"


# =============================================================================
# Global Registry Instance
# =============================================================================

_registry: Optional[AgentRegistry] = None


def get_registry() -> AgentRegistry:
    """
    Get the global agent registry.

    Returns:
        AgentRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry


def reload_registry() -> AgentRegistry:
    """Reload and return the registry."""
    global _registry
    _registry = AgentRegistry()
    return _registry


# =============================================================================
# Agent Access Helpers
# =============================================================================


def get_agent(name: str) -> Optional[BaseAgent]:
    """Get an agent by name from the global registry."""
    return get_registry().get(name)


def get_all_agents() -> list[BaseAgent]:
    """Get all agents from the global registry."""
    return get_registry().all()


def get_routing_descriptions() -> dict[str, str]:
    """Get routing descriptions from the global registry."""
    return get_registry().routing_descriptions()


# =============================================================================
# CLI for testing
# =============================================================================

if __name__ == "__main__":
    registry = get_registry()
    print(f"Registry: {registry}")
    print("\nAvailable agents:")
    for agent in registry.all():
        print(f"  - {agent.name}: {agent.role_description}")
        print(f"    model: {agent.model_path}")
    print("\nRouting descriptions:")
    for name, desc in registry.routing_descriptions().items():
        print(f"  {name}: {desc}")
