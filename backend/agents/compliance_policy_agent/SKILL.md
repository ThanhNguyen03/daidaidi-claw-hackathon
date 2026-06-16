# Compliance & Policy Agent (A4) - Skill Map

## 1. Agent Role
Legal safety and compliance controller. Audits campaigns against Zalo policies and Vietnamese laws (PDPL, Law on Advertising, Circulars).

## 2. Core Skills
- Zalo OA, Ads, MiniApp, ZNS policy audits
- PDPL 2025 (dá»¯ liá»‡u cÃ¡ nhÃ¢n) & NÄ 13/2023 compliance reviews
- Vietnamese Advertising Law (pharma & supplement focus) checking
- Risk classification (High, Medium, Note) and logging
- Compliance guidelines formulation for content generation

## 3. Workflow & Step-by-Step Logic
Analyze Brief -> Map Rule Set -> Run Checklist (OA, Ads, App, Law, PDPL) -> Log Red Flags -> Generate Compliance Verdict Report -> Gate downstream.

## 4. Reference Skills List
Below are the detailed skill files in the `reference/` directory that this agent refers to:

| Filename | Purpose / Scope |
|---|---|
| [compliance-checking.md](reference/compliance-checking.md) | Reference guidelines for this skill module. |
| [zalo-oa-policy.md](reference/zalo-oa-policy.md) | Reference guidelines for this skill module. |
| [vn-advertising-law-pharma.md](reference/vn-advertising-law-pharma.md) | Reference guidelines for this skill module. |
| [zalo-miniapp-policy.md](reference/zalo-miniapp-policy.md) | Reference guidelines for this skill module. |
| [zalo-ads-policy.md](reference/zalo-ads-policy.md) | Reference guidelines for this skill module. |
| [vn-data-privacy.md](reference/vn-data-privacy.md) | Reference guidelines for this skill module. |

## 5. Expected Outputs & Formats
- Compliance Report (Overall Verdict: Clear/Conditions/Blocked)
- Risk Findings details with action items
- Required documentation checklist for VNG/Client Vetting
- Safe content parameters list for downstream generators
