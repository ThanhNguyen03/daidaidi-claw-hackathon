# Vietnamese Data Privacy Law Reference

Sources:
- **Luật Bảo vệ Dữ liệu Cá nhân — Luật số 91/2025/QH15 (PDPL)**
  Passed: 26/06/2025 | Effective: **01/01/2026**
- **Nghị định 13/2023/NĐ-CP**
  Effective: 01/07/2023 | Still in force; supplemented by PDPL 2025
- Luật An ninh mạng số 24/2018/QH14 (indirect — applies to data on Vietnamese networks)

> ⚠️ NOTE: The implementing decree (Nghị định hướng dẫn) for PDPL 2025 is still in
> draft as of June 2026. Flag as [VERIFY-POLICY] for any PDPL provisions where
> operational requirements remain unclear.

---

## 1. Applicability

Applies to **all organizations and individuals**, domestic and foreign, that:
- Process personal data of people in Vietnam
- Process personal data of Vietnamese citizens anywhere in the world

**Relevant to Adtima/Zalo campaigns when:**
- Mini App collects user data (name, phone, email, location, health info)
- OA Form or ZNS Form collects leads
- Campaign brief includes CRM integration, data enrichment, or remarketing
- Data is shared with the client's internal systems or third-party tools

---

## 2. Data Classification

### Basic Personal Data (Dữ liệu cá nhân cơ bản)
Full name, date of birth, address, phone number, email, IP address, cookies,
purchase history, behavioral data, etc.

### Sensitive Personal Data (Dữ liệu cá nhân nhạy cảm) — Stricter rules
- Political opinions, religious beliefs
- Health records, medical history, genetic data, biometric data
- Financial information, credit records
- Precise location / movement history
- Sexual orientation or gender identity
- Criminal records
- Data of children under 16

**Sensitive data requires: separate, explicit consent + higher security measures**

---

## 3. Lawful Bases for Processing

Under PDPL 2025, processing is lawful only if one of these applies:
1. **Explicit consent** of the data subject
2. **Legal obligation** — required by law
3. **Vital interests** — protect life in emergency
4. **Legitimate interest** — must be proportionate and not override subject's rights

For Adtima campaign use cases: **consent** is almost always the required basis.

---

## 4. Consent Requirements

Consent must be:
- **Freely given** — no coercion, not bundled with service access
- **Specific** — for a defined, stated purpose
- **Informed** — data subject understands what they are consenting to
- **Unambiguous** — clear opt-in action (pre-ticked boxes are invalid)
- **Withdrawable** — user can withdraw at any time, as easily as they gave it

### Blanket Consent = INVALID
A single "I agree to all terms" checkbox covering multiple unrelated processing
purposes is not valid consent under PDPL 2025.

### What must be disclosed before collection
1. Identity and contact of the data controller
2. Purpose of processing
3. Types of data to be collected
4. Recipients of the data (if shared with third parties)
5. Retention period
6. User's rights and how to exercise them

---

## 5. Rights of Data Subjects (11 Rights under PDPL 2025)

| Right | Obligation on processor |
|---|---|
| Right to know | Disclose processing activities upon request |
| Right to consent | Must obtain consent before processing |
| Right to access | Provide copy of data held within defined timeframe |
| Right to correct | Update inaccurate data promptly |
| Right to delete | Delete data when no longer needed or upon request |
| Right to restrict | Pause processing when subject objects |
| Right to data portability | Provide data in machine-readable format |
| Right to object | Stop processing for direct marketing on objection |
| Right to withdraw consent | At any time; withdrawal must not penalize the user |
| Right to complain | Escalation path to A86 (Ministry of Public Security) |
| Rights of children | Special rules for data of children under 16 |

---

## 6. Cross-Border Data Transfer

Under PDPL 2025 (stricter than NĐ 13/2023):
- Data transfer outside Vietnam requires:
  1. Recipient country has adequate data protection (assessed by A86), OR
  2. Standard contractual clauses (SCC) approved by A86, OR
  3. Explicit consent of the data subject covering cross-border transfer
- Organizations must **notify A86** before transferring sensitive data abroad
- Violation: fine up to **3 billion VND** or **5% of prior year Vietnam revenue**

**Relevance for Zalo campaigns:** If client uses foreign ad tech (DMPs, CDPs, cloud
CRMs with servers outside Vietnam), cross-border transfer rules apply.

---

## 7. Key Differences: NĐ 13/2023 vs PDPL 2025

| | NĐ 13/2023 | PDPL 2025 |
|---|---|---|
| Legal status | Decree | **Law** (higher authority) |
| Effective | 01/07/2023 | **01/01/2026** |
| Sale of personal data | Not explicitly prohibited | **Prohibited** |
| Max fine | Not specified clearly | 3 billion VND / 5% revenue |
| DPO requirement | Not required | May be required (pending decree) |
| Cross-border transfer | Notification to A86 | Stricter approval process |
| Children's data | Under 16 = sensitive | Under 16 = special chapter |

---

## 8. Compliance Checklist for Campaigns Collecting Data

- [ ] Consent notice displayed before any data field appears
- [ ] Separate consent for sensitive data (health, location, financial)
- [ ] No pre-ticked boxes; active opt-in required
- [ ] Purpose of collection stated in plain language
- [ ] Third-party recipients listed if data is shared with client CRM/DMP
- [ ] Retention period stated or linked to privacy policy
- [ ] User can access, correct, or delete their data (contact provided)
- [ ] For cross-border transfer: appropriate safeguard in place
- [ ] Children under 16: parental consent required; do not use for targeting

---

## 9. Penalties Summary

| Violation | Fine |
|---|---|
| Processing without consent | Up to 3 billion VND |
| Selling personal data | Criminal prosecution possible |
| Cross-border transfer without safeguard | Up to 3 billion VND / 5% revenue |
| Failure to notify data breach | Administrative fine + civil liability |
| Violating children's data rules | Aggravated penalty |
