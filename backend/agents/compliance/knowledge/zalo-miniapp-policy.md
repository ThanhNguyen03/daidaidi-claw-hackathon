# Zalo Mini App Policy Reference

Source: developers.zalo.me (official) — Last verified: June 2026

---

## 1. Prerequisites

- Mini App **must be linked to a verified (xác thực) OA**
- Developer account must be registered at developers.zalo.me
- App passes **two-tier review**: technical review + content/policy review
- Review timeline: 2–5 business days (standard); up to 10 days for health/finance/education

---

## 2. Content Rules

### Prohibited
- False or misleading information about the app's functionality
- Impersonation of other brands, government bodies, or Zalo itself
- Content that violates any Zalo OA content policy (see `zalo-oa-policy.md`)
- Hidden functionality not disclosed at review time
- Content targeting minors without appropriate safeguards

### Required
- App description must accurately reflect actual functionality
- Privacy policy URL must be linked at the onboarding screen
- App must only request permissions necessary for its stated function

---

## 3. Data Permissions — Over-Permissioning is a Violation

Common over-permissioning failures to flag:

| Permission Requested | Only allowed if... |
|---|---|
| Phone number | Core to the service (e.g., loyalty registration, OTP) |
| Location | App function explicitly requires location (e.g., store finder) |
| Camera / media | App has a scan, upload, or photo feature |
| Contacts | App has a social/referral feature with explicit consent |
| Health data | Medical/wellness app with separate sensitive data consent |

**Red flag:** A promotional campaign Mini App requesting phone + location + camera
with no functional justification = likely 🔴 HIGH compliance issue.

---

## 4. Sector-Specific Requirements

| Industry | Additional Requirements |
|---|---|
| Healthcare / pharma | Must display medical disclaimer; no diagnosis features without medical license |
| Financial services | Must display SBV/SSC license number |
| Education | Degree programs must show Ministry of Education accreditation |
| E-commerce | Must comply with Luật Bảo vệ Người tiêu dùng 2023 |
| Government services | Must be officially commissioned by the government body |

---

## 5. Data Handling in Mini Apps

All Mini Apps that collect personal data must comply with PDPL 2025:
- Consent screen before first data collection
- Clear statement of what data is collected and why
- Option to withdraw consent and delete data
- See `vn-data-privacy.md` for full requirements
