"""
CsAgentSkill
------------
CSHub Sale Assistant: hỗ trợ nội bộ cho sale AdtimaBox.
Handles userguide lookup và bug intake flow.
Uses SKILL.md from agents/cs-agent/ as system prompt.
"""

from __future__ import annotations

import os

from skills.base import BaseSkill, SkillContext, SkillOutput

_HERE = os.path.dirname(os.path.abspath(__file__))
_AGENTS_DIR = os.path.join(_HERE, "..", "..", "agents", "cs-agent")
_SKILL_MD = os.path.join(_AGENTS_DIR, "SKILL.md")
_REF_USERGUIDE = os.path.join(_AGENTS_DIR, "reference", "Reference-userguide.md")
_REF_BUG = os.path.join(_AGENTS_DIR, "reference", "Reference-bug.md")


class CsAgentSkill(BaseSkill):
    def __init__(self):
        super().__init__(
            name="cs_agent",
            description="CSHub Sale Assistant: userguide lookup and bug intake for internal sales team",
            model_key="MODEL_CS_AGENT",
            skill_md_path=_SKILL_MD,
        )
        # Load reference docs at init for direct injection (reference/ not in KB knowledge/)
        self._ref_userguide = self._load_file(_REF_USERGUIDE)
        self._ref_bug = self._load_file(_REF_BUG)

    async def execute(self, context: SkillContext) -> SkillOutput:
        system = self._skill_content
        if self._ref_userguide:
            system += f"\n\n---\n## reference-userguide.md\n{self._ref_userguide}"
        if self._ref_bug:
            system += f"\n\n---\n## reference-bug.md\n{self._ref_bug}"

        try:
            content, truncated = await self._call_llm(
                system=system,
                user_msg=context.task,
                history=context.messages,
                max_tokens=2000,
                temperature=0.4,
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
            status="PARTIAL" if truncated else "COMPLETE",
            payload={"response": content},
            summary=(content[:200] + " [Bị cắt do giới hạn độ dài]") if truncated else content[:200],
            content=content,
        )
