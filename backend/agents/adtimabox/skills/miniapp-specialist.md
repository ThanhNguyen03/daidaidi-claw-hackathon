---
name: adtimabox-miniapp-specialist
description: >
  AdtimaBox Zalo MiniApp specialist — explains core user flows (onboarding, reading content, shopping, events, missions, redeeming rewards, earning points) and identifies standard vs non-standard flow requests. Activate when asked: "what flow does a user go through when X", "how does onboarding work", "what triggers point accumulation", "can the brand change this flow". For which package includes which module → refer to adtimabox-product-advisor. Do NOT use for package pricing, solution recommendation, or backend admin operations.
---

# AdtimaBox MiniApp Specialist

## PRINCIPLES

- **Answer only from documented sources:** 7 MiniApp user flows + credential capability overview
- **Do not infer** flows or features not present in the source
- **Do not compare packages / quote pricing** → redirect to `adtimabox-product-advisor`
- **Do not explain backend admin operations** → no source available
- When in doubt → state clearly: "This has not been fully documented — needs confirmation with the tech lead"

---

## VALID INPUT TYPES

| Question type | Example |
|---|---|
| User flow on MiniApp | "What steps does a user go through to redeem a reward?" |
| What a MiniApp module does | "What does the Loyalty module on the MiniApp include?" |
| Map module to package | "Which package includes the points accumulation feature?" |
| Point earn triggers | "What actions help users earn points?" |
| Identify custom flow request | "Can the brand let users browse before registering?" |
| HCP / professional audience flow | "How does whitelist verification work for HCP onboarding?" |
| Event acquisition flow | "How does walk-in registration at an offline event work?" |
| UTC / on-pack code flow | "How does the UTC code scanning and lucky draw work?" |
| Interactive game flow | "What is the user journey in the HTML5 game campaign?" |
| Pharma open registration vs whitelist | "What's the difference between the two HCP models?" |

---

## STANDARD OUTPUT FORMAT

```
1. What this flow/module is (1-2 sentences)
2. What the user experiences — step by step
3. Which subscription package includes this module
4. Notes if applicable
```

---

## 7 USER FLOWS ON THE MINIAPP

### Flow 1 — Onboarding (Register & Consent)
*Available in: all packages*
```
Scan QR / Zalo Ads / OA message
    ↓ Enter MiniApp
    ↓ Enter name → tap phone number field
    ↓ Permission modal to access phone number → auto-prefill
    ↓ Tick consent to terms + agree to receive marketing messages
    ↓ Modal suggesting Follow OA → Follow → receive welcome message (optional)
    ↓ Enter MiniApp home screen
```
*From the 2nd visit onward: info auto-filled, user goes straight to content*

---

### Flow 2 — Reading Content (Content Hub)
*Available in: Base 2+*
*Point reward from reading: Pro 1+ only (requires Loyalty module)*
```
Home screen → select "News" / featured article banner
    ↓ Article list (filter by category / tag)
    ↓ Tap article → read content
    ├── Scroll to end of article → trigger point reward (Pro 1+ only)
    ├── Tap Like / Share
    └── View related articles
    ↓ Receive points (Pro 1+ only — Base 2/3 can read but no points)
```

---

### Flow 3 — Shopping (D2C Shop)
*Available in: Base 3+*
*Point earn from purchase: Pro 1+ only (requires Loyalty module)*
*Use points to pay: Pro 1+ only*
```
Home screen → enter "Shop"
    ↓ Browse / search products → view product detail
    ↓ Select quantity / variant → "Add to cart" / "Buy now"
    ↓ View cart
    ├── Apply discount voucher
    └── Use points to reduce order value (Pro 1+ only)
    ↓ Enter delivery address → select payment (COD / E-wallet / ZaloPay)
    ↓ Confirm order
    ↓ Receive order ID + Zalo OA notification
    ↓ Points credited from order (Pro 1+ only — Base 3 can shop but no points)
```

---

### Flow 4 — Events (Event Hub)
*Available in: Pro 2 only*
```
Home screen → enter "Events"
    ↓ View list of ongoing / upcoming events
    ↓ Select event → view details (time, location, description)
    ├── Register / Save event
    ├── Share with friends
    └── Set reminder
    ↓ Receive OA notification before event
    ↓ Check in via QR code on-site → earn points (if applicable)
```

---

