"""
AdtimaBox HTML Deck Generator.
Follows adtimabox-deck.skill + adtimabox-deck-html.skill design system exactly.
Slide types: value / flow / tier  (no title/closing — spec doesn't define them)
Layout: vertical scroll, all slides visible (not a carousel)
"""

from __future__ import annotations

import asyncio
import json
from functools import partial

# ─── DESIGN TOKENS (from adtimabox-deck.skill §1) ────────────────────────────
_CSS = """
:root{
  --ink:#1D1D1F;--gray:#6B6B70;--gray-light:#9A9AA0;
  --orange:#F65009;--orange-2:#E84A1A;
  --line:#ECE6E1;--card:#FBF8F5;
  --teal:#0F9B8E;--purple:#5B4FC4;--gold:#C8932B;--white:#FFFFFF;
}
*{box-sizing:border-box;margin:0;padding:0;}
body{
  font-family:system-ui,-apple-system,'Segoe UI',Helvetica,Arial,sans-serif;
  background:#0d0d16;
  display:flex;flex-direction:column;align-items:center;gap:40px;padding:40px;
}

/* ── Slide shell (adtimabox-deck §3) ───────────────────────────────────── */
.slide{
  width:1280px;max-width:100%;height:720px;
  position:relative;overflow:hidden;flex-shrink:0;
  box-shadow:0 30px 80px rgba(0,0,0,.5);
  background:
    radial-gradient(circle at 8% 0%,rgba(246,80,9,.10),transparent 40%),
    linear-gradient(135deg,#FFF8F5 0%,#FFFFFF 45%,#FFFFFF 100%);
  padding:44px 64px 40px;
  display:flex;flex-direction:column;
}

/* ── Topbar (adtimabox-deck-html §3 TOPBAR) ─────────────────────────── */
.topbar{display:flex;justify-content:space-between;align-items:center;}
.eyebrow{
  display:flex;align-items:center;gap:10px;
  font-size:12px;font-weight:700;letter-spacing:.10em;text-transform:uppercase;color:var(--ink);
}
.eyebrow .bar{width:4px;height:16px;background:var(--orange);border-radius:2px;flex-shrink:0;}
.eyebrow .tier-tag{font-size:11px;font-weight:700;color:var(--orange);margin-left:2px;}
.logo .mark{font-size:13px;font-weight:800;color:var(--ink);}
.logo .mark span{color:var(--orange);}
.logo .by{font-size:11px;color:var(--gray-light);font-weight:400;margin-left:6px;}

/* ── Stat-bar (margin-top:auto → bám đáy) ─────────────────────────────── */
.stat-bar{margin-top:auto;display:flex;gap:40px;padding-top:16px;border-top:1px solid var(--line);}
.stat-bar .sv{font-size:28px;font-weight:700;color:var(--ink);line-height:1;}
.stat-bar .sl{font-size:12px;color:var(--gray-light);margin-top:4px;font-weight:400;}

/* ── VALUE layout ──────────────────────────────────────────────────────── */
.body-row{flex:1;display:flex;gap:56px;margin-top:20px;align-items:flex-start;}
.left-col{flex:1;display:flex;flex-direction:column;}
.left-col h2{font-size:38px;font-weight:400;color:var(--ink);line-height:1.18;letter-spacing:-.02em;margin-bottom:10px;}
.left-col h2 b{color:var(--orange);font-weight:700;}
.lede{font-size:14px;color:var(--gray);line-height:1.6;margin-bottom:20px;}
.feat-list{display:flex;flex-direction:column;gap:10px;}
.feat-item{
  display:flex;gap:14px;align-items:flex-start;
  background:#fff;border:1px solid var(--line);border-radius:14px;padding:14px 18px;
}
.feat-item .ic{
  width:32px;height:32px;border-radius:8px;background:var(--card);
  display:flex;align-items:center;justify-content:center;font-size:17px;flex-shrink:0;
}
.feat-item h4{font-size:14px;font-weight:600;color:var(--ink);line-height:1.3;margin-bottom:3px;}
.feat-item p{font-size:13px;color:var(--gray);line-height:1.5;}
.tag-core{
  font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;
  color:var(--teal);background:rgba(15,155,142,.10);padding:2px 8px;border-radius:4px;
  display:inline-block;margin-top:6px;
}
.tag-custom{
  font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;
  color:var(--orange-2);background:rgba(246,80,9,.08);padding:2px 8px;border-radius:4px;
  display:inline-block;margin-top:6px;
}

/* ── FLOW layout ───────────────────────────────────────────────────────── */
.flow-body{flex:1;display:flex;flex-direction:column;margin-top:16px;}
.flow-heading h2{font-size:34px;font-weight:400;color:var(--ink);line-height:1.22;letter-spacing:-.02em;margin-bottom:8px;}
.flow-heading h2 b{color:var(--orange);font-weight:700;}
.legend{display:flex;align-items:center;gap:16px;margin:6px 0 20px;}
.legend-item{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--gray);}
.legend-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0;}
.legend-dot.core{background:var(--teal);}
.legend-dot.custom{background:var(--orange);}
.flow-row{display:flex;align-items:flex-start;}
.step{display:flex;flex-direction:column;align-items:center;text-align:center;flex:1;}
.step-pill{
  display:inline-flex;align-items:center;gap:5px;
  font-size:9.5px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;margin-bottom:10px;
}
.step-pill .pd{width:6px;height:6px;border-radius:50%;flex-shrink:0;}
.step-pill.admin{color:var(--purple);}   .step-pill.admin .pd{background:var(--purple);}
.step-pill.customer{color:var(--teal);} .step-pill.customer .pd{background:var(--teal);}
.step-pill.staff{color:var(--orange-2);}  .step-pill.staff .pd{background:var(--orange-2);}
.step-pill.system{color:var(--gray-light);} .step-pill.system .pd{background:var(--gray-light);}
.step-icon-wrap{position:relative;margin-bottom:10px;}
.step-icon{
  width:68px;height:68px;border-radius:16px;background:#fff;
  border:1px solid var(--line);font-size:26px;
  display:flex;align-items:center;justify-content:center;
  box-shadow:0 4px 12px rgba(0,0,0,.06);
}
.core-dot{position:absolute;top:-4px;right:-4px;width:12px;height:12px;border-radius:50%;border:2px solid #fff;}
.core-dot.core{background:var(--teal);}
.core-dot.custom{background:var(--orange);}
.step-label{font-size:12.5px;font-weight:600;color:var(--ink);line-height:1.3;margin-bottom:4px;}
.step-desc{font-size:11px;color:var(--gray);line-height:1.45;max-width:116px;margin:0 auto;}
.step-sep{display:flex;align-items:center;padding-top:34px;flex-shrink:0;min-width:32px;flex:0.3;justify-content:center;}
.step-sep svg{width:100%;height:12px;}
.flow-footer{margin-top:auto;padding-top:14px;border-top:1px solid var(--line);}
.flow-footer p{font-size:12px;color:var(--gray);line-height:1.6;}
.flow-footer b{font-weight:600;color:var(--ink);}

/* ── TIER pricing ──────────────────────────────────────────────────────── */
.pricing-body{flex:1;display:flex;flex-direction:column;margin-top:20px;}
.pricing-body h2{font-size:38px;font-weight:400;color:var(--ink);line-height:1.18;letter-spacing:-.02em;margin-bottom:8px;}
.pricing-body h2 b{color:var(--orange);font-weight:700;}
.lede-sm{font-size:14px;color:var(--gray);line-height:1.6;margin-bottom:18px;}
.tier-grid{display:grid;gap:14px;flex:1;}
.tier-grid.cols-2{grid-template-columns:1fr 1fr;}
.tier-grid.cols-3{grid-template-columns:1fr 1fr 1fr;}
.tier-grid.cols-4{grid-template-columns:1fr 1fr 1fr 1fr;}
.tier-card{background:#fff;border:1px solid var(--line);border-radius:16px;overflow:hidden;display:flex;flex-direction:column;}
.tier-bar{height:6px;width:100%;}
.tier-inner{padding:16px 18px;display:flex;flex-direction:column;flex:1;}
.tier-name{font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;margin-bottom:3px;}
.tier-module{font-size:10px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--gray-light);margin-bottom:10px;}
.tier-price{display:flex;align-items:baseline;gap:5px;margin-bottom:3px;}
.tier-price .amount{font-size:40px;font-weight:800;color:var(--ink);line-height:1;}
.tier-price .unit{font-size:13px;font-weight:500;color:var(--gray);}
.tier-period{font-size:11px;color:var(--gray-light);margin-bottom:12px;}
.tier-checks{display:flex;flex-direction:column;gap:7px;flex:1;}
.check-row{display:flex;align-items:flex-start;gap:8px;font-size:12.5px;color:var(--ink);line-height:1.4;}
.check-icon{color:var(--teal);font-size:11px;flex-shrink:0;margin-top:2px;}
.tier-deploy{margin-top:12px;padding-top:10px;border-top:1px solid var(--line);font-size:12px;color:var(--gray);}
.tier-deploy b{font-weight:700;color:var(--ink);}
"""

