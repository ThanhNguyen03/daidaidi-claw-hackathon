\---

name: adtimabox-domain-knowledge
description: >
AdtimaBox domain knowledge — activate when an agent needs to understand WHY a mechanic works a certain way, what the business logic is behind a module, or how a specific scenario plays out technically. Covers offline-to-online bridge mechanics, loyalty earn/burn logic, B2B vs B2C differences, messaging strategy, segmentation patterns, and module constraints. Input: a "how does X work" or "what happens when Y" question about AdtimaBox mechanics. Output: business logic explanation, constraints, and key considerations. Does NOT design user journeys (→ adtimabox-solution-designer), quote pricing (→ adtimabox-product-advisor), explain step-by-step user flows (→ adtimabox-miniapp-specialist), or gather requirements (→ adtimabox-requirement-elicitor).
---

# AdtimaBox Domain Knowledge

**Scope:** Explain HOW to solve specific business problems using AdtimaBox — solution patterns, module combinations, offline-to-online flows, and constraints.

**Structure:** Organized by business problem, not by module. Each pattern covers: the scenario, recommended solution, required modules/packages, flow, and critical constraints.

**Key rule:** Never confirm technical feasibility of custom flows — always flag for tech lead confirmation.

\---

## PATTERN 1: OFFLINE CUSTOMER ONBOARDING TO ZALO

**Scenario:** Brand has customers buying at physical stores but no digital CRM. Wants to bring them onto Zalo MiniApp and start building a relationship.

**The core challenge:** Customers are offline — they don't spontaneously open a MiniApp. Need a trigger or incentive at the point of purchase.

**Solution options by entry point:**

**Option A — QR code at store / product**

```
Customer at store
    → Sees QR code (on shelf, receipt, product packaging, PG tablet)
    → Scans with Zalo camera
    → Opens MiniApp → Onboarding form (name, phone, consent)
    → Receives instant reward (voucher, lucky spin, points)
    → Becomes member in AdtimaBox CRM
```

* Required: Any CShub package + QR generation (no extra cost)
* Best for: Stores with PG presence, branded packaging, or receipt QR

**Option B — PG-assisted onboarding**

```
PG at store approaches customer
    → Asks customer to scan QR from PG's device / tablet
    → Guides customer through MiniApp onboarding
    → Customer receives reward at counter
```

* Required: Any CShub package
* Note: Depends on PG behavior change — training required
* Works well when PG has incentive to enroll customers

**Option C — Media-driven (Zalo Ads / OA message)**

```
Customer sees Zalo Ad or OA message
    → Clicks → Opens MiniApp
    → Onboarding → Reward
```

* Required: Any CShub package + Zalo Ads budget (separate media spend)
* Best for: Brands with existing OA followers or running Zalo media campaigns

**Key constraints:**

* Zalo does NOT auto-collect user info — customer must actively consent and fill form
* Form should be 2–5 fields max to minimize drop rate (onboarding takes \~20 seconds)
* Customer must have Zalo installed — desktop users get a QR landing page instead
* First-time onboarding only: returning users auto-fill and go straight to content

\---

## PATTERN 2: OFFLINE PURCHASE → POINT ACCUMULATION

**Scenario:** Customer buys at a physical store (GT, MT, pharmacy, garage...). Brand wants that purchase to trigger loyalty points in AdtimaBox.

**The core challenge:** AdtimaBox doesn't automatically know about offline purchases — a bridge mechanism is needed.

**Solution options:**

**Option A — UTC on-pack code** *(most common for FMCG)*

```
Product has printed QR or unique code
    → Customer scans QR / enters code on MiniApp
    → System validates code → Credits points or issues reward
    → Code is single-use, anti-fraud protected
```

* Required: CShub Pro 1 (loyalty) + Campaign UTC 80M + UTC code generation (20M per batch)
* Best for: FMCG with packaged products (bottles, boxes, sachets)
* Constraint: Code must be activated in batches to prevent pre-market scanning

**Option B — Scan Bill** *(best for MT / pharmacy)*

```
Customer buys at supermarket / pharmacy
    → Takes photo of receipt
    → Uploads to MiniApp
    → OCR reads bill → validates purchase → credits points or reward
```

