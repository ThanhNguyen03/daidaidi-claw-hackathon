---
name: zalo-miniapp-wireframe-patterns
description: >
  The standard screen inventory per AdtimaBox journey type (loyalty redemption, membership
  acquisition, UTC code + lucky draw, booking, ordering, HCP whitelist) plus the canonical
  block composition of each of the ten Zalo Mini App screen archetypes. Activate when deciding
  how many screens a journey needs, which archetype each step maps to, and which blocks each
  screen carries. Gives per-archetype block orders so a wireframe reads like a real Zalo Mini
  App rather than a generic mobile app. Do NOT use for ZNS or OA message structure → see
  zns-oa-templates.md. Do NOT use for how much content to put in a block → see
  wireframe-fidelity.md.
---

# Zalo Mini App — Screen Inventory & Archetypes

## PRINCIPLE

A Mini App journey is short at the *entry* and deep in the *middle*. Users arrive from a QR
scan or an OA message with one intent and no patience for onboarding — but once inside, the
screens they move through are as rich as any shopping app they already use. Both halves of
that shape matter: compress the entry and a rep gets asked "so how do they sign up?", flatten
the middle and the client sees a prototype rather than a product.

Zalo pre-fills identity. A Mini App knows the user's Zalo name and can request their phone
number with one permission modal, so a registration screen is a **consent screen with one or
two fields** — never a sign-up form with email and password. Drawing a password field in a
Zalo Mini App wireframe is a factual error about the platform, not a stylistic choice.

---

## PART 1 — SCREEN INVENTORY PER JOURNEY

Start from the journey in the proposal's Section 3. These are the screens each journey type
normally needs. Include a screen when the journey implies it, even if the proposal does not
name it — see the structure-vs-content rule in SKILL.md.

### Loyalty redemption — the most common AdtimaBox journey (9 screens)

```
1.  Consent / Onboarding      form        first visit only: name + phone + consent toggles
2.  Home                      home        hero (points + tier) · carousel · chips · grid · tabbar
3.  Reward listing            listing     chips filter · grid or voucher list
4.  Reward detail             detail      banner · card of terms · points cost · CTA
5.  Redeem confirmation       confirm     sheet or two cards: what + what it costs
6.  Redemption success        success     qr for the counter · voucher · expiry
7.  My vouchers               collection  tabs (Đang dùng / Đã dùng / Hết hạn) · voucher list
8.  Points history            history     steps or list with meta figures
9.  ZNS — voucher issued      zns         see zns-oa-templates.md
```

Drop 1 if the proposal says members are already identified. Drop 8 if points are not part of
the mechanic. Never drop 6 — the counter artefact is the moment the whole journey exists for.

### Membership acquisition from an offline event / QR at a booth (6 screens)

```
1.  Landing from QR           home        banner (campaign KV) · text · CTA "Đăng ký ngay"
2.  Registration              form        name · phone (auto-filled) · consent toggles · note
3.  Registration success      success     hero (new member card) · steps of what happens next
4.  Member card               detail      hero · qr (member ID for the counter) · card of benefits
5.  Benefits overview         listing     section · grid of member perks
6.  OA welcome message        oa          see zns-oa-templates.md
```

### UTC / on-pack code + lucky draw (7 screens)

```
1.  Home                      home        hero (số lượt còn lại) · banner · steps of how to play
2.  Enter code                form        field (mã UTC) · note (điều kiện) · CTA
3.  Draw / result             success     banner (kết quả) · voucher or empty (chúc bạn may mắn)
4.  Prize detail              detail      voucher · card of terms · CTA nhận thưởng
5.  Claim form                form        field ×2-3 (địa chỉ nhận thưởng) · note
6.  My entries                collection  tabs · list with meta (mã · thời gian · kết quả)
7.  ZNS — prize won           zns         see zns-oa-templates.md
```

The `empty` block on screen 3 is the losing branch, and drawing it is what makes the mechanic
honest — a lucky-draw wireframe that only shows the winning path oversells the campaign.

### Booking / appointment (8 screens)

```
1.  Home                      home        hero or banner · chips (loại dịch vụ) · grid · tabbar
2.  Branch listing            listing     chips (khu vực) · list with meta (khoảng cách)
3.  Branch detail             detail      banner · card (địa chỉ · giờ mở cửa) · CTA đặt chỗ
4.  Slot picker               form        timeslot (ngày) · timeslot (giờ) · note
5.  Booking confirmation      confirm     sheet: dịch vụ · chi nhánh · giờ · CTA
6.  Booking success           success     qr (mã đặt chỗ) · card · steps (chuẩn bị gì)
7.  My bookings               collection  tabs (Sắp tới / Đã xong) · list · empty
8.  ZNS — booking confirmed   zns         see zns-oa-templates.md
```