### Flow 5 — Missions
*Available in: Pro 1+*
```
Home screen → enter "Missions" / "Challenges"
    ↓ View mission list (Daily / Weekly / Special)
    ↓ Select mission → view requirements & rewards
    ↓ Complete mission (Read article / Purchase / Share / Check-in / Invite friend...)
    ↓ System automatically records completion
    ↓ Tap "Claim reward"
    ↓ Points / Voucher credited to account
    ↓ View overall mission progress
```

---

### Flow 6 — Redeeming Rewards
*Available in: Pro 1+*
```
Home screen → enter "Rewards" / "Reward Catalog"
    ↓ View reward list (filter by points / category)
    ↓ Select reward → view details & redemption conditions
    ├── Enough points → tap "Redeem now"
    └── Not enough → suggested ways to earn more points
    ↓ Confirm redemption
    ↓ Select delivery method
    ├── Collect at store (display QR code)
    └── Deliver to address
    ↓ Points deducted → reward code / redemption slip issued
    ↓ Confirmation received via Zalo OA
    ↓ View redemption history
```

---

### Flow 7 — Points Accumulation (All Earn Triggers)
*Available in: Pro 1+*

| Action | Notes |
|---|---|
| New account registration | One-time |
| Read article for required duration | Based on admin configuration |
| Complete mission | Daily / Weekly / Special |
| Successful purchase | Based on conversion rate set by admin |
| Share article / event | |
| Check in at event | |
| Successful referral (friend registers) | |
| Birthday / Anniversary bonus | |

*Exact point values are configured by the brand admin — not fixed*

---

## MODULE → PACKAGE MAP

| MiniApp Module | Voucher 1 | Base 1 | Base 2 | Base 3 | Pro 1 | Pro 2 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Onboarding / Lead form | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Voucher distribution after form | ✓ | — | — | — | — | — |
| Content Hub (Reading) | — | — | ✓ | ✓ | ✓ | ✓ |
| D2C Shop (Shopping) | — | — | — | ✓ | ✓ | ✓ |
| Missions | — | — | — | — | ✓ | ✓ |
| Loyalty / Reward Redemption | — | — | — | — | ✓ | ✓ |
| Event Hub + QR Check-in | — | — | — | — | — | ✓ |
| UTC On-Pack Code → Lucky Draw | Campaign add-on UTC (purchased separately) — see **Flow 11** |
| HTML5 Game → Lucky Draw | Campaign add-on Game 80M (purchased separately) — see **Flow 12** |
| Lucky Draw (standalone) | Campaign add-on Lucky Draw 60M (purchased separately) |
| Scan Bill → Points/Reward | Campaign add-on Scan Bill 80M (purchased separately) |

---

### Flow 8 — HCP Whitelist-Gated Onboarding (Pharma / Professional Audience)
*Available in: Pro 1+ — requires custom whitelist validation logic (confirm with tech lead)*
```
Entry point: QR code at event / Owned channel (email, MedRep message) / Word-of-mouth
    ↓ Open MiniApp
    ↓ Information acquire permission pop-up
        → User grants Zalo phone access
    ↓ FORM 1 (auto-fill): Name + phone number pre-populated from Zalo permission
        → Tick: T&C data consent + Follow OA (first time only)
        → Tap: Register
    ↓ FORM 2 (manual fill): Work info — hospital, title, specialty, department
    ↓ AdtimaBox maps phone number against brand's whitelist
    ├── Phone matches whitelist (existing/pre-approved HCP):
    │       → Go to Home screen
    │       → Receive: Successful registration OA message
    └── Phone NOT in whitelist (new / unknown HCP):
            → Manual approval queue (brand reviews)
            ├── Approved:
            │       → Go to Home screen
            │       → Receive: Successful registration OA message
            └── Rejected:
                    → Popup: Rejection notification
                    → Receive: Failed registration OA message
```
*Key constraint: Whitelist must be provided and maintained by the brand; manual approval step depends on brand ops capacity — flag for operational planning*

---

### Flow 9 — New HCP User Acquisition at Offline Events (Walk-in Registration)
*Available in: Pro 2 (Event Hub) — supports new user onboarding via event entry point*
```
Non-member HCP arrives at offline event (not yet in brand's Hub)
    ↓ On-site staff shows QR code for event registration
    ↓ HCP scans QR → Opens MiniApp registration form
        → All fields manual fill (no Zalo pre-fill since first time)
        → Opt-in consent: T&C data + T&C Zalo + Follow OA
    ↓ On-site staff checks submission on event check-in application
    ↓ AdtimaBox validates submission
    ├── Valid:
    │       → Successful new registration logged in CRM
    │       → Staff app shows: Successful check-in pop-up → HCP enters event
    │       → HCP receives: Registration confirmation + Welcome to Hub message via Zalo OA
    └── Invalid:
            → Staff app shows: Failed check-in pop-up
            → HCP is guided to re-register
```
*Use case: Brand leverages existing offline events as acquisition touchpoints to grow HCP database — particularly effective for pharma new product launch phases*

