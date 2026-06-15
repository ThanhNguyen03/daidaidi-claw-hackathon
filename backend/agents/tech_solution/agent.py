"""
Tech Solution Agent - Real Implementation
==========================================
Uses RAG (platform knowledge, integration advisor skill) + LLM
to produce grounded technical recommendations and architecture advice.
"""

import os
from typing import Optional

from agents.base import BaseAgent
from llm.greennode import get_llm_client
from schemas.state import SalesCaseState, AgentOutput


class TechSolutionAgent(BaseAgent):
    def __init__(self, **kwargs):
        _here = os.path.dirname(os.path.abspath(__file__))
        super().__init__(
            name="tech_solution",
            model_key="MODEL_TECH_SOLUTION",
            role_description="Technical solution design and integration specialist",
            prompt_path=os.path.join(_here, "prompt.md"),
            knowledge_dir=os.path.join(_here, "knowledge"),
            skills_dir=os.path.join(_here, "skills"),
            **kwargs,
        )

    async def run(self, state: SalesCaseState) -> AgentOutput:
        brief = state.brief

        industry = brief.industry if brief else ""
        goal = brief.goal if brief else ""
        requirements = brief.specific_requirements if brief else []
        query = f"technical solution integration {industry} {goal} {' '.join(requirements)}".strip()

        # Retrieve relevant skills (integration-advisor) and knowledge (platform docs)
        rag_context = await self.build_rag_context(query, skill_top_k=2, knowledge_top_k=3)

        # Most recent user message
        user_message = ""
        for msg in reversed(state.messages):
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
                break

        brief_block = ""
        if brief:
            brief_block = f"""
## Client Brief
- Industry: {brief.industry or 'Not specified'}
- Goal: {brief.goal or 'Not specified'}
- Timeline: {brief.timeline or 'Not specified'}
- Budget: {f"{brief.budget_vnd:,} VND" if brief.budget_vnd else 'Not specified'}
- Specific requirements: {", ".join(requirements) if requirements else 'None specified'}
"""

        # Include outputs from prior agents (e.g. market strategy context)
        prior_context = ""
        if state.outputs.get("market_strategy"):
            ms = state.outputs["market_strategy"]
            if ms.status == "COMPLETE" and "strategy" in ms.payload:
                prior_context = f"\n## Market Strategy Context (from Market Strategy Agent):\n{ms.payload['strategy'][:800]}...\n"

        system_prompt = self.system_prompt + rag_context

        user_prompt = f"""Design the technical solution for this client.

{brief_block}
{prior_context}
User request: {user_message}

Provide concrete, actionable technical recommendations:
1. **Recommended Platform / Technology Stack** — specific products/platforms suited for {industry or 'this use case'} with reasons
2. **Integration Architecture** — how the components connect (CRM, Zalo OA, AdtimaBox, etc.)
3. **Implementation Phases** — breakdown of delivery phases with estimated time per phase
4. **Timeline & Effort Estimate** — realistic timeline given the {brief.timeline or 'stated'} deadline
5. **Technical Risks & Mitigations** — top 3 risks and how to address them
6. **Why This Stack** — justify each key technology choice against alternatives

Use the platform knowledge in the knowledge base. Be specific — reference actual product names and integration patterns.
Respond in the same language as the user request (Vietnamese if the request is in Vietnamese)."""

        try:
            client = get_llm_client(self.name)
            response = client.create_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                stream=False,
                temperature=0.5,
                max_tokens=2500,
            )

            content = (
                response.choices[0].message.content
                if response.choices
                else "No content generated."
            )

            return AgentOutput(
                agent=self.name,
                status="COMPLETE",
                payload={
                    "recommendations": content,
                    "industry": industry,
                    "rag_used": bool(rag_context),
                },
                summary=f"Technical solution designed for {industry or 'client'}",
                confidence=0.85 if rag_context else 0.65,
                needs=None,
                questions=[],
            )

        except Exception as e:
            return AgentOutput(
                agent=self.name,
                status="FAILED",
                payload={"error": str(e)},
                summary=f"Tech solution failed: {e}",
                confidence=0.0,
                needs=None,
                questions=[],
            )


_instance: Optional[TechSolutionAgent] = None


def get_tech_solution_agent() -> TechSolutionAgent:
    global _instance
    if _instance is None:
        _instance = TechSolutionAgent()
    return _instance
