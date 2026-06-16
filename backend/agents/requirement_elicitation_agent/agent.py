"""
Requirement Elicitation Agent
=============================
Transforms a loose brief into a structured requirement summary and only
asks the minimum number of clarifying questions needed to unblock routing.
"""

from __future__ import annotations

import json
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

    async def _missing_questions(
        self,
        state: SalesCaseState,
        validation_missing: Optional[list[str]] = None,
        validation_ambiguities: Optional[list] = None,
    ) -> list[Question]:
        brief = state.brief or Brief()
        missing_fields = list(validation_missing or [])
        if not missing_fields:
            for field in ["industry", "goal", "target_audience", "budget_vnd", "timeline"]:
                if not getattr(brief, field, None):
                    missing_fields.append(field)

        ambiguity_fields = []
        for amb in validation_ambiguities or []:
            field = getattr(amb, "field", None)
            if field:
                ambiguity_fields.append(field)

        if not missing_fields:
            return []

        query = " ".join(
            [
                "requirement elicitation",
                brief.industry or "",
                brief.goal or "",
                brief.target_audience or "",
                brief.additional_context or "",
                " ".join(brief.specific_requirements or []),
                " ".join(brief.constraints or []),
                " ".join(missing_fields),
                " ".join(ambiguity_fields),
            ]
        ).strip()

        rag_context = await self.build_required_skill_context(query, skill_top_k=2, knowledge_top_k=2)
        system_prompt = (
            self.system_prompt
            + rag_context
            + "\n\n"
            + "You are asking the minimum set of clarifying questions needed to unblock execution. "
            + "Do not use internal layer names in the chat. Ask at most 3 questions. "
            + "Prefer the most blocking unknowns first. Return JSON only."
        )

        prompt = f"""
Generate clarifying questions from the current brief.

Missing fields: {", ".join(missing_fields) if missing_fields else "None"}
Ambiguities: {", ".join(ambiguity_fields) if ambiguity_fields else "None"}

Current brief:
- Industry: {brief.industry or "not specified"}
- Goal: {brief.goal or "not specified"}
- Audience: {brief.target_audience or "not specified"}
- Budget: {brief.budget_vnd or "not specified"}
- Timeline: {brief.timeline or "not specified"}
- Requirements: {", ".join(brief.specific_requirements or []) or "None"}
- Constraints: {", ".join(brief.constraints or []) or "None"}
- Additional context: {brief.additional_context or "None"}

Return JSON with:
{{
  "questions": [
    {{
      "field": "industry|goal|target_audience|budget_vnd|timeline|constraints|specific_requirements|additional_context",
      "text": "friendly user-facing question",
      "priority": 1,
      "is_mandatory": true,
      "options": ["optional", "choices", "if", "useful"]
    }}
  ]
}}

Rules:
- Ask no more than 3 questions.
- Ask only what is needed to unblock the next step.
- Use plain language for sales/account users.
- Do not mention layers, framework names, or internal policy.
"""

        try:
            client = get_llm_client(self.name)
            response = client.create_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                stream=False,
                temperature=0.2,
                max_tokens=900,
            )
            content = response.choices[0].message.content if response.choices else "{}"
            if "```json" in content:
                content = content.split("```json", 1)[1].split("```", 1)[0]
            elif "```" in content:
                content = content.split("```", 1)[1].split("```", 1)[0]

            data = json.loads(content.strip() or "{}")
            questions: list[Question] = []
            for item in data.get("questions", [])[:3]:
                field = item.get("field")
                text = item.get("text")
                if not field or not text:
                    continue
                questions.append(
                    Question(
                        id=f"requirement_{field}",
                        text=text,
                        priority=int(item.get("priority", 1)),
                        is_mandatory=bool(item.get("is_mandatory", True)),
                        assumption=None,
                        target_field=field,
                        options=item.get("options"),
                    )
                )
            if questions:
                return questions
        except Exception as exc:
            print(f"Warning: requirement question synthesis failed, falling back to templates: {exc}")

        return []

    async def generate_questions(
        self,
        state: SalesCaseState,
        validation_missing: Optional[list[str]] = None,
        validation_ambiguities: Optional[list] = None,
    ) -> list[Question]:
        return await self._missing_questions(state, validation_missing, validation_ambiguities)

    async def run(self, state: SalesCaseState) -> AgentOutput:
        brief = state.brief
        questions = await self._missing_questions(state)
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
        rag_context = await self.build_required_skill_context(query, skill_top_k=2, knowledge_top_k=3)
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
