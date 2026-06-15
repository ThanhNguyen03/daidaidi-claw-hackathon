"""
Market Strategy Agent - Real Implementation
=============================================
Uses RAG (buyer personas, competitive intel, objection bank) + LLM
to produce grounded market analysis and sales strategy.
"""

import os
from typing import Optional

from agents.base import BaseAgent
from llm.greennode import get_llm_client
from schemas.state import SalesCaseState, AgentOutput


class MarketStrategyAgent(BaseAgent):
    def __init__(self, **kwargs):
        _here = os.path.dirname(os.path.abspath(__file__))
        super().__init__(
            name="market_strategy",
            model_key="MODEL_MARKET_STRATEGY",
            role_description="Market analysis and sales strategy specialist",
            prompt_path=os.path.join(_here, "prompt.md"),
            knowledge_dir=os.path.join(_here, "knowledge"),
            skills_dir=os.path.join(_here, "skills"),
            **kwargs,
        )

    async def run(self, state: SalesCaseState) -> AgentOutput:
        brief = state.brief

        # Build a query that targets the right KB chunks
        industry = brief.industry if brief else ""
        goal = brief.goal if brief else ""
        audience = brief.target_audience if brief else ""
        query = f"market strategy {industry} {goal} {audience}".strip()

        # Retrieve relevant skills and knowledge via RAG
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
- Target audience: {brief.target_audience or 'Not specified'}
- Budget: {f"{brief.budget_vnd:,} VND" if brief.budget_vnd else 'Not specified'}
- Timeline: {brief.timeline or 'Not specified'}
- Requirements: {", ".join(brief.specific_requirements) if brief.specific_requirements else 'None specified'}
"""

        system_prompt = self.system_prompt + rag_context

        user_prompt = f"""Analyze the market and develop a concrete sales strategy for this client.

{brief_block}
User request: {user_message}

Provide a comprehensive, actionable market strategy with:
1. **Market Overview** — size, growth trends, key opportunities in {industry or 'this market'}
2. **Competitive Landscape** — who are the main competitors and how to position against them
3. **Target Segments** — specific customer segments to prioritize and why
4. **Sales Strategy** — recommended approach, key messages, and differentiators
5. **Objection Handling** — likely objections and how to address them
6. **Recommended Next Steps** — concrete actions for the sales team

Use the knowledge base context provided. Be specific to {industry or 'this industry'} — avoid generic advice.
Respond in the same language as the user request (Vietnamese if the request is in Vietnamese)."""

        try:
            client = get_llm_client(self.name)
            response = client.create_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                stream=False,
                temperature=0.7,
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
                    "strategy": content,
                    "industry": industry,
                    "rag_used": bool(rag_context),
                },
                summary=f"Market strategy completed for {industry or 'client'}",
                confidence=0.85 if rag_context else 0.65,
                needs=None,
                questions=[],
            )

        except Exception as e:
            return AgentOutput(
                agent=self.name,
                status="FAILED",
                payload={"error": str(e)},
                summary=f"Market strategy failed: {e}",
                confidence=0.0,
                needs=None,
                questions=[],
            )


_instance: Optional[MarketStrategyAgent] = None


def get_market_strategy_agent() -> MarketStrategyAgent:
    global _instance
    if _instance is None:
        _instance = MarketStrategyAgent()
    return _instance
