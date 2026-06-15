---
name: platform-kiotviet
description: >
  KiotViet platform knowledge for AdtimaBox integration assessment — activate when a client is using KiotViet and the agent needs to understand what KiotViet already does, where it overlaps with AdtimaBox, and what AdtimaBox adds. Source: official KiotViet documentation (kiotviet.vn), researched June 2025.
---

# KiotViet × AdtimaBox

*Source: kiotviet.vn, developers.zalo.me. Researched June 2025.*

---

## WHAT KIOTVIET HAS

**Core platform:**
- POS + inventory management for small/medium retail, F&B, pharmacy
- Customer profile management (linked by phone number)
- Open API available (Thiết lập kết nối API in settings) — can push customer, order, invoice data

**Zalo ZNS integration:**
- Sends transaction ZNS: order confirmation, purchase confirmation, return confirmation
- Requires Zalo OA connection
- Has API/webhook support for custom ZNS triggers

**Loyalty:**
- No native loyalty module — basic point tracking only
- 3rd party loyalty plugins available (e.g. WeLoyalty) but limited capability
- No tier management, no reward catalog, no automation

---

## WHAT ADTIMABOX ADDS

- **Zalo MiniApp** branded experience — KiotViet has none
- Full loyalty program (earn/burn/tier/reward catalog)
- Complex automation journeys on Zalo
- Content Hub, deep segmentation, Auto EDA/Zalo DMP
- Event Hub (Pro 2)

---

## OVERLAP — MUST DEFINE BOUNDARY

**Messaging:**
KiotViet sends transaction ZNS. AdtimaBox sends loyalty/engagement ZNS. Define same boundary as Haravan.

→ Recommended split:
- KiotViet sends: order/purchase confirmation ZNS
- AdtimaBox sends: loyalty points, tier upgrade, engagement automation

**Member data:**
KiotViet captures phone number at POS → can sync to AdtimaBox via API for point earning.

---

## RECOMMENDED SETUP

```
KiotViet
  → manages POS + inventory
  → sends order/purchase ZNS

AdtimaBox
  → manages full loyalty + member CRM on Zalo
  → sends loyalty/engagement ZNS + automation
  → provides Zalo MiniApp experience

KiotViet API
  → pushes transaction data (phone + order value)
  → AdtimaBox credits loyalty points
```

---

## NEEDS TECH CONFIRMATION

- KiotViet API format compatibility with AdtimaBox inbound data integration
- Real-time vs batch sync — KiotViet typically supports batch
- Whether KiotViet captures phone number consistently at all store locations
