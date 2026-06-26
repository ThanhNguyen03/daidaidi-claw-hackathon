"""
AdtimaBox HTML Deck Generator.
Follows adtimabox-deck-html.skill design system.
Generates a self-contained HTML file (no external deps) that renders
as a proper slide deck viewable in any browser.
"""

from __future__ import annotations

import asyncio
import json
from functools import partial
from datetime import datetime
from typing import Optional

_CSS = """
:root{
  --orange:#F65009;--ink:#1D1D1F;--teal:#0F9B8E;
  --purple:#5B4FC4;--gold:#C8932B;--line:#ECE6E1;
  --card:#FBF8F5;--muted:#78787D;--white:#FFFFFF;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:#2B2B2B;font-family:'Inter',system-ui,-apple-system,sans-serif;
     display:flex;flex-direction:column;align-items:center;gap:24px;padding:32px 16px;
     min-height:100vh;}
.slide{
  width:1280px;max-width:100%;
  height:720px;position:relative;overflow:hidden;
  background:radial-gradient(circle at 8% 0%,rgba(246,80,9,.10) 0%,transparent 55%)
             ,linear-gradient(135deg,#FFF8F5 0%,#FFFFFF 100%);
  border-radius:4px;box-shadow:0 8px 32px rgba(0,0,0,.35);
}
/* --- Topbar --- */
.topbar{
  position:absolute;top:0;left:0;right:0;height:44px;
  background:var(--orange);
  display:flex;align-items:center;padding:0 40px;
}
.topbar-teal{background:var(--teal)}
.topbar-ink{background:var(--ink)}
.topbar .brand{color:#fff;font-size:13px;font-weight:700;letter-spacing:.08em}
.topbar .tagline{color:rgba(255,255,255,.6);font-size:11px;margin-left:auto}
/* --- Content area --- */
.content{position:absolute;top:64px;left:40px;right:40px;bottom:36px;}
/* --- Headline --- */
.headline{font-size:28px;font-weight:700;color:var(--ink);line-height:1.2;
          max-width:820px;margin-bottom:6px}
.headline-lg{font-size:36px}
.subline{font-size:14px;color:var(--muted);margin-top:4px;margin-bottom:20px}
/* --- Divider --- */
.divider{height:3px;border-radius:2px;background:var(--orange);
         width:56px;margin:8px 0 20px}
.divider-teal{background:var(--teal)}
/* --- Feature list --- */
.feat-list{list-style:none;display:flex;flex-direction:column;gap:10px;margin-top:4px}
.feat-item{display:flex;align-items:flex-start;gap:10px;font-size:14px;color:var(--ink)}
.feat-item::before{
  content:'';display:inline-block;
  width:8px;height:8px;border-radius:50%;
  background:var(--orange);flex-shrink:0;margin-top:4px;
}
/* --- Stat bar --- */
.stat-bar{position:absolute;bottom:0;left:0;right:0;padding:14px 40px;
          display:flex;align-items:baseline;gap:8px;
          border-top:1px solid var(--line)}
.stat-value{font-size:42px;font-weight:800;color:var(--orange);line-height:1}
.stat-label{font-size:12px;color:var(--muted);font-weight:500}
/* --- Flow slide --- */
.flow-row{display:flex;gap:0;align-items:stretch;margin-top:8px;flex:1}
.step{
  flex:1;background:#fff;border:1px solid var(--line);border-radius:6px;
  padding:16px 14px;position:relative;margin:0 5px;
}
.step-num{
  width:28px;height:28px;border-radius:50%;background:var(--orange);
  color:#fff;font-weight:700;font-size:13px;
  display:flex;align-items:center;justify-content:center;
  margin-bottom:10px;
}
.step-label{font-size:12px;font-weight:700;color:var(--ink);margin-bottom:6px}
.step-desc{font-size:11px;color:var(--muted);line-height:1.4}
.step-arrow{
  display:flex;align-items:center;padding:0 4px;color:var(--orange);
  font-size:18px;flex-shrink:0;align-self:center;
}
/* --- Tier slide --- */
.tier-row{display:flex;gap:16px;margin-top:8px;align-items:stretch}
.tier-card{
  flex:1;background:#fff;border:1px solid var(--line);border-radius:8px;
  overflow:hidden;display:flex;flex-direction:column;
}
.tier-accent{height:6px;background:var(--orange)}
.tier-accent-teal{background:var(--teal)}
.tier-accent-purple{background:var(--purple)}
.tier-body{padding:16px;flex:1;display:flex;flex-direction:column;gap:6px}
.tier-name{font-size:13px;font-weight:700;color:var(--ink)}
.tier-price{font-size:22px;font-weight:800;color:var(--orange);line-height:1}
.tier-price-teal{color:var(--teal)}
.tier-price-purple{color:var(--purple)}
.tier-note{font-size:10px;color:var(--muted);font-style:italic}
.tier-perks{list-style:none;margin-top:8px;display:flex;flex-direction:column;gap:5px}
.tier-perks li{font-size:11px;color:var(--ink);padding-left:14px;position:relative}
.tier-perks li::before{
  content:'✓';position:absolute;left:0;
  color:var(--orange);font-size:10px;font-weight:700;
}
.tier-perks-teal li::before{color:var(--teal)}
.tier-perks-purple li::before{color:var(--purple)}
/* --- Title slide --- */
.title-slide{
  background:linear-gradient(135deg,#FFF4F0 0%,#FFFFFF 60%);
}
.title-stripe{
  position:absolute;left:0;top:0;bottom:0;width:14px;background:var(--orange);
}
.title-content{
  position:absolute;top:0;left:28px;right:0;bottom:0;
  display:flex;flex-direction:column;justify-content:center;padding:0 40px;
}
.title-brand-tag{font-size:11px;font-weight:700;color:var(--orange);
                 letter-spacing:.12em;text-transform:uppercase;margin-bottom:16px}
.title-headline{font-size:42px;font-weight:800;color:var(--ink);
                line-height:1.15;max-width:760px;margin-bottom:16px}
.title-sub{font-size:16px;color:var(--muted);max-width:600px;margin-bottom:12px}
.title-client{font-size:14px;font-weight:700;color:var(--teal)}
.title-date{
  position:absolute;bottom:24px;right:40px;
  font-size:11px;color:var(--muted);
}
.title-bot{
  position:absolute;bottom:0;left:14px;right:0;height:10px;background:var(--orange)
}
/* --- Closing slide --- */
.closing-top{
  position:absolute;top:0;left:0;right:0;height:55%;
  background:var(--orange);
  display:flex;flex-direction:column;justify-content:center;
  padding:32px 48px;
}
.closing-brand{font-size:11px;font-weight:700;color:rgba(255,255,255,.7);
               letter-spacing:.12em;margin-bottom:20px}
.closing-headline{font-size:34px;font-weight:800;color:#fff;line-height:1.2}
.closing-bottom{
  position:absolute;bottom:0;left:0;right:0;top:55%;
  background:#fff;
  display:flex;flex-direction:column;justify-content:center;
  padding:24px 48px;
}
.closing-sub{font-size:15px;color:var(--ink);margin-bottom:8px}
.closing-contact{font-size:13px;font-weight:700;color:var(--teal)}
.closing-bar{
  position:absolute;bottom:0;left:0;right:0;height:10px;background:var(--ink)
}
/* Nav controls */
.nav{position:fixed;bottom:24px;right:24px;display:flex;gap:8px;z-index:999}
.nav button{
  width:40px;height:40px;border-radius:50%;border:none;cursor:pointer;
  background:var(--orange);color:#fff;font-size:18px;font-weight:700;
  display:flex;align-items:center;justify-content:center;
  box-shadow:0 2px 8px rgba(0,0,0,.3);
}
.counter{
  position:fixed;bottom:28px;left:50%;transform:translateX(-50%);
  font-family:system-ui;font-size:12px;color:#aaa;z-index:999;
}
"""

