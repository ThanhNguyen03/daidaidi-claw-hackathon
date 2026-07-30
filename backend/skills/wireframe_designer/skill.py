"""
WireframeDesignerSkill
----------------------
Auto-triggered after proposal_assembler completes.
Generates:
  1. AdtimaBox-branded HTML deck (self-contained, viewable in browser) —
     generation/html_deck.py, 14-type/7-section schema.
  2. Adtima-corporate-branded PPTX file (downloadable) — generation/pptx_corporate.py,
     an independent 5-section schema strictly following generation/sample-output.pptx.
  These are extracted from the same proposal_content by two independent LLM calls
  (different schemas) run concurrently, so one extraction failing does not sink
  the other.

Payload keys:
  html_content   — full HTML string
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
                "Generates AdtimaBox-branded proposal deck: "
                "HTML slideshow (viewable URL) + branded PPTX file (downloadable). "
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
                summary="No proposal content available to generate deck",
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

        from generation.html_deck import HTMLDeckGenerator
        from generation.pptx_corporate import CorporatePPTXGenerator
        from generation.pptx_corporate_extract import extract_pptx_slides

        # HTML and PPTX extraction are two independent schemas (different slide
        # types, different section scheme — see PPTX_CORPORATE_SCHEMA.md) run
        # concurrently against the same proposal_content, each with its own
        # no-fabrication/skip-if-absent rules.
        extractor = HTMLDeckGenerator()
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
            slides_data = []
            pptx_slides_data = []
        else:
            results = await asyncio.gather(
                extractor._extract_slides_with_retry(proposal_content, brief_dict),
                extract_pptx_slides(proposal_content, brief_dict),
                return_exceptions=True,
            )
            slides_data, pptx_slides_data = results
            if isinstance(slides_data, BaseException):
                print(f"[WireframeDesigner] HTML slide extraction error: {slides_data}")
                slides_data = extractor._fallback_slides(brief_dict)
            if isinstance(pptx_slides_data, BaseException):
                print(f"[WireframeDesigner] PPTX slide extraction error: {pptx_slides_data}")
                pptx_slides_data = []
        slides_data = extractor._ensure_required_slides(slides_data, brief_dict)
        pptx_content_slides = [s for s in pptx_slides_data if s.get("type") not in ("cover", "closing")]

        # Extraction failing leaves only the scaffold: a cover and a closing slide and
        # nothing between them. That used to be handed over as if it were a finished
        # deck, so the first sign of trouble was a rep opening a two-page proposal.
        # Say it out loud instead.
        content_slides = [s for s in slides_data if s.get("type") not in ("cover", "closing")]
        if not content_slides:
            # A cover and a closing slide is not a deck. It used to be built, stored and
            # offered behind "View Deck" and "Download PPTX" anyway, so the rep's first
            # sign of trouble was opening a two-page proposal. Hand over nothing and say
            # why: no artifact means no artifact to be misled by.
            print(
                "[WireframeDesigner] no content slides extracted — not building a deck "
                f"({len(slides_data)} scaffold slide(s) only)"
            )
            return SkillOutput(
                skill=self.name,
                status="FAILED",
                payload={},
                summary=(
                    "⚠️ Chưa dựng được deck: bước trích nội dung slide không có gì để "
                    "trích (thường do hết hạn mức gọi model ở các bước phân tích trước). "
                    "Chạy lại lệnh tạo proposal sau ít phút."
                ),
                content=(
                    "DECK NOT BUILT — slide-content extraction had no proposal content to "
                    "work from, usually because the analysis skills were rate-limited. No "
                    "deck file and no PPTX exist for this turn.\n"
                    "Tell the rep plainly that the deck could not be built yet and to ask "
                    "again in a few minutes. Do NOT describe, list or link any slide: "
                    "there are none, and there is nothing to download."
                ),
            )

        # HTML render + PPTX build are pure CPU/disk work — 0.5-3s that used to run
        # directly on the event loop, freezing every other rep's SSE stream (and the
        # heartbeat that exists specifically to keep those streams alive) for the
        # duration. One thread for the whole span; both try/except blocks move in
        # verbatim so a partial failure still degrades (html_content="" /
        # pptx_bytes=None) instead of losing the fallback behaviour.
        def _build_artifacts() -> tuple[str, Optional[bytes]]:
            # 1. HTML deck — render only (no extra LLM call)
            html_content = ""
            try:
                html_content = extractor._render_html(slides_data)
            except Exception as e:
                print(f"[WireframeDesigner] HTML render error: {e}")

            # 2. PPTX — build only (no extra LLM call). Skipped, not degraded, if
            # extraction found none of the 5 sections this template covers.
            pptx_bytes: bytes | None = None
            if not pptx_content_slides:
                print("[WireframeDesigner] PPTX extraction produced no content slides — skipping PPTX build")
            else:
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

            return html_content, pptx_bytes

        html_content, pptx_bytes = await asyncio.to_thread(_build_artifacts)

        # A factual manifest of what the deck actually contains. Without it the answer
        # writer has no idea what was built — it was inventing slide lists ("Slide 3:
        # Phân bổ ngân sách…") for a file that held a cover and a closing slide and
        # nothing else. Telling a rep their deck has seven slides when it has two is
        # worse than the empty deck. A deck with no content slides never reaches here;
        # it returns FAILED above.
        titles = []
        for i, s in enumerate(slides_data, 1):
            label = s.get("title") or s.get("brand") or s.get("type", "slide")
            titles.append(f"  {i}. [{s.get('type', '?')}] {str(label)[:70]}")
        pptx_note = (
            "The downloadable PPTX uses a different template/section scheme than this "
            "HTML deck (client requirements, solution, quotation, case study only — no "
            "executive summary or next-steps slides) and may have a different slide count; "
            "do not describe the PPTX's contents as identical to the list below.\n"
            if pptx_bytes else
            "PPTX build was skipped this turn (no PPTX-template sections found) — only the "
            "HTML deck is available; do not mention a downloadable PPTX.\n"
        )
        manifest = (
            f"DECK BUILT — {len(slides_data)} slides, available as an HTML deck"
            + (" and a downloadable PPTX" if pptx_bytes else "")
            + " via the buttons in the chat.\n"
            + pptx_note +
            "These are the actual HTML deck slides. If you describe the deck, describe "
            "THESE and nothing else — never invent a slide that is not on this list.\n"
            + "\n".join(titles)
        )

        return SkillOutput(
            skill=self.name,
            status="COMPLETE",
            payload={
                "html_content": html_content,
                "pptx_bytes": pptx_bytes,
                "session_id": sid,
                "slide_count": len(slides_data),
            },
            summary=f"Đã tạo proposal deck ({len(slides_data)} slide, HTML + PPTX)",
            content=manifest,
        )