# ─── EXTRACTION PROMPT (aligned with adtimabox-deck.skill schema) ─────────
_EXTRACT_SYSTEM = """You are a slide-deck content extractor for AdtimaBox branded presentations.
Given a sales proposal in Markdown, extract structured slide data.
Return ONLY a valid JSON array (no markdown fences, no explanation). Max 5 slides.

Slide schemas — use EXACTLY these field names:

VALUE slide (solution features):
{"type":"value","eyebrow":"<2-3 word context>","tier":"<optional tier label or empty string>","headline":{"plain":"<main phrase ending with space>","bold":"<1-3 key words>"},"lede":"<1 sentence summary, max 18 words>","cards":[{"icon":"<single emoji>","title":"<feature, max 6 words>","desc":"<benefit, max 12 words>","tag":null}],"stats":[{"v":"<metric with unit>","l":"<3-word label>"}]}

FLOW slide (user journey):
{"type":"flow","eyebrow":"<2-3 word context>","headline":{"plain":"<phrase ending with space>","bold":"<key phrase>"},"steps":[{"icon":"<single emoji>","label":"<2-3 words>","desc":"<max 8 words>","role":"customer|admin|staff|system","dot":"core|custom"}],"footer":"<optional addon/custom note, or empty string>","stats":[{"v":"<metric>","l":"<3-word label>"}]}

TIER slide (pricing):
{"type":"tier","eyebrow":"<section label>","headline":{"plain":"<phrase ending with space>","bold":"<key phrase>"},"lede":"<1 sentence, max 15 words>","tiers":[{"barColor":"<hex no #, pastel>","name":"<tier name>","nameColor":"<hex no #>","module":"<module name>","price":"<amount + unit, e.g. 20M VNĐ>","period":"<duration>","checks":["<feature, max 8 words>"],"deploy":"<X ngày làm việc>"}],"stats":[{"v":"<metric>","l":"<3-word label>"}]}

Rules:
- 1 value slide minimum; add flow if user journey is described; add tier if pricing exists
- cards: max 4 per slide, always include icon emoji
- steps: max 6 per flow slide, assign role (customer/admin/staff/system) and dot (core/custom)
- tiers: max 3; use colors — purple tier: nameColor=5B4FC4 barColor=D4CEEF; teal tier: nameColor=0F9B8E barColor=B8E4DF; orange tier: nameColor=F65009 barColor=FFD9CC
- stats: 3-4 real numbers from the proposal per slide
- card tag field: null if no custom/add-on, otherwise {"type":"core|custom","text":"<label>"}
- CRITICAL: Vietnamese spelling — never duplicate vowel diacritics (write "Sách" not "Sáách", "Ngân" not "Ngâân")
- Return ONLY the JSON array, nothing else"""