### Ordering / D2C commerce (9 screens)

```
1.  Home                      home        hero · carousel · chips · grid · tabbar
2.  Category listing          listing     chips · grid with meta (giá)
3.  Product detail            detail      banner · text · card (giá · khuyến mãi) · CTA
4.  Cart                      collection  list with meta · card (tạm tính · phí ship · tổng)
5.  Checkout                  form        field (địa chỉ · ghi chú) · card (tổng) · note
6.  Order confirmation        confirm     sheet: tổng tiền · phương thức · CTA
7.  Order success             success     card (mã đơn) · steps (trạng thái đơn)
8.  Order tracking            history     steps · card · CTA liên hệ
9.  ZNS — order confirmed     zns         see zns-oa-templates.md
```

### HCP / whitelist-gated audience (6 screens)

```
1.  Verification gate         form        field (mã HCP / số CCHN) · note (điều kiện) · CTA
2.  Pending / rejected        success     empty or steps · note explaining the wait
3.  Home (verified)           home        hero · section · grid (nội dung chuyên môn) · tabbar
4.  Content detail            detail      banner · text · card (nguồn) · CTA
5.  Saved content             collection  tabs · list · empty
6.  ZNS — verification result zns         see zns-oa-templates.md
```

Whitelist journeys are the one case where a **rejected/pending state is a required screen**:
the client's compliance team will ask what a non-HCP sees.

---

## PART 2 — THE TEN SCREEN ARCHETYPES

Each archetype lists its canonical block order. Follow it unless the proposal describes
something different. Drop a block when the proposal gives it nothing and no `placeholder`
label would be meaningful; use `placeholder` when the region clearly exists but its contents
are unspecified.

### A. `home` — top-level destination

The screen a QR scan lands on. The only archetype that carries a `tabbar`, and it never
carries `back: true`. This is the screen most often drawn too flat.

```
appbar     (title = brand or app name, back: false)
hero       (member name · tier · points balance · progress toward next tier)
carousel   (2-3 current campaigns — or banner if there is only one)
section    (title = "Ưu đãi nổi bật", action = "Xem tất cả")
chips      (2-4 categories, first active)
grid       (2-4 reward/product tiles)
tabbar     (2-4 destinations)
```

If the proposal describes no points/tier mechanic, replace `hero` with `banner` + `stats`.

### B. `listing` — browse / filter

Reached from home. Repeated same-shaped items.

```
appbar     (back: true)
field      (search — only if the proposal mentions search; type "text")
chips      (filters, first active)
section    (optional heading with result context)
grid  OR  list      (grid for visual items, list for text-led items with meta figures)
empty      (only on a dedicated empty-state screen — not alongside a populated list)
```

No `cta`: the action is tapping an item. A primary CTA on a pure listing screen misrepresents
the interaction.

### C. `detail` — one item, expanded, with the commit action

```
appbar     (back: true)
banner     (the item's own image slot — dashed placeholder in low-fi)
text       (heading = item name)
text       (body = description from the proposal)
card       (rows = the figures the user checks: giá · điểm cần · HSD · điều kiện)
note       (terms or restrictions, tone "info")
cta        (primary = the commit action)
```

For a voucher rather than a product, lead with `voucher` instead of `banner` + heading.

### D. `form` — consent, registration, data capture, code entry

Short on Zalo. Never draw password, email-verification or OTP-entry fields.

```
appbar     (back: true)
text       (body = one sentence on why the data is needed)
field      (×1-4, only fields the proposal names; use type "phone" / "select" / "date")
toggle     (×1-2 consent opt-ins — marketing consent is almost always one of them)
note       (the consent/terms line, tone "info")
cta        (primary = submit)
```

Phone number is normally auto-filled by the platform — draw it as a `field` only when the
proposal describes the user confirming or editing it.

### E. `confirm` — the "are you sure" before an irreversible action

Where a redemption journey earns its trust. Worth a screen of its own.

```
appbar     (back: true)
card       (title + subtitle = what is being committed to)
card       (rows = the arithmetic: số dư trước · số điểm dùng · số dư sau)
note       (irreversibility warning, tone "warning")
cta        (primary = confirm)
cta        (secondary = cancel)
```

