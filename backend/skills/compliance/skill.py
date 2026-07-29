"""
ComplianceSkill
---------------
Legal safety controller: Zalo policy audits, PDPL 2025, Vietnamese Advertising Law, risk classification.
Uses existing knowledge from agents/compliance_policy_agent/reference/ via RAG.
"""

from __future__ import annotations

import os
import re

from skills.base import BaseSkill, SkillContext, SkillOutput

_HERE = os.path.dirname(os.path.abspath(__file__))
_AGENTS_DIR = os.path.join(_HERE, "..", "..", "agents", "compliance_policy_agent")
_SKILL_MD = os.path.join(_AGENTS_DIR, "SKILL.md")
if not os.path.exists(_SKILL_MD):
    _SKILL_MD = os.path.join(_AGENTS_DIR, "prompt.md")

# SKILL.md requires the model to emit a line like "VERDICT: CLEAR (Đủ điều kiện
# triển khai)" — the ASCII token is what proposal_assembler's Rule 1 and
# wireframe_designer's compliance gate match on, and it was previously nowhere
# in the payload: `narrative`/`findings` carried only prose, so nothing
# downstream could gate on it despite compliance's own SKILL.md claiming its
# workflow ends in "Gate downstream". Defaults to CONDITIONS (not CLEAR) when
# the model omits the line — an unrecognised verdict should read as "not
# fully cleared", never as a silent pass.
_VERDICT_RE = re.compile(r"VERDICT:\s*(CLEAR|CONDITIONS|BLOCKED)", re.IGNORECASE)


def _extract_verdict(text: str) -> str:
    m = _VERDICT_RE.search(text or "")
    return m.group(1).upper() if m else "CONDITIONS"


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
        ref_context = await self.retrieve_reference_context(context, top_k=4)

        system = self._build_system_prompt(context.constraints)
        if ref_context:
            system = system + ref_context

        context_block = self._build_context_block(context)
        user_msg = f"{context.task}\n\n{context_block}" if context_block else context.task

        try:
            content, truncated = await self._call_llm(
                system=system,
                user_msg=user_msg,
                history=context.messages,
                # Was 2000 for four Vietnamese artifacts (findings, checklist,
                # required docs, safe-content parameters) with no length
                # guidance in SKILL.md — the same budget market_strategy gets
                # for six. Vietnamese runs token-heavy, so 2000 was a real
                # truncation risk on a full audit.
                max_tokens=3500,
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
            payload={"findings": content, "narrative": content, "verdict": _extract_verdict(content)},
            summary=(content[:200] + " [Bị cắt do giới hạn độ dài]") if truncated else content[:200],
            content=content,
        )
