"""
Content Generator Agent (A6)
==============================
Synthesises Group-1 outputs (strategy, compliance, adtimabox) into
a cohesive proposal narrative: insight, solution, user journey, earn/burn.

This agent MUST run after Group-1 agents complete — it reads state.outputs
to build its context, so its parallel_group must be > Group-1's value.
"""

import os
from typing import Optional

from agents.base import BaseAgent
from llm.greennode import get_llm_client
from schemas.state import SalesCaseState, AgentOutput


def _extract_text(output, *payload_keys: str) -> str:
    """Pull text from an AgentOutput's payload (tries each key) or falls back to summary."""
    if output is None or output.status != "COMPLETE":
        return ""
    payload = getattr(output, "payload", {}) or {}
    for key in payload_keys:
        if key in payload and payload[key]:
            return str(payload[key])
    return output.summary or ""


class ContentGeneratorAgent(BaseAgent):
    def __init__(self, **kwargs):
        _here = os.path.dirname(os.path.abspath(__file__))
        super().__init__(
            name="content_generator",
            model_key="MODEL_CONTENT_GENERATOR",
            role_description="Proposal content writer — synthesises analysis into narrative",
            prompt_path=os.path.join(_here, "prompt.md"),
            knowledge_dir=os.path.join(_here, "knowledge"),
            skills_dir=os.path.join(_here, "skills"),
            **kwargs,
        )

    async def run(self, state: SalesCaseState) -> AgentOutput:
        brief = state.brief
        outputs = state.outputs or {}

        # ── Gather Group-1 outputs ────────────────────────────────────────
        strategy_text = _extract_text(outputs.get("market_strategy"), "strategy")
        tech_text = _extract_text(outputs.get("tech_solution"), "recommendations")
        compliance_text = _extract_text(outputs.get("compliance"), "findings", "narrative", "summary")
        product_text = _extract_text(outputs.get("adtimabox"), "integration", "summary")

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
"""

        analysis_block = ""
        if strategy_text:
            analysis_block += f"\n## Market Strategy Analysis:\n{strategy_text}\n"
        if tech_text:
            analysis_block += f"\n## Technical Solution (from Tech Team):\n{tech_text}\n"
        if compliance_text:
            analysis_block += f"\n## Compliance Notes:\n{compliance_text}\n"
        if product_text:
            analysis_block += f"\n## Product Expert Notes:\n{product_text}\n"

        if not analysis_block:
            analysis_block = "\n*(No prior agent analysis available — use brief context only)*\n"

        system_prompt = self.system_prompt

        user_prompt = f"""Using the analysis below, write the proposal content for this client.

{brief_block}
User request: {user_message}

--- ANALYSIS FROM SPECIALIST AGENTS ---
{analysis_block}
--- END ANALYSIS ---

Write a complete proposal narrative with these sections:
1. **Insight khách hàng** — pain point, market context, opportunity for this client
2. **Giải pháp đề xuất** — how our products (ZNS, Mini App, OA, AdtimaBox) solve their specific problem
3. **Hành trình người dùng** — awareness → engagement → loyalty → advocacy with concrete touchpoints
4. **Mô hình giá trị (Earn/Burn)** — how the solution creates revenue and saves cost
5. **Tại sao chọn chúng tôi** — competitive differentiation vs alternatives

Be specific to {brief.industry if brief and brief.industry else 'this industry'}.
Do NOT write generic filler — every paragraph must reference the client's actual context.
Respond in the same language as the user request (Vietnamese if written in Vietnamese)."""

        try:
            client = get_llm_client(self.name)
            response = client.create_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                stream=False,
                temperature=0.7,
                max_tokens=3000,
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
                    "content": content,
                    "sources_used": {
                        "strategy": bool(strategy_text),
                        "compliance": bool(compliance_text),
                        "product": bool(product_text),
                    },
                },
                summary="Proposal content written",
                confidence=0.85 if (strategy_text or compliance_text) else 0.55,
                needs=None,
                questions=[],
            )

        except Exception as e:
            return AgentOutput(
                agent=self.name,
                status="FAILED",
                payload={"error": str(e)},
                summary=f"Content generation failed: {e}",
                confidence=0.0,
                needs=None,
                questions=[],
            )


_instance: Optional[ContentGeneratorAgent] = None


def get_content_generator_agent() -> ContentGeneratorAgent:
    global _instance
    if _instance is None:
        _instance = ContentGeneratorAgent()
    return _instance
