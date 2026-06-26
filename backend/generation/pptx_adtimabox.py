"""
AdtimaBox-branded PPTX generator.
Follows adtimabox-deck-pptx.skill design system:
  - Slide: 10" × 5.625" (16:9 widescreen)
  - Brand: orange #F65009, teal #0F9B8E, ink #1D1D1F
  - Font: Calibri (closest widely available to Inter)
  - Layouts: title, value, flow, tier, closing
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from functools import partial
from typing import Any, Optional

# Brand palette — RGB (0-255)
_C = {
    "orange":  (246, 80, 9),
    "teal":    (15, 155, 142),
    "ink":     (29, 29, 31),
    "white":   (255, 255, 255),
    "cream":   (251, 248, 245),
    "line":    (236, 230, 225),
    "muted":   (120, 120, 125),
    "purple":  (91, 79, 196),
    "gold":    (200, 147, 43),
}

SLIDE_W = 10.0     # inches
SLIDE_H = 5.625    # inches
FONT = "Calibri"

# Layout constants (inches)
PAD_L = 0.55
PAD_T = 0.90   # below topbar
PAD_R = 0.55
TOPBAR_H = 0.45
CONTENT_W = SLIDE_W - PAD_L - PAD_R
CONTENT_H = SLIDE_H - TOPBAR_H - PAD_T - 0.35  # usable content area

_EXTRACT_SYSTEM = """You are a slide-deck content extractor.
Given a sales proposal in Markdown, extract structured data for a presentation deck.
Return ONLY a valid JSON array (no markdown fences). Max 6 slides total.

Slide types and schema:
{"type":"title", "headline":"<short headline>", "sub":"<1 sentence>", "brand":"<brand/client name>", "date":"<month year>"}
{"type":"value", "title":"<slide title>", "features":["<8 words max each>"], "stat_value":"<big number or %>", "stat_label":"<3 words>"}
{"type":"flow", "title":"<slide title>", "steps":[{"label":"<3 words>","desc":"<8 words>"}]}
{"type":"tier", "title":"Báo giá / Pricing", "tiers":[{"name":"<tier name>","price":"<price string>","note":"<short note>","perks":["<feature>"]}]}
{"type":"closing", "headline":"<call to action>", "sub":"<1 sentence next step>", "contact":"contact@adtima.vn"}