* Required: CShub Pro 1 (loyalty) + Campaign Scan Bill 80M + OCR training 1M/retailer
* Best for: Brands selling through MT channels (Coopmart, Winmart, pharmacy chains)
* Constraint: Each retailer's receipt format requires OCR training; manual review needed for edge cases

**Option C — POS API integration** *(most seamless but most complex)*

```
Customer pays at POS
    → POS records transaction with phone number
    → POS pushes data to AdtimaBox via API
    → AdtimaBox credits points automatically
```

* Required: CShub Pro 1 + Integration add-on (data activity: 25–50M) + POS must have API
* Best for: Brands with their own store chain and POS system (e.g. Haravan)
* Constraint: **Needs tech confirmation** — not all POS systems are compatible; real-time vs batch sync must be agreed

**Option D — PG/staff manual input** *(lowest tech, lowest accuracy)*

```
Staff enters customer phone number into admin backend
    → Manually credits points for the transaction
    → Admin log records who entered what
```

* Required: CShub Pro 1 + admin account for staff
* Best for: Small-scale, high-touch B2B scenarios (e.g. garage mechanic loyalty)
* Constraint: Prone to error and fraud; not scalable; requires staff training

**Choosing the right option:**

|Channel|Recommended option|
|-|-|
|FMCG packaged product (GT/MT)|UTC on-pack|
|Supermarket / pharmacy purchase|Scan Bill|
|Brand's own store with POS|POS API integration|
|B2B mechanic / garage / small shop|PG manual input or UTC|

\---

## PATTERN 3: LEAD COLLECTION + INSTANT VOUCHER (O2O TRIAL)

**Scenario:** Brand wants to run a short-term campaign — user fills form, gets a voucher, redeems at physical store or online.

**Flow:**

```
Zalo Ad / QR / OA message
    → MiniApp → Onboarding form
    → User verified → Instant voucher issued via Zalo OA message
    → User shows voucher code at store / applies at checkout
    → System marks voucher as used
    → Zalo OA sends reminder if voucher unused after X days
```

**Required:**

* CShub Voucher 1 (if simple lead + voucher, max 30K vouchers / 100M VND total value)
* Or Campaign "Lead form voucher" 20M if outside CShub (note: needs confirmation on scope)

**Add-ons if needed:**

* Game mechanic before voucher (e.g. flip card, minigame) → Campaign HTML5 Game 80M
* 3rd party voucher (Urbox, GotIt) → gateway 20M + vendor contract

**Key constraints:**

* Voucher 1 hard cap: 30K vouchers, total value ≤ 100M VND
* Voucher redemption at store: user shows Zalo message with code — no POS integration needed
* Tracking redemption: admin marks used in backend, or brand tracks separately at POS
* Drop rate: longer forms = higher drop rate; keep to 2–5 fields

\---

## PATTERN 4: LONG-TERM LOYALTY PROGRAM (B2C)

**Scenario:** Brand wants a sustained loyalty system — users earn points over time, redeem for rewards, build tier status.

**Full loyalty architecture:**

```
Acquire → Onboard → Earn points → Tier up → Redeem → Retain
```

**Earn sources (combinable):**

* D2C purchase on MiniApp → automatic (Base 3+)
* UTC code scan → Campaign UTC add-on
* Scan Bill → Campaign Scan Bill add-on
* Read article → Content Hub (Base 2+)
* Complete mission → Pro 1+
* Event check-in → Event Hub (Pro 2)
* Referral → Pro 1+
* Birthday bonus → Pro 1+

**Burn (redemption) options:**

* Offline gift at store: user shows QR, staff scans
* Order voucher: deduct from next D2C purchase
* 3rd party online reward (Urbox, GotIt): gateway add-on 20M

**Tier structure:**

* Admin defines: Bronze / Silver / Gold (or custom names)
* Based on cumulative points earned (NOT current balance)
* Burning points does NOT reduce tier — clarify this with clients
* Tier benefits: bonus earn rate, exclusive rewards, priority access (all configurable)

**Required minimum:** CShub Pro 1

**Key constraints:**

* Basic earn/burn is bundled in Pro 1 — complex schemes (time-limited double points, category multipliers) may need custom development
* Points from non-Zalo channels (POS, website, app) require API integration
* Tier downgrade only if cumulative points drop (e.g. annual reset) — must communicate clearly to users
* 3rd party reward integration requires separate vendor contract (Urbox, GotIt, VTDĐ)

