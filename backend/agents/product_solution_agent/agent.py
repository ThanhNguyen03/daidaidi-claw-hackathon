"""
Product Solution Agent
======================
Merged product expert for AdtimaBox capabilities, solution design,
integration hints, and pricing references.

This agent is conservative by design:
- Uses only provided brief, prior agent outputs, and internal references
- Returns NEEDS_INPUT when required context is missing
- Never invents pricing or capability claims beyond internal knowledge
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Optional

from agents.base import BaseAgent
from llm.greennode import get_llm_client
from schemas.state import AgentOutput, Brief, Question, SalesCaseState


class ProductSolutionAgent(BaseAgent):
    def __init__(self, **kwargs):
        _here = os.path.dirname(os.path.abspath(__file__))
        super().__init__(
            name="product_solution",
            model_key="MODEL_PRODUCT_SOLUTION",
            role_description="Merged product expert for solution design, integration guidance, and pricing references",
            prompt_path=os.path.join(_here, "SKILL.md"),
            knowledge_dir=os.path.join(_here, "reference"),
            skills_dir=os.path.join(_here, "reference"),
            **kwargs,
        )

    def _required_questions(self, brief: Optional[Brief]) -> list[Question]:
        brief = brief or Brief()
        question_specs = [
            ("industry", "What industry or business model is this solution for?"),
            ("goal", "What business outcome should this solution support?"),
            ("target_audience", "Who is the target audience or member segment?"),
        ]
        questions: list[Question] = []
        for field, text in question_specs:
            if not getattr(brief, field, None):
                questions.append(
                    Question(
                        id=f"product_solution_{field}",
                        text=text,
                        priority=1,
                        is_mandatory=True,
                        assumption=None,
                        target_field=field,
                    )
                )
        return questions

    def _rate_card(self) -> dict:
        return {
            "package_base": {"name": "Base package", "price": 50000000, "unit": "project"},
            "integration_addon": {"name": "Integration add-on", "price": 25000000, "unit": "project"},
            "custom_flow": {"name": "Custom flow / unique code", "price": 20000000, "unit": "project"},
            "wireframe": {"name": "Wireframe / slide outline", "price": 15000000, "unit": "project"},
        }

    async def run(self, state: SalesCaseState) -> AgentOutput:
        brief = state.brief
        questions = self._required_questions(brief)
        if questions:
            return AgentOutput(
                agent=self.name,
                status="NEEDS_INPUT",
                payload={"missing_context": [q.target_field for q in questions]},
                summary="Need more context before proposing the product solution and pricing.",
                confidence=0.9,
                questions=questions,
            )

        industry = brief.industry if brief else ""
        goal = brief.goal if brief else ""
        audience = brief.target_audience if brief else ""
        reqs = brief.specific_requirements if brief else []
        constraints = brief.constraints if brief else []

        query = " ".join(
            [
                "product solution",
                industry or "",
                goal or "",
                audience or "",
                " ".join(reqs or []),
                " ".join(constraints or []),
            ]
        ).strip()
        rag_context = await self.build_required_skill_context(query, skill_top_k=2, knowledge_top_k=4)

        market_output = state.outputs.get("market_strategy")
        compliance_output = state.outputs.get("compliance")

        context_chunks = []
        if market_output and market_output.payload:
            context_chunks.append(str(market_output.payload.get("strategy") or market_output.summary))
        if compliance_output and compliance_output.payload:
            context_chunks.append(str(compliance_output.payload.get("summary") or compliance_output.summary))

        user_message = ""
        for msg in reversed(state.messages):
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
                break

        system_prompt = self.system_prompt + rag_context
        user_prompt = f"""
You are the merged product solution expert.

Rules:
- Use only the brief, prior agent outputs, and internal references.
- Do not invent unsupported product capabilities or prices.
- If a module, integration, or price cannot be confirmed, label it as pending confirmation.

Client brief:
- Industry: {industry}
- Goal: {goal}
- Audience: {audience}
- Requirements: {", ".join(reqs) if reqs else "None"}
- Constraints: {", ".join(constraints) if constraints else "None"}

Prior context:
{chr(10).join(f"- {chunk}" for chunk in context_chunks) if context_chunks else "- None"}

User message:
{user_message}

Return JSON-like content with:
1. solution_summary
2. recommended_modules
3. integration_notes
4. pricing_breakdown
5. timeline_estimate
6. confirmation_flags
"""

        try:
            client = get_llm_client(self.name)
            response = client.create_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                stream=False,
                temperature=0.3,
                max_tokens=2200,
            )
            content = response.choices[0].message.content if response.choices else ""

            rate_card = self._rate_card()
            subtotal = sum(item["price"] for item in rate_card.values())
            total_vnd = int(subtotal * 1.08)
            valid_until = (datetime.now() + timedelta(days=30)).date().isoformat()

            return AgentOutput(
                agent=self.name,
                status="COMPLETE",
                payload={
                    "solution_summary": content,
                    "recommended_modules": ["Base package", "Integration add-on", "Wireframe / slide outline"],
                    "integration_notes": "Needs explicit tech confirmation for any system-specific connector or data sync pattern.",
                    "pricing_breakdown": {
                        "items": [
                            {"name": item["name"], "price": item["price"], "unit": item["unit"], "is_estimate": False}
                            for item in rate_card.values()
                        ],
                        "subtotal": subtotal,
                        "vat_8_percent": int(subtotal * 0.08),
                        "total_vnd": total_vnd,
                        "valid_until": valid_until,
                    },
                    "timeline_estimate": "3-6 weeks depending on integration scope and approval gates",
                    "confirmation_flags": [
                        "Any custom integration or data sync needs tech confirmation",
                        "Any unsupported product capability must be clarified before proposal output",
                    ],
                    "rag_used": bool(rag_context),
                },
                summary=f"Product solution prepared for {industry or 'client'}",
                confidence=0.8 if rag_context else 0.6,
                needs=None,
                questions=[],
            )
        except Exception as exc:
            return AgentOutput(
                agent=self.name,
                status="FAILED",
                payload={"error": str(exc)},
                summary=f"Product solution failed: {exc}",
                confidence=0.0,
                needs=None,
                questions=[],
            )


_instance: Optional[ProductSolutionAgent] = None


def get_product_solution_agent() -> ProductSolutionAgent:
    global _instance
    if _instance is None:
        _instance = ProductSolutionAgent()
    return _instance
