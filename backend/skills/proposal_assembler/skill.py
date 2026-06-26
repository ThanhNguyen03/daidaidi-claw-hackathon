"""
ProposalAssemblerSkill
----------------------
Final synthesis skill: assembles all upstream skill outputs (strategy, compliance,
product, design) into a complete, client-ready proposal document.
Does NOT re-run analysis — only synthesizes and formats existing outputs.
"""

from __future__ import annotations

import os

from skills.base import BaseSkill, SkillContext, SkillOutput

_HERE = os.path.dirname(os.path.abspath(__file__))
_AGENTS_DIR = os.path.join(_HERE, "..", "..", "agents", "proposal_assembler_agent")
_SKILL_MD = os.path.join(_AGENTS_DIR, "SKILL.md")
if not os.path.exists(_SKILL_MD):
    _SKILL_MD = os.path.join(_AGENTS_DIR, "prompt.md")


class ProposalAssemblerSkill(BaseSkill):
    def __init__(self):
        super().__init__(
            name="proposal_assembler",
            description="Proposal assembler: synthesizes all skill outputs (strategy, compliance, product, design) into a complete client-ready proposal document",
            model_key="MODEL_PROPOSAL_ASSEMBLER",
            skill_md_path=_SKILL_MD,
        )

    async def execute(self, context: SkillContext) -> SkillOutput:
        system = self._build_system_prompt(context.constraints)

        # Build rich context block from all previous skill outputs
        context_block = self._build_assembly_context(context)
        user_msg = f"{context.task}\n\n{context_block}" if context_block else context.task

        try:
            content = await self._call_llm(
                system=system,
                user_msg=user_msg,
                history=context.messages,
                max_tokens=8192,
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
            payload={"proposal": content, "deliverables": [{"type": "Proposal", "description": content[:200]}]},
            summary=content[:200],
            content=content,
        )

    def _build_assembly_context(self, context: SkillContext) -> str:
        """Build a structured context block from all previous skill outputs.
        previous_outputs is dict[skill_name, {content, summary, payload}].
        """
        parts: list[str] = []

        if context.brief:
            brief_dict = context.brief.model_dump(mode="json", exclude_none=True)
            if brief_dict:
                parts.append("## Client Brief\n" + "\n".join(f"- **{k}:** {v}" for k, v in brief_dict.items()))

        if context.previous_outputs:
            parts.append("## Skill Outputs to Assemble")
            skill_order = ["market_strategy", "compliance", "product_solution", "design"]
            outputs: dict = context.previous_outputs  # type: ignore[assignment]

            # Ordered pass first, then any extras
            for skill_name in skill_order:
                if skill_name not in outputs:
                    continue
                out = outputs[skill_name]
                section_content = out.get("content") or out.get("summary") or ""
                if section_content:
                    parts.append(f"### {skill_name.upper()}\n{section_content}")

            for skill_name, out in outputs.items():
                if skill_name in skill_order:
                    continue
                section_content = out.get("content") or out.get("summary") or ""
                if section_content:
                    parts.append(f"### {skill_name.upper()}\n{section_content}")

        return "\n\n".join(parts)
