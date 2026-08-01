---
name: wireframe-fidelity-rules
description: >
  How much detail belongs in a low-fidelity wireframe versus a visual design, how to represent
  an unspecified region honestly with the placeholder block, how much content each block should
  carry, and the self-check before emitting. Activate when the proposal is thin on UI detail and
  the temptation is either to invent content or to under-draw the journey. Explains the
  structure-versus-content distinction that decides which of those two is the real risk.
---

# Wireframe Fidelity — what to draw and what to leave open

## PRINCIPLE

This wireframe goes into a **preliminary** proposal. Its job is to make the described journey
concrete enough for a client to say "yes, that's the flow" or "no, we need a step before that".

There are two ways to fail that, and they pull in opposite directions:

- **Inventing content.** A made-up price, tier name or branch list gets approved on false
  premises, and the gap surfaces later as scope disagreement. The rep presenting this deck did
  not design these screens and cannot defend an invented figure when the client asks about it.
- **Under-drawing structure.** A journey compressed into three flat screens does not read as a
  product. The client cannot approve a flow they cannot picture, and the estimate attached to it
  stops being credible.

The resolution is the same rule stated two ways: **structure is inference, content is
quotation.** Draw the screens and regions the journey implies. Fill them only with what the
proposal says, and mark the rest openly.

The test for any string you emit: **could the rep point at the proposal and show where this
came from?** The test for any screen you draw: **would the client be surprised this screen
exists?** A QR screen at the end of a redemption journey surprises nobody. A pricing tier the
proposal never mentioned surprises everybody.

---

## WHAT LOW-FIDELITY MEANS HERE

| Draw | Do not draw |
|---|---|
| Block structure and reading order | Colours, gradients, shadows, brand styling |
| Real labels, prices, tier names from the proposal | Invented copy that "sounds right" |
| The regions where images and QR codes go | Actual imagery, icon systems, real codes |
| 2–4 list/grid items showing the pattern | Ten rows to fill the screen |
| Every user-facing step the journey names or implies | Loading, error and offline states |
| The business-meaningful states (losing draw, empty wallet, rejected verification) | One screen per UI state of the same step |

The renderer draws `placeholder`, `banner` and `grid` image regions as dashed boxes precisely so
a client reads them as "to be defined" rather than as decisions already made. Use that — a
dashed region is not an admission of ignorance, it is the correct notation.

---

## THE PLACEHOLDER BLOCK IS THE POINT

`{"kind":"placeholder","label":"..."}` is the correct output for a region the proposal implies
but does not specify. Compare:

| Proposal says | Wrong (invented) | Right (honest) |
|---|---|---|
| "hiển thị danh sách chi nhánh" | a `list` of three made-up branch names and addresses | `{"kind":"placeholder","label":"Danh sách chi nhánh"}` |
| "banner khuyến mãi ở trang chủ" | `banner` with text "Giảm 50% toàn bộ sản phẩm" | `banner` with text "Banner khuyến mãi" |
| "màn hình có mã QR để nhân viên quét" | `qr` with a fabricated code "VNM-8829-XK" | `qr` with the label from the proposal and no `code` |
| "form thu thập thông tin khách hàng" | six fields: email, DOB, address, gender… | only the fields the proposal names, plus a `placeholder` labelled "Trường bổ sung theo yêu cầu" if it says "và các thông tin khác" |
| "khách được tặng voucher" (no value given) | `voucher` with value "50K" | `voucher` with `title` from the proposal and no `value` |

Note the pattern in the last three rows: **draw the specific block, omit the invented field.**
A `qr` block with no code still communicates "there is a code here, shown at the counter" —
which is the structural fact the client needs to approve. Downgrading it to a bare
`placeholder` throws that away, and inventing a code fabricates data. Omitting the field is
the third option, and it is the right one.

Label a `placeholder` with *what belongs there*, in the proposal's language, so a designer
picking this up knows what to fill in.

---

## HOW MUCH TO PUT IN A BLOCK

- **`text` with `style: "body"`** — one or two sentences maximum. Long paragraphs do not survive
  rendering at wireframe scale and get cropped in the deck slide.
