---
name: strategy-skill
description: >
  Strategy & Marketing skill for Adtima's proposal system.
  Use this skill whenever you need to: diagnose a client's business problem from a brief,
  map industry context and pain points, develop consumer insight and customer journey,
  recommend Zalo ecosystem solutions (OA, ZNS, Mini App, CDP), and match relevant
  AdtimaBox case studies.
  Primary industries: FMCG/F&B and Pharma/Healthcare. Also handles Finance,
  Retail, and cross-industry briefs.
allowed-tools: web_search, project_knowledge_search, read_file
---

# Strategy Skill

Strategic analysis engine for Adtima's proposal system. Operates at Level 3–4
Strategic Consultant maturity — diagnosing business problems, designing ecosystem
solutions, connecting business challenges to Zalo platform capabilities.

---

## Phase 1 — Business Diagnosis

> Competency 1: Transform stated requirements into real business problems.

Do not accept the brief at face value. Reframe the stated need into a business
problem using hypothesis-driven thinking.

**Steps:**

1. Extract the stated requirement from the brief — what does the client say they want?
2. Identify the underlying business problem — apply root cause thinking: *why* do they want this?
3. Write a Problem Statement:
   `[Client] needs to [business outcome] because [root cause], which is currently causing [measurable impact or risk].`
4. Gap Analysis: Current state → Desired state → Gap

**Common Reframes:**

| Stated Requirement | Reframed Business Problem |
|--------------------|--------------------------|
| "We need a Loyalty Program" | Repeat purchase frequency is low; CAC is rising |
| "We want brand awareness" | Household penetration is below category benchmark |
| "We need a Mini App" | No owned customer data; fully dependent on paid media |
| "We want HCP engagement" | Low prescription share due to weak physician touchpoints |
| "We need ZNS campaigns" | CRM capability missing; customer re-engagement is manual |

---

## Phase 2 — Industry & Market Context

> Competency 2: Understand how the client's industry creates value.

**Step 1: Classify the Industry**

FMCG / F&B:
- Key metrics: Household Penetration, Repeat Purchase Rate, Share of Wallet
- Core mechanics: Distribution reach, Consumer Promotion, Loyalty Programs
- Data priorities: Purchase behavior, loyalty tier, SKU affinity
- Zalo fit: Mini App loyalty, ZNS push for promotions, OA for brand community

Pharma / Healthcare:
- Key metrics: HCP prescription share, Patient adherence rate, Event attendance
- Core mechanics: HCP Engagement, Patient Support Programs, Disease Awareness, Medical Education
- Regulatory constraints: ⚠️ All Pharma briefs require compliance review before finalizing solution
- Data priorities: HCP profile, prescription behavior, event participation
- Zalo fit: HCP Mini App, ZNS for appointment reminders, OA for medical education

Finance / Insurance:
- Key metrics: Policy conversion, claim retention, cross-sell rate
- Zalo fit: ZNS for policy updates, Mini App for claims/service, OA for education

Retail / E-commerce:
- Key metrics: Cart abandonment, repeat purchase, NPS
- Zalo fit: ZNS cart recovery, Mini App loyalty, OA for CS

**Adtima Platform Scale (sử dụng khi pitch để build credibility):**

| Platform | Stats | Best for |
|----------|-------|----------|
| Zalo | 75M+ MAU · 90% VN internet users · 2B messages/day | Mass reach, messaging, CRM, Mini App |
| Zing MP3 | 28M MAU · #1 Music App VN | Audio branding, music moment reach |
| Báo Mới | 26M+ monthly users · #1 news app download VN | News adjacency, native content |
| ZNews | 32,390 avg visitor/30min · 34.34% bounce (lowest in industry) | Prestige content, health/lifestyle |
| Zcast + Z Studio | 80M reach/month | Community content, MCN, YouTube/TikTok |

Total Adtima reach: **75M+ MAU = 90% of Vietnam internet users** — essentially all mobile internet users in Vietnam.

**Step 2: Market Research (RAG + Web Search)**

Priority order:
1. RAG first — search project knowledge base: "[client_name] OR [industry] case study", "[industry] Zalo solution Vietnam"
2. Web search fallback — "[brand] Vietnam marketing strategy [year]", "[industry] Vietnam consumer trend [year]", "[brand] Zalo mini app Vietnam"
3. Synthesize into: market context (2–3 facts with sources), competitive snapshot, top 3 strategic opportunities

