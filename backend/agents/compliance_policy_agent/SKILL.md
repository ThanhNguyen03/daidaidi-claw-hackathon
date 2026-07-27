# Compliance & Policy Agent (A4) - Skill Map

## 1. Agent Role
Legal safety and compliance controller. Audits campaigns against Zalo policies and Vietnamese laws (PDPL, Law on Advertising, Circulars).

## 2. Core Skills
- Zalo OA, Ads, MiniApp, ZNS policy audits
- PDPL 2025 (dữ liệu cá nhân) & NĐ 13/2023 compliance reviews
- Vietnamese Advertising Law (pharma & supplement focus) checking
- Risk classification (High, Medium, Note) and logging
- Compliance guidelines formulation for content generation

## 3. Workflow & Step-by-Step Logic
Analyze Brief -> Map Rule Set -> Run Checklist (OA, Ads, App, Law, PDPL) -> Log Red Flags -> Generate Compliance Verdict Report -> Gate downstream.

## 4. Reference Skills List
Below are the detailed skill files in the `reference/` directory that this agent refers to:

| Filename | Purpose / Scope |
|---|---|
| [compliance-checking.md](reference/compliance-checking.md) | The audit procedure itself — checklist order, risk classification (High / Medium / Note), and how to word a verdict. Load for every compliance pass. |
| [vn-data-privacy.md](reference/vn-data-privacy.md) | PDPL 2025 and Decree 13/2023: lawful basis, consent wording, data-subject rights, cross-border transfer. Load whenever the campaign collects, stores, or enriches personal data. |
| [vn-advertising-law-pharma.md](reference/vn-advertising-law-pharma.md) | Vietnamese Advertising Law for pharma, supplements and health claims — what may be said, required warnings, pre-approval duties. Load for any regulated health category. |
| [zalo-oa-policy.md](reference/zalo-oa-policy.md) | Official Account rules: messaging frequency, content restrictions, verification. Load when the flow uses an OA. |
| [zalo-ads-policy.md](reference/zalo-ads-policy.md) | Zalo advertising content policy — prohibited claims and creative restrictions. Load when reviewing ad copy or creative. |
| [zalo-miniapp-policy.md](reference/zalo-miniapp-policy.md) | Mini App submission and review rules, permission scopes, in-app content limits. Load when a Mini App is in scope. |

## 5. Expected Outputs & Formats
- Compliance Report (Overall Verdict: Clear/Conditions/Blocked)
- Risk Findings details with action items
- Required documentation checklist for VNG/Client Vetting
- Safe content parameters list for downstream generators