_JS = """
const slides = document.querySelectorAll('.slide');
let cur = 0;
function show(n) {
  slides.forEach((s,i) => s.style.display = i===n ? 'block' : 'none');
  document.getElementById('counter').textContent = (n+1) + ' / ' + slides.length;
  cur = n;
}
document.addEventListener('keydown', e => {
  if(e.key==='ArrowRight'||e.key===' ') { if(cur<slides.length-1) show(cur+1); }
  if(e.key==='ArrowLeft') { if(cur>0) show(cur-1); }
});
show(0);
"""

_EXTRACT_SYSTEM = """You are a slide-deck content extractor.
Given a sales proposal in Markdown, extract structured data for a presentation deck.
Return ONLY a valid JSON array (no markdown fences). Max 6 slides total.

Slide schemas (use exact field names):
{"type":"title","headline":"<short headline>","sub":"<1 sentence>","brand":"<brand/client name>","date":"<month year>"}
{"type":"value","title":"<slide title>","features":["<feature text, max 10 words each>"],"stat_value":"<big number>","stat_label":"<3 words>"}
{"type":"flow","title":"<slide title>","steps":[{"label":"<3-4 words>","desc":"<8 words max>"}]}
{"type":"tier","title":"Báo giá / Pricing","tiers":[{"name":"<tier name>","price":"<price>","note":"<note>","perks":["<feature>"]}]}
{"type":"closing","headline":"<call to action>","sub":"<next step sentence>","contact":"contact@adtima.vn"}

Rules:
- Always start with title, always end with closing
- 1-3 value slides for strategy/solution content
- flow slide only if user journey steps exist
- tier slide only if pricing data exists in proposal
- features: max 5 items per value slide
- steps: max 5 per flow; tiers: max 3
- Return ONLY the JSON array"""