def _extract_schema_section(skill_spec: str) -> str:
    """Pull only the slide-schema + extraction-rules sections from SKILL.md.
    Strips CSS/layout detail that confuses the extraction LLM."""
    import re
    if not skill_spec:
        return ""
    # Keep from "### Slide Types" (or "## Slide Types") through "## Extraction Rules" (inclusive)
    match = re.search(
        r'(#{1,3}\s+Slide Types.+?)(?=##\s+Output Format|##\s+Topbar|$)',
        skill_spec,
        re.DOTALL | re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()
    # Fallback: return first 1500 chars (won't be the full file)
    return skill_spec[:1500]


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


class HTMLDeckGenerator:
    """Generates self-contained AdtimaBox HTML slide decks per adtimabox-deck-html.skill."""

    async def generate(self, proposal_text: str, brief: dict, skill_spec: str = "") -> str:
        try:
            slides = await self._extract_slides(proposal_text, brief, skill_spec)
        except Exception as e:
            print(f"[HTMLDeck] Extraction failed ({e}), using fallback")
            slides = self._fallback_slides(brief)
        return self._render_html(slides)

    async def _extract_slides(self, proposal_text: str, brief: dict, skill_spec: str = "") -> list[dict]:
        from llm.greennode import get_llm_client
        from skills.base import strip_think_blocks, extract_json_block

        client = get_llm_client("product_solution")
        brand_hint = (brief or {}).get("industry", "")
        trimmed = proposal_text[:8000]

        # Prepend only the schema+rules section from SKILL.md (not CSS/layout details)
        schema_hint = _extract_schema_section(skill_spec)
        system = (_EXTRACT_SYSTEM + "\n\n# Additional spec from SKILL.md:\n" + schema_hint
                  if schema_hint else _EXTRACT_SYSTEM)
        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(
            None,
            partial(
                client.create_completion,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": f"Brand: {brand_hint}\n\n---\n{trimmed}"},
                ],
                temperature=0.1,
                max_tokens=3000,
                stream=False,
            ),
        )
        raw = strip_think_blocks(resp.choices[0].message.content or "[]")
        raw = extract_json_block(raw)
        print(f"[HTMLDeck] extraction raw ({len(raw)} chars): {raw[:300]}")
        data = json.loads(raw)
        if not isinstance(data, list) or not data:
            print("[HTMLDeck] extraction returned empty/invalid list, using fallback")
            return self._fallback_slides(brief)
        print(f"[HTMLDeck] extracted {len(data)} slides: {[s.get('type') for s in data]}")
        return data

    def _fallback_slides(self, brief: dict) -> list[dict]:
        b = brief or {}
        brand = b.get("industry", "Brand")
        return [
            {
                "type": "value",
                "eyebrow": "Giải pháp Zalo",
                "tier": "",
                "headline": {"plain": "Tăng tương tác & thu data trên ", "bold": "Zalo ecosystem"},
                "lede": "Kết hợp OA, ZNS, Mini App để thu lead, tái tiếp cận và tăng loyalty.",
                "cards": [
                    {"icon": "📲", "title": "Zalo OA — kênh giao tiếp chính thức", "desc": "Reach 40M+ người dùng không cần app riêng", "tag": None},
                    {"icon": "🔔", "title": "ZNS — thông báo push cá nhân hoá", "desc": "Tỉ lệ mở cao, không bị spam filter", "tag": None},
                    {"icon": "🎮", "title": "Mini App — gamification & loyalty", "desc": "Voucher, điểm thưởng, đổi quà tại chỗ", "tag": None},
                    {"icon": "📊", "title": "Data & reactivation", "desc": "Thu lead offline, tái tiếp cận qua Zalo", "tag": None},
                ],
                "stats": [
                    {"v": "40M+", "l": "người dùng Zalo"},
                    {"v": "10k", "l": f"user mới — {brand}"},
                    {"v": "1-2", "l": "tháng campaign"},
                ],
            },
        ]

    def _render_html(self, slides: list[dict]) -> str:
        slides_html = "".join(
            self._render_slide(sd) for sd in slides
        )
        return f"""<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AdtimaBox Proposal Deck</title>
<style>{_CSS}</style>
</head>
<body>
{slides_html}
</body>
</html>"""

    def _render_slide(self, sd: dict) -> str:
        t = sd.get("type", "value")
        if t == "value":
            return self._slide_value(sd)
        if t == "flow":
            return self._slide_flow(sd)
        if t == "tier":
            return self._slide_tier(sd)
        return ""

    # ── Common topbar ──────────────────────────────────────────────────────
    def _topbar(self, eyebrow: str, tier: str = "") -> str:
        tier_html = f' <span class="tier-tag">{_esc(tier)}</span>' if tier else ""
        return f"""<div class="topbar">
  <div class="eyebrow"><div class="bar"></div>{_esc(eyebrow)}{tier_html}</div>
  <div class="logo"><span class="mark">adtima<span>box</span></span><span class="by">by Adtima</span></div>
</div>"""

    def _stat_bar(self, stats: list) -> str:
        if not stats:
            return ""
        items = "".join(
            f'<div><div class="sv">{_esc(s.get("v",""))}</div><div class="sl">{_esc(s.get("l",""))}</div></div>'
            for s in stats[:4]
        )
        return f'<div class="stat-bar">{items}</div>'

    # ── Value slide ────────────────────────────────────────────────────────
    def _slide_value(self, sd: dict) -> str:
        hl = sd.get("headline", {})
        plain = _esc(hl.get("plain", ""))
        bold = _esc(hl.get("bold", ""))
        lede = _esc(sd.get("lede", ""))
        cards = sd.get("cards") or []
        stats = sd.get("stats") or []

        cards_html = ""
        for c in cards[:4]:
            icon = _esc(c.get("icon", ""))
            title = _esc(c.get("title", ""))
            desc = _esc(c.get("desc", ""))
            tag = c.get("tag")
            tag_html = ""
            if tag and isinstance(tag, dict):
                tc = "tag-core" if tag.get("type") == "core" else "tag-custom"
                tag_html = f'<span class="{tc}">{_esc(tag.get("text",""))}</span>'
            cards_html += f"""<div class="feat-item">
  <div class="ic">{icon}</div>
  <div><h4>{title}</h4><p>{desc}</p>{tag_html}</div>
</div>"""

        return f"""<div class="slide">
  {self._topbar(sd.get("eyebrow",""), sd.get("tier",""))}
  <div class="body-row">
    <div class="left-col">
      <h2>{plain}<b>{bold}</b></h2>
      {f'<p class="lede">{lede}</p>' if lede else ""}
      <div class="feat-list">{cards_html}</div>
    </div>
  </div>
  {self._stat_bar(stats)}
</div>\n"""

    # ── Flow slide ─────────────────────────────────────────────────────────
    def _slide_flow(self, sd: dict) -> str:
        hl = sd.get("headline", {})
        plain = _esc(hl.get("plain", ""))
        bold = _esc(hl.get("bold", ""))
        steps = sd.get("steps") or []
        footer = sd.get("footer", "")
        stats = sd.get("stats") or []

        steps_html = ""
        for i, st in enumerate(steps[:6]):
            icon = _esc(st.get("icon", ""))
            label = _esc(st.get("label", ""))
            desc = _esc(st.get("desc", ""))
            role = st.get("role", "customer")
            dot = st.get("dot", "core")
            steps_html += f"""<div class="step">
  <div class="step-pill {role}"><span class="pd"></span>{role.upper()}</div>
  <div class="step-icon-wrap">
    <div class="step-icon">{icon}</div>
    <div class="core-dot {dot}"></div>
  </div>
  <div class="step-label">{label}</div>
  <div class="step-desc">{desc}</div>
</div>"""
            if i < len(steps) - 1:
                steps_html += """<div class="step-sep">
  <svg viewBox="0 0 30 12" fill="none" preserveAspectRatio="none">
    <line x1="0" y1="6" x2="22" y2="6" stroke="#C8C8CC" stroke-width="1.5" stroke-dasharray="3 2"/>
    <path d="M20 2.5L26 6L20 9.5" stroke="#C8C8CC" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
  </svg>
</div>"""

        footer_html = ""
        if footer:
            footer_html = f'<div class="flow-footer"><p><b>Custom thêm:</b> {_esc(footer)}</p></div>'

        return f"""<div class="slide">
  {self._topbar(sd.get("eyebrow",""))}
  <div class="flow-body">
    <div class="flow-heading">
      <h2>{plain}<b>{bold}</b></h2>
    </div>
    <div class="legend">
      <div class="legend-item"><div class="legend-dot core"></div>Core (có sẵn)</div>
      <div class="legend-item"><div class="legend-dot custom"></div>Custom (mở rộng)</div>
    </div>
    <div class="flow-row">{steps_html}</div>
    {footer_html}
  </div>
  {self._stat_bar(stats)}
</div>\n"""

    # ── Tier slide ─────────────────────────────────────────────────────────
    def _slide_tier(self, sd: dict) -> str:
        hl = sd.get("headline", {})
        plain = _esc(hl.get("plain", ""))
        bold = _esc(hl.get("bold", ""))
        lede = _esc(sd.get("lede", ""))
        tiers = sd.get("tiers") or []
        stats = sd.get("stats") or []

        n = min(len(tiers), 4)
        grid_cls = f"cols-{n}" if n >= 2 else "cols-2"
        cards_html = ""
        for t in tiers[:4]:
            bar_color = _esc(t.get("barColor", "ECE6E1"))
            name_color = _esc(t.get("nameColor", "1D1D1F"))
            name = _esc(t.get("name", ""))
            module = _esc(t.get("module", ""))
            price = _esc(t.get("price", ""))
            period = _esc(t.get("period", ""))
            checks = t.get("checks") or []
            deploy = _esc(t.get("deploy", ""))

            checks_html = "".join(
                f'<div class="check-row"><span class="check-icon">✓</span>{_esc(c)}</div>'
                for c in checks[:5]
            )
            cards_html += f"""<div class="tier-card">
  <div class="tier-bar" style="background:#{bar_color}"></div>
  <div class="tier-inner">
    <div class="tier-name" style="color:#{name_color}">{name}</div>
    <div class="tier-module">{module}</div>
    <div class="tier-price"><span class="amount">{price}</span></div>
    <div class="tier-period">{period}</div>
    <div class="tier-checks">{checks_html}</div>
    {f'<div class="tier-deploy"><b>Triển khai:</b> {deploy}</div>' if deploy else ""}
  </div>
</div>"""

        return f"""<div class="slide">
  {self._topbar(sd.get("eyebrow",""))}
  <div class="pricing-body">
    <h2>{plain}<b>{bold}</b></h2>
    {f'<p class="lede-sm">{lede}</p>' if lede else ""}
    <div class="tier-grid {grid_cls}">{cards_html}</div>
  </div>
  {self._stat_bar(stats)}
</div>\n"""


def create_html_deck_generator() -> HTMLDeckGenerator:
    return HTMLDeckGenerator()
