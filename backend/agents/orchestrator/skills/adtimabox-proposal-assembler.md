---
name: adtimabox-proposal-assembler
description: >
  AdtimaBox proposal assembler — final synthesis node in the proposal generation pipeline.
  Activated by the orchestrator after all parallel nodes complete: requirement elicitor,
  case studies, domain knowledge / strategy, integration (if applicable), solution designer,
  compliance, and pricing advisor. Takes structured outputs from all upstream skills and
  renders a complete, client-ready proposal document in Vietnamese or English.
  Output: executive summary, business problem, solution flow, case proof, compliance status,
  investment summary, integration notes (if applicable), and next steps.
  Triggers: orchestrator signals "all upstream nodes complete", "assemble proposal",
  "generate final proposal", "compile outputs".
  Does NOT re-run any upstream skill — assembles only what it receives.
---

# AdtimaBox Proposal Assembler

**Scope:** Synthesize all upstream skill outputs into one cohesive client proposal document.

**Position in pipeline:**
```
[requirement-elicitor] ──┐
[case-studies]           ├──► [proposal-assembler] → PROPOSAL OUTPUT
[strategy-skill]         │
[integration] (opt.)     │
[solution-designer]      │
[compliance]             │
[product-advisor]        ┘
```

**Language rule:** Match the language of the original client brief.
Vietnamese brief → proposal in Vietnamese. English brief → English. Mixed → Vietnamese.

---

## INPUTS EXPECTED

The orchestrator passes the following into this skill. All fields are required unless marked optional.

| Source skill | Key content passed |
|---|---|
| `adtimabox-requirement-elicitor` | CLIENT REQUIREMENT SUMMARY (AS-IS, objective, audience, mechanics, constraints, preliminary scope) |
| `adtimabox-case-studies` | Matched case alias, rationale, proof point, recommended package |
| `strategy-skill` | problem_statement, gap_analysis, industry_context, customer_strategy, business_economics, solution_recommendation |
| `adtimabox-solution-designer` | SOLUTION FLOW (package, campaign add-ons, custom items, journey steps, Mermaid diagram) |
| `zalo-compliance-legal` | A4 COMPLIANCE REPORT (overall verdict, findings, compliance conditions, docs required) |
| `adtimabox-product-advisor` | Pricing breakdown (CShub package + price, campaign add-ons + price, total estimate) |
| `adtimabox-integration` *(optional)* | Platform assessment, recommended integration pattern, tech confirmation items |

**If any input is missing or marked BLOCKED:**
- Missing upstream output → note the gap in the relevant section, do not fabricate content
- Compliance verdict is ❌ BLOCKED → stop after Section 5, output a BLOCKED notice, do not render pricing or next steps

---

## OUTPUT FORMAT

Render the proposal as a structured document. Use the section template below exactly.
Keep each section concise — this is a pitch document, not a report.

---

```
╔══════════════════════════════════════════════════════════════╗
║  ADTIMABOX PROPOSAL                                          ║
║  Client: [Brand name]          Date: [YYYY-MM-DD]            ║
║  Industry: [Industry]          Track: [B2B | B2C | B2B2C]   ║
╚══════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 1 — EXECUTIVE SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[2–3 sentences: client's core pain, recommended solution, expected outcome.
Write for a CMO or Marketing Director — strategic framing, no jargon.]

Recommended solution: [CShub package] + [Campaign add-ons if any]
Total investment estimate: [X]M VND (excl. VAT 8%)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 2 — BUSINESS PROBLEM
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Current state: [AS-IS from requirement elicitor — what the brand has today]
Core pain: [Reframed problem statement from strategy skill — 1 sentence]
Desired outcome: [TO-BE from requirement elicitor — what success looks like]
Gap: [What's missing between now and the desired state]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 3 — RECOMMENDED SOLUTION FLOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Package: [CShub package name and period]
Campaign add-ons: [list, or "None"]
Custom items requiring tech confirmation: [list, or "None"]

JOURNEY:
[Copy the JOURNEY block from solution-designer output verbatim — one step per line with arrows]

MESSAGING TOUCHPOINTS:
[Copy the messaging map from solution-designer: trigger → message type]

[If Mermaid diagram is available from solution-designer, include it here:]
```mermaid
[paste diagram]
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 4 — CASE PROOF
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[For each matched case study — max 2:]

CASE [alias]:
Why relevant: [rationale from case-studies skill]
What they did: [1–2 sentences on solution]
Key result: [proof point]
Applicable to [client name] because: [1 sentence connection]