class HTMLDeckGenerator:
    """Generates self-contained AdtimaBox HTML slide decks."""

    async def generate(self, proposal_text: str, brief: dict) -> str:
        """Return a self-contained HTML string."""
        try:
            slides_data = await self._extract_slides(proposal_text, brief)
        except Exception as e:
            print(f"[HTMLDeck] Slide extraction failed ({e}), using fallback")
            slides_data = self._fallback_slides(brief)

        return self._render_html(slides_data)

    async def _extract_slides(self, proposal_text: str, brief: dict) -> list[dict]:
        from llm.greennode import get_llm_client
        from skills.base import strip_think_blocks, extract_json_block

        client = get_llm_client("central_agent")
        trimmed = proposal_text[:4000]
        brand_hint = (brief or {}).get("industry", "")

        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(
            None,
            partial(
                client.create_completion,
                messages=[
                    {"role": "system", "content": _EXTRACT_SYSTEM},
                    {"role": "user", "content": f"Brand: {brand_hint}\n\n---\n{trimmed}"},
                ],
                temperature=0.1,
                max_tokens=1200,
                stream=False,
            ),
        )
        raw = strip_think_blocks(resp.choices[0].message.content or "[]")
        raw = extract_json_block(raw)
        data = json.loads(raw)
        return data if isinstance(data, list) and data else self._fallback_slides(brief)

    def _fallback_slides(self, brief: dict) -> list[dict]:
        b = brief or {}
        return [
            {"type": "title", "headline": "Đề xuất giải pháp Zalo",
             "sub": "Powered by Adtima — Zalo ecosystem specialist",
             "brand": b.get("industry", "Brand"), "date": datetime.now().strftime("%B %Y")},
            {"type": "value", "title": "Giải pháp đề xuất",
             "features": ["Zalo OA — kênh giao tiếp chính thức",
                          "ZNS — thông báo push cá nhân hoá",
                          "Mini App — tăng tương tác & loyalty",
                          "Brand Hub — quản lý thương hiệu tập trung"],
             "stat_value": "40M+", "stat_label": "người dùng Zalo"},
            {"type": "closing", "headline": "Sẵn sàng bắt đầu?",
             "sub": "Liên hệ team Adtima để nhận tư vấn chi tiết và báo giá",
             "contact": "contact@adtima.vn"},
        ]

    def _render_html(self, slides: list[dict]) -> str:
        slides_html = ""
        for i, sd in enumerate(slides):
            t = sd.get("type", "value")
            style = "" if i == 0 else ' style="display:none"'
            if t == "title":
                slides_html += self._slide_title(sd, style)
            elif t == "value":
                slides_html += self._slide_value(sd, style)
            elif t == "flow":
                slides_html += self._slide_flow(sd, style)
            elif t == "tier":
                slides_html += self._slide_tier(sd, style)
            elif t == "closing":
                slides_html += self._slide_closing(sd, style)

        n = len(slides)
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
<div class="nav">
  <button onclick="if(cur>0)show(cur-1)" title="Prev">&#8592;</button>
  <button onclick="if(cur<{n-1})show(cur+1)" title="Next">&#8594;</button>
</div>
<div class="counter" id="counter">1 / {n}</div>
<script>
var cur=0;
var slides=document.querySelectorAll('.slide');
function show(n){{slides.forEach(function(s,i){{s.style.display=i===n?'block':'none';}});
document.getElementById('counter').textContent=(n+1)+' / '+slides.length;cur=n;}}
document.addEventListener('keydown',function(e){{
  if(e.key==='ArrowRight'||e.key===' '){{if(cur<slides.length-1)show(cur+1);}}
  if(e.key==='ArrowLeft'){{if(cur>0)show(cur-1);}}
}});
</script>
</body>
</html>"""

    def _topbar(self, brand: str = "ADTIMA", color: str = "orange") -> str:
        cls = f"topbar topbar-{color}" if color != "orange" else "topbar"
        return f'<div class="{cls}"><span class="brand">{brand}</span></div>'

    def _slide_title(self, sd: dict, style: str) -> str:
        h = _esc(sd.get("headline", "Đề xuất giải pháp Zalo"))
        sub = _esc(sd.get("sub", ""))
        brand = _esc(sd.get("brand", ""))
        date = _esc(sd.get("date", datetime.now().strftime("%B %Y")))
        return f"""<div class="slide title-slide"{style}>
  <div class="title-stripe"></div>
  <div class="title-content">
    <div class="title-brand-tag">ADTIMA</div>
    <div class="title-headline">{h}</div>
    {"" if not sub else f'<div class="title-sub">{sub}</div>'}
    {"" if not brand else f'<div class="title-client">{brand}</div>'}
  </div>
  <div class="title-date">{date}</div>
  <div class="title-bot"></div>
