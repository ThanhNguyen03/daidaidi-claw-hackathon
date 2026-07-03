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
  font-family:'Inter',system-ui,-apple-system,sans-serif;
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
.stat-bar{margin-top:auto;flex-shrink:0;display:flex;gap:40px;padding-top:16px;border-top:1px solid var(--line);}
.stat-bar .v{font-size:28px;font-weight:700;color:var(--ink);line-height:1;}
.stat-bar .l{font-size:12px;color:var(--gray-light);margin-top:4px;font-weight:400;}

/* ── VALUE layout ──────────────────────────────────────────────────────── */
/* min-height:0 on flex children is required for overflow:hidden to work   */
.body-row{flex:1;min-height:0;overflow:hidden;display:flex;gap:56px;margin-top:16px;align-items:flex-start;}
.left-col{flex:1;min-height:0;overflow:hidden;display:flex;flex-direction:column;}
.left-col h2{font-size:38px;font-weight:400;color:var(--ink);line-height:1.18;letter-spacing:-.02em;margin-bottom:10px;}
.left-col h2 b{color:var(--orange);font-weight:700;}
.lede{font-size:13px;color:var(--gray);line-height:1.55;margin-bottom:12px;}
.feat-list{display:flex;flex-direction:column;gap:7px;min-height:0;overflow:hidden;}
.feat-item{
  display:flex;gap:12px;align-items:flex-start;
  background:#fff;border:1px solid var(--line);border-radius:12px;padding:10px 14px;flex-shrink:0;
  border-left:3px solid var(--fi-accent,var(--line));
}
.feat-item .ic{
  width:32px;height:32px;border-radius:8px;background:var(--fi-bg,var(--card));
  display:flex;align-items:center;justify-content:center;font-size:17px;flex-shrink:0;
  font-family:'Segoe UI Emoji','Apple Color Emoji','Noto Color Emoji',system-ui,sans-serif;
  box-shadow:0 2px 6px rgba(0,0,0,.06);
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
  font-family:'Segoe UI Emoji','Apple Color Emoji','Noto Color Emoji',system-ui,sans-serif;
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
  overflow:hidden;position:relative;
}
.metric-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--mc-color,var(--orange));}
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

/* ── VALUE right stat column ───────────────────────────────────── */
.right-stat-col{width:240px;flex-shrink:0;display:flex;flex-direction:column;gap:12px;padding-top:6px;}
.rs-card-primary{
  background:linear-gradient(135deg,var(--orange) 0%,var(--orange-2) 100%);
  border-radius:16px;padding:20px 22px;color:#fff;flex-shrink:0;
}
.rs-card-primary .rsv{font-size:44px;font-weight:800;line-height:1;margin-bottom:4px;}
.rs-card-primary .rsl{font-size:12px;opacity:.88;font-weight:400;line-height:1.4;}
.rs-card-secondary{
  background:#fff;border:1px solid var(--line);
  border-radius:16px;padding:16px 22px;flex-shrink:0;
}
.rs-card-secondary .rsv{font-size:32px;font-weight:800;color:var(--ink);line-height:1;margin-bottom:4px;}
.rs-card-secondary .rsl{font-size:12px;color:var(--gray-light);font-weight:400;line-height:1.4;}

/* ── SCREEN slide ──────────────────────────────────────────────── */
.screen-body{flex:1;min-height:0;overflow:hidden;display:flex;flex-direction:column;margin-top:8px;}
.screen-intro{margin-bottom:14px;flex-shrink:0;}
.screen-intro h2{font-size:26px;font-weight:400;color:var(--ink);line-height:1.22;letter-spacing:-.02em;margin-bottom:4px;}
.screen-intro h2 b{color:var(--orange);font-weight:700;}
.screen-intro .sc-lede{font-size:13px;color:var(--gray);line-height:1.5;}
.phones-row{display:flex;gap:32px;justify-content:center;align-items:flex-start;flex:1;min-height:0;}
.phone-wrap{display:flex;flex-direction:column;align-items:center;}

