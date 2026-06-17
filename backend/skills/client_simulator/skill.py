"""
ClientSimulatorSkill
--------------------
Buyer persona simulator: objection roleplay, competitor defense, pitch preparation coaching.
Uses existing knowledge from agents/client_simulator_agent/reference/ via RAG.
"""

from __future__ import annotations

import os

from skills.base import BaseSkill, SkillContext, SkillOutput

_HERE = os.path.dirname(os.path.abspath(__file__))
_AGENTS_DIR = os.path.join(_HERE, "..", "..", "agents", "client_simulator_agent")
_SKILL_MD = os.path.join(_AGENTS_DIR, "SKILL.md")
if not os.path.exists(_SKILL_MD):
    _SKILL_MD = os.path.join(_AGENTS_DIR, "prompt.md")


class ClientSimulatorSkill(BaseSkill):
    def __init__(self):
        super().__init__(
            name="client_simulator",
            description="Buyer persona simulator: objection roleplay, competitor defense, pitch preparation coaching",
            model_key="MODEL_CLIENT_SIMULATOR",
            skill_md_path=_SKILL_MD,
        )

    async def execute(self, context: SkillContext) -> SkillOutput:
        # Retrieve buyer persona and objection bank knowledge
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
            payload={"objections": [], "content": content},
            summary=content[:200],
            content=content,
        )
