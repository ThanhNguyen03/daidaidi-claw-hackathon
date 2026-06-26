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

/* ── Stat-bar (flex-shrink:0 → never compressed; always visible at bottom) */
.stat-bar{margin-top:auto;flex-shrink:0;display:flex;gap:40px;padding-top:14px;border-top:1px solid var(--line);}
.stat-bar .sv{font-size:24px;font-weight:700;color:var(--ink);line-height:1;}
.stat-bar .sl{font-size:11px;color:var(--gray-light);margin-top:3px;font-weight:400;}

/* ── VALUE layout ──────────────────────────────────────────────────────── */
/* min-height:0 on flex children is required for overflow:hidden to work   */
.body-row{flex:1;min-height:0;overflow:hidden;display:flex;gap:56px;margin-top:16px;align-items:flex-start;}
.left-col{flex:1;min-height:0;overflow:hidden;display:flex;flex-direction:column;}
.left-col h2{font-size:30px;font-weight:400;color:var(--ink);line-height:1.18;letter-spacing:-.02em;margin-bottom:8px;}
.left-col h2 b{color:var(--orange);font-weight:700;}
.lede{font-size:13px;color:var(--gray);line-height:1.55;margin-bottom:12px;}
.feat-list{display:flex;flex-direction:column;gap:7px;min-height:0;overflow:hidden;}
.feat-item{
  display:flex;gap:12px;align-items:flex-start;
  background:#fff;border:1px solid var(--line);border-radius:12px;padding:10px 14px;flex-shrink:0;
}
.feat-item .ic{
  width:30px;height:30px;border-radius:7px;background:var(--card);
  display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;
}
.feat-item h4{font-size:13px;font-weight:600;color:var(--ink);line-height:1.3;margin-bottom:2px;}
.feat-item p{font-size:12px;color:var(--gray);line-height:1.45;}
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
.flow-body{flex:1;min-height:0;overflow:hidden;display:flex;flex-direction:column;margin-top:14px;}
.flow-heading h2{font-size:28px;font-weight:400;color:var(--ink);line-height:1.22;letter-spacing:-.02em;margin-bottom:6px;}
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
.legend-role{font-size:12px;color:var(--gray);margin-left:auto;}
.has-footer .stat-bar{border-top:none;padding-top:10px;}

/* ── HIGHLIGHT (exec summary) ────────────────────────────────────────── */
.highlight-body{flex:1;min-height:0;overflow:hidden;display:flex;flex-direction:column;justify-content:center;margin-top:8px;}
.highlight-body h2{font-size:36px;font-weight:400;color:var(--ink);line-height:1.15;letter-spacing:-.02em;margin-bottom:12px;}
.highlight-body h2 b{color:var(--orange);font-weight:700;}
.highlight-summary{font-size:14px;color:var(--gray);line-height:1.55;max-width:680px;margin-bottom:20px;}
.metrics-row{display:flex;gap:20px;flex-wrap:wrap;}
.metric-card{
  display:flex;flex-direction:column;background:#fff;
  border:1px solid var(--line);border-radius:14px;padding:16px 22px;min-width:140px;flex:1;max-width:200px;
}
.metric-val{font-size:32px;font-weight:800;line-height:1;margin-bottom:5px;}
.metric-lbl{font-size:11px;color:var(--gray);font-weight:400;line-height:1.4;}

/* ── TIER pricing ──────────────────────────────────────────────────────── */
.pricing-body{flex:1;min-height:0;overflow:hidden;display:flex;flex-direction:column;margin-top:16px;}
.pricing-body h2{font-size:30px;font-weight:400;color:var(--ink);line-height:1.18;letter-spacing:-.02em;margin-bottom:6px;}
.pricing-body h2 b{color:var(--orange);font-weight:700;}
.lede-sm{font-size:13px;color:var(--gray);line-height:1.55;margin-bottom:14px;}
.tier-grid{display:grid;gap:14px;flex:1;}
.tier-grid.cols-1{grid-template-columns:1fr;max-width:420px;}
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
Given a sales proposal (may include CLIENT BRIEF + multiple SKILL OUTPUT sections), extract ALL content into structured slide data.

