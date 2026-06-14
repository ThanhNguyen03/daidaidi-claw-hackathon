"""
Constraint Injection
=====================
Injects active feedback rules into agent system prompts.

D.2: Active in-scope rules are prepended to system prompts
so constraints are structurally enforced, not "hopefully remembered".
"""

from typing import Optional

from schemas.state import FeedbackRule


def inject_constraints(
    base_prompt: str,
    constraints: list[FeedbackRule],
    agent_name: str,
) -> str:
    """
    Inject active constraints into an agent's system prompt.

    Args:
        base_prompt: The agent's base system prompt
        constraints: List of active feedback rules
        agent_name: Name of the agent receiving the prompt

    Returns:
        Modified prompt with constraints prepended
    """
    # Filter constraints relevant to this agent
    relevant = [
        c for c in constraints
        if c.active and (agent_name in c.scope or "orchestrator" in c.scope)
    ]

    if not relevant:
        return base_prompt

    # Build constraint section
    constraint_lines = [
        "=" * 60,
        "ACTIVE CONSTRAINTS (Learned from user feedback):",
        "=" * 60,
    ]

    for constraint in relevant:
        constraint_lines.append(f"- [{constraint.type}] {constraint.rule}")
        if constraint.source_quote:
            constraint_lines.append(f"  Source: \"{constraint.source_quote}\"")

    constraint_lines.extend([
        "=" * 60,
        "IMPORTANT: You MUST follow these constraints in all responses.",
        "Do NOT suggest, recommend, or mention anything that violates",
        "these constraints. This is not optional - it's system behavior.",
        "=" * 60,
        "",
    ])

    constraint_section = "\n".join(constraint_lines)

    # Prepend to base prompt
    return f"{constraint_section}\n{base_prompt}"


def get_constraints_for_agent(
    all_constraints: list[FeedbackRule],
    agent_name: str,
) -> list[FeedbackRule]:
    """
    Filter constraints relevant to a specific agent.

    Args:
        all_constraints: All available constraints
        agent_name: Name of the agent

    Returns:
        List of constraints relevant to this agent
    """
    relevant = []

    for constraint in all_constraints:
        if not constraint.active:
            continue

        # Check if agent is in scope
        # Orchestrator gets all constraints (it coordinates)
        if agent_name == "orchestrator":
            relevant.append(constraint)
        elif agent_name in constraint.scope:
            relevant.append(constraint)

    return relevant


def format_constraint_summary(constraints: list[FeedbackRule]) -> str:
    """
    Format constraints for display in UI (Context panel).

    Args:
        constraints: List of constraints

    Returns:
        Formatted summary string
    """
    if not constraints:
        return "No active constraints"

    lines = []
    for c in constraints:
        if c.active:
            type_emoji = "🔴" if c.type == "NEGATIVE_CONSTRAINT" else "🟢"
            lines.append(f"{type_emoji} {c.rule}")

    return "\n".join(lines) if lines else "No active constraints"


def toggle_constraint(
    constraints: list[FeedbackRule],
    rule_id: str,
    active: bool,
) -> list[FeedbackRule]:
    """
    Toggle a constraint's active status.

    Args:
        constraints: All constraints
        rule_id: ID of the rule to toggle
        active: New active status

    Returns:
        Updated constraints list
    """
    updated = []
    for c in constraints:
        if c.rule_id == rule_id:
            # Create new rule with toggled status
            from datetime import datetime

            updated.append(
                FeedbackRule(
                    rule_id=c.rule_id,
                    salesperson_id=c.salesperson_id,
                    type=c.type,
                    scope=c.scope,
                    rule=c.rule,
                    source_quote=c.source_quote,
                    active=active,
                    created_at=c.created_at,
                    updated_at=datetime.now(),
                )
            )
        else:
            updated.append(c)

    return updated