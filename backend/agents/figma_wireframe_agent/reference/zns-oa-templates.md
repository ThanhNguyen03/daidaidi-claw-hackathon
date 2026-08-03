---
name: zns-oa-wireframe-templates
description: >
  ZNS notification template structure and Zalo OA message surfaces — what a transactional ZNS
  may and may not contain, how an OA message differs from a Mini App screen, and which
  journey touchpoints become a message rather than a screen. Activate when the journey
  includes a messaging touchpoint (ZNS reminder, OTP, order update, OA broadcast, welcome
  message). Do NOT use for Mini App screen composition → see zalo-miniapp-patterns.md.
---

# ZNS & Zalo OA — Wireframe Templates

## PRINCIPLE

A ZNS is not a screen. It is a template Zalo renders inside the user's chat list, and its
shape is fixed by the platform — you are filling slots, not designing a layout. The most
common wireframe error is drawing a ZNS as if it were an app screen: a tabbar, a search
field, or a scrolling list of offers inside a notification is not a thing that can exist.

A ZNS also cannot be promotional in the way a banner can. ZNS is transactional by policy:
it fires because the user did something, and its content must relate to that action.
Wireframing a "flash sale 50%" ZNS blast misrepresents what the platform permits — that is
an OA broadcast, a different surface with different rules.

---

## ZNS TEMPLATE — the fixed slot structure

Use `platform: "zns"` and keep it short. The canonical composition:

```
appbar    (title = the OA / brand name — this is the sender strip, back: false)
text      (heading — the notification subject line, max 8 words)
card      (rows = 2-4 transaction details, label/value pairs)
note      (expiry, terms, or a "không hoàn tác" caveat — tone "info", optional)
cta       (at most one, usually secondary — "Xem chi tiết" opening the Mini App)
```

Three blocks beyond that composition are legitimate in a ZNS, and each replaces the `card`
rather than joining it:

- **`voucher`** — when the ZNS *is* the voucher being issued. The ticket shape carries value,
  condition and expiry in one object, which is exactly a voucher-issued notification.
- **`qr`** — when the notification itself is what the user shows at a counter. Rare but real:
  some redemption flows deliver the code by ZNS instead of in the Mini App.
- **`steps`** — for an order or booking status update, where the point of the message is
  *where in the process this is*. Two to four steps, the current one the last `done: true`.

`progress` and `stats` are permitted but rarely right — a notification is a moment, not a
dashboard.

Hard rules for a `zns` screen:

| Never in a ZNS | Why |
|---|---|
| `tabbar`, `tabs` | A notification has no navigation destinations and no in-screen state split |
| `list`, `grid`, `carousel` | ZNS renders a fixed template, not a scrolling or browsable collection |
| `field`, `toggle`, `timeslot` | No input of any kind inside a notification |
| `chips` | Filtering implies a collection to filter |
| `sheet` | An overlay needs a screen to overlay |
| `hero` | The member header belongs to the app, not to a message about one transaction |
| `empty` | A notification with nothing in it would not have been sent |
| More than one `cta` | The template allows a single action button |
| `banner` as a promo hero | ZNS is transactional; a promo hero belongs to an OA broadcast or a Mini App screen |

The renderer enforces this list by dropping those blocks from a `zns` screen, so emitting one
does not produce a warning — it silently loses the region you meant to fill.

The `card.rows` are the whole point of a ZNS — they are the figures the user opens the
notification to check. Every one must be real:

```
Mã đơn hàng      | #DH-48219
Số điểm cộng     | + 120 điểm
Số dư hiện tại   | 1.250 điểm
Hạn sử dụng      | 31/08/2026
```

---

## THE FIVE ZNS TYPES THAT APPEAR IN ADTIMABOX JOURNEYS

| Type | Fires when | Carry it with | Content |
|---|---|---|---|
| Points credited | A purchase or action earns points | `card` | amount credited, new balance, source transaction |
| Voucher issued | A redemption completes | `voucher` | value, condition, expiry, code |
| Expiry reminder | A voucher or point balance is about to lapse | `voucher` or `card` + `note` (tone "warning") | what expires, when, current value |
| Booking / order confirmation | A booking or order is placed | `card`, or `steps` when status is the point | reference code, time/slot, location, total |
| OTP | Identity confirmation is needed | `card` with one row | the code and its validity window — nothing else |

An OTP ZNS carries **only** the code and its expiry. No CTA, no branding line, no
cross-sell, no `voucher`, no `qr`. Drawing anything else in an OTP template is a compliance
problem, not a design choice.

---

## ZALO OA MESSAGE — `platform: "oa"`

An OA message is a chat surface: the brand's Official Account talking to the user in a
thread. It permits more than ZNS (richer content, promotional messages within policy and
frequency limits) but it is still a chat bubble, not an app screen.

Canonical composition:

```
appbar    (title = the OA name, back: true — the user is inside a chat thread)
banner    (the message's image/hero slot — dashed placeholder in low-fi)
text      (body — the message copy, from the proposal)
note      (a policy or frequency caveat, when the proposal states one — optional)
cta       (primary — the button attached to the message, usually opening the Mini App)
cta       (secondary — a second quick-reply, only if the proposal describes one)
```

Rules:

- Quick-reply buttons are `cta` blocks, not a `list` and not `chips`. Two is a normal maximum.
- No `field`: the user replies in the chat input, which is platform chrome and not part of
  the message you are wireframing.
- No `tabbar`, `tabs`, `grid`, `timeslot`, `toggle` or `sheet` — all of those belong to an app
  screen. A `voucher` is acceptable when the message delivers one.
- No `hero`: an OA message about one thing is not the member dashboard.
- A welcome message (fired when the user follows the OA) is the most common OA touchpoint in
  an AdtimaBox journey, and it is where the Mini App entry CTA lives.

---

## WHICH TOUCHPOINTS BECOME A MESSAGE

| The journey / touchpoint map says… | Draw as |
|---|---|
| "Gửi ZNS nhắc hạn voucher" | `zns` — expiry reminder |
| "ZNS xác nhận đơn hàng" | `zns` — order confirmation |
| "ZNS OTP xác thực số điện thoại" | `zns` — OTP, code and expiry only |
| "Tin nhắn chào mừng sau khi Follow OA" | `oa` — welcome message with Mini App CTA |
| "Gửi tin OA thông báo campaign mới" | `oa` — broadcast |
| "Push notification trong Mini App" | `oa` if it renders in the chat; skip if it is an in-app toast (not a wireframable surface) |
| "Email xác nhận" | Skip — not a Zalo surface, and not something Adtima delivers |
| "SMS OTP" | Skip — outside the Zalo ecosystem |

A journey with three Mini App screens and one ZNS reminder is a complete, honest wireframe
set. Do not add messaging screens the touchpoint map does not describe just to make the
output look fuller — an invented ZNS is an invented compliance obligation.