\---

## PATTERN 5: B2B INTERMEDIARY LOYALTY (RETAILER / DISTRIBUTOR / HCP)

**Scenario:** Brand's "customer" is not an end consumer but an intermediary — garage owner, pharmacy, retailer, distributor, or HCP. Brand wants to build loyalty with this channel.

**Key difference from B2C:**

* Intermediary is motivated by business incentives, not personal rewards
* Registration requires more profile fields (business name, location, specialty)
* Points may be tied to sales volume, not individual purchases
* Tier system often maps to sales performance tiers

**Typical B2B flow:**

```
Brand sends invitation (OA message / MedRep / QR at workshop)
    → Intermediary opens MiniApp
    → Registers with business profile (name, phone, shop/clinic info, specialty)
    → Joins loyalty program
    → Earns points: scan QR per unit sold / record sales / attend training
    → Redeems: business gifts, trade incentives, cash equivalents
    → Receives personalized content by segment (specialty, region, tier)
```

**Required:** CShub Pro 1 or Pro 2 (depending on whether events are needed)

**Key differences in implementation:**

* Segmentation by specialty / region / tier is critical — use tag + segment features
* Content Hub is important: training materials, product updates by specialty (Base 2+)
* Event Hub useful for workshops, product launches, training sessions (Pro 2)
* Automation: reminder to scan, tier upgrade alert, content update by specialty (Pro 1)

**Key constraints:**

* B2B profiles need more data fields — may need custom form fields (confirm tech)
* Point earning from sales volume (not just QR scans) requires POS/order API integration
* Anti-fraud is more critical — intermediaries may try to game the system

\---

## PATTERN 6: UTC CAMPAIGN + LONG-TERM LOYALTY (COMBINED)

**Scenario:** FMCG brand runs seasonal UTC campaign but also wants to build long-term loyalty. Both need to work together.

**Architecture:**

```
UTC Campaign (short-term activation)
    + CShub Pro 1 (long-term backbone)
    = Points earned from UTC feed into loyalty account
```

**Flow:**

```
User scans on-pack QR (UTC campaign)
    → If new user: goes through onboarding first → becomes member
    → If existing member: directly validates code
    → Points credited to loyalty account
    → User can see total points, tier status, reward catalog
    → Automation sends follow-up (e.g. "You've earned 50 points! 200 more to redeem a gift")
```

**Why this combination matters:**

* UTC alone (without Pro 1) = one-shot campaign, data lost after campaign ends
* Pro 1 alone (without UTC) = loyalty platform with no offline touchpoint
* Together = every product purchase feeds the long-term relationship

**Required:** CShub Pro 1 + Campaign UTC 80M + UTC code generation

**Key constraint:**

* UTC campaign and loyalty platform must be configured to share the same member database
* Code prefix design should match the loyalty earn rule (e.g. prefix A = 10 points, prefix B = 50 points)

\---

## PATTERN 7: MESSAGING STRATEGY

**Scenario:** Brand wants to communicate with customers on Zalo — but doesn't know which message type to use.

**Decision guide:**

|Situation|Message type|Requirement|
|-|-|-|
|Send OTP, order confirmation, delivery update|ZNS|Pre-approved template + phone number|
|Welcome new member, birthday greeting, campaign push|Broadcast (Tin truyền thông)|User must follow OA|
|Respond to user inquiry, 1-1 conversation|Advisory (Tin tư vấn)|User must have messaged OA first|
|Order status update, point credit notification|Transaction (Tin giao dịch)|User interaction context|
|Automated journey (welcome series, tier upgrade)|Automation (Pro 1+)|Trigger event + message template|

**ZNS tips:**

* ZNS is the most reliable — delivered to phone number regardless of OA follow status
* But requires pre-approved template — Zalo approval takes time; plan ahead
* Character limits apply; cannot add images to standard ZNS

**Broadcast tips:**

* Only sent to OA followers — growing follower base is prerequisite
* Zalo limits daily send volume per OA — large campaigns need batching
* Personalization (name, tier, points balance) is possible with dynamic variables

**Automation tips (Pro 1+):**

