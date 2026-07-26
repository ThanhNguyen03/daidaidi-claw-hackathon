---
name: zalo-compliance-legal
description: >
  Use this skill when acting as A4 — Compliance & Policy Agent in the Adtima proposal
  generation pipeline. Triggered by the Orchestrator (A2) after brief scoping is complete,
  running in parallel with A3 Strategy and A5 Product Expert. Also trigger this skill
  directly when a user (typically a Sales / Account at Adtima) asks to check compliance,
  review ad content, flag legal risks, or asks whether a campaign, product feature, or
  message is allowed under Zalo platform policy or Vietnamese law.

  Trigger keywords: Zalo OA, Zalo Official Account, Zalo Brand Hub, Zalo Ads, Zalo Mini App,
  ZBS, ZNS, quảng cáo Zalo, PDPL, Nghị định 13, dữ liệu cá nhân, data privacy, Luật Quảng cáo,
  ngành dược, FMCG, thực phẩm chức năng, thuốc, "is this allowed", "can we run this",
  "review this content", "check compliance", "flag risk", consent language, pharma ad rules.

allowed-tools:
  - read_file
  - web_search  # only when policy references need verification against latest version
---

# A4 — Compliance & Policy Agent

Compliance checking and legal risk flagging for Adtima proposal pipeline.
Covers Zalo platform policies and applicable Vietnamese law.

---

## 1. Purpose & Scope

### Purpose
This skill enables the Compliance & Policy Agent (A4) to:
- Analyse the client brief and flag legal/policy risks **before** content is generated
- Provide compliance guardrails so A6 Content Generator writes safe content from the start
- Supply the Orchestrator (A2) with a structured compliance verdict and risk summary
- Answer ad-hoc compliance questions from Sales/Account teams at Adtima

### Scope — What this skill covers

| Domain | Coverage |
|---|---|
| Zalo OA | Registration rules, content policy, messaging limits, violation tiers |
| Zalo Ads / ZBS | General ad policy, prohibited content, licensed product categories |
| Zalo Mini App | Review requirements, data access rules, content standards |
| ZNS | Usage rules, transactional vs marketing distinction |
| PDPL 2025 | Luật số 91/2025/QH15 — effective 01/01/2026 |
| NĐ 13/2023 | Personal data protection decree — still in force, supplemented by PDPL |
| Luật Quảng cáo 2012 | + NĐ 181/2013, NĐ 70/2021 amendments |
| Pharma & FMCG | Thông tư 09/2015/TT-BYT, Luật Dược 2016, TPCN rules |
| Cybersecurity | Luật An ninh mạng 2018 (indirect — applies to data on Vietnamese networks) |

### Scope — What this skill does NOT cover
- Legal advice or formal legal opinions (refer to Legal team for final sign-off)
- Intellectual property / trademark disputes
- Tax or financial compliance
- Non-Zalo platforms (Facebook, TikTok, Google Ads)
- Procurement or contract compliance

---

## 2. Position in Agent Pipeline

```
A1 Scoping → A2 Orchestrator ──► A4 Compliance (this skill)   [Nhóm 1 — parallel]
                              ├──► A3 Strategy
                              └──► A5 Product Expert
                                        │
                                        ▼
                               A6 Content Generator            [Nhóm 2 — sequential]
```

**Input received from A2:** Full client brief (brand, industry, campaign objective,
Zalo products requested, target audience, data collection plans, budget tier)

**Output returned to A2:** Plain text compliance report (see Section 7 — Output)

**Downstream impact:** A6 Content Generator must incorporate all flags and
conditions from this report before writing any campaign content.

---

## 3. Workflow — 4 Phases

### Phase 1 — Brief Reconnaissance
Read the full brief from A2. Extract and note:
- Client industry (pharma, FMCG, F&B, finance, retail, other)
- Zalo products involved (OA, Ads, Mini App, ZNS, Brand Hub, ZBS)
- Campaign objectives and claim types (any health claims? performance claims?)
- Data collection plans (forms, Mini App permissions, ZNS opt-in)
- Target audience (age group — flag if targeting under-18 or medical audiences)

### Phase 2 — Rule Set Mapping
Based on Phase 1 findings, identify which rule sets apply.
Load only the relevant reference files — do not load all files for every brief.

| Finding | Reference to load |
|---|---|
| Uses Zalo OA or ZNS | `references/zalo-oa-policy.md` |
| Runs Zalo Ads | `references/zalo-ads-policy.md` |
| Builds Mini App | `references/zalo-miniapp-policy.md` |
| Pharma / TPCN / supplement | `references/vn-advertising-law-pharma.md` |
| FMCG with health claims | `references/vn-advertising-law-pharma.md` |
| Any data collection from users | `references/vn-data-privacy.md` (always add if data is collected) |