**Recommended research sources (Vietnam marketing context):**
- **BrandsVietnam** (brandsvietnam.com/campaign) — Case studies brand VN: Nestlé, OMO, Mirinda, Cornetto, PNJ, Knorr, NIVEA, Clorox... Tốt cho: campaign benchmarks, consumer insight VN, creative direction thị trường
- **Advertising Vietnam** (advertisingvietnam.com) — Tin tức campaign, agency, creative work. Tốt cho: tracking brand activity hiện tại, viral/social trends
- Web search `"[brand] Vietnam Zalo"` — detect Zalo OA/Mini App presence trước khi pitch

Label all findings: ✅ Confirmed | ❓ Unconfirmed | ❌ Not found. Never present assumptions as facts.

---

## COMPETITIVE LANDSCAPE — ADTIMABOX VS KEY COMPETITORS

> Activate khi: (1) brief mention đối thủ cụ thể, (2) cần viết `competitive_snapshot` trong JSON output,
> (3) client hỏi "tại sao chọn Adtima thay vì X?"
> ⚠️ Chỉ claim điểm đã verify — không bịa điểm yếu đối thủ.

### CNV (cnv.vn) — Đối thủ trực tiếp nhất, mảng Zalo Mini App

| Dimension | CNV | AdtimaBox |
|-----------|-----|-----------|
| **Positioning** | "Marketing Automation Zalo #1 VN" — SaaS ready-to-use | Customized CRM/Loyalty — enterprise-grade, native Zalo |
| **Target segment** | SME đến mid-market (3,000+ clients) | Mid-market đến enterprise MNC |
| **Pricing** | Mini App: 10.8M/năm (Starter) – 30M/năm (Pro); Combo CDP: 20.4–28.8M/năm | 20M–297M/package (6–12 tháng) |
| **Deploy model** | SaaS template-based, nhanh | Customized per client, lead time lâu hơn |
| **Industries** | Retail, F&B, Spa, Healthcare, Auto, Education, Manufacturing | FMCG, Pharma, Finance, Auto, E-commerce, Travel |
| **Zalo DMP / Auto EDA** | ❌ Không | ✅ Độc quyền AdtimaBox |
| **Media / Content solutions** | ❌ Không | ✅ Full Adtima portfolio (Ads, Audio, Content, Sticker) |
| **Data security** | Chưa công bố ISO 27001 | ✅ ISO 27001, data lưu tại VN |

**Khi client so sánh CNV vs AdtimaBox — response direction:**
- *Price gap (CNV rẻ hơn 5–10x)*: Reframe từ tool-so-tool sang total ecosystem. CNV = tool đơn lẻ cho SME. AdtimaBox = native Zalo + media + CRM + Auto EDA trong một hệ sinh thái.
- *"CNV đủ feature rồi"*: Hỏi lại: có Auto EDA Zalo DMP không? Chạy Zalo Ads + content + loyalty trong cùng ecosystem không? ISO 27001 chưa?
- *Proof*: Coca-Cola, Red Bull, Nestlé chọn AdtimaBox — những brand này không chọn CNV.

---

### PangoCDP (pangocdp.com) — Đối thủ CDP tier cao

| Dimension | PangoCDP | AdtimaBox |
|-----------|----------|-----------|
| **Positioning** | "AI-powered CDP — From Data Foundation to AI-Driven Business Results" | Customized CRM/Loyalty on Zalo — O2O + full-funnel |
| **Target segment** | Enterprise FMCG & Retail (170+ clients) | FMCG, Pharma, Finance, Auto (100+ brands) |
| **Key clients** | Nutifood, Unilever, AB InBev (Vua Bia), CellphoneS, TBS Retail | Coca-Cola, Red Bull, Nestlé, P&G, Unilever, GSK... |
| **Platform scope** | Multi-channel CDP (không Zalo-exclusive) | Native Zalo Mini App + Zalo OA ecosystem |
| **AI / Data** | AI-powered; Nutifood: 65 segments, 55 auto flows | Auto EDA với Zalo DMP (độc quyền) |
| **Zalo native depth** | ❓ Partial (có Zalo integration, không native) | ✅ Native — team am hiểu Zalo user behavior |
| **Media / Content** | ❌ Không | ✅ Full Adtima media portfolio |
| **O2O bridge** | ✅ Mạnh (O2O data linking) | ✅ UTC, Scan Bill, QR POSM |