Alternatively express the whole commit as a single `sheet` over the previous screen's content
— use `sheet` when the proposal describes a modal, two `card`s when it describes a page. The
two-part split matters either way: the first part says *what*, the second says *what it costs*.
Collapsing both into one card is the most common way this screen loses its purpose.

### F. `success` — the result, and the artefact

```
appbar     (back: false — the journey is over)
qr         (the code the user shows staff — label it from the proposal)
voucher    (the thing they now own, when the outcome is a voucher)
text       (heading = what just happened)
card       (rows = mã · HSD · chi nhánh áp dụng · giờ đặt)
steps      (what happens next, when there is a next)
cta        (secondary = về trang chủ)
```

When the proposal describes a code shown to staff at a counter, the `qr` block is mandatory.
It is the single most-missed block in redemption journeys, and without it the wireframe implies
the user is done when they still have to present something.

### G. `collection` — the user's own things ("Ví voucher của tôi", "Đơn của tôi")

The screen a rep gets asked about in every demo and the one most often forgotten.

```
appbar     (back: true or false depending on whether it is a tabbar destination)
tabs       (state split: Đang dùng / Đã dùng / Hết hạn — or Sắp tới / Đã xong)
voucher    (×1-2 for a voucher wallet)  OR  list with meta (for orders/bookings)
empty      (the empty state for the currently-selected tab, when worth showing)
tabbar     (only if this is a top-level destination)
```

### H. `history` — a record over time

```
appbar     (back: true)
stats      (2-3 totals: tổng điểm tích · tổng điểm dùng · số đơn)
tabs       (optional: Tích điểm / Dùng điểm)
list       (items with meta = the signed figure and the date)
empty      (when the record can be empty)
```

For a single item's progress over time (one order, one booking), use `steps` instead of `list`
— `steps` shows sequence and completion, `list` shows a ledger.

### I. `gate` — verification / pending / rejected

Whitelist and HCP journeys only.

```
appbar     (back: false on the gate itself)
banner     (or empty for a pending/rejected state)
text       (heading = what is being verified)
field      (the credential — mã HCP, số CCHN, mã nhân viên)
note       (who qualifies and what happens next, tone "info")
cta        (primary = submit)
steps      (on the pending screen: nộp → thẩm định → kết quả)
```

### J. `settings` — notification and consent management

Include only when the proposal mentions consent management or notification preferences.

```
appbar     (back: true)
section    (title = "Thông báo")
toggle     (×2-3 the consent categories the proposal names)
section    (title = "Tài khoản")
list       (account rows with meta)
note       (how to withdraw consent, tone "info")
```

---

## PART 3 — MAPPING JOURNEY STEPS TO SCREENS

| Journey step reads like… | Screen? | Archetype |
|---|---|---|
| "Người dùng quét QR vào Mini App" | Yes | `home` |
| "Đăng ký thành viên / đồng ý điều khoản" | Yes | `form` |
| "Xem danh sách ưu đãi" | Yes | `listing` |
| "Chọn ưu đãi muốn đổi" | Yes | `detail` |
| "Xác nhận đổi điểm" | Yes | `confirm` |
| "Nhận mã / hiển thị QR cho nhân viên" | Yes — mandatory | `success` |
| "Xem lại voucher đã đổi" | Yes | `collection` |
| "Xem lịch sử tích điểm" | Yes | `history` |
| "Nhập mã UTC trên bao bì" | Yes | `form` |
| "Chọn chi nhánh và giờ hẹn" | Yes | `form` with `timeslot` |
| "Xác thực là nhân viên y tế (HCP)" | Yes | `gate` |
| "Quản lý nhận thông báo" | Only if the proposal mentions it | `settings` |
| "Hệ thống cộng điểm vào tài khoản" | **No** — system event; the ZNS announcing it *is* a screen | — |
| "Nhân viên quét mã xác nhận" | **No** — staff-side, a different app | — |
| "Admin xem báo cáo trên dashboard" | **No** — not a Mini App surface | — |
| "Đồng bộ dữ liệu về CRM / CDP" | **No** — backend integration | — |
| "Gửi ZNS nhắc hạn dùng voucher" | Yes, as `platform: "zns"` | see zns-oa-templates.md |
| "Tin nhắn chào mừng sau khi Follow OA" | Yes, as `platform: "oa"` | see zns-oa-templates.md |

**On state variants.** Loading, error and offline states are not separate screens here. The one
exception is a state that changes the *business* answer rather than the UI: the losing branch of
a lucky draw, an empty voucher wallet, a rejected HCP verification. Those carry information a
client needs to approve; a spinner does not.
