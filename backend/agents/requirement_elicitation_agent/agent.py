"""
Requirement Elicitation Agent
=============================
Transforms a loose brief into a structured requirement summary and only
asks the minimum number of clarifying questions needed to unblock routing.
"""

from __future__ import annotations

import os
from typing import Optional

from agents.base import BaseAgent
from llm.greennode import get_llm_client
from schemas.state import AgentOutput, Brief, Question, SalesCaseState


class RequirementElicitationAgent(BaseAgent):
    def __init__(self, **kwargs):
        _here = os.path.dirname(os.path.abspath(__file__))
        super().__init__(
            name="requirement_elicitation",
            model_key="MODEL_REQUIREMENT_ELICITATION",
            role_description="Requirement elicitation and brief normalization specialist",
            prompt_path=os.path.join(_here, "SKILL.md"),
            knowledge_dir=os.path.join(_here, "reference"),
            skills_dir=os.path.join(_here, "reference"),
            **kwargs,
        )

    def _missing_questions(self, brief: Optional[Brief]) -> list[Question]:
        brief = brief or Brief()
        question_specs = [
            ("industry", "What industry or business model is this for?"),
            ("goal", "What business outcome do you want this to support?"),
            ("target_audience", "Who is the target audience or user segment?"),
            ("budget_vnd", "What is the budget range for this scope?"),
            ("timeline", "What is the target timeline?"),
        ]
        questions: list[Question] = []
        for field, text in question_specs:
            if not getattr(brief, field, None):
                questions.append(
                    Question(
                        id=f"requirement_{field}",
                        text=text,
                        priority=1,
                        is_mandatory=True,
                        assumption=None,
                        target_field=field,
                    )
                )
        return questions[:3]

    async def run(self, state: SalesCaseState) -> AgentOutput:
        brief = state.brief
        questions = self._missing_questions(brief)
        if questions:
            return AgentOutput(
                agent=self.name,
                status="NEEDS_INPUT",
                payload={
                    "missing_context": [q.target_field for q in questions],
                    "next_questions": [q.model_dump() for q in questions],
                },
                summary="Need a little more context before normalizing the brief.",
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
                "requirement elicitation",
                industry or "",
                goal or "",
                audience or "",
                " ".join(reqs or []),
                " ".join(constraints or []),
            ]
        ).strip()
        rag_context = await self.build_rag_context(query, skill_top_k=2, knowledge_top_k=3)
        system_prompt = self.system_prompt + rag_context

        prompt = f"""Normalize this brief into a structured requirement summary.

Rules:
- Do not assume missing facts.
- Keep only what is explicitly provided or clearly inferred from the brief.
- Flag anything that still needs confirmation.

Brief:
- Industry: {industry}
- Goal: {goal}
- Audience: {audience}
- Requirements: {', '.join(reqs) if reqs else 'None'}
- Constraints: {', '.join(constraints) if constraints else 'None'}

Return JSON-like content with:
1. requirement_summary
2. as_is
3. to_be
4. constraint_map
5. unresolved_questions
"""
        try:
            client = get_llm_client(self.name)
            response = client.create_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                stream=False,
                temperature=0.3,
                max_tokens=1800,
            )
            content = response.choices[0].message.content if response.choices else ""
            return AgentOutput(
                agent=self.name,
                status="COMPLETE",
                payload={
                    "requirement_summary": content,
                    "industry": industry,
                    "goal": goal,
                    "target_audience": audience,
                    "rag_used": bool(rag_context),
                },
                summary="Requirement summary prepared",
                confidence=0.85 if rag_context else 0.7,
                needs=None,
                questions=[],
            )
        except Exception as exc:
            return AgentOutput(
                agent=self.name,
                status="FAILED",
                payload={"error": str(exc)},
                summary=f"Requirement elicitation failed: {exc}",
                confidence=0.0,
                needs=None,
                questions=[],
            )


_instance: Optional[RequirementElicitationAgent] = None


def get_requirement_elicitation_agent() -> RequirementElicitationAgent:
    global _instance
    if _instance is None:
        _instance = RequirementElicitationAgent()
    return _instance
