"""
AdtimaBox-branded PPTX generator.
Follows adtimabox-deck-pptx.skill + adtimabox-deck.skill design system.
Slide types: value / flow / tier  (no title/closing — spec doesn't define them)
Extraction schema shared with html_deck.py (_EXTRACT_SYSTEM imported from there).
"""

from __future__ import annotations

import asyncio
import json
import os
from functools import partial
from typing import Any

# Brand palette — RGB (0-255)
_C = {
    "orange":  (246, 80, 9),
    "orange2": (232, 74, 26),
    "teal":    (15, 155, 142),
    "ink":     (29, 29, 31),
    "white":   (255, 255, 255),
    "cream":   (251, 248, 245),
    "line":    (236, 230, 225),
    "gray":    (107, 107, 112),
    "gray_lt": (154, 154, 160),
    "purple":  (91, 79, 196),
    "gold":    (200, 147, 43),
}

SLIDE_W = 10.0     # inches
SLIDE_H = 5.625    # inches
FONT = "Calibri"

# Layout constants (align with adtimabox-deck-pptx.skill)
PAD_X = 0.67   # left + right padding
PAD_T = 0.44   # top padding (TOPBAR_H + gap)
TOPBAR_H = 0.18
STAT_BAR_H = 0.55
CONTENT_W = SLIDE_W - PAD_X * 2
BODY_TOP = PAD_T + TOPBAR_H + 0.18   # below topbar
BODY_H = SLIDE_H - BODY_TOP - STAT_BAR_H - 0.10