---

### Flow 10 — Existing Member Check-in at Offline Event (QR Code)
*Available in: Pro 2 (Event Hub)*
```
Registered HCP receives successful registration confirmation message (via Zalo OA)
    → Message contains unique QR code for event check-in
    ↓ HCP arrives at event → shows QR code to on-site staff
    ↓ Staff scans QR using check-in application
    ↓ System cross-checks QR data vs registration list (in Salesforce or AdtimaBox CRM)
    ├── QR verified:
    │       → Staff app: Successful check-in pop-up
    │       → HCP: Informed to enter event site
    │       → Data logged in CRM for records
    └── QR not verified:
            → Staff app: Failed check-in pop-up
            → HCP: Guided to proceed with new registration (Flow 9)
```
*Online event variant: Registration confirmation message includes online meeting link instead of QR code. Platform (Zoom etc.) confirmed at implementation stage.*

---

### Flow 11 — UTC On-Pack Code → Lucky Draw (FMCG Campaign Add-on)
*Available in: Campaign UTC add-on (purchased separately — not included in any CShub subscription)*
```
User scans QR code on product packaging
    ↓ Zalo MiniApp opens
    ↓ Onboarding (first time only):
        - Follow Zalo OA
        - Allow Zalo to access phone number & Zalo ID
        - Fill info: full name, phone, address (manual)
    ↓ Enter security code (mã bảo mật) printed on product
    ↓ System validates BOTH: QR code + security code
    ├── Valid (Hợp lệ):
    │       → User receives X lucky draw turns (ZNS notification sent)
    │       → Enter Lucky Draw screen
    │       ├── Win (Quay trúng):
    │       │       → ZNS notification sent
    │       │       → Prize options: E-voucher / Physical gift / Brand discount voucher / ...
    │       └── No win (Không trúng):
    │               → ZNS notification sent
    └── Invalid (Không hợp lệ):
            → Prompt: Try again (Tham gia lại)
```
*Returning user: Onboarding auto-skipped (phone pre-filled from Zalo permission). User goes straight to code entry.*

*Key constraints:*
- *QR code + security code = dual validation. Both must be on the product*
- *Each code is single-use — anti-fraud protected*
- *UTC codes generated in batches (20M per batch) — must be pre-ordered before campaign launch*
- *Number of lucky draw turns is configurable by admin (e.g. 1 valid code = 1 turn)*

---

### Flow 12 — Interactive Game → Lucky Draw (FMCG Campaign Add-on)
*Available in: Campaign HTML5 Game add-on (80M, purchased separately)*
```
Player enters via:
    ├── Scan QR code offline (event, POS, packaging)
    ├── Zalo Ads
    ├── Other ads channels (Facebook, TikTok etc.)
    └── Social post / word-of-mouth
    ↓ Zalo MiniApp opens
    ↓ Onboarding (first time only):
        - Follow Zalo OA
        - Allow Zalo to access phone number & Zalo ID
        - Fill info: full name, phone, address (manual)
    ↓ Select / enter game
        Game types available (HTML5 games):
        + Running game
        + Puzzle / Xếp hình (tile matching)
        + Jumping game
        + Fruit slash / Chém trái cây
        + Angry Bird-style game
    ├── Success (Thành công) — score / target reached:
    │       → ZNS notification sent
    │       → User receives X lucky draw turns
    │       → Enter Lucky Draw screen
    │       ├── Win (Quay trúng):
    │       │       → ZNS notification sent
    │       │       → Prize: E-voucher / Physical gift / Brand discount voucher / ...
    │       └── No win (Không trúng):
    │               → ZNS notification sent
    └── Fail (Thất bại) — score / target not reached:
            → Prompt: Play again (Tham gia lại)
```
*Key constraints:*
- *Game type is defined at campaign scoping — one game per campaign (not user-selectable menu)*
- *Success condition (score/target) configured by admin at setup*
- *Number of lucky draw turns per success is configurable*
- *Multiple entry channels = same MiniApp, different UTM tracking per channel*
- *This is a campaign add-on, NOT a permanent MiniApp module — it runs for a defined campaign period*

---