Rules:
- title slide: always first
- closing slide: always last
- value slides: 1-3 slides for strategy/solution content
- flow slide: if solution has user journey steps
- tier slide: only if pricing info exists in proposal
- Keep all text SHORT (≤10 words per item)
- features: max 5 items per value slide
- steps: max 5 steps per flow slide
- tiers: max 3 tiers
- Return ONLY the JSON array, nothing else"""


class AdtimaBoxPPTXGenerator:
    """Generates AdtimaBox-branded PPTX from proposal markdown."""

    async def generate(
        self,
        proposal_text: str,
        brief: dict,
        output_path: str,
    ) -> dict:
        try:
            from pptx import Presentation
            from pptx.util import Inches, Emu
            from pptx.dml.color import RGBColor
        except ImportError:
            return {"status": "error", "error": "python-pptx not installed"}

        try:
            slides_data = await self._extract_slides(proposal_text, brief)
        except Exception as e:
            print(f"[PPTX] Slide extraction failed ({e}), using fallback")
            slides_data = self._fallback_slides(brief)

        try:
            prs = self._build_pptx(slides_data)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            prs.save(output_path)
            return {"status": "success", "file_path": output_path, "slide_count": len(slides_data)}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _extract_slides(self, proposal_text: str, brief: dict) -> list[dict]:
        from llm.greennode import get_llm_client
        from skills.base import strip_think_blocks, extract_json_block

        client = get_llm_client("central_agent")
        brand_hint = (brief or {}).get("industry", "") or ""
        trimmed = proposal_text[:4000]

        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(
            None,
            partial(
                client.create_completion,
                messages=[
                    {"role": "system", "content": _EXTRACT_SYSTEM},
                    {"role": "user", "content": f"Brand hint: {brand_hint}\n\n---\n{trimmed}"},
                ],
                temperature=0.1,
                max_tokens=1200,
                stream=False,
            ),
        )
        raw = strip_think_blocks(resp.choices[0].message.content or "[]")
        raw = extract_json_block(raw)
        data = json.loads(raw)
        if not isinstance(data, list) or not data:
            return self._fallback_slides(brief)
        return data

    def _fallback_slides(self, brief: dict) -> list[dict]:
        b = brief or {}
        return [
            {"type": "title", "headline": "Đề xuất giải pháp Zalo", "sub": "Powered by Adtima",
             "brand": b.get("industry", "Brand"), "date": datetime.now().strftime("%B %Y")},
            {"type": "value", "title": "Giải pháp đề xuất",
             "features": ["Zalo OA — kênh giao tiếp chính", "ZNS — thông báo cá nhân hoá",
                          "Mini App — tăng tương tác loyalty", "Brand Hub — quản lý thương hiệu"],
             "stat_value": "40M+", "stat_label": "người dùng Zalo"},
            {"type": "closing", "headline": "Bắt đầu ngay hôm nay",
             "sub": "Liên hệ team Adtima để nhận tư vấn chi tiết",
             "contact": "contact@adtima.vn"},
        ]

    # ------------------------------------------------------------------
    # PPTX builder
    # ------------------------------------------------------------------

    def _build_pptx(self, slides: list[dict]):
        from pptx import Presentation
        from pptx.util import Inches, Emu

        prs = Presentation()
        prs.slide_width = Inches(SLIDE_W)
        prs.slide_height = Inches(SLIDE_H)

        dispatch = {
            "title":   self._render_title,
            "value":   self._render_value,
            "flow":    self._render_flow,
            "tier":    self._render_tier,
            "closing": self._render_closing,
        }

        blank = prs.slide_layouts[6]  # completely blank layout
        for sd in slides:
            slide = prs.slides.add_slide(blank)
            renderer = dispatch.get(sd.get("type", "value"), self._render_value)
            renderer(slide, sd)

        return prs

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _rgb(name: str):
        from pptx.dml.color import RGBColor
        r, g, b = _C[name]
        return RGBColor(r, g, b)

    def _bg(self, slide, color_name: str = "cream"):
        from pptx.util import Inches
        bg = slide.shapes.add_shape(1, 0, 0, Inches(SLIDE_W), Inches(SLIDE_H))
        bg.fill.solid()
        bg.fill.fore_color.rgb = self._rgb(color_name)
        bg.line.fill.background()
        return bg

    def _topbar(self, slide, color: str = "orange", brand_text: str = "ADTIMA"):
        from pptx.util import Inches, Pt
        bar = slide.shapes.add_shape(1, 0, 0, Inches(SLIDE_W), Inches(TOPBAR_H))
        bar.fill.solid()
        bar.fill.fore_color.rgb = self._rgb(color)
        bar.line.fill.background()

        tb = slide.shapes.add_textbox(Inches(PAD_L), Inches(0.08), Inches(3), Inches(TOPBAR_H - 0.16))
        tf = tb.text_frame
        tf.word_wrap = False
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = brand_text
        run.font.name = FONT
        run.font.bold = True
        run.font.size = Pt(13)
        run.font.color.rgb = self._rgb("white")

    def _title_text(self, slide, left, top, width, height, text, size, color,
                    bold=False, italic=False, align="LEFT", wrap=True):
        from pptx.util import Inches, Pt
        from pptx.enum.text import PP_ALIGN
        aligns = {"LEFT": PP_ALIGN.LEFT, "CENTER": PP_ALIGN.CENTER, "RIGHT": PP_ALIGN.RIGHT}
        tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
        tf = tb.text_frame
        tf.word_wrap = wrap
        p = tf.paragraphs[0]
        p.alignment = aligns.get(align, PP_ALIGN.LEFT)
        run = p.add_run()
        run.text = text
        run.font.name = FONT
        run.font.size = Pt(size)
        run.font.color.rgb = self._rgb(color)
        run.font.bold = bold
        run.font.italic = italic
        return tb

    def _accent_bar(self, slide, top, color="orange", width=0.06):
        from pptx.util import Inches
        bar = slide.shapes.add_shape(1, Inches(PAD_L), Inches(top),
                                     Inches(width), Inches(0.04))
        bar.fill.solid()
        bar.fill.fore_color.rgb = self._rgb(color)
        bar.line.fill.background()

    def _divider(self, slide, top, left=None, width=None, color="line"):
        from pptx.util import Inches
        l = left if left is not None else PAD_L
        w = width if width is not None else CONTENT_W
        ln = slide.shapes.add_shape(1, Inches(l), Inches(top), Inches(w), Inches(0.015))
        ln.fill.solid()
        ln.fill.fore_color.rgb = self._rgb(color)
        ln.line.fill.background()

    # ── Slide renderers ────────────────────────────────────────────────

    def _render_title(self, slide, sd: dict):
        """Title slide: centered headline + brand + date."""
        self._bg(slide, "white")

        # Left orange accent stripe
        stripe = slide.shapes.add_shape(1, 0, 0, Inches(0.18), Inches(SLIDE_H))
        stripe.fill.solid()
        stripe.fill.fore_color.rgb = self._rgb("orange")
        stripe.line.fill.background()

        from pptx.util import Inches
        # ADTIMA wordmark top-left
        self._title_text(slide, 0.32, 0.30, 3, 0.35, "ADTIMA", 11, "orange", bold=True)

        # Main headline — large
        headline = sd.get("headline", "Đề xuất giải pháp Zalo")
        self._title_text(slide, 0.32, 1.10, 8.5, 1.6, headline, 36, "ink", bold=True)

        # Sub-line
        sub = sd.get("sub", "")
        if sub:
            self._title_text(slide, 0.32, 2.75, 7, 0.6, sub, 16, "muted")

        # Brand name
        brand = sd.get("brand", "")
        if brand:
            self._title_text(slide, 0.32, 3.45, 5, 0.45, brand, 14, "teal", bold=True)

        # Date bottom-right
        date_str = sd.get("date", datetime.now().strftime("%B %Y"))
        self._title_text(slide, SLIDE_W - 2.2, SLIDE_H - 0.55, 2.0, 0.4, date_str, 11, "muted", align="RIGHT")

        # Bottom orange bar
        bot = slide.shapes.add_shape(1, Inches(0.18), Inches(SLIDE_H - 0.14),
                                     Inches(SLIDE_W - 0.18), Inches(0.14))
        bot.fill.solid()
        bot.fill.fore_color.rgb = self._rgb("orange")
        bot.line.fill.background()

    def _render_value(self, slide, sd: dict):
        """Value slide: title + feature list + optional stat."""
        from pptx.util import Inches, Pt
        self._bg(slide, "cream")
        self._topbar(slide)

        title = sd.get("title", "Giải pháp")
        self._title_text(slide, PAD_L, PAD_T, CONTENT_W, 0.55, title, 22, "ink", bold=True)
        self._divider(slide, PAD_T + 0.60, color="orange")

        features = sd.get("features") or []
        y = PAD_T + 0.75
        for feat in features[:5]:
            # Orange bullet
            dot = slide.shapes.add_shape(1, Inches(PAD_L), Inches(y + 0.08),
                                         Inches(0.09), Inches(0.09))
            dot.fill.solid()
            dot.fill.fore_color.rgb = self._rgb("orange")
            dot.line.fill.background()
            self._title_text(slide, PAD_L + 0.18, y, CONTENT_W - 0.2, 0.42, feat, 13, "ink")
            y += 0.50

        # Stat at bottom-right
        sv = sd.get("stat_value", "")
        sl = sd.get("stat_label", "")
        if sv:
            self._title_text(slide, SLIDE_W - 2.8, SLIDE_H - 1.0, 2.5, 0.65, sv, 36, "orange", bold=True, align="RIGHT")
            if sl:
                self._title_text(slide, SLIDE_W - 2.8, SLIDE_H - 0.55, 2.5, 0.40, sl, 11, "muted", align="RIGHT")

    def _render_flow(self, slide, sd: dict):
        """Flow slide: horizontal step-by-step."""
        from pptx.util import Inches, Pt
        self._bg(slide, "cream")
        self._topbar(slide)

        title = sd.get("title", "Hành trình người dùng")
        self._title_text(slide, PAD_L, PAD_T, CONTENT_W, 0.55, title, 22, "ink", bold=True)
        self._divider(slide, PAD_T + 0.60, color="teal")

        steps = sd.get("steps") or []
        steps = steps[:5]
        n = max(len(steps), 1)
        step_w = CONTENT_W / n
        step_y = PAD_T + 0.85
        step_h = SLIDE_H - step_y - 0.55

        for i, step in enumerate(steps):
            x = PAD_L + i * step_w
            # Step box background
            box = slide.shapes.add_shape(1, Inches(x + 0.05), Inches(step_y),
                                         Inches(step_w - 0.12), Inches(step_h))
            box.fill.solid()
            box.fill.fore_color.rgb = self._rgb("white")
            box.line.color.rgb = self._rgb("line")
            box.line.width = Pt(0.75)
            # Corner radius via adjustment (limited in python-pptx, skip)

            # Step number
            num_txt = str(i + 1)
            num_box = slide.shapes.add_shape(1, Inches(x + 0.15), Inches(step_y + 0.12),
                                             Inches(0.36), Inches(0.36))
            num_box.fill.solid()
            num_box.fill.fore_color.rgb = self._rgb("orange")
            num_box.line.fill.background()
            self._title_text(slide, x + 0.16, step_y + 0.14, 0.34, 0.30,
                              num_txt, 12, "white", bold=True, align="CENTER")

            # Step label
            label = step.get("label", "")
            self._title_text(slide, x + 0.1, step_y + 0.55, step_w - 0.22, 0.42,
                              label, 12, "ink", bold=True)

            # Step desc
            desc = step.get("desc", "")
            if desc:
                self._title_text(slide, x + 0.1, step_y + 0.98, step_w - 0.22, 0.80,
                                  desc, 10, "muted")

            # Arrow between steps
            if i < n - 1:
                arr_x = x + step_w - 0.14
                arr_y = step_y + step_h / 2
                arrow = slide.shapes.add_shape(1, Inches(arr_x), Inches(arr_y - 0.04),
                                               Inches(0.20), Inches(0.10))
                arrow.fill.solid()
                arrow.fill.fore_color.rgb = self._rgb("orange")
                arrow.line.fill.background()

    def _render_tier(self, slide, sd: dict):
        """Tier slide: side-by-side pricing columns."""
        from pptx.util import Inches, Pt
        self._bg(slide, "cream")
        self._topbar(slide)

        title = sd.get("title", "Báo giá")
        self._title_text(slide, PAD_L, PAD_T, CONTENT_W, 0.55, title, 22, "ink", bold=True)
        self._divider(slide, PAD_T + 0.60, color="orange")

        tiers = sd.get("tiers") or []
        tiers = tiers[:3]
        n = max(len(tiers), 1)
        tier_w = CONTENT_W / n
        tier_y = PAD_T + 0.78
        tier_h = SLIDE_H - tier_y - 0.40

        tier_colors = ["orange", "teal", "purple"]

        for i, tier in enumerate(tiers):
            x = PAD_L + i * tier_w
            accent = tier_colors[i % len(tier_colors)]

            # Card background
            card = slide.shapes.add_shape(1, Inches(x + 0.06), Inches(tier_y),
                                          Inches(tier_w - 0.14), Inches(tier_h))
            card.fill.solid()
            card.fill.fore_color.rgb = self._rgb("white")
            card.line.color.rgb = self._rgb("line")
            card.line.width = Pt(0.75)

            # Top accent bar on card
            top_acc = slide.shapes.add_shape(1, Inches(x + 0.06), Inches(tier_y),
                                             Inches(tier_w - 0.14), Inches(0.08))
            top_acc.fill.solid()
            top_acc.fill.fore_color.rgb = self._rgb(accent)
            top_acc.line.fill.background()

            # Tier name
            self._title_text(slide, x + 0.14, tier_y + 0.14, tier_w - 0.30, 0.38,
                              tier.get("name", ""), 13, "ink", bold=True)

            # Price
            price = tier.get("price", "")
            self._title_text(slide, x + 0.14, tier_y + 0.52, tier_w - 0.30, 0.50,
                              price, 18, accent, bold=True)

            # Note
            note = tier.get("note", "")
            if note:
                self._title_text(slide, x + 0.14, tier_y + 1.02, tier_w - 0.30, 0.30,
                                  note, 9, "muted", italic=True)

            # Perks
            perks = tier.get("perks") or []
            py = tier_y + 1.35
            for perk in perks[:4]:
                dot = slide.shapes.add_shape(1, Inches(x + 0.18), Inches(py + 0.07),
                                             Inches(0.07), Inches(0.07))
                dot.fill.solid()
                dot.fill.fore_color.rgb = self._rgb(accent)
                dot.line.fill.background()
                self._title_text(slide, x + 0.30, py, tier_w - 0.46, 0.36, perk, 9.5, "ink")
                py += 0.40

    def _render_closing(self, slide, sd: dict):
        """Closing slide: orange gradient + call to action."""
        from pptx.util import Inches
        self._bg(slide, "white")

        # Full-bleed orange half
        half = slide.shapes.add_shape(1, 0, 0, Inches(SLIDE_W), Inches(SLIDE_H * 0.55))
        half.fill.solid()
        half.fill.fore_color.rgb = self._rgb("orange")
        half.line.fill.background()

        # ADTIMA brand
        self._title_text(slide, PAD_L, 0.22, 3, 0.35, "ADTIMA", 11, "white", bold=True)

        # Headline on orange
        headline = sd.get("headline", "Hãy bắt đầu ngay hôm nay")
        self._title_text(slide, PAD_L, 0.80, CONTENT_W, 1.0, headline, 30, "white", bold=True)

        # Sub below orange section
        sub = sd.get("sub", "")
        if sub:
            self._title_text(slide, PAD_L, SLIDE_H * 0.58, CONTENT_W, 0.55, sub, 14, "ink")

        # Contact
        contact = sd.get("contact", "contact@adtima.vn")
        self._title_text(slide, PAD_L, SLIDE_H * 0.78, CONTENT_W, 0.40, contact, 12, "teal", bold=True)

        # Bottom accent
        bot = slide.shapes.add_shape(1, 0, Inches(SLIDE_H - 0.12),
                                     Inches(SLIDE_W), Inches(0.12))
        bot.fill.solid()
        bot.fill.fore_color.rgb = self._rgb("ink")
        bot.line.fill.background()


from pptx.util import Inches as _Inches  # noqa — cached reference


def create_adtimabox_pptx_generator() -> AdtimaBoxPPTXGenerator:
    return AdtimaBoxPPTXGenerator()