[If no case study matched: "No direct case match — this is a new pattern for AdtimaBox.
Recommend presenting as a first-mover opportunity."]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 5 — COMPLIANCE STATUS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Overall verdict: [✅ CLEAR TO PROCEED | ⚠️ PROCEED WITH CONDITIONS | ❌ BLOCKED]

[If CLEAR: "No compliance blockers identified. Standard Zalo policy and data privacy
requirements apply — see onboarding consent flow in Section 3."]

[If PROCEED WITH CONDITIONS:]
Conditions that must be met before campaign launch:
- [condition 1 from compliance report]
- [condition 2]
Documents client must provide:
- [document list from compliance report]

[If BLOCKED:]
⛔ THIS PROPOSAL IS ON HOLD — COMPLIANCE BLOCKER IDENTIFIED
Issue: [HIGH finding from compliance report]
Required action: [what must be resolved]
→ Sections 6 and 7 are not rendered until this blocker is resolved.
[STOP — do not render Sections 6 or 7 if BLOCKED]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 6 — INVESTMENT SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Only render if compliance verdict is CLEAR or PROCEED WITH CONDITIONS]

CShub subscription:
  [Package name] × [period]     [X]M VND

Campaign instant add-ons:
  [Item 1]                       [X]M VND
  [Item 2]                       [X]M VND

CShub add-ons (if any):
  [Item]                         [X]M VND

──────────────────────────────────────────
  Subtotal (excl. VAT)           [X]M VND
  VAT 8%                         [X]M VND
  TOTAL                          [X]M VND
──────────────────────────────────────────

Notes:
- Campaign instant prices excl. Agency fee
- [Any pricing caveat from product-advisor — e.g. OCR per-scan cost for high volume]
- [Storage overage risk if database > 10K rows]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 7 — NEXT STEPS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Only render if compliance verdict is CLEAR or PROCEED WITH CONDITIONS]

KEY DECISIONS FOR CLIENT:
- [Decision 1 from solution-designer — e.g. migrate vs sync existing loyalty]
- [Decision 2 — e.g. UTC vs Scan Bill as offline earn mechanic]

ITEMS REQUIRING TECH CONFIRMATION (before signing):
- [Custom flow item 1 from solution-designer]
- [Integration feasibility item from integration skill, if applicable]

DOCUMENTS TO REQUEST FROM CLIENT:
- [Document list from compliance report — e.g. Cục ATTP certificate]
- [If no compliance docs needed: "No additional regulatory documentation required"]

SUGGESTED TIMELINE:
  Week 1–2: Contract + OA verification + ZNS template submission
  Week 3–4: Platform setup + onboarding flow configuration
  Week 5–6: UAT + soft launch
  Week 7+:  Full launch + first campaign activation

══════════════════════════════════════════════════════════════
Prepared by AdtimaBox | [Date]
This proposal is confidential. Package prices excl. VAT 8%.
Prices valid for 30 days from proposal date.
══════════════════════════════════════════════════════════════
```

---

## ASSEMBLY RULES

**Rule 1 — Compliance gates everything after Section 5.**
If compliance verdict is BLOCKED, output Sections 1–5 only and add a visible stop notice.
Do not render investment or next steps for a blocked proposal.

**Rule 2 — Never fabricate numbers.**
If pricing advisor did not return a specific line item, write `[to be confirmed with product advisor]`
rather than estimating. Wrong numbers in a proposal are worse than missing numbers.

**Rule 3 — Case proof must be honest about source.**
Cases from `adtimabox-case-studies` (CS-01 to CS-11) are Adtima's own cases — cite them directly.
Any market evidence referenced elsewhere (MerapLion, FPT Long Châu, etc.) must be labeled
"market precedent" or "industry evidence", never presented as an Adtima result.
CS-06 is internal reference only — never include in client-facing output.

**Rule 4 — Custom items must be visible.**
Any item flagged as "needs tech confirmation" or "custom flow" in the solution designer output
must appear in Section 7. Never bury these in body text.

**Rule 5 — Language consistency.**
Do not mix Vietnamese and English within sections. If the proposal is in Vietnamese,
all section headers, field labels, and body text must be in Vietnamese.
The Mermaid diagram node labels may remain in English if originally written that way.

---

## QUALITY CHECKLIST

Before outputting the proposal, verify:

- [ ] All 7 sections present (or Section 6/7 correctly blocked by compliance)
- [ ] Executive summary has a total investment number
- [ ] Journey steps copied verbatim from solution-designer — not paraphrased
- [ ] Case proof does not claim CS-06 or any non-Adtima case as Adtima's own
- [ ] Compliance verdict matches the A4 report word-for-word (CLEAR / CONDITIONS / BLOCKED)
- [ ] Investment table adds up correctly; VAT 8% applied
- [ ] Custom items and tech-confirmation items in Section 7 — none hidden
- [ ] Language consistent throughout
- [ ] No placeholder text left (no "[TBD]", "[to be filled]", lorem ipsum)