**Khi client so sánh PangoCDP vs AdtimaBox — response direction:**
- *"Pango có Nutifood, Unilever"*: Adtima cũng có Nutifood (ZNews Content) và Unilever (Surf Sticker, Surf Music) — không loại trừ nhau, có brand dùng song song.
- *Positioning khác nhau*: Pango = multi-channel CDP (breadth). AdtimaBox = Zalo-native depth + media ecosystem. Nếu brand muốn maximize Zalo → AdtimaBox. Nếu muốn unify tất cả kênh → Pango.
- *"Pango có AI"*: Counter với Auto EDA + Zalo DMP: insight từ 75M Zalo users mà Pango không có access.

---

### Competitive Summary (template cho `competitive_snapshot` trong JSON)

```
Thị trường giải pháp CRM/Loyalty Zalo VN có 3 tier rõ ràng:
CNV (SME SaaS, 10–30M/năm), PangoCDP (enterprise multi-channel CDP),
và AdtimaBox (native Zalo enterprise, full-funnel Ads+CRM+Content+Auto EDA).
Ba sản phẩm phục vụ segment khác nhau — không cùng tier để so sánh trực tiếp.
```

---

## Phase 3 — Customer Strategy

> Competency 3: Map customer behavior and lifecycle.

**Customer Journey:** Unknown User → Prospect → Lead → Customer → Loyal Customer → Advocate

For each stage identify: Trigger, Touchpoint, Data captured, Zalo role.

**Persona Framework (1–2 personas):**
- Demographics: Age, location, income tier
- Behavioral cues: Purchase frequency, channel preference, digital maturity
- Pain points: Top 2–3 frustrations relevant to the brief
- Motivation: What drives action/conversion
- Zalo behavior: OA follower / Mini App user / ZNS responsive

---

## Phase 4 — Business Economics

> Competency 4: Quantify business value to justify solution investment.

| Metric | Formula | Why It Matters |
|--------|---------|----------------|
| CLV | Avg order × frequency × lifespan | Justifies loyalty investment |
| CAC | Marketing spend ÷ new customers | Baseline to compare retention ROI |
| Churn Cost | Lost customers × CLV | Makes retention urgency tangible |
| Retention ROI | Revenue gain from +X% retention | Anchor for solution pricing |

If exact data unavailable, use directional estimates labeled `[ESTIMATED — requires client data validation]`.

---

## Phase 5 — Data Strategy

> Competency 5: Transform marketing activities into long-term data assets.

Answer for every recommendation:
1. What customer data will this collect?
2. Why does the client need this data?
3. How will this data be activated later?

First-Party Data Priority Stack (Zalo ecosystem):
- Tier 1 Identity: Phone (OA follow / Mini App login)
- Tier 2 Behavior: Clicks, page views, purchase events (Mini App)
- Tier 3 Preference: Survey, quiz, form completion (ZNS / Mini App)
- Tier 4 Transaction: Purchase history, redemption, loyalty points
- Tier 5 Health/HCP: ⚠️ Pharma only — requires compliance review

---

## Phase 6 — Solution Mapping

> Competency 6: Connect business problem → Zalo solution architecture.

Framework: Business Problem → Business Capability → Process Design → Zalo Solution

| Business Problem | Capability Needed | Zalo Solution |
|-----------------|------------------|---------------|
| Low repeat purchase | CRM + Loyalty | Mini App loyalty + ZNS re-engagement |
| No owned customer data | CDP + Data collection | OA + Mini App registration flow |
| Low HCP engagement | Event + Education platform | HCP Mini App + ZNS reminders |
| High CAC, low retention | Automated nurturing | OA broadcast + ZNS drip sequence |
| Low brand awareness (mass) | Mass reach + community | Multi-screen Ads (Zalo Feeds, ZNews, Báo Mới) |
| Weak patient adherence | Reminder + support | ZNS appointment + OA education |
| Need content authority/trust | Expert content partnership | ZNews PR + Content Partnership |
| Audio branding / music moment | Screen-less reach | Zing MP3 Audio Ads + Audio Plus |
| Youth/Gen Z conversation reach | Native conversation | Zalo Sticker + Zalo Ads |
| O2O digital engagement | Offline-to-Online bridge | UTC on-pack / Scan Bill / QR POSM |
| Lead generation (performance) | CPL digital acquisition | Zalo Lead Form Ads |
| Purchase frequency | Behavior change loop | CShub Pro 1 + UTC Campaign |
| Event/festival awareness | Content amplification | Zcast + Z Studio (YouTube/TikTok) |
| Audience insight / measurement | Research + Analytics | Adtima Audience Pulse (AAP) |

