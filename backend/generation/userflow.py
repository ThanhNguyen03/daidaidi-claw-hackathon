# Userflow Generation Module
# =========================
# Generates userflow diagrams (Mermaid/FigJam) from approved plans/proposals.

import json
from typing import Optional


class UserflowGenerator:
    """Generates userflow diagrams from approved plans/proposals."""

    def __init__(self):
        """Initialize the userflow generator."""
        pass

    async def generate(
        self,
        plan_data: dict,
        format: str = "mermaid"
    ) -> dict:
        """
        Generate a userflow diagram from plan data.

        Args:
            plan_data: The approved plan/proposal data containing:
                - user_journey: List of user steps/actions
                - decisions: Decision points
                - outcomes: Possible outcomes
            format: Output format - "mermaid" or "figjam"

        Returns:
            dict with status, diagram code, and preview info
        """
        if format == "mermaid":
            return await self._generate_mermaid(plan_data)
        elif format == "figjam":
            return await self._generate_figjam(plan_data)
        else:
            return {
                "status": "error",
                "error": f"Unsupported format: {format}"
            }

    async def _generate_mermaid(self, plan_data: dict) -> dict:
        """Generate a Mermaid flowchart from plan data."""

        # Build journey from plan data
        journey = plan_data.get("user_journey", [])
        decisions = plan_data.get("decisions", [])
        outcomes = plan_data.get("outcomes", [])

        # Start building the Mermaid graph
        lines = ["flowchart TD"]

        # Add styling
        lines.append("    %% Styles")
        lines.append("    classDef startend fill:#22c55e,stroke:#16a34a,color:white")
        lines.append("    classDef process fill:#3b82f6,stroke:#2563eb,color:white")
        lines.append("    classDef decision fill:#f59e0b,stroke:#d97706,color:white")
        lines.append("    classDef outcome fill:#8b5cf6,stroke:#7c3aed,color:white")

        # Add start node
        lines.append("    Start([Start]):::startend")

        if journey:
            # First step
            first_step = journey[0]
            lines.append(f"    Start --> {self._to_node_id(first_step)}[{first_step}]:::process")

            # Middle steps
            for i, step in enumerate(journey[1:], 1):
                prev_step = journey[i-1]
                lines.append(f"    {self._to_node_id(prev_step)} --> {self._to_node_id(step)}[{step}]:::process")

        # Add decision points
        for i, decision in enumerate(decisions):
            node_id = f"Decision{i+1}"
            lines.append(f"    {self._to_node_id(journey[-1] if journey else 'Start')} --> {node_id}{{{decision}}}:::decision")

            # Add outcomes from decision
            for j, outcome in enumerate(outcomes):
                lines.append(f"    {node_id} --> {self._to_node_id(outcome)}[{outcome}]:::outcome")

        # Add end nodes
        if outcomes:
            for outcome in outcomes:
                lines.append(f"    {self._to_node_id(outcome)} --> End([End]):::startend")
        elif journey:
            lines.append(f"    {self._to_node_id(journey[-1])} --> End([End]):::startend")
        else:
            lines.append("    Start --> End([End]):::startend")

        mermaid_code = "\n".join(lines)

        # Generate a simple text preview
        preview = self._generate_text_preview(plan_data)

        return {
            "status": "success",
            "format": "mermaid",
            "code": mermaid_code,
            "preview": preview,
            "nodes": len(journey) + len(decisions) + len(outcomes) + 2,
            "edges": len(journey) + len(decisions) + len(outcomes)
        }

    async def _generate_figjam(self, plan_data: dict) -> dict:
        """Generate a FigJam-compatible structure (for MCP export)."""

        # Build nodes and connectors for FigJam
        journey = plan_data.get("user_journey", [])
        decisions = plan_data.get("decisions", [])
        outcomes = plan_data.get("outcomes", [])

        nodes = []
        connectors = []

        # Start node
        nodes.append({
            "id": "start",
            "type": "ellipse",
            "text": "Start",
            "color": "#22c55e"
        })

        # Journey nodes
        for i, step in enumerate(journey):
            nodes.append({
                "id": f"step_{i}",
                "type": "rectangle",
                "text": step,
                "color": "#3b82f6"
            })

            if i == 0:
                connectors.append({"from": "start", "to": f"step_{i}"})
            else:
                connectors.append({"from": f"step_{i-1}", "to": f"step_{i}"})

        # Decision nodes
        last_step_id = f"step_{len(journey)-1}" if journey else "start"
        for i, decision in enumerate(decisions):
            decision_id = f"decision_{i}"
            nodes.append({
                "id": decision_id,
                "type": "diamond",
                "text": decision,
                "color": "#f59e0b"
            })
            connectors.append({"from": last_step_id, "to": decision_id})
            last_step_id = decision_id

        # Outcome nodes
        for i, outcome in enumerate(outcomes):
            outcome_id = f"outcome_{i}"
            nodes.append({
                "id": outcome_id,
                "type": "rectangle",
                "text": outcome,
                "color": "#8b5cf6"
            })
            connectors.append({"from": last_step_id, "to": outcome_id})

            # End connector
            connectors.append({"from": outcome_id, "to": "end"})

        # End node
        nodes.append({
            "id": "end",
            "type": "ellipse",
            "text": "End",
            "color": "#22c55e"
        })

        if not outcomes and journey:
            connectors.append({"from": last_step_id, "to": "end"})

        return {
            "status": "success",
            "format": "figjam",
            "nodes": nodes,
            "connectors": connectors,
            "preview": self._generate_text_preview(plan_data),
            "node_count": len(nodes),
            "connector_count": len(connectors)
        }

    def _to_node_id(self, text: str) -> str:
        """Convert text to a valid Mermaid node ID."""
        # Remove special chars and limit length
        clean = "".join(c for c in text if c.isalnum() or c == "_")[:20]
        return clean.lower() or "node"

    def _generate_text_preview(self, plan_data: dict) -> str:
        """Generate a simple text preview of the userflow."""

        journey = plan_data.get("user_journey", [])
        decisions = plan_data.get("decisions", [])
        outcomes = plan_data.get("outcomes", [])

        lines = ["=== USERFLOW PREVIEW ===\n"]

        if journey:
            lines.append("User Journey:")
            for i, step in enumerate(journey, 1):
                lines.append(f"  {i}. {step}")
            lines.append("")

        if decisions:
            lines.append("Decision Points:")
            for decision in decisions:
                lines.append(f"  ◇ {decision}")
            lines.append("")

        if outcomes:
            lines.append("Possible Outcomes:")
            for outcome in outcomes:
                lines.append(f"  → {outcome}")

        if not journey and not decisions and not outcomes:
            lines.append("  (No userflow data provided)")

        return "\n".join(lines)

    def get_supported_formats(self) -> list[str]:
        """Return list of supported output formats."""
        return ["mermaid", "figjam"]


# Factory function for creating generator
def create_userflow_generator() -> UserflowGenerator:
    """Create a userflow generator instance."""
    return UserflowGenerator()


# Render Mermaid to SVG (stub - requires mermaid-cli or similar)
async def render_mermaid_to_svg(mermaid_code: str) -> Optional[bytes]:
    """
    Render Mermaid code to SVG.
    Requires mermaid-cli to be installed: npm install -g mermaid
    """
    try:
        import subprocess
        result = subprocess.run(
            ["mmdc", "-i", "-", "-o", "-"],
            input=mermaid_code,
            capture_output=True,
            timeout=30
        )
        if result.returncode == 0:
            return result.stdout
    except Exception:
        pass
    return None