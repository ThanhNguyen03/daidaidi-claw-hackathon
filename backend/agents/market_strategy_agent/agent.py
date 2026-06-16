"""
Market Strategy Agent
=====================
Grounded market analysis and sales strategy specialist.
"""

from __future__ import annotations

import os
from typing import Optional

from agents.base import BaseAgent
from llm.greennode import get_llm_client
from schemas.state import AgentOutput, SalesCaseState


class MarketStrategyAgent(BaseAgent):
    def __init__(self, **kwargs):
        _here = os.path.dirname(os.path.abspath(__file__))
        super().__init__(
            name="market_strategy",
            model_key="MODEL_MARKET_STRATEGY",
            role_description="Market analysis and sales strategy specialist",
            prompt_path=os.path.join(_here, "SKILL.md"),
            knowledge_dir=os.path.join(_here, "reference"),
            skills_dir=os.path.join(_here, "reference"),
            **kwargs,
        )

    def _latest_user_message(self, state: SalesCaseState) -> str:
        for msg in reversed(state.messages):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return ""

    def _build_missing_context_notes(self, state: SalesCaseState) -> tuple[list[str], str]:
        brief = state.brief
        missing_fields: list[str] = []
        if not brief:
            missing_fields = ["industry", "goal", "target_audience"]
        else:
            for field in ["industry", "goal", "target_audience"]:
                if not getattr(brief, field, None):
                    missing_fields.append(field)

        if not missing_fields:
            return [], ""

        notes = (
            "Missing or unconfirmed context: "
            + ", ".join(missing_fields)
            + ". Proceed with best effort only and label unsupported points as pending confirmation."
        )
        return missing_fields, notes

    async def run(self, state: SalesCaseState) -> AgentOutput:
        brief = state.brief
        missing_fields, missing_notes = self._build_missing_context_notes(state)

        industry = brief.industry if brief else ""
        goal = brief.goal if brief else ""
        audience = brief.target_audience if brief else ""
        reqs = brief.specific_requirements if brief else []

        query = " ".join([
            "market strategy",
            industry or "",
            goal or "",
            audience or "",
            " ".join(reqs or []),
        ]).strip()
        rag_context = await self.build_required_skill_context(query, skill_top_k=2, knowledge_top_k=3)
        user_message = self._latest_user_message(state)
        system_prompt = self.system_prompt + rag_context

        user_prompt = f"""Analyze the client brief and produce a market strategy grounded only in the provided context.

Client brief:
- Industry: {industry or 'Not specified'}
- Goal: {goal or 'Not specified'}
- Target audience: {audience or 'Not specified'}
- Requirements: {', '.join(reqs) if reqs else 'None'}

User request:
{user_message or 'No extra message provided'}

Return a concise but useful strategy with:
1. Problem framing
2. Market context
3. Competitive positioning
4. Audience prioritization
5. Key messages / objection handling
6. Recommended next steps

Do not invent unsupported market facts. If something is not in the provided context, label it as unconfirmed or pending confirmation.
{missing_notes}
"""

        try:
            client = get_llm_client(self.name)
            response = client.create_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                stream=False,
                temperature=0.6,
                max_tokens=2200,
            )
            content = response.choices[0].message.content if response.choices else ""
            return AgentOutput(
                agent=self.name,
                status="COMPLETE",
                payload={
                    "strategy": content,
                    "industry": industry,
                    "goal": goal,
                    "target_audience": audience,
                    "missing_context": missing_fields,
                    "rag_used": bool(rag_context),
                },
                summary=f"Market strategy completed for {industry or 'client'}" + (" with best-effort constraints noted" if missing_fields else ""),
                confidence=0.85 if rag_context else 0.65,
                needs=None,
                questions=[],
            )
        except Exception as exc:
            return AgentOutput(
                agent=self.name,
                status="FAILED",
                payload={"error": str(exc)},
                summary=f"Market strategy failed: {exc}",
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