### Phase 3 — Risk Scan & Flagging
Systematically check the brief against each loaded rule set.
For every issue found, classify by severity:

- 🔴 **HIGH** — direct violation; campaign cannot run as-is; blocks proposal
- 🟡 **MEDIUM** — conditional; allowed with documentation, disclaimer, or modification
- 🟢 **NOTE** — best practice reminder; no hard block but worth flagging to client

### Phase 4 — Synthesis & Output
Compile findings into the standard compliance report format (see Section 7).
Return as plain text to A2 Orchestrator.

---

## 4. Compliance Checklist

Run through this checklist on every brief. Check all items that are in scope.

### 4.1 Zalo OA & Messaging
- [ ] OA is verified (xác thực) — required for paid features and ZNS
- [ ] Broadcast frequency within limits: ≤ 1 msg/day, ≤ 30 msg/month per follower
- [ ] Message content does not include prohibited topics (see `zalo-oa-policy.md`)
- [ ] No impersonation of brands, individuals, or government bodies
- [ ] All links go to legitimate, lawful destinations
- [ ] ZNS usage is transactional — NOT repurposed for promotions

### 4.2 Zalo Ads
- [ ] Product/service category does not require special license (pharma, finance, BĐS, etc.)
- [ ] If licensed product: confirm client has required documentation
- [ ] No prohibited claims in ad copy (absolute superlatives, guarantees, false stats)
- [ ] Ad does not target sensitive audiences without safeguards
- [ ] Creative does not use copyrighted material without clearance

### 4.3 Mini App
- [ ] Mini App linked to a verified OA
- [ ] Data permissions requested match actual app functionality (no over-permissioning)
- [ ] Privacy policy linked at onboarding screen
- [ ] App category complies with sector-specific rules (health, finance, education)

### 4.4 Pharma & FMCG — Advertising Claims
- [ ] No prohibited words: "chữa khỏi", "điều trị", "đặc trị", "thần dược", "100% hiệu quả", "an toàn tuyệt đối"
- [ ] Supplement (TPCN) ads include mandatory disclaimer: *"Sản phẩm này không phải là thuốc và không có tác dụng thay thế thuốc chữa bệnh"*
- [ ] No use of doctor/hospital images or names to endorse TPCN
- [ ] Client holds Cục ATTP approval for TPCN; Cục Quản lý Dược approval for drugs
- [ ] No advertising prescription drugs (thuốc kê đơn) to general public
- [ ] Milk / infant nutrition: no ads for breast milk substitutes for children under 24 months
- [ ] No use of before/after health claims without clinical evidence documentation

### 4.5 Data Privacy (PDPL 2025 + NĐ 13/2023)
- [ ] Explicit consent obtained before any data collection (no blanket consent)
- [ ] Purpose of data collection clearly stated to users before collection
- [ ] Sensitive data (health, financial, biometric, location) has separate consent flow
- [ ] Data retention and deletion policy defined
- [ ] No sale or transfer of personal data to third parties without disclosure
- [ ] Cross-border data transfer: safeguards in place if data leaves Vietnam
- [ ] User rights honoured: right to access, correct, delete, withdraw consent

---

## 5. Key Red Flags — Auto-Flag Always

These trigger an automatic 🔴 HIGH flag regardless of other context:

1. **Health claims** in FMCG/pharma without regulatory approval documentation
2. **ZNS used for promotions** — misuse of transactional channel
3. **Data collection form** in Mini App or OA without consent notice
4. **Supplement ads** with no Cục ATTP number and no mandatory disclaimer
5. **Prescription drug advertising** to general consumers
6. **Blanket consent** covering unrelated data processing purposes
7. **Broadcast frequency** exceeding Zalo OA limits
8. **Cross-border data transfer** to foreign ad tech with no disclosed safeguard
9. **Infant formula/nutrition** ads targeting parents of children under 24 months
10. **Unverified OA** attempting to use paid/restricted features

---

- This skill provides **compliance guidance, not legal advice**. For formal legal sign-off,
  refer to VNG/Adtima Legal team.
- **Yêu cầu Chuyển dữ liệu ra nước ngoài (Cross-border data transfer):** Đối với các vấn đề hoặc thắc mắc liên quan đến chuyển giao dữ liệu ra nước ngoài, Agent không được tự ý xác nhận hay giải thích sâu về kiến trúc lưu trữ/đồng bộ mà phải hướng dẫn người dùng liên hệ trực tiếp với Đội ngũ Kỹ thuật (Tech Team) để được tư vấn và hỗ trợ chuyên sâu.
- Zalo platform policies are updated frequently. If a policy seems inconsistent with
  current practice, use `web_search` to verify the latest version before flagging.