class AdtimaBoxPPTXGenerator:
    """Generates AdtimaBox-branded PPTX from proposal markdown."""

    async def generate(self, proposal_text: str, brief: dict, output_path: str, skill_spec: str = "") -> dict:
        try:
            from pptx import Presentation  # noqa
        except ImportError:
            return {"status": "error", "error": "python-pptx not installed"}

        try:
            # Share extraction with html_deck (same schema, retry logic included)
            from generation.html_deck import HTMLDeckGenerator
            helper = HTMLDeckGenerator()
            slides_data = await helper._extract_slides_with_retry(proposal_text, brief)
            if not slides_data:
                slides_data = self._fallback_slides(brief)
        except Exception as e:
            print(f"[PPTX] Extraction failed ({e}), using fallback")
            slides_data = self._fallback_slides(brief)

        try:
            prs = self._build_pptx(slides_data)
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            prs.save(output_path)
            return {"status": "success", "file_path": output_path, "slide_count": len(slides_data)}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _fallback_slides(self, brief: dict) -> list[dict]:
        b = brief or {}
        return [
            {
                "type": "value",
                "eyebrow": "Giải pháp Zalo",
                "tier": "",
                "headline": {"plain": "Tăng tương tác & thu data trên ", "bold": "Zalo ecosystem"},
                "lede": "Kết hợp OA, ZNS, Mini App để thu lead, tái tiếp cận và tăng loyalty.",
                "cards": [
                    {"icon": "📲", "title": "Zalo OA — kênh chính thức", "desc": "Reach 40M+ không cần app riêng", "tag": None},
                    {"icon": "🔔", "title": "ZNS — push cá nhân hoá", "desc": "Tỉ lệ mở cao, tránh spam", "tag": None},
                    {"icon": "🎮", "title": "Mini App — gamification", "desc": "Voucher, điểm thưởng, đổi quà", "tag": None},
                ],
                "stats": [
                    {"v": "40M+", "l": "người dùng Zalo"},
                    {"v": "10k", "l": f"user — {b.get('industry','Brand')}"},
                ],
            }
        ]

    def _build_pptx(self, slides: list[dict]):
        from pptx import Presentation
        from pptx.util import Inches

        prs = Presentation()
        prs.slide_width = Inches(SLIDE_W)
        prs.slide_height = Inches(SLIDE_H)

        dispatch = {
            "value": self._render_value,
            "flow":  self._render_flow,
            "tier":  self._render_tier,
        }
        blank = prs.slide_layouts[6]
        for sd in slides:
            slide = prs.slides.add_slide(blank)
            renderer = dispatch.get(sd.get("type", "value"), self._render_value)
            renderer(slide, sd)
        return prs

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _rgb(key: str):
        from pptx.dml.color import RGBColor
        r, g, b = _C[key]
        return RGBColor(r, g, b)

    @staticmethod
    def _hex_rgb(hex_str: str):
        from pptx.dml.color import RGBColor
        h = hex_str.lstrip("#").upper()
        if len(h) != 6:
            return RGBColor(29, 29, 31)
        return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    def _bg(self, slide):
        from pptx.util import Inches
        bg = slide.shapes.add_shape(1, 0, 0, Inches(SLIDE_W), Inches(SLIDE_H))
        bg.fill.solid()
        bg.fill.fore_color.rgb = self._rgb("cream")
        bg.line.fill.background()

    def _topbar(self, slide, eyebrow: str, tier: str = ""):
        from pptx.util import Inches, Pt
        # Small orange accent bar (4px × 16px equivalent in inches ≈ 0.04" × 0.13")
        bar = slide.shapes.add_shape(1, Inches(PAD_X), Inches(PAD_T + 0.03),
                                     Inches(0.04), Inches(0.14))
        bar.fill.solid()
        bar.fill.fore_color.rgb = self._rgb("orange")
        bar.line.fill.background()

        # Eyebrow text
        label = eyebrow.upper()
        if tier:
            label += f"  {tier.upper()}"
        tb = slide.shapes.add_textbox(Inches(PAD_X + 0.10), Inches(PAD_T),
                                      Inches(CONTENT_W * 0.6), Inches(TOPBAR_H))
        tf = tb.text_frame
        tf.word_wrap = False
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = label
        run.font.name = FONT
        run.font.size = Pt(9)
        run.font.bold = True
        run.font.color.rgb = self._rgb("ink")

        # Logo — right aligned
        logo_tb = slide.shapes.add_textbox(Inches(SLIDE_W - PAD_X - 1.5), Inches(PAD_T),
                                           Inches(1.5), Inches(TOPBAR_H))
        lf = logo_tb.text_frame
        lf.word_wrap = False
        lp = lf.paragraphs[0]
        from pptx.enum.text import PP_ALIGN
        lp.alignment = PP_ALIGN.RIGHT
        lr = lp.add_run()
        lr.text = "adtimabox"
        lr.font.name = FONT
        lr.font.size = Pt(9)
        lr.font.bold = True
        lr.font.color.rgb = self._rgb("ink")

    def _stat_bar(self, slide, stats: list):
        from pptx.util import Inches, Pt
        if not stats:
            return
        # Divider line
        div = slide.shapes.add_shape(1, Inches(PAD_X),
                                     Inches(SLIDE_H - STAT_BAR_H - 0.02),
                                     Inches(CONTENT_W), Inches(0.01))
        div.fill.solid()
        div.fill.fore_color.rgb = self._rgb("line")
        div.line.fill.background()

        stat_x = PAD_X
        stat_y = SLIDE_H - STAT_BAR_H + 0.06
        col_w = CONTENT_W / min(len(stats), 4)
        for s in stats[:4]:
            self._text(slide, stat_x, stat_y, col_w - 0.1, 0.35,
                       s.get("v", ""), 22, "ink", bold=True)
            self._text(slide, stat_x, stat_y + 0.35, col_w - 0.1, 0.20,
                       s.get("l", ""), 8, "gray_lt")
            stat_x += col_w

    def _text(self, slide, left, top, width, height, text, size, color_key,
              bold=False, italic=False, align="LEFT"):
        from pptx.util import Inches, Pt
        from pptx.enum.text import PP_ALIGN
        aligns = {"LEFT": PP_ALIGN.LEFT, "CENTER": PP_ALIGN.CENTER, "RIGHT": PP_ALIGN.RIGHT}
        tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = aligns.get(align, PP_ALIGN.LEFT)
        run = p.add_run()
        run.text = text or ""
        run.font.name = FONT
        run.font.size = Pt(size)
        run.font.color.rgb = self._rgb(color_key)
        run.font.bold = bold
        run.font.italic = italic
        return tb

    def _text_mixed(self, slide, left, top, width, height, plain: str, bold_text: str, size: int):
        """Two-run paragraph: plain + bold (orange) for headline:{plain,bold}."""
        from pptx.util import Inches, Pt
        tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        r1 = p.add_run()
        r1.text = plain or ""
        r1.font.name = FONT
        r1.font.size = Pt(size)
        r1.font.color.rgb = self._rgb("ink")
        if bold_text:
            r2 = p.add_run()
            r2.text = bold_text
            r2.font.name = FONT
            r2.font.size = Pt(size)
            r2.font.color.rgb = self._rgb("orange")
            r2.font.bold = True
        return tb

    # ── Slide renderers ──────────────────────────────────────────────────

    def _render_value(self, slide, sd: dict):
        from pptx.util import Inches, Pt
        self._bg(slide)
        hl = sd.get("headline", {})
        self._topbar(slide, sd.get("eyebrow", ""), sd.get("tier", ""))

        # Headline
        self._text_mixed(slide, PAD_X, BODY_TOP, CONTENT_W * 0.6, 0.80,
                         hl.get("plain", ""), hl.get("bold", ""), 26)

        # Lede
        lede = sd.get("lede", "")
        if lede:
            self._text(slide, PAD_X, BODY_TOP + 0.85, CONTENT_W * 0.55, 0.40, lede, 10, "gray")

        # Feature cards
        cards = sd.get("cards") or []
        card_y = BODY_TOP + 1.30
        card_h = (BODY_H - 1.30) / max(len(cards), 1) - 0.05
        for c in cards[:4]:
            # Card bg
            crd = slide.shapes.add_shape(1, Inches(PAD_X), Inches(card_y),
                                         Inches(CONTENT_W * 0.58), Inches(max(card_h, 0.42)))
            crd.fill.solid()
            crd.fill.fore_color.rgb = self._rgb("white")
            crd.line.color.rgb = self._rgb("line")
            from pptx.util import Pt as _Pt
            crd.line.width = _Pt(0.5)

            # Icon box
            icon_box = slide.shapes.add_shape(1, Inches(PAD_X + 0.08), Inches(card_y + 0.06),
                                              Inches(0.30), Inches(0.30))
            icon_box.fill.solid()
            icon_box.fill.fore_color.rgb = self._rgb("cream")
            icon_box.line.fill.background()
            self._text(slide, PAD_X + 0.08, card_y + 0.04, 0.32, 0.30,
                       c.get("icon", ""), 12, "ink", align="CENTER")

            self._text(slide, PAD_X + 0.46, card_y + 0.04, CONTENT_W * 0.48, 0.22,
                       c.get("title", ""), 10, "ink", bold=True)
            self._text(slide, PAD_X + 0.46, card_y + 0.24, CONTENT_W * 0.48, 0.22,
                       c.get("desc", ""), 9, "gray")
            card_y += max(card_h, 0.42) + 0.06

        self._stat_bar(slide, sd.get("stats") or [])

    def _render_flow(self, slide, sd: dict):
        from pptx.util import Inches, Pt
        self._bg(slide)
        hl = sd.get("headline", {})
        self._topbar(slide, sd.get("eyebrow", ""))

        self._text_mixed(slide, PAD_X, BODY_TOP, CONTENT_W, 0.75,
                         hl.get("plain", ""), hl.get("bold", ""), 24)

        steps = (sd.get("steps") or [])[:6]
        n = max(len(steps), 1)
        step_w = CONTENT_W / n
        step_top = BODY_TOP + 0.88
        step_h = SLIDE_H - step_top - STAT_BAR_H - 0.15

        role_colors = {
            "customer": "teal", "admin": "purple",
            "staff": "orange2", "system": "gray_lt",
        }

        for i, st in enumerate(steps):
            x = PAD_X + i * step_w
            role = st.get("role", "customer")
            dot = st.get("dot", "core")
            role_color = role_colors.get(role, "gray_lt")

            # Role pill strip at top
            pill = slide.shapes.add_shape(1, Inches(x + 0.05), Inches(step_top),
                                          Inches(step_w - 0.12), Inches(0.18))
            pill.fill.solid()
            pill.fill.fore_color.rgb = self._rgb(role_color)
            pill.line.fill.background()
            self._text(slide, x + 0.08, step_top + 0.01, step_w - 0.18, 0.16,
                       role.upper(), 6.5, "white", bold=True)

            # Icon box
            icon_y = step_top + 0.22
            icon_box = slide.shapes.add_shape(1, Inches(x + step_w / 2 - 0.28), Inches(icon_y),
                                              Inches(0.56), Inches(0.56))
            icon_box.fill.solid()
            icon_box.fill.fore_color.rgb = self._rgb("white")
            icon_box.line.color.rgb = self._rgb("line")
            icon_box.line.width = Pt(0.5)
            self._text(slide, x + step_w / 2 - 0.27, icon_y + 0.04, 0.54, 0.46,
                       st.get("icon", ""), 18, "ink", align="CENTER")

            # Core/custom dot
            dot_color = "teal" if dot == "core" else "orange"
            dd = slide.shapes.add_shape(1, Inches(x + step_w / 2 + 0.14), Inches(icon_y - 0.04),
                                        Inches(0.12), Inches(0.12))
            dd.fill.solid()
            dd.fill.fore_color.rgb = self._rgb(dot_color)
            dd.line.fill.background()

            # Label + desc
            self._text(slide, x + 0.06, icon_y + 0.62, step_w - 0.14, 0.30,
                       st.get("label", ""), 9.5, "ink", bold=True, align="CENTER")
            self._text(slide, x + 0.06, icon_y + 0.94, step_w - 0.14, 0.55,
                       st.get("desc", ""), 8, "gray", align="CENTER")

            # Arrow between steps
            if i < n - 1:
                arr = slide.shapes.add_shape(1, Inches(x + step_w - 0.12), Inches(step_top + step_h / 2),
                                             Inches(0.14), Inches(0.10))
                arr.fill.solid()
                arr.fill.fore_color.rgb = self._rgb("line")
                arr.line.fill.background()

        self._stat_bar(slide, sd.get("stats") or [])

    def _render_tier(self, slide, sd: dict):
        from pptx.util import Inches, Pt
        self._bg(slide)
        hl = sd.get("headline", {})
        self._topbar(slide, sd.get("eyebrow", ""))

        self._text_mixed(slide, PAD_X, BODY_TOP, CONTENT_W, 0.65,
                         hl.get("plain", ""), hl.get("bold", ""), 24)

        lede = sd.get("lede", "")
        if lede:
            self._text(slide, PAD_X, BODY_TOP + 0.68, CONTENT_W, 0.30, lede, 10, "gray")

        tiers = (sd.get("tiers") or [])[:4]
        n = max(len(tiers), 1)
        tier_w = CONTENT_W / n
        tier_top = BODY_TOP + (1.05 if lede else 0.75)
        tier_h = SLIDE_H - tier_top - STAT_BAR_H - 0.12

        for i, t in enumerate(tiers):
            x = PAD_X + i * tier_w

            # Card bg
            crd = slide.shapes.add_shape(1, Inches(x + 0.05), Inches(tier_top),
                                         Inches(tier_w - 0.12), Inches(tier_h))
            crd.fill.solid()
            crd.fill.fore_color.rgb = self._rgb("white")
            crd.line.color.rgb = self._rgb("line")
            crd.line.width = Pt(0.5)

            # Top color bar (6px ≈ 0.06")
            bar_color = self._hex_rgb(t.get("barColor", "ECE6E1"))
            top_bar = slide.shapes.add_shape(1, Inches(x + 0.05), Inches(tier_top),
                                             Inches(tier_w - 0.12), Inches(0.06))
            top_bar.fill.solid()
            top_bar.fill.fore_color.rgb = bar_color
            top_bar.line.fill.background()

            # Tier name
            name_color = self._hex_rgb(t.get("nameColor", "1D1D1F"))
            name_tb = slide.shapes.add_textbox(Inches(x + 0.12), Inches(tier_top + 0.10),
                                               Inches(tier_w - 0.26), Inches(0.30))
            nf = name_tb.text_frame
            nf.word_wrap = False
            np_ = nf.paragraphs[0]
            nr = np_.add_run()
            nr.text = t.get("name", "")
            nr.font.name = FONT
            nr.font.size = Pt(9)
            nr.font.bold = True
            nr.font.color.rgb = name_color

            # Module
            self._text(slide, x + 0.12, tier_top + 0.38, tier_w - 0.26, 0.22,
                       t.get("module", ""), 7.5, "gray_lt", bold=True)

            # Price
            self._text(slide, x + 0.12, tier_top + 0.60, tier_w - 0.26, 0.45,
                       t.get("price", ""), 17, "ink", bold=True)

            # Period
            self._text(slide, x + 0.12, tier_top + 1.02, tier_w - 0.26, 0.22,
                       t.get("period", ""), 8, "gray_lt")

            # Divider
            d = slide.shapes.add_shape(1, Inches(x + 0.12), Inches(tier_top + 1.24),
                                       Inches(tier_w - 0.26), Inches(0.01))
            d.fill.solid()
            d.fill.fore_color.rgb = self._rgb("line")
            d.line.fill.background()

            # Checks
            cy = tier_top + 1.32
            for ck in (t.get("checks") or [])[:5]:
                self._text(slide, x + 0.24, cy, tier_w - 0.38, 0.25, "✓  " + ck, 8.5, "ink")
                cy += 0.28

            # Deploy
            deploy = t.get("deploy", "")
            if deploy:
                self._text(slide, x + 0.12, tier_top + tier_h - 0.34, tier_w - 0.26, 0.30,
                           f"Triển khai: {deploy}", 8, "gray")

        self._stat_bar(slide, sd.get("stats") or [])


def create_adtimabox_pptx_generator() -> AdtimaBoxPPTXGenerator:
    return AdtimaBoxPPTXGenerator()
