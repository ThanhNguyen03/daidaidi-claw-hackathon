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

        # Logo — right aligned: "adtimabox  by Adtima"
        logo_tb = slide.shapes.add_textbox(Inches(SLIDE_W - PAD_X - 1.8), Inches(PAD_T),
                                           Inches(1.8), Inches(TOPBAR_H))
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
        lr2 = lp.add_run()
        lr2.text = "  by Adtima"
        lr2.font.name = FONT
        lr2.font.size = Pt(8)
        lr2.font.bold = False
        lr2.font.color.rgb = self._rgb("gray_lt")

    def _stat_bar(self, slide, stats: list, no_line: bool = False):
        from pptx.util import Inches, Pt
        if not stats:
            return
        # Divider line (omit when caller has own footer divider)
        if not no_line:
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
        self._text_mixed(slide, PAD_X, BODY_TOP, CONTENT_W * 0.6, 1.00,
                         hl.get("plain", ""), hl.get("bold", ""), 24)

        # Lede
        lede = sd.get("lede", "")
        if lede:
            self._text(slide, PAD_X, BODY_TOP + 1.05, CONTENT_W * 0.55, 0.40, lede, 10, "gray")

        # Feature cards
        cards = sd.get("cards") or []
        card_y = BODY_TOP + 1.52
        card_h = (BODY_H - 1.52) / max(len(cards), 1) - 0.05
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

        # Headline (full width)
        self._text_mixed(slide, PAD_X, BODY_TOP, CONTENT_W, 0.80,
                         hl.get("plain", ""), hl.get("bold", ""), 22)

        # ── Legend row ──
        lg_y = BODY_TOP + 0.80
        # Teal dot: Core
        d1 = slide.shapes.add_shape(1, Inches(PAD_X), Inches(lg_y + 0.04), Inches(0.10), Inches(0.10))
        d1.fill.solid(); d1.fill.fore_color.rgb = self._rgb("teal"); d1.line.fill.background()
        self._text(slide, PAD_X + 0.14, lg_y, 1.3, 0.18, "Core (có sẵn)", 8.5, "gray")
        # Orange dot: Custom
        d2 = slide.shapes.add_shape(1, Inches(PAD_X + 1.6), Inches(lg_y + 0.04), Inches(0.10), Inches(0.10))
        d2.fill.solid(); d2.fill.fore_color.rgb = self._rgb("orange"); d2.line.fill.background()
        self._text(slide, PAD_X + 1.74, lg_y, 1.5, 0.18, "Custom (mở rộng)", 8.5, "gray")
        # Role color explanation (right side)
        self._text(slide, PAD_X + 3.6, lg_y, 5.5, 0.18,
                   "Tím = Admin · CMS    Xanh = Customer · Mini App", 8.5, "gray")

        # ── Footer layout ──
        footer = sd.get("footer", "")
        stat_div_y = SLIDE_H - STAT_BAR_H - 0.02
        footer_h = 0.22
        footer_y = stat_div_y - footer_h - 0.08 if footer else stat_div_y

        # ── Steps ──
        steps = (sd.get("steps") or [])[:6]
        n = max(len(steps), 1)
        step_w = CONTENT_W / n
        flow_top = lg_y + 0.24
        icon_size = 0.60
        # Center icon row vertically between flow_top and footer_y
        label_h = 0.26 + 0.42  # label + desc below icon
        avail_v = footer_y - flow_top - 0.26 - icon_size - label_h
        icon_y = flow_top + 0.26 + max(avail_v / 2, 0)

        role_colors = {
            "customer": "teal", "admin": "purple",
            "staff": "orange2", "system": "gray_lt",
        }

        for i, st in enumerate(steps):
            cx = PAD_X + i * step_w + step_w / 2
            role = st.get("role", "customer")
            dot = st.get("dot", "core")
            rc = role_colors.get(role, "gray_lt")

            # Role pill (centered on cx)
            pill_w, pill_h = min(step_w - 0.12, 0.90), 0.16
            px = cx - pill_w / 2
            pill = slide.shapes.add_shape(1, Inches(px), Inches(icon_y - 0.26),
                                           Inches(pill_w), Inches(pill_h))
            pill.fill.solid(); pill.fill.fore_color.rgb = self._rgb(rc)
            pill.line.fill.background()
            self._text(slide, px + 0.02, icon_y - 0.26, pill_w - 0.04, pill_h,
                       role.upper(), 6.5, "white", bold=True, align="CENTER")

            # Icon box (centered on cx)
            ix = cx - icon_size / 2
            icon_box = slide.shapes.add_shape(1, Inches(ix), Inches(icon_y),
                                               Inches(icon_size), Inches(icon_size))
            icon_box.fill.solid(); icon_box.fill.fore_color.rgb = self._rgb("white")
            icon_box.line.color.rgb = self._rgb("line"); icon_box.line.width = Pt(0.5)
            self._text(slide, ix + 0.02, icon_y + 0.05, icon_size - 0.04, icon_size - 0.10,
                       st.get("icon", ""), 18, "ink", align="CENTER")

            # Core/custom dot (top-right of icon)
            dot_color = "teal" if dot == "core" else "orange"
            dd = slide.shapes.add_shape(1, Inches(cx + icon_size / 2 - 0.10), Inches(icon_y - 0.04),
                                         Inches(0.11), Inches(0.11))
            dd.fill.solid(); dd.fill.fore_color.rgb = self._rgb(dot_color)
            dd.line.fill.background()

            # Label + desc centered below icon
            lbl_w = min(step_w - 0.10, 1.20)
            lx = cx - lbl_w / 2
            self._text(slide, lx, icon_y + icon_size + 0.10, lbl_w, 0.26,
                       st.get("label", ""), 9, "ink", bold=True, align="CENTER")
            self._text(slide, lx, icon_y + icon_size + 0.38, lbl_w, 0.42,
                       st.get("desc", ""), 7.5, "gray", align="CENTER")

            # Arrow between steps
            if i < n - 1:
                arr_x = cx + icon_size / 2 + 0.04
                arr_w = max(step_w - icon_size - 0.14, 0.05)
                arr = slide.shapes.add_shape(1, Inches(arr_x), Inches(icon_y + icon_size / 2 - 0.005),
                                              Inches(arr_w), Inches(0.01))
                arr.fill.solid(); arr.fill.fore_color.rgb = self._rgb("gray_lt")
                arr.line.fill.background()

        # ── Footer (if present) ──
        if footer:
            fdiv = slide.shapes.add_shape(1, Inches(PAD_X), Inches(footer_y),
                                           Inches(CONTENT_W), Inches(0.008))
            fdiv.fill.solid(); fdiv.fill.fore_color.rgb = self._rgb("line")
            fdiv.line.fill.background()
            tb = slide.shapes.add_textbox(Inches(PAD_X), Inches(footer_y + 0.04),
                                           Inches(CONTENT_W), Inches(footer_h))
            tf = tb.text_frame; tf.word_wrap = True
            p = tf.paragraphs[0]
            r1 = p.add_run()
            r1.text = "Custom thêm: "
            r1.font.name = FONT; r1.font.size = Pt(8)
            r1.font.bold = True; r1.font.color.rgb = self._rgb("ink")
            r2 = p.add_run()
            r2.text = footer
            r2.font.name = FONT; r2.font.size = Pt(8)
            r2.font.bold = False; r2.font.color.rgb = self._rgb("gray")

        self._stat_bar(slide, sd.get("stats") or [], no_line=bool(footer))

    def _render_tier(self, slide, sd: dict):
        from pptx.util import Inches, Pt
        self._bg(slide)
        hl = sd.get("headline", {})
        self._topbar(slide, sd.get("eyebrow", ""))

        self._text_mixed(slide, PAD_X, BODY_TOP, CONTENT_W, 0.85,
                         hl.get("plain", ""), hl.get("bold", ""), 22)

        lede = sd.get("lede", "")
        if lede:
            # Lede fits inside headline block (0.62" to 0.84" from BODY_TOP)
            self._text(slide, PAD_X, BODY_TOP + 0.62, CONTENT_W - 1.0, 0.22, lede, 10, "gray")

        tiers = (sd.get("tiers") or [])[:4]
        n = max(len(tiers), 1)
        gap = 0.10  # gap between tier cards
        tier_w = (CONTENT_W - gap * (n - 1)) / n
        tier_top = BODY_TOP + 0.92  # constant — lede sits inside headline block above
        tier_h = SLIDE_H - tier_top - STAT_BAR_H - 0.12

        for i, t in enumerate(tiers):
            x = PAD_X + i * (tier_w + gap)

            # Card bg
            crd = slide.shapes.add_shape(1, Inches(x + 0.04), Inches(tier_top),
                                         Inches(tier_w - 0.06), Inches(tier_h))
            crd.fill.solid()
            crd.fill.fore_color.rgb = self._rgb("white")
            crd.line.color.rgb = self._rgb("line")
            crd.line.width = Pt(0.5)

            # Top color bar (6px ≈ 0.06")
            bar_color = self._hex_rgb(t.get("barColor", "ECE6E1"))
            top_bar = slide.shapes.add_shape(1, Inches(x + 0.04), Inches(tier_top),
                                             Inches(tier_w - 0.06), Inches(0.06))
            top_bar.fill.solid()
            top_bar.fill.fore_color.rgb = bar_color
            top_bar.line.fill.background()

            # Tier name
            name_color = self._hex_rgb(t.get("nameColor", "1D1D1F"))
            name_tb = slide.shapes.add_textbox(Inches(x + 0.12), Inches(tier_top + 0.10),
                                               Inches(tier_w - 0.26), Inches(0.30))
            nf = name_tb.text_frame
            nf.word_wrap = True
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

            # Price — split amount (large) + unit (small gray)
            price_str = t.get("price", "")
            p_parts = price_str.rsplit(" ", 1)
            amount_str = p_parts[0]
            unit_str = p_parts[1] if len(p_parts) > 1 else ""
            self._text(slide, x + 0.12, tier_top + 0.60, tier_w - 0.26, 0.38,
                       amount_str, 20, "ink", bold=True)
            if unit_str:
                self._text(slide, x + 0.12, tier_top + 0.96, tier_w - 0.26, 0.18,
                           unit_str, 8, "gray")

            # Period
            self._text(slide, x + 0.12, tier_top + 1.16, tier_w - 0.26, 0.22,
                       t.get("period", ""), 8, "gray_lt")

            # Divider
            d = slide.shapes.add_shape(1, Inches(x + 0.12), Inches(tier_top + 1.38),
                                       Inches(tier_w - 0.26), Inches(0.01))
            d.fill.solid()
            d.fill.fore_color.rgb = self._rgb("line")
            d.line.fill.background()

            # Checks — dynamic cap to never overlap deploy text
            deploy = t.get("deploy", "")
            deploy_y = tier_top + tier_h - 0.34
            checks_start = tier_top + 1.46
            available_h = deploy_y - checks_start - 0.10
            max_ck = max(0, min(4, int(available_h / 0.27)))
            cy = checks_start
            for ck in (t.get("checks") or [])[:max_ck]:
                self._text(slide, x + 0.24, cy, tier_w - 0.38, 0.25, "✓  " + ck, 8.5, "ink")
                cy += 0.27

            # Deploy
            if deploy:
                self._text(slide, x + 0.12, deploy_y, tier_w - 0.26, 0.30,
                           f"Triển khai: {deploy}", 8, "gray")

        self._stat_bar(slide, sd.get("stats") or [])


def create_adtimabox_pptx_generator() -> AdtimaBoxPPTXGenerator:
    return AdtimaBoxPPTXGenerator()