* Welcome series: trigger on onboarding → Day 0, Day 3, Day 7 messages
* Re-engagement: trigger on 30 days inactivity → send reactivation offer
* Tier upgrade: trigger on point milestone → "You've reached Gold tier" message
* Birthday: trigger on birthday date → send voucher or bonus points

\---

## PATTERN 8: SEGMENTATION \& PERSONALIZATION

**Scenario:** Brand has thousands of members and wants to send relevant content/offers to different groups — not one-size-fits-all.

**Segmentation dimensions available:**

|Dimension|Example|
|-|-|
|Demographics (from form)|Province, gender, age group|
|Behavior|Last active date, purchase count, points earned|
|Tier|Bronze / Silver / Gold|
|Source|Acquired via UTC / Scan Bill / Zalo Ads / PG|
|Tag / Label|Auto-tagged by automation trigger|
|Content interest|Which articles they read (Base 2+)|

**Auto-tagging (Pro 1+):**

* Define rule: "User completes purchase → tag as 'buyer'"
* Automation assigns tag → tag is used in segment → personalized message sent
* Useful for B2B: "User is doctor" → tag specialty → segment → send specialty content

**----**

## PATTERN 9: WHITELIST-GATED HCP ONBOARDING

**Scenario:** Pharma brand wants to build an HCP community on Zalo but must restrict access to verified healthcare professionals only — cannot allow open self-registration.

**The core challenge:** AdtimaBox's default flow allows any Zalo user to register. For pharma/professional audiences, the brand needs a verification gate to ensure only legitimate HCPs access the hub.

**Solution flow:**

```
HCP enters via: QR at event / MedRep URL / Email campaign / Word-of-mouth
    ↓ Information acquire permission pop-up (Zalo grants brand access to phone/name)
    ↓ Form 1: Name + phone auto-filled → consent tick → OA follow (1st time)
    ↓ Form 2: Manual fill — hospital, title, specialty, department
    ↓ AdtimaBox maps phone number against brand's whitelist (pre-loaded HCP database)
    ├── Match found (existing HCP):
    │       → Direct access to Hub home screen
    │       → Receive successful registration message via OA
    └── No match (unknown HCP):
            → Manual approval queue (brand's medical/compliance team reviews)
            ├── Approved:
            │       → Access granted → Welcome message
            └── Rejected:
                    → Popup rejection → Failed registration message
```

**Segmentation from Form 2 data:**
- By Hospital (e.g. Hospital 115, Hoàn Mỹ, Chợ Rẫy)
- By Specialty (e.g. Endocrinologist, Cardiologist, Nephrologist)
- By Level (e.g. Level A, Level B, Level C)
- By City / Province / District
- Behavioral labels auto-added post-registration (preferred content, event attendance)

**Required:** CShub Pro 1+ + whitelist data provided by brand + manual approval workflow agreed upfront

**Key operational constraint:** Manual approval requires dedicated brand-side resource; if manual queue is large, set approval timeline expectations. Whitelist must be regularly updated by brand.

---

## PATTERN 10: MCE (MULTI-CHANNEL ENGAGEMENT) FOR PHARMA PRODUCT LAUNCH

**Scenario:** Pharma brand launching a new product needs to move HCPs through a structured awareness-to-trial funnel using multiple digital and physical channels in a coordinated way.

**MCE framework (3-phase):**

```
PRE-LAUNCH phase
Objective: Cost per HCP Acquisition (CPA)
Channels:
    - Zalo OA broadcast → drive HCPs to register on Hub
    - Email marketing with QR code / URL → MiniApp onboarding
    - MedRep personally invites via Zalo message
    - Offline medical events → QR code walk-in registration
    → KPI: Number of verified HCPs onboarded

LAUNCH phase
Objective: Trial prescription count
Channels:
    - Zalo personalized message by specialty → product education
    - Content Hub articles: efficacy, dosing, safety, patient profiles
    - Online/offline medical events (symposia, webinars) → HCP attendance
    - HCP Portal (3rd party medical platforms) for detailed clinical info
    - 3rd party medical networks (Hello Doctor, Docquity, MIMs etc.) for awareness
    → KPI: Event registrations, content engagement, trial prescription signals

POST-LAUNCH phase
Objective: Positive product mentions and advocacy
Channels:
    - Post-event survey (automated via Zalo OA message after each event)
    - Loyalty point accumulation for continuous engagement
    - Digital activities: medical quiz, AI e-card for HCP appreciation days
    - Year-end recap / tribute activities
    → KPI: Survey completion rate, positive brand mentions
```