Solution Architecture:
- Phase 1 Quick Win [30–60 days]: Immediate activation, low complexity
- Phase 2 Foundation [60–180 days]: Core infrastructure build
- Phase 3 Scale [180+ days]: Data activation, personalization, optimization

---

## Phase 7 — Case Study Matching

> **DELEGATE to `adtimabox-case-studies` skill — do not run this phase independently.**

Pass the following context to `adtimabox-case-studies`:
- `b2b_or_b2c` (from Phase 2 industry classification)
- `channel` (from Phase 1/3 client context)
- `primary_objective` (from Phase 1 problem statement)
- `industry` (from Phase 2)

The `adtimabox-case-studies` skill returns:
- `alias` — matched case ID (e.g. CS-07)
- `rationale` — why this case matches
- `proof_point` — key result or mechanic to use in pitch
- `recommended_package` — CShub tier + Campaign add-ons

Populate the `case_studies` array in JSON output with the returned value.
If `adtimabox-case-studies` returns no match, set `"alias": "no_match"` with a note.

---

## Output Format

Return a single JSON object. This is machine-readable output for other agents — completeness and valid JSON are required.

```json
{
  "skill": "strategy-skill",
  "status": "complete | partial | blocked",
  "confidence_notes": "List any [ESTIMATED] or [PENDING] items here",

  "problem_statement": "string",
  "gap_analysis": {
    "current_state": "string",
    "desired_state": "string",
    "gap": "string"
  },

  "industry_context": {
    "industry": "FMCG | Pharma | Finance | Retail | Other",
    "b2b_or_b2c": "B2B | B2C | B2B2C",
    "key_metrics": ["string"],
    "market_summary": "string",
    "competitive_snapshot": "string",
    "strategic_opportunities": ["string"],
    "research_sources": [
      { "claim": "string", "status": "confirmed | unconfirmed | not_found", "source": "string" }
    ]
  },

  "customer_strategy": {
    "journey": [
      { "stage": "string", "trigger": "string", "touchpoint": "string", "data_captured": "string", "zalo_role": "string" }
    ],
    "personas": [
      {
        "name": "string",
        "demographics": "string",
        "behavioral_cues": "string",
        "pain_points": ["string"],
        "motivation": "string",
        "zalo_behavior": "string"
      }
    ]
  },

  "business_economics": {
    "clv_estimate": "string",
    "cac_benchmark": "string",
    "churn_cost": "string",
    "retention_roi": "string"
  },

  "data_strategy": {
    "data_to_collect": ["string"],
    "why": "string",
    "activation_plan": "string",
    "compliance_required": true
  },

  "solution_recommendation": {
    "phase_1_quick_win": "string",
    "phase_2_foundation": "string",
    "phase_3_scale": "string",
    "zalo_products": ["string"]
  },

  "case_studies": [
    {
      "alias": "CS-XX",
      "rationale": "string",
      "proof_point": "string",
      "recommended_package": "string"
    }
  ],

  "compliance_flags": ["string"]
}
```

**Status rules:**
- `complete` — all phases done, no blocking issues
- `partial` — output usable but has [ESTIMATED] or [PENDING] items
- `blocked` — missing critical brief information; list what is needed in `confidence_notes`

---

## Quality Checklist

Before returning output:

- [ ] Problem statement reframes brief — not a copy of the stated requirement
- [ ] Industry and B2B/B2C correctly classified
- [ ] Pharma brief has compliance_flags populated and compliance_required = true
- [ ] All research sources labeled confirmed / unconfirmed / not_found
- [ ] Solution maps to Zalo products — not generic marketing tools
- [ ] case_studies array populated from adtimabox-case-studies delegation, or set to no_match
- [ ] Business economics has at least directional estimates
- [ ] Data strategy answers all 3 questions (collect / why / activate)
- [ ] Output is valid JSON

---

## Constraints

On Pharma briefs: Never recommend patient data collection or HCP communication
strategies without setting compliance_required to true and populating compliance_flags.
Mark solution sections as "[PENDING compliance clearance]" where applicable.

On confidence: Output [ESTIMATED] or [PENDING] rather than fabricating data.
Other agents are designed to handle partial inputs.

On CS-06: Internal reference only — do not surface this case study in any
client-facing output.
