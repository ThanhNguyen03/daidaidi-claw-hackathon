"""
WireframeDesignerSkill
----------------------
Auto-triggered after proposal_assembler completes.
Generates:
  1. AdtimaBox-branded HTML deck (self-contained, viewable in browser)
  2. AdtimaBox-branded PPTX file (downloadable)

Payload keys:
  html_content   — full HTML string
  pptx_path      — absolute path to saved PPTX (or None on failure)
  session_id     — for artifact naming
"""

from __future__ import annotations

import os
import tempfile
import uuid

from skills.base import BaseSkill, SkillContext, SkillOutput

_HERE = os.path.dirname(os.path.abspath(__file__))
_SKILL_MD = os.path.join(_HERE, "SKILL.md")
_ARTIFACTS_DIR = os.path.join(_HERE, "..", "..", "data", "artifacts")


class WireframeDesignerSkill(BaseSkill):
    def __init__(self):
        super().__init__(
            name="wireframe_designer",
            description=(
                "Generates AdtimaBox-branded proposal deck: "
                "HTML slideshow (viewable URL) + branded PPTX file (downloadable). "
                "Auto-triggered after proposal_assembler — do NOT select manually."
            ),
            model_key="MODEL_WIREFRAME_DESIGNER",
            skill_md_path=_SKILL_MD,
        )

    async def execute(self, context: SkillContext) -> SkillOutput:
        from generation.html_deck import create_html_deck_generator
        from generation.pptx_adtimabox import create_adtimabox_pptx_generator

        # Get proposal content — prefer proposal_assembler output, fall back to last assistant msg
        proposal_content = (
            context.previous_outputs.get("proposal_assembler", {}).get("content", "")
        )
        if not proposal_content or len(proposal_content) < 100:
            for m in reversed(context.messages):
                if m.get("role") == "assistant" and len(m.get("content", "")) > 200:
                    proposal_content = m["content"]
                    break

        if not proposal_content or len(proposal_content) < 50:
            return SkillOutput(
                skill=self.name,
                status="FAILED",
                summary="No proposal content available to generate deck",
                content="",
                payload={},
            )

        brief_dict: dict = {}
        if context.brief:
            try:
                brief_dict = context.brief.model_dump(mode="json", exclude_none=True)
            except Exception:
                pass

        try:
            os.makedirs(_ARTIFACTS_DIR, exist_ok=True)
        except Exception:
            pass  # non-fatal; PPTX temp will fall back to system tmpdir

        sid = context.session_id or uuid.uuid4().hex[:10]

        # Pass SKILL.md content to deck generators so LLM extraction uses the spec
        skill_spec = self._skill_content or ""

        # 1. HTML deck
        html_content = ""
        try:
            html_gen = create_html_deck_generator()
            html_content = await html_gen.generate(proposal_content, brief_dict, skill_spec)
        except Exception as e:
            print(f"[WireframeDesigner] HTML generation error: {e}")

        # 2. PPTX — write to system tempfile, read bytes, delete immediately
        pptx_bytes: bytes | None = None
        try:
            pptx_gen = create_adtimabox_pptx_generator()
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".pptx")
            os.close(tmp_fd)
            result = await pptx_gen.generate(proposal_content, brief_dict, tmp_path, skill_spec)
            if result.get("status") == "success" and os.path.exists(tmp_path):
                with open(tmp_path, "rb") as f:
                    pptx_bytes = f.read()
        except Exception as e:
            print(f"[WireframeDesigner] PPTX generation error: {e}")
        finally:
            try:
                if 'tmp_path' in dir() and os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass

        return SkillOutput(
            skill=self.name,
            status="COMPLETE",
            payload={
                "html_content": html_content,
                "pptx_bytes": pptx_bytes,
                "session_id": sid,
            },
            summary="Đã tạo proposal deck (HTML + PPTX)",
            content="",  # no visible chat content — assets delivered via proposal_assets event
        )