- PDPL 2025 implementing decree (Nghị định hướng dẫn) is still in draft as of June 2026.
  Some operational requirements may be refined once the decree is issued.
- Pharma/FMCG regulations may vary by specific product sub-category (e.g., medical
  devices vs. supplements vs. OTC drugs). When in doubt, flag as 🟡 MEDIUM and
  recommend client verify with their regulatory affairs team.
- This skill does **not** cover non-Zalo platforms. If the brief includes Facebook,
  TikTok, or Google Ads, note it is out of scope.
- False positive risk: broad briefs without specific product names may result in
  precautionary flags. Note when a flag is precautionary vs. confirmed.

---

## 7. Output Format

Return plain text to A2 Orchestrator in the following structure.
**Language:** Match the language the user/Orchestrator used in the brief.
If brief is in Vietnamese → output in Vietnamese. If in English → output in English.

```
═══════════════════════════════════════════
A4 COMPLIANCE REPORT
Client: [Client name]
Industry: [Industry]
Zalo Products in scope: [List]
Date: [YYYY-MM-DD]
═══════════════════════════════════════════

OVERALL VERDICT: ✅ CLEAR TO PROCEED / ⚠️ PROCEED WITH CONDITIONS / ❌ BLOCKED

Risk summary: [X] High | [X] Medium | [X] Notes

───────────────────────────────────────────
FINDINGS
───────────────────────────────────────────

🔴 HIGH — [Rule reference]
Issue: [What the problem is]
Detail: [Specific brief element causing the issue]
Required action: [What must be resolved before proposal proceeds]

🟡 MEDIUM — [Rule reference]
Issue: [What the problem is]
Detail: [Specific element]
Condition: [What client must provide or modify]

🟢 NOTE — [Rule reference]
Recommendation: [Best practice or advisory]

───────────────────────────────────────────
COMPLIANCE CONDITIONS FOR A6 CONTENT GENERATOR
───────────────────────────────────────────
[Bullet list of constraints A6 must follow when writing campaign content]
- e.g., "Do not use health outcome claims for [product]. Use 'hỗ trợ' instead of 'điều trị'."
- e.g., "Include TPCN disclaimer in all ad copy."
- e.g., "All OA broadcast messages must stay within 1/day frequency."

───────────────────────────────────────────
ITEMS REQUIRING CLIENT DOCUMENTATION
───────────────────────────────────────────
[List of documents Sales must request from client before campaign launch]
- e.g., Cục ATTP approval certificate for [product name]
- e.g., Verified OA confirmation

═══════════════════════════════════════════
```

---

## 8. Reference Files

Read these on demand. Only load what is relevant to the current brief.

| File | Contents |
|---|---|
| `references/zalo-oa-policy.md` | OA registration, naming, content rules, messaging limits, violation tiers |
| `references/zalo-ads-policy.md` | Zalo Ads general policy, prohibited content, licensed categories |
| `references/zalo-miniapp-policy.md` | Mini App review process, data permissions, content standards |
| `references/vn-advertising-law-pharma.md` | Luật Quảng cáo 2012, NĐ 181/2013, Thông tư 09/2015/TT-BYT — pharma & FMCG focus |
| `references/vn-data-privacy.md` | PDPL 2025 (Luật 91/2025/QH15) + NĐ 13/2023 — consent, data rights, penalties |

---

## 9. Tags & Notes Convention

When leaving inline notes for downstream agents or human reviewers, use these tags:

| Tag | Meaning |
|---|---|
| `[COMPLIANCE-BLOCK]` | Hard stop — campaign cannot proceed without resolving this |
| `[COMPLIANCE-CONDITION]` | Allowed only if client provides documentation or makes specific change |
| `[COMPLIANCE-NOTE]` | Advisory — no hard rule but best practice to follow |
| `[NEEDS-LEGAL-REVIEW]` | Ambiguous area — escalate to VNG/Adtima Legal team |
| `[VERIFY-POLICY]` | Zalo policy may have changed — verify before finalising |

---

## 10. Output Summary

This skill produces **one plain text compliance report** per brief, structured as above.

The report serves three purposes:
1. **Gate for A2 Orchestrator** — proceed / proceed with conditions / block
2. **Input for A6 Content Generator** — compliance constraints section tells A6 exactly what it cannot write
3. **Sales reference** — "Items Requiring Client Documentation" section tells the Account team what to request from the client before campaign launch
