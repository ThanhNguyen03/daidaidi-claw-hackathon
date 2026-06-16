---
name: platform-haravan
description: >
  Haravan platform knowledge for AdtimaBox integration assessment — activate when a client is using Haravan and the agent needs to understand what Haravan already does, where it overlaps with AdtimaBox, and what AdtimaBox adds. Source: official Haravan documentation (help.haravan.com, haravan.com), researched June 2025.
---

# Haravan × AdtimaBox

*Source: help.haravan.com, haravan.com/pages/haraloyalty. Researched June 2025.*

---

## WHAT HARAVAN HAS

**Core platform:**
- POS + order management + inventory + omnichannel e-commerce
- Customer profile management (linked by phone number)
- Harasocial: social commerce + chatbot on Zalo OA

**Haravan Loyalty** *(Scale plan, 3M VND/month+)*
- Points accumulation + tier membership
- Auto reward campaigns
- Broadcast campaigns via Zalo ZNS, Email, SMS, Messenger

**Zalo ZNS integration:**
- Sends transaction ZNS: order confirmation, delivery update, return, payment reminder
- Requires Zalo OA connection + approved ZNS template
- **Promotion Quota limit** (from Nov 2024): Zalo limits monthly promotional ZNS per OA based on prior 2-month transaction volume — `Quota = (transaction + care ZNS last 2 months) × 1/6`

---

## WHAT ADTIMABOX ADDS

- **Zalo MiniApp** branded experience — Haravan has no MiniApp capability
- **Auto EDA with Zalo DMP** — Haravan has no DMP access
- Deep segmentation by Zalo behavior (beyond purchase data)
- Complex automation journeys (welcome series, birthday, tier upgrade, re-engagement)
- Content Hub for brand articles/news on MiniApp
- Event Hub for offline/online events (Pro 2)
- Referral mechanic on Zalo

---

## OVERLAP — MUST DEFINE BOUNDARY

**Messaging:**
Both Haravan and AdtimaBox can send Zalo ZNS. Running both without coordination = user receives duplicate messages.

→ Recommended split:
- Haravan sends: order confirmation, delivery, return ZNS
- AdtimaBox sends: loyalty points credited, tier upgrade, engagement, automation journey

**Loyalty:**
Both have points + tier. Never run two loyalty programs without a clear user-facing logic.

→ Options:
1. **Migrate**: move all loyalty to AdtimaBox, retire Haravan Loyalty
2. **Sync**: Haravan records transactions → AdtimaBox manages loyalty — confirm data mapping with tech lead

---

## RECOMMENDED SETUP

```
Haravan
  → manages orders, inventory, POS
  → sends order/delivery ZNS

AdtimaBox
  → manages loyalty program + member CRM on Zalo
  → sends engagement/loyalty ZNS + automation
  → provides Zalo MiniApp experience

API bridge
  → Haravan pushes purchase transaction (phone + order value)
  → AdtimaBox credits points to member account
```

---

## NEEDS TECH CONFIRMATION

- Haravan API format + availability for pushing transaction data to AdtimaBox
- Whether Haravan Loyalty member data can be migrated to AdtimaBox
- ZNS template ownership — which OA owns which template type
- Promotion Quota impact — if Haravan already uses heavy ZNS volume, AdtimaBox ZNS quota may be affected
