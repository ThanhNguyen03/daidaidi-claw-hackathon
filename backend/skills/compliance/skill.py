"""
ComplianceSkill
---------------
Legal safety controller: Zalo policy audits, PDPL 2025, Vietnamese Advertising Law, risk classification.
Uses existing knowledge from agents/compliance_policy_agent/reference/ via RAG.
"""

from __future__ import annotations

import os

from skills.base import BaseSkill, SkillContext, SkillOutput

_HERE = os.path.dirname(os.path.abspath(__file__))
_AGENTS_DIR = os.path.join(_HERE, "..", "..", "agents", "compliance_policy_agent")
_SKILL_MD = os.path.join(_AGENTS_DIR, "SKILL.md")
if not os.path.exists(_SKILL_MD):
    _SKILL_MD = os.path.join(_AGENTS_DIR, "prompt.md")


class ComplianceSkill(BaseSkill):
    def __init__(self):
        super().__init__(
            name="compliance",
            description="Legal safety controller: Zalo policy audits, PDPL 2025, Vietnamese Advertising Law, risk classification",
            model_key="MODEL_COMPLIANCE",
            skill_md_path=_SKILL_MD,
        )

    async def execute(self, context: SkillContext) -> SkillOutput:
        # Retrieve compliance reference knowledge: policies, laws, regulations
        ref_context = await self.retrieve_reference_context(context.task, top_k=4)

        system = self._build_system_prompt(context.constraints)
        if ref_context:
            system = system + ref_context

        context_block = self._build_context_block(context)
        user_msg = f"{context.task}\n\n{context_block}" if context_block else context.task

        try:
            content = await self._call_llm(
                system=system,
                user_msg=user_msg,
                history=context.messages,
                max_tokens=3000,
            )
        except Exception as e:
            return SkillOutput(
                skill=self.name,
                status="FAILED",
                payload={"error": str(e)},
                summary=f"Skill {self.name} failed: {e}",
                content="",
            )

        return SkillOutput(
            skill=self.name,
            status="COMPLETE",
            payload={"findings": content, "narrative": content},
            summary=content[:200],
            content=content,
        )