</div>\n"""

    def _slide_value(self, sd: dict, style: str) -> str:
        title = _esc(sd.get("title", "Giải pháp"))
        feats = sd.get("features") or []
        sv = _esc(sd.get("stat_value", ""))
        sl = _esc(sd.get("stat_label", ""))
        feat_html = "\n".join(f'<li class="feat-item">{_esc(f)}</li>' for f in feats[:5])
        stat_html = ""
        if sv:
            stat_html = f"""<div class="stat-bar">
  <span class="stat-value">{sv}</span>
  {"" if not sl else f'<span class="stat-label">{sl}</span>'}
</div>"""
        return f"""<div class="slide"{style}>
  {self._topbar()}
  <div class="content">
    <div class="headline">{title}</div>
    <div class="divider"></div>
    <ul class="feat-list">{feat_html}</ul>
  </div>
  {stat_html}
</div>\n"""

    def _slide_flow(self, sd: dict, style: str) -> str:
        title = _esc(sd.get("title", "Hành trình người dùng"))
        steps = sd.get("steps") or []
        steps_html = ""
        for i, step in enumerate(steps[:5]):
            label = _esc(step.get("label", ""))
            desc = _esc(step.get("desc", ""))
            arrow = '<div class="step-arrow">&#8594;</div>' if i < len(steps) - 1 else ""
            steps_html += f"""<div class="step">
  <div class="step-num">{i+1}</div>
  <div class="step-label">{label}</div>
  {"" if not desc else f'<div class="step-desc">{desc}</div>'}
</div>{arrow}\n"""
        return f"""<div class="slide"{style}>
  {self._topbar(color="teal")}
  <div class="content">
    <div class="headline">{title}</div>
    <div class="divider divider-teal"></div>
    <div class="flow-row">{steps_html}</div>
  </div>
</div>\n"""

    def _slide_tier(self, sd: dict, style: str) -> str:
        title = _esc(sd.get("title", "Báo giá"))
        tiers = sd.get("tiers") or []
        accents = [("orange", ""), ("teal", "-teal"), ("purple", "-purple")]
        cards_html = ""
        for i, tier in enumerate(tiers[:3]):
            acc, suffix = accents[i % len(accents)]
            name = _esc(tier.get("name", ""))
            price = _esc(tier.get("price", ""))
            note = _esc(tier.get("note", ""))
            perks = tier.get("perks") or []
            perks_html = "\n".join(f"<li>{_esc(p)}</li>" for p in perks[:5])
            cards_html += f"""<div class="tier-card">
  <div class="tier-accent tier-accent{suffix}"></div>
  <div class="tier-body">
    <div class="tier-name">{name}</div>
    <div class="tier-price tier-price{suffix}">{price}</div>
    {"" if not note else f'<div class="tier-note">{note}</div>'}
    <ul class="tier-perks tier-perks{suffix}">{perks_html}</ul>
  </div>
</div>\n"""
        return f"""<div class="slide"{style}>
  {self._topbar()}
  <div class="content">
    <div class="headline">{title}</div>
    <div class="divider"></div>
    <div class="tier-row">{cards_html}</div>
  </div>
</div>\n"""

    def _slide_closing(self, sd: dict, style: str) -> str:
        h = _esc(sd.get("headline", "Bắt đầu ngay hôm nay"))
        sub = _esc(sd.get("sub", ""))
        contact = _esc(sd.get("contact", "contact@adtima.vn"))
        return f"""<div class="slide"{style}>
  <div class="closing-top">
    <div class="closing-brand">ADTIMA</div>
    <div class="closing-headline">{h}</div>
  </div>
  <div class="closing-bottom">
    {"" if not sub else f'<div class="closing-sub">{sub}</div>'}
    <div class="closing-contact">{contact}</div>
  </div>
  <div class="closing-bar"></div>
</div>\n"""


def _esc(s: str) -> str:
    """HTML-escape a string."""
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def create_html_deck_generator() -> HTMLDeckGenerator:
    return HTMLDeckGenerator()