### Flow 13 — HCP Pharma Hub: Open Registration + Staff-Gated Check-in (Alternative Pharma Pattern)
*Available in: Pro 2 (Event Hub) — staff check-in requires separate staff app setup*

*Note: This is a DIFFERENT model from Flow 8 (whitelist-gated HCP onboarding). In this model, HCP registration is open; the whitelist gate applies to STAFF (event check-in operators), not to HCPs.*

**HCP Journey:**
```
HCP enters via:
    ├── Direct search for OA on Zalo
    ├── Events / Webinars (QR or link)
    └── Social media ads
    ↓ [1] Registration Form (Zalo MiniApp):
        - Full name, phone/SĐT, email
        - Khoa/Phòng (department/specialty)
        - Consent checkboxes
        - Follow OA checkbox
        - CTA: Submit (Đăng ký)
    ↓ Successful Registration
    ↓ M1 — Welcome ZNS sent automatically
    ↓ [2] Home screen (Trang chủ) — 3 sections:
        ├── [3] Content Hub (Tin tức):
        │       → Xem tin tức về thuốc và bệnh (medical news)
        │       → Xem thông tin về sự kiện / recap
        ├── [4] Đăng ký Sự kiện (Event Registration):
        │       → View event list (Danh sách sự kiện)
        │       → Select event (Chọn sự kiện)
        │       → Register (Đăng ký)
        │       → M2 — Confirmation ZNS sent (event confirmed)
        │       → M3 — Reminder ZNS + pre-survey (before event day)
        │       → M4 — Recap ZNS + post-survey (after event)
        └── [5] Personal Profile (Trang cá nhân):
                → View personal info
                → Personal QR code (mã QR cá nhân)
                → Event participation QR code (mã QR tham dự sự kiện)
```

**ZNS Message Map (triggered automatically):**
| Message | Trigger | Content |
|---|---|---|
| M1 | Successful registration | Welcome to Hub message |
| M2 | Event registration confirmed | Event details + QR check-in code |
| M3 | Before event (configurable timing) | Reminder + pre-event survey link |
| M4 | After event | Recap content + post-event survey link |

**Staff Check-in Journey (parallel flow):**
```
Staff added to whitelist by brand admin
    ↓ Staff onboards on MiniApp using their phone number
    ↓ Staff sees MiniApp home + CTA: "Check-in"
    ↓ Staff scans HCP's QR code (from HCP's Zalo message or personal profile page)
    ↓ System validates HCP QR code
    ├── Valid (Hợp lệ):
    │       → Staff app: "Xác nhận" (Confirm) button
    │       → Staff taps Confirm → HCP attendance logged
    └── Invalid (Không hợp lệ):
            → Staff app: Notification screen
            → HCP guided to re-register or troubleshoot
```

*Key difference from Flow 8 (whitelist-gated):*
- Flow 8: HCP phone must be in whitelist → HCP cannot access Hub without prior brand approval
- Flow 13: HCP registers freely → Staff (not HCP) is whitelist-controlled for check-in operations
- Use Flow 13 when: brand wants low-friction HCP acquisition + controlled event attendance tracking
- Use Flow 8 when: brand needs verified-only HCP community (pharma compliance requirement)

---


- Backend admin operations and platform UI
- Specific UI details of individual MiniApp screens
- Survey / Quiz / Course modules on MiniApp
- Detailed automation logic

→ Response: **"This has not been fully documented — please confirm with the tech lead."**

---

## CORE FLOW vs CUSTOM FLOW

### Core Flow
The default order and logic of the platform — included in the subscription, no additional development required. Flows 1–7 above are core flows for B2C. Flows 8–10 are documented HCP/pharma patterns (require Pro 1–Pro 2 + tech confirmation). Flows 11–12 are FMCG campaign add-on flows (UTC and Game). Flow 13 is an alternative pharma hub pattern with open registration + staff-gated check-in.

### Custom Flow
When a brand wants to **change the order or logic** compared to the default core flow.

**Example:**
- Core: Onboarding required first → then access home screen
- Custom: Allow user to browse home screen first → only require registration when they want to use a feature

**When a custom flow request is identified:**
```
1. Explain what the current core flow looks like
2. Confirm which specific point the brand wants to change
3. Suggest possibilities if known — but DO NOT confirm feasibility
4. Flag clearly: "This is a custom flow — needs confirmation from the tech lead
   regarding feasibility, and will incur costs beyond the subscription"
5. Redirect pricing questions to adtimabox-product-advisor
```

**Never self-confirm** whether a custom flow is technically possible — that is the tech lead's decision.