- **`list.items` / `grid.items` / `carousel.items`** — 2 to 4. The collection demonstrates a
  repeating pattern; the fifth item adds nothing the third did not establish.
- **`card.rows` / `sheet.rows`** — 2 to 4. Eight rows is a table, and a table in a mobile
  wireframe means the screen has not been decomposed properly.
- **`stats.items`** — 2 to 4. Four is already a crowded row at 375px.
- **`chips.items` / `tabs.items`** — 2 to 4. Five chips overflow the screen (deliberately, to
  read as scrollable), but five *tabs* just look broken.
- **`steps.items`** — 2 to 5. A six-step vertical stepper does not fit above the fold.
- **`cta.text`** — max 5 words, imperative, in the proposal's language. "Đổi điểm ngay", not
  "Nhấn vào đây để tiến hành đổi điểm của bạn".
- **`hero.progress` / `progress.value`** — a real fraction between 0 and 1, derived from figures
  the proposal gives (750 of 1000 points to the next tier → 0.75). If the proposal gives no
  figures, omit `progress` rather than picking a number that looks good.
- **blocks per screen** — 5 to 9 for `miniapp`, 3 to 5 for `zns` and `oa`.
- **screens per journey** — 6 to 12. Below 5 the journey has been compressed; above 12 you are
  drawing states.

---

## WHEN THE PROPOSAL HAS ALMOST NO UI DETAIL

This happens, and it has a correct answer. Work down this list:

1. **Is there a journey in Section 3?** Its steps give you screen boundaries even when no screen
   contents are described. Draw the full archetype inventory for that journey type (see
   zalo-miniapp-patterns.md), using the specific blocks each archetype calls for and
   `placeholder` where content is unspecified. This is a genuinely useful wireframe: the
   structure is real and the gaps are openly marked. **Do not shrink the journey because the
   detail is thin** — thin detail is an argument for more `placeholder`, not fewer screens.
2. **Is there a touchpoint/messaging map but no journey?** Draw the messaging surfaces only. ZNS
   and OA templates are highly structured, so they survive thin input better than app screens do
   (see zns-oa-templates.md).
3. **Neither?** Output `{"meta": {...}, "screens": []}`. There is nothing to draw, and the
   caller reports exactly that: the proposal needs its solution section developed before
   wireframing. Inventing an app to avoid an empty array converts a visible gap into an
   invisible one.

---

## SELF-CHECK BEFORE EMITTING

Structure:
- [ ] 6–12 screens for a full journey; every user-facing step in Section 3 has a screen
- [ ] The counter artefact screen exists if anything is redeemed in person (`qr`)
- [ ] A `collection` screen exists if the user accumulates anything (vouchers, orders, bookings)
- [ ] No screen for a system event, a staff action, an admin dashboard, or a backend integration
- [ ] 5–9 blocks per `miniapp` screen — no screen is just heading + list + button

Block choice:
- [ ] Every `kind` is one of the 25 in the vocabulary
- [ ] The most specific available block is used for each region (`hero` not `card` for the member
      header; `voucher` not `list` for an owned discount; `qr` not `placeholder` for a counter code;
      `grid` not `list` for visual tiles; `steps` not `list` for status over time)
- [ ] `appbar` first; `tabbar` only on top-level destinations, and last
- [ ] At most one `primary` CTA per screen
- [ ] No `zns` screen carries `tabbar`, `tabs`, `list`, `field`, `grid`, `carousel`, `chips`,
      `timeslot`, `toggle`, `sheet`, `hero` or `empty`

Content:
- [ ] Every price, tier, points figure, voucher value, code, branch name and message body traces
      to proposal text
- [ ] Zero literal placeholder strings (`TBD`, `N/A`, `[...]`, `undefined`, `""`) in any field —
      omit the field instead
- [ ] Unspecified regions use `placeholder`, or the specific block with the unknown field omitted
- [ ] `progress` values derive from real figures, or are absent
- [ ] Vietnamese diacritics correct, no doubled tone marks
- [ ] No Zalo Ads surface anywhere; no password, email-verification or OTP-entry field