IMPORTANT OUTPUT RULE: Your response must start with [ and end with ]. Output ONLY the raw JSON array.
No preamble, no explanation, no markdown fences (no ```), no trailing text. Just the JSON array itself.

SLIDE COUNT: Generate 5–8 slides. Do NOT generate fewer than 5 slides. Extract every distinct product, feature set, and pricing tier as its own slide.

MANDATORY slide order:
1. HIGHLIGHT slide — REQUIRED as the first slide: executive summary with 3–4 big impact metrics drawn from the proposal (reach, ROI, timeline, cost savings, etc.)
2. VALUE slide(s) — one per major product/module section (e.g. slide for OA, slide for ZNS+Mini App, slide for overall Zalo ecosystem). Up to 3 value slides. Do NOT merge multiple products into one slide if distinct sections exist.
3. FLOW slide — REQUIRED if ANY user journey, userflow, or sequence of steps is described. Extract ALL steps (up to 6).
4. TIER slide — REQUIRED if ANY pricing, packages, or tiers are mentioned. Extract ALL tiers.

Slide schemas — use EXACTLY these field names:

HIGHLIGHT slide (executive summary, always first):
{"type":"highlight","eyebrow":"<section label e.g. Executive Summary>","headline":{"plain":"<impact phrase ending with space>","bold":"<1-3 key words>"},"summary":"<2–3 sentence executive overview for decision-maker, max 45 words, drawn from strategy/product outputs>","metrics":[{"value":"<big metric e.g. 40M+>","label":"<3-4 word description>","color":"orange|teal|purple|gold"}],"stats":[{"v":"<metric>","l":"<3-word label>"}]}

VALUE slide (solution features — one per product/module):
{"type":"value","eyebrow":"<product name e.g. Zalo OA>","tier":"<optional tier label or empty string>","headline":{"plain":"<main phrase ending with space>","bold":"<1-3 key words>"},"lede":"<1 sentence summary, max 18 words>","cards":[{"icon":"<single emoji>","title":"<feature, max 6 words>","desc":"<benefit, max 12 words>","tag":null}],"stats":[{"v":"<metric with unit>","l":"<3-word label>"}]}

FLOW slide (user journey):
{"type":"flow","eyebrow":"<2-3 word context>","headline":{"plain":"<phrase ending with space>","bold":"<key phrase>"},"steps":[{"icon":"<single emoji>","label":"<2-3 words>","desc":"<max 8 words>","role":"customer|admin|staff|system","dot":"core|custom"}],"footer":"<optional addon/custom note, or empty string>","stats":[{"v":"<metric>","l":"<3-word label>"}]}

TIER slide (pricing):
{"type":"tier","eyebrow":"<section label>","headline":{"plain":"<phrase ending with space>","bold":"<key phrase>"},"lede":"<1 sentence, max 15 words>","tiers":[{"barColor":"<hex no #, pastel>","name":"<tier name>","nameColor":"<hex no #>","module":"<module name>","price":"<amount + unit, e.g. 20M VNĐ>","period":"<duration>","checks":["<feature, max 8 words>"],"deploy":"<X ngày làm việc>"}],"stats":[{"v":"<metric>","l":"<3-word label>"}]}

Content rules:
- highlight metrics: extract 3–4 REAL big numbers (user reach, open rate, ROI %, timeline, price saved, etc.); assign colors: first=orange, second=teal, third=purple, fourth=gold
- cards: FILL ALL 4 cards per value slide — extract 4 DISTINCT features from that product's section in the proposal
- steps: FILL ALL steps (up to 6) per flow slide — map every step of the described user journey
- tiers: extract ALL tiers/packages mentioned (up to 4); colors: purple nameColor=5B4FC4 barColor=D4CEEF; teal nameColor=0F9B8E barColor=B8E4DF; orange nameColor=F65009 barColor=FFD9CC; gold nameColor=C8932B barColor=F5E6C4
- stats: 3–4 REAL numbers from the proposal per slide (price, timeline, capacity, user count, etc.)
- card tag: null if no add-on; {"type":"core|custom","text":"CUSTOM +XM VNĐ"} if add-on explicitly priced
- flow footer: list custom add-ons outside main flow as "Addon A (+XM) · Addon B (liên hệ)"
- headline: plain + bold COMBINED max 8 words — short, punchy; long headlines break layout
- CRITICAL: Vietnamese spelling — never duplicate vowel diacritics (write "Sách" not "Sáách")
- START your response with [ — the very first character must be ["""


def _find_json_array(text: str) -> str:
    """Bracket-balanced extractor: finds the outermost [...] in text.
    Handles LLM preamble/postamble and nested structures correctly."""
    start = text.find('[')
    if start == -1:
        return text
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        c = text[i]
        if escape:
            escape = False
            continue
        if c == '\\' and in_string:
            escape = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == '[':
            depth += 1
        elif c == ']':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return text


def _validate_slides(slides: list) -> list:
    """Drop slides missing required fields or with empty content."""
    valid = []
    required = {
        "highlight": ["headline"],
        "value": ["headline", "cards"],
        "flow": ["headline", "steps"],
        "tier": ["headline", "tiers"],
    }
    for s in slides:
        t = s.get("type")
        if t not in required:
            continue
        if not all(s.get(f) for f in required[t]):
            continue
        if t == "value" and not any(c.get("title") for c in (s.get("cards") or [])):
            continue
        if t == "flow" and not any(st.get("label") for st in (s.get("steps") or [])):
            continue
        if t == "tier" and not any(ti.get("name") for ti in (s.get("tiers") or [])):
            continue
        valid.append(s)
    return valid


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


class HTMLDeckGenerator:
    """Generates self-contained AdtimaBox HTML slide decks per adtimabox-deck-html.skill."""

    async def generate(self, proposal_text: str, brief: dict, skill_spec: str = "") -> str:
        slides = await self._extract_slides_with_retry(proposal_text, brief)
        return self._render_html(slides)

    async def _extract_slides_with_retry(self, proposal_text: str, brief: dict) -> list[dict]:
        """Try extraction twice before falling back to hardcoded slides."""
        slides: list[dict] = []
        for attempt in range(2):
            try:
                slides = await self._extract_slides(proposal_text, brief, attempt)
                if slides:
                    break
            except Exception as e:
                print(f"[HTMLDeck] Extraction attempt {attempt+1} failed: {e}")
        if not slides:
            print("[HTMLDeck] Both attempts failed, using fallback")
            slides = self._fallback_slides(brief)
        # Guarantee all required slide types are present
        slides = self._ensure_required_slides(slides, brief)
        return slides

    def _ensure_required_slides(self, slides: list[dict], brief: dict) -> list[dict]:
        """Add any missing required slide types so the deck always has highlight + value + flow + tier."""
        b = brief or {}
        brand = b.get("industry", "Brand")
        types_present = {s.get("type") for s in slides}

        if "highlight" not in types_present:
            slides.insert(0, {
                "type": "highlight",
                "eyebrow": "Executive Summary",
                "headline": {"plain": "Giải pháp Zalo toàn diện cho ", "bold": brand},
                "summary": "Tận dụng hệ sinh thái Zalo — OA, ZNS, Mini App — để thu lead, tăng tương tác và giữ chân khách hàng với chi phí tối ưu.",
                "metrics": [
                    {"value": "40M+", "label": "người dùng Zalo hoạt động", "color": "orange"},
                    {"value": "3x", "label": "tăng tỉ lệ tương tác", "color": "teal"},
                    {"value": "66%", "label": "giảm thời gian onboard", "color": "purple"},
                    {"value": "30 ngày", "label": "go-live cam kết", "color": "gold"},
                ],
                "stats": [{"v": "40M+", "l": "người dùng Zalo"}, {"v": "3x", "l": "tăng tương tác"}],
            })

        if "value" not in types_present:
            slides.insert(0, {
                "type": "value",
                "eyebrow": "Giải pháp Zalo",
                "tier": "",
                "headline": {"plain": "Giải pháp toàn diện trên ", "bold": "Zalo ecosystem"},
                "lede": "Kết hợp OA, ZNS, Mini App để thu lead và tăng loyalty.",
                "cards": [
                    {"icon": "📲", "title": "Zalo OA — kênh chính thức", "desc": "Reach 40M+ không cần app riêng", "tag": None},
                    {"icon": "🔔", "title": "ZNS — push cá nhân hoá", "desc": "Tỉ lệ mở cao, tránh spam", "tag": None},
                    {"icon": "🎮", "title": "Mini App — gamification", "desc": "Voucher, điểm thưởng, đổi quà", "tag": None},
                    {"icon": "📊", "title": "Data & Retargeting", "desc": "Thu lead, tái tiếp cận hiệu quả", "tag": None},
                ],
                "stats": [{"v": "40M+", "l": "người dùng Zalo"}, {"v": "3x", "l": "tăng tương tác"}],
            })

        if "flow" not in types_present:
            slides.append({
                "type": "flow",
                "eyebrow": "User Journey",
                "headline": {"plain": "Hành trình khách hàng trên ", "bold": "Zalo"},
                "steps": [
                    {"icon": "👆", "label": "Khám phá", "desc": "Tiếp cận qua Zalo OA", "role": "customer", "dot": "core"},
                    {"icon": "📋", "label": "Đăng ký", "desc": "Form nhanh qua Mini App", "role": "customer", "dot": "core"},
                    {"icon": "🎁", "label": "Nhận ưu đãi", "desc": "Voucher ngay lập tức", "role": "customer", "dot": "custom"},
                    {"icon": "🔔", "label": "Nhắc nhở", "desc": "ZNS cá nhân hoá", "role": "system", "dot": "core"},
                    {"icon": "🏆", "label": "Loyalty", "desc": "Tích điểm, đổi quà", "role": "customer", "dot": "custom"},
                ],
                "footer": "",
                "stats": [{"v": "5", "l": "bước hành trình"}, {"v": "< 2 min", "l": "thời gian onboard"}],
            })

        if "tier" not in types_present:
            slides.append({
                "type": "tier",
                "eyebrow": "Pricing & Packages",
                "headline": {"plain": "Gói triển khai ", "bold": "linh hoạt"},
                "lede": "3 gói phù hợp với quy mô và ngân sách của từng doanh nghiệp.",
                "tiers": [
                    {"barColor": "D4CEEF", "name": "STARTER", "nameColor": "5B4FC4", "module": "Zalo OA + ZNS",
                     "price": "Liên hệ VNĐ", "period": "Theo thoả thuận",
                     "checks": ["Zalo OA Official Account", "ZNS template cơ bản", "Dashboard báo cáo", "Hỗ trợ setup"],
                     "deploy": "15 ngày làm việc"},
                    {"barColor": "B8E4DF", "name": "GROWTH", "nameColor": "0F9B8E", "module": "OA + ZNS + Mini App",
                     "price": "Liên hệ VNĐ", "period": "Theo thoả thuận",
                     "checks": ["Toàn bộ STARTER", "Mini App gamification", "Loyalty & voucher", "Campaign automation"],
                     "deploy": "30 ngày làm việc"},
                    {"barColor": "FFD9CC", "name": "ENTERPRISE", "nameColor": "F65009", "module": "Full Ecosystem",
                     "price": "Liên hệ VNĐ", "period": "Theo thoả thuận",
                     "checks": ["Toàn bộ GROWTH", "Data & retargeting", "Custom integration", "Dedicated support"],
                     "deploy": "45 ngày làm việc"},
                ],
                "stats": [{"v": "3", "l": "gói triển khai"}, {"v": "15-45", "l": "ngày go-live"}],
            })

        return slides

    async def _extract_slides(self, proposal_text: str, brief: dict, attempt: int = 0) -> list[dict]:
        from llm.greennode import get_llm_client
        from skills.base import strip_think_blocks, extract_json_block

        # Use design model (minimax) — better at strict JSON-only output, no thinking mode issues
        client = get_llm_client("design")
        brand_hint = (brief or {}).get("industry", "")
        # Second attempt: slightly shorter input to reduce LLM confusion
        trimmed = proposal_text[:10000] if attempt > 0 else proposal_text[:15000]

        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(
            None,
            partial(
                client.create_completion,
                messages=[
                    {"role": "system", "content": _EXTRACT_SYSTEM},
                    {"role": "user", "content": f"Brand context: {brand_hint}\n\nProposal:\n{trimmed}"},
                ],
                temperature=0.0,
                max_tokens=8000,
                stream=False,
            ),
        )
        raw = resp.choices[0].message.content or ""
        raw = strip_think_blocks(raw)
        raw = extract_json_block(raw)  # handles ```json...``` fences
        raw = _find_json_array(raw)   # handles preamble text before [
        print(f"[HTMLDeck] attempt {attempt+1} raw ({len(raw)} chars): {raw[:500]}")

        data = json.loads(raw)
        if not isinstance(data, list) or not data:
            print(f"[HTMLDeck] attempt {attempt+1}: empty/invalid list")
            return []
        validated = _validate_slides(data)
        if not validated:
            print(f"[HTMLDeck] attempt {attempt+1}: {len(data)} slides parsed but 0 passed validation")
            return []
        print(f"[HTMLDeck] attempt {attempt+1}: {len(validated)} valid slides {[s.get('type') for s in validated]}")
        return validated

    def _fallback_slides(self, brief: dict) -> list[dict]:
        # Return empty list — _ensure_required_slides will build all 3 required types
        return []

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
        if t == "highlight":
            return self._slide_highlight(sd)
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

    # ── Highlight slide ────────────────────────────────────────────────────
    def _slide_highlight(self, sd: dict) -> str:
        hl = sd.get("headline", {})
        plain = _esc(hl.get("plain", ""))
        bold = _esc(hl.get("bold", ""))
        summary = _esc(sd.get("summary", ""))
        metrics = sd.get("metrics") or []
        stats = sd.get("stats") or []

        color_map = {
            "orange": "var(--orange)", "teal": "var(--teal)",
            "purple": "var(--purple)", "gold": "var(--gold)",
        }
        metrics_html = ""
        for m in metrics[:4]:
            color = color_map.get(m.get("color", "orange"), "var(--orange)")
            metrics_html += f"""<div class="metric-card">
  <div class="metric-val" style="color:{color}">{_esc(m.get("value",""))}</div>
  <div class="metric-lbl">{_esc(m.get("label",""))}</div>
</div>"""

        return f"""<div class="slide">
  {self._topbar(sd.get("eyebrow",""))}
  <div class="highlight-body">
    <h2>{plain}<b>{bold}</b></h2>
    {f'<p class="highlight-summary">{summary}</p>' if summary else ""}
    <div class="metrics-row">{metrics_html}</div>
  </div>
  {self._stat_bar(stats)}
</div>\n"""

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

        slide_cls = "slide has-footer" if footer else "slide"
        return f"""<div class="{slide_cls}">
  {self._topbar(sd.get("eyebrow",""))}
  <div class="flow-body">
    <div class="flow-heading">
      <h2>{plain}<b>{bold}</b></h2>
    </div>
    <div class="legend">
      <div class="legend-item"><div class="legend-dot core"></div>Core (có sẵn)</div>
      <div class="legend-item"><div class="legend-dot custom"></div>Custom (mở rộng)</div>
      <div class="legend-role">Tím = Admin · CMS &nbsp;&nbsp; Xanh = Customer · Mini App</div>
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
        grid_cls = f"cols-{n}" if n >= 2 else "cols-1"
        cards_html = ""
        for t in tiers[:4]:
            bar_color = _esc(t.get("barColor", "ECE6E1"))
            name_color = _esc(t.get("nameColor", "1D1D1F"))
            name = _esc(t.get("name", ""))
            module = _esc(t.get("module", ""))
            price_str = t.get("price", "")
            period = _esc(t.get("period", ""))
            checks = t.get("checks") or []
            deploy = _esc(t.get("deploy", ""))

            # Split price into amount + unit (e.g. "20M" + "VNĐ")
            p_parts = price_str.rsplit(" ", 1)
            amount = _esc(p_parts[0])
            unit = _esc(p_parts[1]) if len(p_parts) > 1 else ""
            unit_span = f'<span class="unit">{unit}</span>' if unit else ""

            checks_html = "".join(
                f'<div class="check-row"><span class="check-icon">✓</span>{_esc(c)}</div>'
                for c in checks[:5]
            )
            cards_html += f"""<div class="tier-card">
  <div class="tier-bar" style="background:#{bar_color}"></div>
  <div class="tier-inner">
    <div class="tier-name" style="color:#{name_color}">{name}</div>
    <div class="tier-module">{module}</div>
    <div class="tier-price"><span class="amount">{amount}</span>{unit_span}</div>
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