**What AdtimaBox contributes to MCE:**
- HCP database management (segmented by specialty, hospital, level)
- Personalized ZBS messages at every event stage (announcement → reminder → during → post-event)
- Content Hub for clinical education content
- Event Hub for online/offline event management and QR check-in
- Loyalty and digital engagement layer
- 2-way data sync with brand's enterprise CRM (Salesforce)

**What AdtimaBox does NOT replace:**
- 3rd party medical networks (Hello Doctor, Docquity) — separate buy
- Email marketing platform — separate system
- HCP Portal (brand's own web portal for clinical materials) — separate system
- Call center / e-RMA / e-Rep follow-up — separate system

**AdtimaBox is the Zalo layer of MCE — not the full MCE stack.**

---

## PATTERN 11: SALESFORCE ↔ ADTIMABOX TWO-WAY DATA SYNC

**Scenario:** Brand already uses Salesforce as their enterprise CRM. They want AdtimaBox to be the Zalo engagement layer — but data must flow both ways so Salesforce stays as the system of record.

**Data flow architecture:**

```
Direction 1 — Salesforce → AdtimaBox:
Salesforce pushes: HCP whitelist, existing member records, approved new registrations
    → AdtimaBox uses this to: verify onboarding, pre-populate member labels, trigger personalized messages

Direction 2 — AdtimaBox → Salesforce:
AdtimaBox pushes: all raw data logs (every action on MiniApp/OA)
    - Registration form data (from onboarding)
    - Event registration + check-in logs
    - Content engagement (views, likes, shares)
    - Message interaction data (sent / opened / clicked)
    - Survey responses
    → Salesforce uses this to: segmentation, follow-up sequencing, e-Rep triggers, RMA triggers
```

**Integration implementation:**
- AdtimaBox hosts open APIs for CRM integration
- Salesforce sets up webhook / scheduled API pull to receive data
- Data stays onshore (Vietnam) — no international transfer
- All data processed with user consent (compliant with Decree 13/2023/NĐ-CP)
- Post-event data auto-syncs to Salesforce for follow-up segmentation

**Requirements:**
- Integration add-on: 25–50M VND depending on data volume / complexity
- Salesforce-side engineering resources required (API keys, token rotation, error handling)
- Tech confirmation mandatory before committing to client — not all Salesforce configurations are identical
- Adtima Tech Team must assess Salesforce instance and agree on integration pattern

**Critical constraints:**
- Real-time vs batch sync must be agreed upfront (real-time costs more)
- Salesforce must expose API endpoint (or support scheduled pulls)
- Role permissions in Salesforce must be defined (who can see Zalo behavioral data?)
- This is always an add-on — NOT included in any CShub base package

---



|Confusion|Correct understanding|
|-|-|
|"Base 3 has a lucky draw"|Base 3 has a lucky SPIN after D2C purchase only — different from Lucky Draw campaign (60M separate, flexible triggers, GAP mechanic, winner list)|
|"Loyalty points work automatically from offline purchase"|No — requires a bridge: UTC code, Scan Bill, or POS API integration|
|"Voucher 1 is the same as voucher in Base/Pro"|Different. Voucher 1 = lead form → instant voucher (standalone). Base/Pro = in-purchase D2C voucher only|
|"Tier drops when user redeems points"|Tier is based on CUMULATIVE points earned, not current balance. Redeeming does not reduce tier (unless annual reset is configured)|
|"Scan Bill is included in Pro 2"|No. Scan Bill is always a campaign add-on (80M) regardless of CShub package|
|"ZNS and broadcast are the same"|ZNS goes to phone number (no OA follow needed). Broadcast goes to OA followers only|
|"UTC and CShub are separate programs"|They can work together — UTC earns feed into Pro 1 loyalty account when configured correctly|
|"B2B loyalty works the same as B2C"|Different profile fields, different earn logic (sales volume vs individual actions), different segmentation needs|
|"There is only one pharma HCP model"|Two documented models: (A) Whitelist-gated — HCP access restricted until approved; (B) Open registration + staff check-in — HCP registers freely, staff controls event attendance. See Pattern 13|
|"UTC and Game are MiniApp modules"|No. Both are CAMPAIGN ADD-ONS purchased separately. They run for a defined period on the MiniApp — not permanent Hub modules. Flows 11 and 12 document how each works|

## PATTERN 12: ZBS MESSAGE AUTOMATION CADENCE FOR PHARMA EVENTS (TRANSACTIONAL ONLY, NO PROMO)

| Label | Trigger | Message purpose | Key content |
|---|---|---|---|
| M1 | Đăng ký tài khoản thành công | Xác nhận đăng ký tài khoản thành công | Thông tin tài khoản mới |
| M2 | Đăng ký sự kiện thành công | Xác nhận đăng ký sự kiện | Link phòng họp (nếu Online) HOẶC Mã QR check-in cá nhân (nếu Offline) |
| M3 | Quét QR check-in sự kiện offline | Xác nhận check-in thành công | Lời chào mừng khi đến sự kiện |
| M4 | Sự kiện kết thúc | Khảo sát sau sự kiện | Link khảo sát ý kiến đánh giá sau sự kiện |

**Why this cadence matters:**
- Each message fires on a different trigger — they are not a single broadcast
- M2 depends on event registration data (unique QR per HCP — not same for everyone)
- M3 timing is configurable (brand decides: day before, morning of event, etc.)
- M4 depends on event completion — needs event end time defined in admin
- Post-event survey data feeds back to Salesforce (if integration enabled) for follow-up segmentation

**ZNS vs Broadcast (OA message) — when to use each:**
- ZNS: goes directly to phone number — HCP does NOT need to follow OA. Used for transactional messages (M1 confirmation, M2 event QR, M3 reminder)
- Broadcast (OA message): goes to OA followers only — HCP must have followed OA. Used for general announcements (upcoming events, new content, news)
- For pharma events: M2 (event QR) should be ZNS, not broadcast, to ensure delivery even if HCP hasn't followed OA

---

## PATTERN 13: TWO PHARMA HCP DEPLOYMENT MODELS — COMPARISON

**When to use which model for a pharma client:**

| Dimension | Model A: Whitelist-Gated (Flow 8) | Model B: Open Registration + Staff Check-in (Flow 13) |
|---|---|---|
| HCP registration | Restricted — phone must be in whitelist | Open — any HCP can register |
| Access control | At point of Hub entry | At point of physical event (via staff) |
| Staff role | Brand/medical team reviews & approves new HCPs | On-site event staff uses check-in app to scan QR |
| New HCP acquisition | Via manual approval queue | Freely — anyone with the link/QR |
| Compliance fit | Higher — only verified HCPs in the system | Lower — unverified HCPs can enter Hub |
| Friction for HCP | Higher — may be rejected, slower access | Lower — immediate access after registration |
| Best for | Brands with strict HCP verification requirements (e.g. prescription-only products) | Brands prioritizing community growth with event-based attendance tracking |
| Staff whitelist | Not applicable (staff don't use a separate app) | Staff added to brand whitelist → use staff check-in app to scan HCPs |
| Event check-in | QR code check-in (Flow 10) — HCP scanned by staff | Staff-side QR scan with confirm/invalid result (Flow 13 staff journey) |
| Salesforce sync | Recommended (all new HCP data → Salesforce) | Optional |

**Decision guide for sales:**
- Client is pharma MNC with compliance team → probe: "Do you need to verify each doctor before they access the Hub?" → If YES → Model A (whitelist-gated)
- Client wants to grow HCP database quickly via events → probe: "Is it OK for any doctor who scans our QR to join the Hub?" → If YES → Model B (open + staff check-in)
- Model B can later be upgraded to Model A as database matures and brand wants tighter control

---



* POS integration specifics for non-Haravan/KiotViet platforms (confirm with tech lead)
* Custom earn schemes (bonus multiplier, time-limited double points)
* Survey / Quiz / Course module mechanics
* Automation step limits and delay configuration details
* OCR accuracy rates by retailer type
* Haravan / specific POS connector availability
* Salesforce integration specifics beyond the architecture described in Pattern 11 (data volume limits, rate limits, field mapping) — confirm with tech lead

→ Response: **"This needs to be confirmed with the tech lead before committing to the client."**

