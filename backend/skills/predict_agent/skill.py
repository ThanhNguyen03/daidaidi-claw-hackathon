"""
PredictAgentSkill
-----------------
Tarot & Fortune Reading Assistant: xem bói tarot vui vẻ cho sale team.
Tự động hỏi thông tin (tên, ngày sinh, chủ đề) nếu chưa có trong hội thoại,
skip bước hỏi và bói luôn nếu đã đủ thông tin.
Uses SKILL.md from agents/predict-agent/ as system prompt.
"""

from __future__ import annotations

import os

from skills.base import BaseSkill, SkillContext, SkillOutput

_HERE = os.path.dirname(os.path.abspath(__file__))
_AGENTS_DIR = os.path.join(_HERE, "..", "..", "agents", "predict-agent")
_SKILL_MD = os.path.join(_AGENTS_DIR, "SKILL.md")


class PredictAgentSkill(BaseSkill):
    def __init__(self):
        super().__init__(
            name="predict_agent",
            description="Tarot & fortune reading assistant: collect user info then do fun prediction",
            model_key="MODEL_PREDICT_AGENT",
            skill_md_path=_SKILL_MD,
        )

    async def execute(self, context: SkillContext) -> SkillOutput:
        # Use skill content directly — no external reference injection needed for tarot
        system = self._skill_content

        try:
            content, truncated = await self._call_llm(
                system=system,
                user_msg=context.task,
                history=context.messages,
                max_tokens=2000,
                temperature=0.75,  # Higher temp for more creative, engaging readings
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
            payload={"reading": content},
            summary=(content[:200] + " [Bị cắt do giới hạn độ dài]") if truncated else content[:200],
            content=content,
        )
