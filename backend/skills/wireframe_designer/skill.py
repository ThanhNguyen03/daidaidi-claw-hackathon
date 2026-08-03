"""
WireframeDesignerSkill
----------------------
Auto-triggered after proposal_assembler completes. Builds the one downloadable
deliverable: an Adtima-corporate-branded PPTX — generation/pptx_corporate.py, a
5-section schema strictly following generation/sample-output.pptx.

This used to build a second artifact alongside it, a self-contained HTML deck
(generation/html_deck.py, a separate 14-type/7-section schema) surfaced as a
"View Deck" button. That was dropped on request: the PPTX is the proposal reps
actually send, and the HTML deck cost a second extraction LLM call on a path
where LLM_MAX_CONCURRENCY=1 puts it directly in the rep's wait. html_deck.py and
its schema in agents/wireframe_designer_agent/SKILL.md are left in place — that
SKILL.md is still this skill's knowledge file — but nothing calls the renderer.

Payload keys:
  pptx_bytes     — PPTX file bytes, or None if extraction found none of the 5
                    sections this template covers
  session_id     — for artifact naming
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import uuid
from typing import Optional

from skills.base import BaseSkill, SkillContext, SkillOutput

_HERE = os.path.dirname(os.path.abspath(__file__))
# Real prompt/schema doc lives in agents/wireframe_designer_agent/SKILL.md (same file
# generation/html_deck.py loads for its extraction LLM call — single source of truth).
_SKILL_MD = os.path.join(_HERE, "..", "..", "agents", "wireframe_designer_agent", "SKILL.md")
_ARTIFACTS_DIR = os.path.join(_HERE, "..", "..", "data", "artifacts")

# Below this, the input cannot be a proposal — see the guard in execute().
_MIN_PROPOSAL_CHARS = 1200


class WireframeDesignerSkill(BaseSkill):
    def __init__(self):
        super().__init__(
            name="wireframe_designer",
            description=(
                "Generates the AdtimaBox-branded proposal as a downloadable PPTX file. "
                "Auto-triggered after proposal_assembler — do NOT select manually."
            ),
            model_key="MODEL_WIREFRAME_DESIGNER",
            skill_md_path=_SKILL_MD,
        )

    def _build_rich_content(self, context: SkillContext) -> str:
        """Aggregate all skill outputs into one rich content block for the deck extractor.
        Includes brief + every available skill output so the LLM has maximum signal."""
        parts: list[str] = []

        if context.brief:
            try:
                brief_dict = context.brief.model_dump(mode="json", exclude_none=True)
                brief_lines = "\n".join(f"- {k}: {v}" for k, v in brief_dict.items() if v)
                if brief_lines:
                    parts.append(f"## CLIENT BRIEF\n{brief_lines}")
            except Exception:
                pass

        prev = context.previous_outputs or {}

        # The assembler runs in the group before this one, so its finished 7-section
        # proposal is normally here — which is what the extraction prompt is written
        # against. The four raw analysis outputs are the fallback for when it failed.
        proposal_content = prev.get("proposal_assembler", {}).get("content", "")
        if proposal_content and len(proposal_content) > 100:
            parts.append(f"## PROPOSAL DOCUMENT\n{proposal_content}")
        else:
            for skill_name in ["market_strategy", "product_solution", "compliance", "design"]:
                content = prev.get(skill_name, {}).get("content", "")
                if content and len(content) > 50:
                    parts.append(f"## {skill_name.upper()} OUTPUT\n{content}")

        return "\n\n---\n\n".join(parts)

    async def execute(self, context: SkillContext) -> SkillOutput:
        # Build rich content from ALL skill outputs for maximum deck fidelity
        proposal_content = self._build_rich_content(context)

        # Fallback: try assembler alone, then last assistant message
        if not proposal_content or len(proposal_content) < 100:
            proposal_content = context.previous_outputs.get("proposal_assembler", {}).get("content", "")
        if not proposal_content or len(proposal_content) < 100:
            for m in reversed(context.messages):
                if m.get("role") == "assistant" and len(m.get("content", "")) > 200:
                    proposal_content = m["content"]
                    break

        if not proposal_content or len(proposal_content) < 50:
            return SkillOutput(
                skill=self.name,
                status="FAILED",
                summary="No proposal content available to generate the PPTX",
                content="",
                payload={},
            )

        brief_dict: dict = {}
        try:
            if context.brief:
                brief_dict = context.brief.model_dump(mode="json", exclude_none=True)
        except Exception:
            pass

        try:
            os.makedirs(_ARTIFACTS_DIR, exist_ok=True)
        except Exception:
            pass  # non-fatal; PPTX temp will fall back to system tmpdir

        sid = context.session_id or uuid.uuid4().hex[:10]

        # _STATIC_INTRO and _CONTENT_ORDER are imported so the manifest below can state
        # the real slide count and order — the same two lists _build_pptx itself works
        # from. validate_pptx.py reads _STATIC_INTRO the same way and for the same
        # reason: the fixed slide count is data, and a copy here would drift.
        from generation.pptx_corporate import (
            CorporatePPTXGenerator, _STATIC_INTRO, _CONTENT_ORDER,
        )
        from generation.pptx_corporate_extract import extract_pptx_slides

        # Extraction is told never to invent content and to skip any slide type its input
        # does not cover, so thin input does not produce a thin deck — it produces one
        # cover slide. Measured: a brief-only input came back at 53 tokens, one slide.
        # A real assembled proposal is upwards of 10k characters, so anything this short
        # means the analysis upstream failed; say so rather than spend a call on a
        # rate-limited tier to be told the same thing.
        if len(proposal_content) < _MIN_PROPOSAL_CHARS:
            print(
                f"[WireframeDesigner] input too thin for a deck "
                f"({len(proposal_content)} chars < {_MIN_PROPOSAL_CHARS}) — "
                "skipping extraction, reporting degraded"
            )
            pptx_slides_data = []
        else:
            try:
                pptx_slides_data = await extract_pptx_slides(proposal_content, brief_dict)
            except Exception as e:
                print(f"[WireframeDesigner] PPTX slide extraction error: {e}")
                pptx_slides_data = []

        # Resolve what the generator will ACTUALLY render, using its own rules:
        # _build_pptx keeps the FIRST slide of each type, drops any type not in
        # _CONTENT_ORDER, and renders them in _CONTENT_ORDER. Doing it here rather than
        # counting the raw extraction is what lets the gate below and the manifest at
        # the end both speak about the real file — a duplicate type or a hallucinated
        # type name would otherwise be counted as a slide the rep never sees.
        by_type: dict[str, dict] = {}
        for s in pptx_slides_data:
            t = s.get("type")
            if t and t not in ("cover", "closing") and t not in by_type:
                by_type[t] = s
        rendered = [(ctype, by_type[ctype]) for ctype, *_ in _CONTENT_ORDER if ctype in by_type]

        # Extraction failing leaves only the scaffold: a cover and a closing slide and
        # nothing between them. That used to be handed over as if it were a finished
        # deck, so the first sign of trouble was a rep opening a two-page proposal.
        # Say it out loud instead. This gate used to key off the HTML deck's own slide
        # list; with the HTML deck gone the PPTX content slides are the only thing left
        # to judge, so it keys off those.
        if not rendered:
            print(
                "[WireframeDesigner] no renderable PPTX content slides — not building a file "
                f"({len(pptx_slides_data)} extracted slide(s), none matching the template)"
            )
            return SkillOutput(
                skill=self.name,
                status="FAILED",
                payload={},
                summary=(
                    "⚠️ Chưa dựng được file proposal: bước trích nội dung slide không có gì "
                    "để trích (thường do hết hạn mức gọi model ở các bước phân tích trước). "
                    "Chạy lại lệnh tạo proposal sau ít phút."
                ),
                content=(
                    "PROPOSAL FILE NOT BUILT — slide-content extraction had no proposal "
                    "content to work from, usually because the analysis skills were "
                    "rate-limited. No PPTX exists for this turn.\n"
                    "Tell the rep plainly that the file could not be built yet and to ask "
                    "again in a few minutes. Do NOT describe, list or link any slide: "
                    "there are none, and there is nothing to download."
                ),
            )

        # The PPTX build is pure CPU/disk work — 0.5-3s that used to run directly on the
        # event loop, freezing every other rep's SSE stream (and the heartbeat that
        # exists specifically to keep those streams alive) for the duration. Kept on its
        # own thread, and kept degrading (pptx_bytes=None) rather than raising.
        def _build_pptx_bytes() -> Optional[bytes]:
            pptx_bytes: bytes | None = None
            tmp_path = None
            try:
                pptx_gen = CorporatePPTXGenerator()
                tmp_fd, tmp_path = tempfile.mkstemp(suffix=".pptx")
                os.close(tmp_fd)
                prs = pptx_gen._build_pptx(pptx_slides_data)
                prs.save(tmp_path)
                with open(tmp_path, "rb") as f:
                    pptx_bytes = f.read()
            except Exception as e:
                import traceback
                print(f"[WireframeDesigner] PPTX build error: {e}")
                traceback.print_exc()
            finally:
                try:
                    if tmp_path and os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                except Exception:
                    pass
            return pptx_bytes

        pptx_bytes = await asyncio.to_thread(_build_pptx_bytes)

        if not pptx_bytes:
            # Extraction found real content but python-pptx could not render it. Same
            # rule as above: no artifact means say so, never hand the synthesizer a
            # manifest for a file that does not exist.
            return SkillOutput(
                skill=self.name,
                status="FAILED",
                payload={},
                summary=(
                    "⚠️ Chưa xuất được file PPTX (lỗi khi dựng file). "
                    "Chạy lại lệnh tạo proposal giúp mình nhé."
                ),
                content=(
                    "PROPOSAL FILE NOT BUILT — slide content was extracted but the PPTX "
                    "build failed. No file exists for this turn. Tell the rep plainly and "
                    "do NOT describe, list or link any slide."
                ),
            )

        # A factual manifest of what the file actually contains. Without it the answer
        # writer has no idea what was built — it was inventing slide lists ("Slide 3:
        # Phân bổ ngân sách…") for a file that held a cover and a closing slide and
        # nothing else. Telling a rep their deck has seven slides when it has two is
        # worse than the empty deck. A file with no content slides never reaches here;
        # it returns FAILED above.
        #
        # `rendered` was resolved above with the generator's own dedupe/order rules, so
        # the count here is the real file: cover + agenda + static intro + these + closing.
        titles = []
        for i, (ctype, s) in enumerate(rendered, 1):
            label = s.get("title") or ctype
            titles.append(f"  {i}. [{ctype}] {str(label)[:70]}")
        total_slides = 2 + len(_STATIC_INTRO) + len(rendered) + 1

        manifest = (
            f"PROPOSAL FILE BUILT — a downloadable PPTX of {total_slides} slides, "
            "available via the download button in the chat. There is no HTML deck and no "
            "'View Deck' link — the PPTX is the only file this turn produced.\n"
            f"Its structure is: a cover, an agenda, {len(_STATIC_INTRO)} fixed Zalo/Adtima "
            "platform slides, then the client-specific slides listed below, then a closing "
            "slide. If you describe the file, describe THESE and nothing else — never "
            "invent a slide that is not on this list.\n"
            + "\n".join(titles)
        )

        return SkillOutput(
            skill=self.name,
            status="COMPLETE",
            payload={
                "pptx_bytes": pptx_bytes,
                "session_id": sid,
                "slide_count": total_slides,
            },
            summary=f"Đã tạo file proposal PPTX ({total_slides} slide)",
            content=manifest,
        )