/* Phone shell */
.phone{
  width:196px;min-width:196px;height:356px;
  background:linear-gradient(160deg,#1A1A2E 0%,#2C2C44 100%);
  border-radius:34px;padding:10px 8px;
  box-shadow:0 28px 72px rgba(0,0,0,.45),0 0 0 1px rgba(255,255,255,.06),inset 0 1px 0 rgba(255,255,255,.08);
  display:flex;flex-direction:column;position:relative;flex-shrink:0;
}
.phone-notch{
  width:64px;height:16px;
  background:linear-gradient(160deg,#1A1A2E 0%,#2C2C44 100%);
  border-radius:0 0 9px 9px;
  position:absolute;top:0;left:50%;transform:translateX(-50%);z-index:2;
}
.phone-screen{
  flex:1;background:#F4F4F6;border-radius:26px;
  overflow:hidden;display:flex;flex-direction:column;
}
.phone-label{
  text-align:center;margin-top:9px;font-size:10px;font-weight:700;
  color:var(--gray-light);letter-spacing:.06em;text-transform:uppercase;flex-shrink:0;
}

/* App elements inside phone */
.app-bar{
  background:var(--orange);padding:9px 12px 8px;
  display:flex;align-items:center;gap:8px;flex-shrink:0;
}
.app-bar .app-name{color:#fff;font-size:11.5px;font-weight:700;flex:1;}
.app-bar .app-icon{color:rgba(255,255,255,.8);font-size:13px;}
.app-content{flex:1;overflow:hidden;display:flex;flex-direction:column;gap:5px;padding:7px 7px 5px;}

.app-banner{
  background:linear-gradient(135deg,var(--orange) 0%,#C43C0A 100%);
  border-radius:9px;padding:9px 11px;color:#fff;
  display:flex;align-items:center;gap:7px;flex-shrink:0;
}
.app-banner .bic{font-size:18px;flex-shrink:0;font-family:'Segoe UI Emoji','Apple Color Emoji','Noto Color Emoji',sans-serif;}
.app-banner .btxt{font-size:10.5px;font-weight:600;line-height:1.3;}

.app-row{
  background:#fff;border-radius:9px;padding:7px 9px;
  display:flex;align-items:center;gap:7px;flex-shrink:0;
  box-shadow:0 1px 4px rgba(0,0,0,.06);
}
.app-row .ric{font-size:15px;flex-shrink:0;font-family:'Segoe UI Emoji','Apple Color Emoji','Noto Color Emoji',sans-serif;}
.app-row .rtxt{flex:1;min-width:0;}
.app-row .rtxt .rt{font-size:10.5px;font-weight:600;color:var(--ink);line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.app-row .rtxt .rs{font-size:9.5px;color:var(--gray-light);}
.app-row .rarrow{color:var(--gray-light);font-size:12px;flex-shrink:0;}

.app-cta{
  background:var(--orange);border-radius:8px;padding:8px;
  color:#fff;font-size:10.5px;font-weight:700;
  text-align:center;flex-shrink:0;margin-top:auto;
}

.app-zns{
  background:#fff;border-radius:9px;padding:9px 10px;
  border:1px solid rgba(246,80,9,.18);border-left:3px solid var(--orange);flex-shrink:0;
}
.app-zns .zns-from{font-size:9px;color:var(--orange);margin-bottom:1px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;}
.app-zns .zns-title{font-size:11px;font-weight:700;color:var(--ink);margin-bottom:2px;line-height:1.3;}
.app-zns .zns-body{font-size:9.5px;color:var(--gray);line-height:1.4;}

.app-points{
  background:linear-gradient(135deg,rgba(15,155,142,.08) 0%,rgba(15,155,142,.04) 100%);
  border-radius:9px;padding:8px 11px;flex-shrink:0;
  display:flex;align-items:center;justify-content:space-between;
  border:1px solid rgba(15,155,142,.12);
}
.app-points .pts-ico{font-size:18px;font-family:'Segoe UI Emoji','Apple Color Emoji','Noto Color Emoji',sans-serif;}
.app-points .pts-right{display:flex;flex-direction:column;align-items:flex-end;}
.app-points .pts-val{font-size:20px;font-weight:800;color:var(--teal);line-height:1;}
.app-points .pts-lbl{font-size:9px;color:var(--gray-light);margin-top:1px;}

/* ── Dark slides: Cover & Closing ──────────────────────────────────────── */
.slide-dark{
  background:#1D1D1F;
  display:flex;flex-direction:column;justify-content:center;align-items:flex-start;
  padding:44px 64px 40px;position:relative;overflow:hidden;
}
.slide-dark::before{
  content:'';position:absolute;top:0;left:0;right:0;height:5px;background:var(--orange);
}
.slide-dark::after{
  content:'';position:absolute;right:-120px;bottom:-120px;
  width:480px;height:480px;border-radius:50%;
  background:radial-gradient(circle,rgba(246,80,9,.10) 0%,transparent 65%);
  pointer-events:none;
}
.slide-dark .dark-eyebrow{
  font-size:12px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;
  color:var(--orange);margin-bottom:18px;
}
.slide-dark .dark-title{
  font-size:44px;font-weight:800;color:#FFFFFF;line-height:1.12;
  letter-spacing:-.02em;margin-bottom:16px;max-width:700px;
}
.slide-dark .dark-subtitle{
  font-size:15px;color:#B8B0AA;font-weight:400;margin-bottom:32px;
}
.slide-dark .dark-meta{
  display:flex;gap:32px;margin-top:auto;padding-top:24px;
  border-top:1px solid rgba(255,255,255,.10);width:100%;
}
.slide-dark .dark-meta-item .dm-label{font-size:10px;color:#6B6B70;text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px;}
.slide-dark .dark-meta-item .dm-val{font-size:13px;color:#FFFFFF;font-weight:600;}
.slide-dark .dark-footer{
  position:absolute;bottom:18px;right:64px;
  font-size:9px;color:#6B6B70;text-transform:uppercase;letter-spacing:.08em;
}
/* Closing-specific */
.slide-dark .dark-closing-tag{
  display:inline-block;background:var(--orange);color:#FFFFFF;
  font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;
  padding:4px 12px;border-radius:4px;margin-bottom:20px;
}

/* ── Agenda slide ───────────────────────────────────────────────────────── */
.agenda-body{flex:1;display:flex;flex-direction:column;justify-content:center;margin-top:8px;}
.agenda-grid{display:flex;flex-wrap:wrap;gap:14px;}
.agenda-item{display:flex;align-items:center;gap:10px;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:11px 16px;flex:1;min-width:180px;}
.agenda-num{width:26px;height:26px;border-radius:50%;background:var(--orange);color:#fff;font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0;}
.agenda-icon{font-size:16px;font-family:'Segoe UI Emoji','Apple Color Emoji','Noto Color Emoji',sans-serif;}
.agenda-label{font-size:13px;font-weight:600;color:var(--ink);}

/* ── Split slide (Business Problem) ────────────────────────────────────── */
.split-body{flex:1;min-height:0;display:flex;gap:24px;margin-top:14px;}
.split-panel{flex:1;display:flex;flex-direction:column;gap:10px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px;}
.split-panel.accent{border-color:var(--orange);border-width:2px;}
.split-panel-label{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.10em;color:var(--orange);margin-bottom:4px;}
.split-panel p{font-size:13px;color:var(--gray);line-height:1.55;}
.split-pain{background:rgba(246,80,9,.07);border-left:3px solid var(--orange);padding:8px 12px;border-radius:4px;font-size:12px;color:var(--ink);margin-top:8px;font-style:italic;}
.split-items{display:flex;flex-direction:column;gap:7px;margin-top:8px;}
.split-item-row{display:flex;gap:8px;align-items:flex-start;font-size:13px;color:var(--ink);}
.split-arrow{color:var(--teal);font-weight:700;flex-shrink:0;font-size:13px;}

/* ── Touchpoints slide ──────────────────────────────────────────────────── */
.tp-body{flex:1;min-height:0;overflow:hidden;margin-top:14px;display:flex;flex-direction:column;}
.tp-table{width:100%;border-collapse:collapse;}
.tp-table th{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--gray);padding:8px 12px;border-bottom:2px solid var(--line);text-align:left;background:#FAFAFA;}
.tp-table td{font-size:13px;color:var(--ink);padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:top;}
.tp-table tr:last-child td{border-bottom:none;}
.tp-badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:700;letter-spacing:.04em;}
.tp-badge.zns{background:rgba(246,80,9,.12);color:#E84A1A;}
.tp-badge.oa{background:rgba(15,155,142,.12);color:#0F9B8E;}
.tp-badge.miniapp{background:rgba(91,79,196,.12);color:#5B4FC4;}
.tp-badge.other{background:rgba(107,107,112,.12);color:#6B6B70;}

/* ── Compliance slide ───────────────────────────────────────────────────── */
.compliance-body{flex:1;min-height:0;display:flex;flex-direction:column;margin-top:12px;gap:14px;}
.compliance-verdict{display:inline-flex;align-items:center;gap:10px;padding:10px 20px;border-radius:8px;font-size:16px;font-weight:700;align-self:flex-start;}
.compliance-verdict.clear{background:#DFF3F0;color:#0A7A71;}
.compliance-verdict.conditions{background:#FEF3C7;color:#92620E;}
.compliance-verdict.blocked{background:#FEE2E2;color:#991B1B;}
.compliance-verdict .v-icon{font-size:20px;}
.compliance-sections{display:flex;gap:20px;flex:1;min-height:0;}
.compliance-col{flex:1;display:flex;flex-direction:column;gap:8px;}
.compliance-col-label{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--gray);padding-bottom:6px;border-bottom:1px solid var(--line);}
.compliance-row{display:flex;gap:8px;align-items:flex-start;font-size:13px;color:var(--ink);line-height:1.4;}
.compliance-dot{width:6px;height:6px;border-radius:50%;background:var(--orange);flex-shrink:0;margin-top:5px;}
.compliance-blocker{background:#FEE2E2;border-left:4px solid #991B1B;padding:10px 14px;border-radius:4px;font-size:13px;color:#7F1D1D;font-weight:600;}

/* ── ROI slide ──────────────────────────────────────────────────────────── */
.roi-body{flex:1;min-height:0;display:flex;gap:20px;margin-top:14px;}
.roi-stats-col{display:flex;flex-direction:column;gap:12px;min-width:220px;}
.roi-stat-card{background:#1D1D1F;border-radius:12px;padding:18px 20px;display:flex;flex-direction:column;align-items:flex-start;}
.roi-stat-card .rs-val{font-size:36px;font-weight:800;line-height:1.1;margin-bottom:4px;}
.roi-stat-card .rs-lbl{font-size:11px;color:#B8B0AA;line-height:1.3;}
.roi-reasons-col{flex:1;display:flex;flex-direction:column;gap:10px;justify-content:center;}
.roi-reason{display:flex;gap:10px;align-items:flex-start;background:var(--card);border:1px solid var(--line);border-radius:9px;padding:12px 14px;}
.roi-reason .rr-icon{font-size:18px;flex-shrink:0;font-family:'Segoe UI Emoji','Apple Color Emoji','Noto Color Emoji',sans-serif;}
.roi-reason .rr-text{font-size:13px;color:var(--ink);line-height:1.45;}

/* ── Timeline slide ─────────────────────────────────────────────────────── */
.timeline-body{flex:1;min-height:0;overflow:hidden;display:flex;flex-direction:column;margin-top:12px;}
.tl-row{display:flex;gap:20px;align-items:flex-start;padding:11px 0;border-bottom:1px solid var(--line);}
.tl-row:last-child{border-bottom:none;}
.tl-week{font-size:10px;font-weight:700;color:var(--orange);text-transform:uppercase;letter-spacing:.07em;min-width:72px;flex-shrink:0;padding-top:3px;}
.tl-content{display:flex;flex-direction:column;gap:3px;}
.tl-label{font-size:14px;font-weight:600;color:var(--ink);}
.tl-items{font-size:12px;color:var(--gray);line-height:1.5;}

/* ── Checklist slide ────────────────────────────────────────────────────── */
.checklist-body{flex:1;min-height:0;display:flex;gap:28px;margin-top:14px;}
.checklist-col{flex:1;display:flex;flex-direction:column;gap:8px;}
.checklist-col-label{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--gray);padding-bottom:6px;border-bottom:2px solid var(--line);margin-bottom:4px;}
.check-item{display:flex;gap:10px;align-items:flex-start;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:9px 12px;}
.check-box{width:18px;height:18px;border-radius:4px;border:2px solid var(--line);flex-shrink:0;margin-top:1px;}
.check-item.high .check-box{border-color:var(--orange);}
.check-text{font-size:13px;color:var(--ink);line-height:1.4;}
.tech-item{display:flex;gap:8px;align-items:flex-start;padding:6px 0;border-bottom:1px solid var(--line);font-size:13px;color:var(--ink);}
.tech-item:last-child{border-bottom:none;}
.tech-icon{color:var(--purple);font-size:13px;flex-shrink:0;}
"""

# ─── EXTRACTION PROMPT (aligned with adtimabox-deck.skill schema) ─────────
_EXTRACT_SYSTEM = """You are a slide-deck content extractor for AdtimaBox branded presentations (adtimabox-proposal-builder skill).
Given a sales proposal following the 7-section AdtimaBox template, extract ALL content into structured slide data.

IMPORTANT OUTPUT RULE: Your response must start with [ and end with ]. Output ONLY the raw JSON array.
No preamble, no explanation, no markdown fences (no ```), no trailing text. Just the JSON array itself.

STRICT NO-FABRICATION RULE: ALL content — text, numbers, company names, case data, compliance conditions, dates — MUST be extracted verbatim or closely paraphrased from the proposal. If a section is absent from the proposal, SKIP that slide type entirely. Do NOT invent content. Fabricating numbers or conditions is a critical error.

PROPOSAL STRUCTURE — 7-section format, map each section to the slide types shown:
  SECTION 1 — EXECUTIVE SUMMARY         -> HIGHLIGHT slide
  SECTION 2 — BUSINESS PROBLEM          -> two SPLIT slides (AS-IS, then TO-BE & Gap)
  SECTION 3 — RECOMMENDED SOLUTION FLOW -> VALUE slide(s) per product/module + FLOW slide (journey) + TOUCHPOINTS slide (if messaging map present) + SCREEN slide(s) (if UI described)
  SECTION 4 — CASE PROOF                -> VALUE slide (card layout, max 2 cases)
  SECTION 5 — COMPLIANCE STATUS         -> COMPLIANCE slide (always, if section present)
  SECTION 6 — INVESTMENT SUMMARY        -> TIER slide (skip entirely if verdict == BLOCKED)
  SECTION 7 — NEXT STEPS                -> TIMELINE slide + CHECKLIST slide (skip entirely if verdict == BLOCKED)

COMPLIANCE GATE: If SECTION 5 verdict is "BLOCKED", do NOT generate slides for Sections 6 or 7.

MANDATORY slide order (follow exactly):
1.  COVER — always first, dark hero
2.  AGENDA — always second, list only sections that have data
3.  SPLIT as_is — Business Problem current state (Section 2)
4.  SPLIT to_be — Business Problem target & gap (Section 2)
5.  HIGHLIGHT — Executive Summary (Section 1) with real metrics
6.  VALUE slide(s) — one per product/module from Section 3
7.  FLOW — Solution Journey from Section 3 JOURNEY block (required if journey present)
8.  TOUCHPOINTS — Messaging map from Section 3 (skip if no touchpoints)
9.  SCREEN slide(s) — if Section 3 describes any app UI / ZNS templates (skip if absent)
10. VALUE — Case Proof from Section 4 (skip if no cases)
11. COMPLIANCE — Section 5 verdict + conditions
12. TIER — Investment from Section 6 (skip if BLOCKED)
13. ROI — derived from Section 6 pricing + Section 4 case data (skip if BLOCKED or no data)
14. TIMELINE — Section 7 suggested timeline (skip if BLOCKED)
15. CHECKLIST — Section 7 decisions + tech confirm (skip if BLOCKED)
16. CLOSING — always last, dark

Slide schemas — use EXACTLY these field names:

COVER (always first):
{"type":"cover","brand":"<client name from proposal header>","industry":"<industry>","date":"<YYYY-MM-DD>","track":"<B2B|B2C|B2B2C>"}

CLOSING (always last):
{"type":"closing","brand":"<client name>","date":"<date>","note":"Confidential. Prices excl. VAT 8%. Valid 30 days from proposal date."}

AGENDA (slide 2 — list only sections that actually have content):
{"type":"agenda","eyebrow":"Agenda","items":["<section name 1>","<section name 2>",...]}

SPLIT (two slides from Section 2 — extract verbatim from proposal):
{"type":"split","eyebrow":"<e.g. Business Problem — AS-IS>","subtype":"as_is","left_label":"<Current State|Hiện Trạng>","left_text":"<problem.as_is verbatim>","left_pain":"<problem.core_pain — 1 sentence>","right_label":"<Target State|Mục Tiêu>","right_text":"<problem.to_be>","gap":"<problem.gap>","right_items":["<gap bullet extracted from proposal>"],"stats":[{"v":"<real metric>","l":"<label>"}]}
{"type":"split","eyebrow":"<e.g. Business Problem — TO-BE & Gap>","subtype":"to_be","left_label":"<Desired Outcome|Mục Tiêu>","left_text":"<problem.to_be>","left_pain":"","right_label":"<The Gap|Khoảng Cách>","right_text":"<gap explanation from proposal>","gap":"<problem.gap>","right_items":["<actionable item from proposal>"],"stats":[{"v":"<real metric>","l":"<label>"}]}

HIGHLIGHT (Section 1 — real numbers only):
{"type":"highlight","eyebrow":"<Executive Summary|Tóm Tắt Điều Hành>","headline":{"plain":"<phrase ending with space>","bold":"<1-3 key words>"},"summary":"<2-3 sentence exec summary from proposal, max 45 words>","metrics":[{"value":"<REAL metric e.g. 450M VND>","label":"<3-4 word desc>","color":"orange|teal|purple|gold"}],"stats":[{"v":"<real metric>","l":"<3-word label>"}]}

VALUE (solution features or case proof — one per distinct product/module/case):
{"type":"value","eyebrow":"<product name or Case Proof>","tier":"","headline":{"plain":"<phrase ending with space>","bold":"<1-3 key words>"},"lede":"<1 sentence from proposal, max 18 words>","cards":[{"icon":"<single emoji>","title":"<feature max 6 words>","desc":"<benefit max 12 words>","tag":null}],"stats":[{"v":"<real metric>","l":"<3-word label>"}]}

FLOW (Section 3 JOURNEY block — copy steps verbatim):
{"type":"flow","eyebrow":"<User Journey|Hành Trình Người Dùng>","headline":{"plain":"<phrase ending with space>","bold":"<key phrase>"},"steps":[{"icon":"<emoji>","label":"<2-3 words from proposal>","desc":"<max 8 words from proposal>","role":"customer|admin|staff|system","dot":"core|custom"}],"footer":"<custom add-ons as 'Item A (+XM) · Item B', or empty>","stats":[{"v":"<real metric>","l":"<label>"}]}

TOUCHPOINTS (Section 3 messaging map — skip if absent):
{"type":"touchpoints","eyebrow":"<Messaging Touchpoints|Điểm Chạm Nhắn Tin>","headline":{"plain":"<phrase ending with space>","bold":"<key words>"},"rows":[{"trigger":"<trigger from proposal>","message_type":"ZNS|OA Message|Mini App Push|ZNS OTP","channel":"Zalo OA|ZNS|Mini App","timing":"<from proposal>"}],"stats":[{"v":"<real metric>","l":"<label>"}]}

COMPLIANCE (Section 5 — always if section present):
{"type":"compliance","eyebrow":"<Compliance Status|Đánh Giá Pháp Lý & Chính Sách>","verdict":"CLEAR|CONDITIONS|BLOCKED","verdict_label":"<exact label from proposal>","conditions":["<condition verbatim>"],"docs_required":["<doc verbatim>"],"blocker":"<blocker text if BLOCKED, else empty>","stats":[{"v":"<real metric>","l":"<label>"}]}

TIER (Section 6 — skip if BLOCKED):
{"type":"tier","eyebrow":"<Investment Summary|Tổng Hợp Ngân Sách Đầu Tư>","headline":{"plain":"<phrase ending with space>","bold":"<key phrase>"},"lede":"<1 sentence max 15 words>","tiers":[{"barColor":"<pastel hex no #>","name":"<package/line label from proposal>","nameColor":"<hex no #>","module":"<module>","price":"<amount M VND from proposal>","period":"<duration or VAT note>","checks":["<item from proposal>"],"deploy":"<timeline if stated>"}],"stats":[{"v":"<real metric>","l":"<label>"}]}

ROI (derived from Section 6 pricing + Section 4 cases — skip if BLOCKED):
{"type":"roi","eyebrow":"<ROI / Why Now|ROI / Vì Sao Là Lúc Này>","headline":{"plain":"<phrase ending with space>","bold":"<key words>"},"stats":[{"value":"<REAL metric from proposal e.g. 3x>","label":"<3-4 word desc>","color":"orange|teal|purple|gold"}],"reasons":["<why-now reason extracted from case data or pricing, not invented>"]}

TIMELINE (Section 7 suggested timeline — skip if BLOCKED):
{"type":"timeline","eyebrow":"<Next Steps & Timeline|Lộ Trình Triển Khai>","headline":{"plain":"<phrase ending with space>","bold":"<key words>"},"weeks":[{"week":"<Week 1-2 etc from proposal>","label":"<phase label from proposal>","items":["<deliverable from proposal>"]}],"stats":[{"v":"<real metric>","l":"<label>"}]}

CHECKLIST (Section 7 decisions — skip if BLOCKED):
{"type":"checklist","eyebrow":"<Key Decisions Required|Quyết Định Cần Phê Duyệt>","headline":{"plain":"<phrase ending with space>","bold":"<key words>"},"decisions":[{"text":"<decision from proposal>","priority":"high|medium"}],"tech_items":["<tech confirm item from proposal>"],"stats":[{"v":"<real metric>","l":"<label>"}]}

SCREEN (Section 3 app UI — skip if absent):
{"type":"screen","eyebrow":"<Demo — Zalo Mini App>","headline":{"plain":"<phrase ending with space>","bold":"<bold phrase>"},"lede":"<optional 1 sentence or empty>","screens":[{"label":"<screen name>","app_name":"<app name from proposal>","items":[{"kind":"banner","emoji":"<emoji>","text":"<hero message max 10 words>"},{"kind":"row","emoji":"<emoji>","title":"<feature 2-4 words>","sub":"<sub 2-3 words>"},{"kind":"cta","text":"<CTA max 5 words>"}]}],"stats":[{"v":"<real metric>","l":"<label>"}]}

Content rules:
- NO fabrication: every number, name, condition, case, step, price must come from the proposal text
- highlight metrics: use real numbers from exec_summary — total investment, user reach, timeline, open rate; color order: orange, teal, purple, gold
- cards: extract 4 DISTINCT real features per value slide from that section
- steps: copy verbatim from Section 3 JOURNEY block; dot="custom" for tech-confirm items
- tiers: extract pricing lines from Section 6; colors — purple: nameColor=5B4FC4 barColor=D4CEEF; teal: 0F9B8E/B8E4DF; orange: F65009/FFD9CC; gold: C8932B/F5E6C4
- agenda items: list only slide section names that have real data in this proposal
- compliance verdict: copy EXACT word from proposal (CLEAR / CONDITIONS / BLOCKED)
- roi reasons: derive from case results and pricing ROI — do not invent
- timeline weeks: copy verbatim from Section 7 SUGGESTED TIMELINE block
- headline: plain + bold combined max 8 words
- Language: match brief language (vi/en); Vietnamese labels: Hiện Trạng, Mục Tiêu, Khoảng Cách, Hành Trình Người Dùng, Điểm Chạm Nhắn Tin, Đánh Giá Pháp Lý, Tổng Hợp Ngân Sách Đầu Tư, Lộ Trình Triển Khai, Quyết Định Cần Phê Duyệt
- CRITICAL: Vietnamese spelling — never duplicate diacritics ("Sách" not "Sáách", "Ngân" not "Ngâân")
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
        "cover": ["brand"],
        "closing": ["brand"],
        "agenda": ["items"],
        "split": ["left_text"],
        "highlight": ["headline"],
        "value": ["headline", "cards"],
        "flow": ["headline", "steps"],
        "touchpoints": ["rows"],
        "compliance": ["verdict"],
        "tier": ["headline", "tiers"],
        "roi": ["stats"],
        "timeline": ["weeks"],
        "checklist": ["decisions"],
        "screen": ["headline", "screens"],
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
        if t == "screen" and not any(sc.get("label") or sc.get("app_name") for sc in (s.get("screens") or [])):
            continue
        valid.append(s)
    return valid


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _safe_icon(text: str) -> str:
    """Strip Unicode that causes invalid HTML or broken emoji rendering:
    lone surrogates (illegal in HTML5), variation selectors without base,
    and C0 control chars. Mirrors _safe_text in pptx_adtimabox.py."""
    if not text:
        return ""
    result = []
    for ch in str(text):
        cp = ord(ch)
        if 0xD800 <= cp <= 0xDFFF:
            continue
        if 0xFE00 <= cp <= 0xFE0F or 0xE0100 <= cp <= 0xE01EF:
            continue
        if cp < 0x20 and ch not in "\t\n\r":
            continue
        result.append(ch)
    return "".join(result)


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
        """Guarantee cover is first and closing is last. All other slides come from proposal extraction only — no fabricated fallbacks."""
        b = brief or {}
        brand = b.get("company_name") or b.get("industry", "Brand")
        industry = b.get("industry", "")
        date = b.get("date", "")
        types_present = {s.get("type") for s in slides}

        # Cover must be first
        if "cover" not in types_present:
            slides.insert(0, {
                "type": "cover",
                "brand": brand,
                "industry": industry,
                "date": date,
                "track": b.get("track", "B2B"),
            })
        elif slides[0].get("type") != "cover":
            cover = next(s for s in slides if s.get("type") == "cover")
            slides.remove(cover)
            slides.insert(0, cover)

        # Closing must be last
        if "closing" not in types_present:
            slides.append({
                "type": "closing",
                "brand": brand,
                "date": date,
            })
        elif slides[-1].get("type") != "closing":
            closing = next(s for s in slides if s.get("type") == "closing")
            slides.remove(closing)
            slides.append(closing)

        return slides

    async def _extract_slides(self, proposal_text: str, brief: dict, attempt: int = 0) -> list[dict]:
        from llm.greennode import get_llm_client
        from skills.base import strip_think_blocks, extract_json_block

        # Use design model (minimax) — better at strict JSON-only output, no thinking mode issues
        client = get_llm_client("design")
        brand_hint = (brief or {}).get("industry", "")
        # Second attempt: shorter input to reduce LLM confusion on retry.
        # First attempt: up to 80k chars (4 skill outputs at ~15k each + brief = ~65k).
        # MiniMax M2.5 has 1M token context so this is well within limits.
        trimmed = proposal_text[:45000] if attempt > 0 else proposal_text[:80000]

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
                max_tokens=12000,
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
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<style>{_CSS}</style>
</head>
<body>
{slides_html}
</body>
</html>"""

    def _render_slide(self, sd: dict) -> str:
        t = sd.get("type", "value")
        if t == "cover":
            return self._slide_cover(sd)
        if t == "closing":
            return self._slide_closing(sd)
        if t == "agenda":
            return self._slide_agenda(sd)
        if t == "split":
            return self._slide_split(sd)
        if t == "highlight":
            return self._slide_highlight(sd)
        if t == "value":
            return self._slide_value(sd)
        if t == "flow":
            return self._slide_flow(sd)
        if t == "touchpoints":
            return self._slide_touchpoints(sd)
        if t == "compliance":
            return self._slide_compliance(sd)
        if t == "tier":
            return self._slide_tier(sd)
        if t == "roi":
            return self._slide_roi(sd)
        if t == "timeline":
            return self._slide_timeline(sd)
        if t == "checklist":
            return self._slide_checklist(sd)
        if t == "screen":
            return self._slide_screen(sd)
        return ""

    # ── Cover slide (dark hero, slide 1) ───────────────────────────────────
    def _slide_cover(self, sd: dict) -> str:
        brand = _esc(sd.get("brand", ""))
        industry = _esc(sd.get("industry", ""))
        date = _esc(sd.get("date", ""))
        track = _esc(sd.get("track", ""))
        meta_items = ""
        if date:
            meta_items += f'<div class="dark-meta-item"><div class="dm-label">Date</div><div class="dm-val">{date}</div></div>'
        if industry:
            meta_items += f'<div class="dark-meta-item"><div class="dm-label">Industry</div><div class="dm-val">{industry}</div></div>'
        if track:
            meta_items += f'<div class="dark-meta-item"><div class="dm-label">Track</div><div class="dm-val">{track}</div></div>'
        meta_html = f'<div class="dark-meta">{meta_items}</div>' if meta_items else ""
        return f"""<div class="slide slide-dark">
  <div class="dark-eyebrow">{brand}</div>
  <div class="dark-title">ADTIMABOX PROPOSAL</div>
  <div class="dark-subtitle">Zalo Ecosystem Solutions — {industry or "Client Pitch"}</div>
  {meta_html}
  <div class="dark-footer">ADTIMA</div>
</div>\n"""

    # ── Closing slide (dark, thank you) ────────────────────────────────────
    def _slide_closing(self, sd: dict) -> str:
        brand = _esc(sd.get("brand", ""))
        date = _esc(sd.get("date", ""))
        note = _esc(sd.get("note", "Confidential. Prices excl. VAT 8%. Valid 30 days from proposal date."))
        return f"""<div class="slide slide-dark">
  <div class="dark-closing-tag">AdtimaBox by Adtima</div>
  <div class="dark-title">Cảm ơn {brand}</div>
  <div class="dark-subtitle">Hẹn gặp lại — chúng tôi sẵn sàng hỗ trợ bạn.</div>
  <div class="dark-meta">
    <div class="dark-meta-item"><div class="dm-label">Prepared by</div><div class="dm-val">AdtimaBox Sales Team</div></div>
    {f'<div class="dark-meta-item"><div class="dm-label">Date</div><div class="dm-val">{date}</div></div>' if date else ""}
  </div>
  <div class="dark-subtitle" style="font-size:11px;margin-top:8px;">{note}</div>
  <div class="dark-footer">ADTIMA</div>
</div>\n"""

    # ── Agenda slide (slide 2 — icon row of sections present) ─────────────
    def _slide_agenda(self, sd: dict) -> str:
        items = sd.get("items") or []
        ICONS = {
            "business problem": "🎯", "bài toán": "🎯",
            "solution": "💡", "giải pháp": "💡",
            "journey": "🗺", "hành trình": "🗺",
            "touchpoints": "💬", "điểm chạm": "💬",
            "case": "📋", "case proof": "📋",
            "compliance": "✅", "pháp lý": "✅",
            "investment": "💰", "ngân sách": "💰",
            "roi": "📈",
            "next steps": "🚀", "lộ trình": "🚀",
            "decisions": "✔", "quyết định": "✔",
        }
        items_html = ""
        for i, item in enumerate(items[:12], 1):
            key = (item or "").lower()
            icon = next((v for k, v in ICONS.items() if k in key), "📌")
            items_html += f'<div class="agenda-item"><div class="agenda-num">{i}</div><span class="agenda-icon">{_safe_icon(icon)}</span><span class="agenda-label">{_esc(item)}</span></div>'
        return f"""<div class="slide">
  {self._topbar(sd.get("eyebrow", "Agenda"))}
  <div class="agenda-body">
    <div class="agenda-grid">{items_html}</div>
  </div>
</div>\n"""

    # ── Split slide (Business Problem AS-IS / TO-BE) ───────────────────────
    def _slide_split(self, sd: dict) -> str:
        left_label = _esc(sd.get("left_label", "Current State"))
        left_text = _esc(sd.get("left_text", ""))
        left_pain = _esc(sd.get("left_pain", ""))
        right_label = _esc(sd.get("right_label", "Target State"))
        right_text = _esc(sd.get("right_text", ""))
        gap = _esc(sd.get("gap", ""))
        right_items = sd.get("right_items") or []
        stats = sd.get("stats") or []

        right_items_html = "".join(
            f'<div class="split-item-row"><span class="split-arrow">→</span>{_esc(it)}</div>'
            for it in right_items[:4]
        )
        pain_html = f'<div class="split-pain">"{left_pain}"</div>' if left_pain else ""
        gap_html = f'<div class="split-pain">{gap}</div>' if gap else ""

        return f"""<div class="slide">
  {self._topbar(sd.get("eyebrow", "Business Problem"))}
  <div class="split-body">
    <div class="split-panel accent">
      <div class="split-panel-label">{left_label}</div>
      <p>{left_text}</p>
      {pain_html}
    </div>
    <div class="split-panel">
      <div class="split-panel-label">{right_label}</div>
      <p>{right_text}</p>
      {gap_html}
      <div class="split-items">{right_items_html}</div>
    </div>
  </div>
  {self._stat_bar(stats)}
</div>\n"""

    # ── Touchpoints slide (messaging map table) ────────────────────────────
    def _slide_touchpoints(self, sd: dict) -> str:
        rows = sd.get("rows") or []
        stats = sd.get("stats") or []
        hl = sd.get("headline", {})
        plain = _esc(hl.get("plain", ""))
        bold = _esc(hl.get("bold", ""))

        def _badge(msg_type: str) -> str:
            t = (msg_type or "").lower()
            cls = "zns" if "zns" in t else "oa" if "oa" in t else "miniapp" if ("mini" in t or "app" in t) else "other"
            return f'<span class="tp-badge {cls}">{_esc(msg_type)}</span>'

        rows_html = "".join(
            f"""<tr>
  <td>{_esc(r.get("trigger",""))}</td>
  <td>{_badge(r.get("message_type",""))}</td>
  <td>{_esc(r.get("channel",""))}</td>
  <td>{_esc(r.get("timing",""))}</td>
</tr>"""
            for r in rows[:8]
        )
        return f"""<div class="slide">
  {self._topbar(sd.get("eyebrow", "Messaging Touchpoints"))}
  <h2 style="font-size:22px;font-weight:700;color:var(--ink);margin:10px 0 4px;">{plain}<b style="color:var(--orange)">{bold}</b></h2>
  <div class="tp-body">
    <table class="tp-table">
      <thead><tr><th>Trigger</th><th>Message Type</th><th>Channel</th><th>Timing</th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>
  {self._stat_bar(stats)}
</div>\n"""

    # ── Compliance slide (status badge + conditions) ───────────────────────
    def _slide_compliance(self, sd: dict) -> str:
        verdict = (sd.get("verdict") or "CLEAR").upper()
        verdict_label = sd.get("verdict_label") or {
            "CLEAR": "CLEAR TO PROCEED",
            "CONDITIONS": "PROCEED WITH CONDITIONS",
            "BLOCKED": "BLOCKED",
        }.get(verdict, verdict)
        conditions = sd.get("conditions") or []
        docs = sd.get("docs_required") or []
        blocker = sd.get("blocker", "")
        stats = sd.get("stats") or []

        cls_map = {"CLEAR": "clear", "CONDITIONS": "conditions", "BLOCKED": "blocked"}
        icon_map = {"CLEAR": "✅", "CONDITIONS": "⚠️", "BLOCKED": "🚫"}
        verdict_cls = cls_map.get(verdict, "clear")
        verdict_icon = _safe_icon(icon_map.get(verdict, "✅"))

        blocker_html = f'<div class="compliance-blocker">Blocker: {_esc(blocker)}</div>' if blocker else ""

        def _col(lst: list, label: str) -> str:
            if not lst:
                return ""
            rows = "".join(
                f'<div class="compliance-row"><div class="compliance-dot"></div>{_esc(it)}</div>'
                for it in lst[:6]
            )
            return f'<div class="compliance-col"><div class="compliance-col-label">{label}</div>{rows}</div>'

        sections_html = ""
        if conditions or docs:
            sections_html = f'<div class="compliance-sections">{_col(conditions, "Conditions Before Launch")}{_col(docs, "Documents Required")}</div>'

        return f"""<div class="slide">
  {self._topbar(sd.get("eyebrow", "Compliance Status"))}
  <div class="compliance-body">
    <div class="compliance-verdict {verdict_cls}">
      <span class="v-icon">{verdict_icon}</span>
      <span>{_esc(verdict_label)}</span>
    </div>
    {blocker_html}
    {sections_html}
  </div>
  {self._stat_bar(stats)}
</div>\n"""

    # ── ROI slide (stat callouts + reasons) ───────────────────────────────
    def _slide_roi(self, sd: dict) -> str:
        stats = sd.get("stats") or []
        reasons = sd.get("reasons") or []
        hl = sd.get("headline", {})
        plain = _esc(hl.get("plain", ""))
        bold = _esc(hl.get("bold", ""))

        color_map = {"orange": "#F65009", "teal": "#0F9B8E", "purple": "#5B4FC4", "gold": "#C8932B"}
        stat_cards = ""
        for s in stats[:3]:
            color = color_map.get(s.get("color", "orange"), "#F65009")
            stat_cards += f"""<div class="roi-stat-card">
  <div class="rs-val" style="color:{color}">{_esc(s.get("value",""))}</div>
  <div class="rs-lbl">{_esc(s.get("label",""))}</div>
</div>"""

        REASON_ICONS = ["🎯", "📈", "⚡", "🤝", "💡"]
        reasons_html = "".join(
            f'<div class="roi-reason"><span class="rr-icon">{_safe_icon(REASON_ICONS[i % len(REASON_ICONS)])}</span><span class="rr-text">{_esc(r)}</span></div>'
            for i, r in enumerate(reasons[:5])
        )
        return f"""<div class="slide">
  {self._topbar(sd.get("eyebrow", "ROI / Why Now"))}
  <h2 style="font-size:22px;font-weight:700;color:var(--ink);margin:10px 0 4px;">{plain}<b style="color:var(--orange)">{bold}</b></h2>
  <div class="roi-body">
    <div class="roi-stats-col">{stat_cards}</div>
    <div class="roi-reasons-col">{reasons_html}</div>
  </div>
</div>\n"""

    # ── Timeline slide (next steps phased) ────────────────────────────────
    def _slide_timeline(self, sd: dict) -> str:
        weeks = sd.get("weeks") or []
        stats = sd.get("stats") or []
        hl = sd.get("headline", {})
        plain = _esc(hl.get("plain", ""))
        bold = _esc(hl.get("bold", ""))

        rows_html = ""
        for w in weeks[:6]:
            items_text = " · ".join(w.get("items") or [])
            rows_html += f"""<div class="tl-row">
  <div class="tl-week">{_esc(w.get("week",""))}</div>
  <div class="tl-content">
    <div class="tl-label">{_esc(w.get("label",""))}</div>
    <div class="tl-items">{_esc(items_text)}</div>
  </div>
</div>"""

        return f"""<div class="slide">
  {self._topbar(sd.get("eyebrow", "Next Steps &amp; Timeline"))}
  <h2 style="font-size:22px;font-weight:700;color:var(--ink);margin:10px 0 4px;">{plain}<b style="color:var(--orange)">{bold}</b></h2>
  <div class="timeline-body">{rows_html}</div>
  {self._stat_bar(stats)}
</div>\n"""

    # ── Checklist slide (client decisions + tech confirm) ─────────────────
    def _slide_checklist(self, sd: dict) -> str:
        decisions = sd.get("decisions") or []
        tech_items = sd.get("tech_items") or []
        stats = sd.get("stats") or []
        hl = sd.get("headline", {})
        plain = _esc(hl.get("plain", ""))
        bold = _esc(hl.get("bold", ""))

        decisions_html = ""
        for d in decisions[:6]:
            text = d.get("text", d) if isinstance(d, dict) else d
            priority = d.get("priority", "") if isinstance(d, dict) else ""
            cls = "check-item high" if priority == "high" else "check-item"
            decisions_html += f'<div class="{cls}"><div class="check-box"></div><div class="check-text">{_esc(str(text))}</div></div>'

        tech_html = "".join(
            f'<div class="tech-item"><span class="tech-icon">⚙</span>{_esc(t)}</div>'
            for t in tech_items[:6]
        )
        tech_col = f'<div class="checklist-col"><div class="checklist-col-label">Tech Confirmation Required</div>{tech_html}</div>' if tech_html else ""

        return f"""<div class="slide">
  {self._topbar(sd.get("eyebrow", "Key Decisions Required"))}
  <h2 style="font-size:22px;font-weight:700;color:var(--ink);margin:10px 0 4px;">{plain}<b style="color:var(--orange)">{bold}</b></h2>
  <div class="checklist-body">
    <div class="checklist-col">
      <div class="checklist-col-label">Client Decisions</div>
      {decisions_html}
    </div>
    {tech_col}
  </div>
  {self._stat_bar(stats)}
</div>\n"""

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
            f'<div><div class="v">{_esc(s.get("v",""))}</div><div class="l">{_esc(s.get("l",""))}</div></div>'
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
            "orange": ("var(--orange)", "#F65009"),
            "teal": ("var(--teal)", "#0F9B8E"),
            "purple": ("var(--purple)", "#5B4FC4"),
            "gold": ("var(--gold)", "#C8932B"),
        }
        metrics_html = ""
        for m in metrics[:4]:
            css_var, hex_val = color_map.get(m.get("color", "orange"), ("var(--orange)", "#F65009"))
            metrics_html += f"""<div class="metric-card" style="--mc-color:{css_var}">
  <div class="metric-val" style="color:{css_var}">{_esc(m.get("value",""))}</div>
  <div class="metric-lbl">{_esc(m.get("label",""))}</div>
</div>"""

        # Decorative background circle — adds depth without cluttering
        deco = '<div style="position:absolute;right:-80px;top:-120px;width:500px;height:500px;border-radius:50%;background:radial-gradient(circle,rgba(246,80,9,.06) 0%,transparent 65%);pointer-events:none;"></div>'
        return f"""<div class="slide" style="overflow:hidden;">
  {deco}
  {self._topbar(sd.get("eyebrow",""))}
  <div class="highlight-body">
    <h2>{plain}<b>{bold}</b></h2>
    {f'<p class="highlight-summary">{summary}</p>' if summary else ""}
    <div class="metrics-row">{metrics_html}</div>
  </div>
  {self._stat_bar(stats)}
</div>\n"""

    # ── Value slide ────────────────────────────────────────────────────────
    _CARD_ACCENTS = [
        ("var(--teal)", "rgba(15,155,142,.08)"),
        ("var(--orange)", "rgba(246,80,9,.07)"),
        ("var(--purple)", "rgba(91,79,196,.08)"),
        ("var(--gold)", "rgba(200,147,43,.08)"),
    ]

    def _slide_value(self, sd: dict) -> str:
        hl = sd.get("headline", {})
        plain = _esc(hl.get("plain", ""))
        bold = _esc(hl.get("bold", ""))
        lede = _esc(sd.get("lede", ""))
        cards = sd.get("cards") or []
        stats = sd.get("stats") or []

        cards_html = ""
        for idx, c in enumerate(cards[:4]):
            icon = _esc(_safe_icon(c.get("icon", "")))
            title = _esc(c.get("title", ""))
            desc = _esc(c.get("desc", ""))
            tag = c.get("tag")
            tag_html = ""
            if tag and isinstance(tag, dict):
                tc = "tag-core" if tag.get("type") == "core" else "tag-custom"
                tag_html = f'<span class="{tc}">{_esc(tag.get("text",""))}</span>'
            accent_border, accent_bg = self._CARD_ACCENTS[idx % 4]
            cards_html += f"""<div class="feat-item" style="--fi-accent:{accent_border};--fi-bg:{accent_bg}">
  <div class="ic">{icon}</div>
  <div><h4>{title}</h4><p>{desc}</p>{tag_html}</div>
</div>"""

        # Right stat column — show top stats visually for fast scanning
        right_col_html = ""
        if stats:
            primary = stats[0]
            right_col_html = f"""<div class="right-stat-col">
  <div class="rs-card-primary">
    <div class="rsv">{_esc(primary.get("v",""))}</div>
    <div class="rsl">{_esc(primary.get("l",""))}</div>
  </div>"""
            for s in stats[1:3]:
                right_col_html += f"""<div class="rs-card-secondary">
    <div class="rsv">{_esc(s.get("v",""))}</div>
    <div class="rsl">{_esc(s.get("l",""))}</div>
  </div>"""
            right_col_html += "</div>"

        return f"""<div class="slide">
  {self._topbar(sd.get("eyebrow",""), sd.get("tier",""))}
  <div class="body-row">
    <div class="left-col">
      <h2>{plain}<b>{bold}</b></h2>
      {f'<p class="lede">{lede}</p>' if lede else ""}
      <div class="feat-list">{cards_html}</div>
    </div>
    {right_col_html}
  </div>
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
            icon = _esc(_safe_icon(st.get("icon", "")))
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


    # ── Screen slide (app mockup) ──────────────────────────────────────────
    def _slide_screen(self, sd: dict) -> str:
        hl = sd.get("headline", {})
        plain = _esc(hl.get("plain", ""))
        bold = _esc(hl.get("bold", ""))
        lede = _esc(sd.get("lede", ""))
        screens = sd.get("screens") or []
        stats = sd.get("stats") or []

        phones_html = ""
        for phone_data in screens[:3]:
            label = _esc(phone_data.get("label", ""))
            app_name = _esc(phone_data.get("app_name", "Mini App"))
            items = phone_data.get("items") or []

            content_html = ""
            for item in items[:6]:
                kind = item.get("kind", "row")
                emoji = _esc(_safe_icon(item.get("emoji", "")))

                if kind == "banner":
                    text = _esc(item.get("text", ""))
                    content_html += f"""<div class="app-banner">
  <span class="bic">{emoji}</span>
  <span class="btxt">{text}</span>
</div>"""
                elif kind == "row":
                    title = _esc(item.get("title", ""))
                    sub = _esc(item.get("sub", ""))
                    sub_html = f'<div class="rs">{sub}</div>' if sub else ""
                    content_html += f"""<div class="app-row">
  <span class="ric">{emoji}</span>
  <div class="rtxt"><div class="rt">{title}</div>{sub_html}</div>
  <span class="rarrow">›</span>
</div>"""
                elif kind == "cta":
                    text = _esc(item.get("text", ""))
                    content_html += f'<div class="app-cta">{text}</div>'
                elif kind == "zns":
                    zns_from = _esc(item.get("from", "Thông báo"))
                    zns_title = _esc(item.get("title", ""))
                    zns_body = _esc(item.get("text", ""))
                    content_html += f"""<div class="app-zns">
  <div class="zns-from">{zns_from}</div>
  <div class="zns-title">{zns_title}</div>
  <div class="zns-body">{zns_body}</div>
</div>"""
                elif kind == "points":
                    pts_emoji = _esc(_safe_icon(item.get("emoji", "⭐")))
                    pts_val = _esc(item.get("value", "0"))
                    pts_lbl = _esc(item.get("text", "Điểm tích lũy"))
                    content_html += f"""<div class="app-points">
  <span class="pts-ico">{pts_emoji}</span>
  <div class="pts-right">
    <div class="pts-val">{pts_val}</div>
    <div class="pts-lbl">{pts_lbl}</div>
  </div>
</div>"""

            phones_html += f"""<div class="phone-wrap">
  <div class="phone">
    <div class="phone-notch"></div>
    <div class="phone-screen">
      <div class="app-bar">
        <span class="app-name">{app_name}</span>
        <span class="app-icon">☰</span>
      </div>
      <div class="app-content">{content_html}</div>
    </div>
  </div>
  {f'<div class="phone-label">{label}</div>' if label else ''}
</div>"""

        return f"""<div class="slide">
  {self._topbar(sd.get("eyebrow",""))}
  <div class="screen-body">
    <div class="screen-intro">
      <h2>{plain}<b>{bold}</b></h2>
      {f'<p class="sc-lede">{lede}</p>' if lede else ""}
    </div>
    <div class="phones-row">{phones_html}</div>
  </div>
  {self._stat_bar(stats)}
</div>\n"""


def create_html_deck_generator() -> HTMLDeckGenerator:
    return HTMLDeckGenerator()
