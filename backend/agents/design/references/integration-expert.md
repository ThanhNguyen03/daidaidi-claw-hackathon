---
name: adtimabox-integration
description: >
  AdtimaBox integration advisor — activate when a client mentions an existing tech platform (POS, CRM, e-commerce, loyalty, messaging) and the agent needs to assess how it interacts with AdtimaBox. For known platforms, load the specific platform skill (platform-haravan, platform-kiotviet). For unknown platforms, this skill provides a research and assessment framework. Triggers: "client uses [platform]", "they already have loyalty", "have their own CRM", "currently using [software]".
---

# AdtimaBox Integration Advisor

**Scope:** Assess how any 3rd party platform interacts with AdtimaBox.

**For known platforms → load the specific platform skill first:**

* Haravan → `platform-haravan`
* KiotViet → `platform-kiotviet`
* More to be added as confirmed by Adtima tech team

**For unknown platforms → follow the research framework below.**

---

## ADTIMABOX CAPABILITY ANCHORS

These AdtimaBox always owns — no 3rd party replaces them:

| Capability | Why |
|-|-|
| Zalo MiniApp branded experience | No other platform builds on Zalo MiniApp |
| ZBS Automation journey | Complex trigger-based Zalo messaging journeys |
| Loyalty tier + reward catalog on Zalo | Unless client platform has equivalent |
| Zalo OA follower sync + behavior segmentation | Only through Zalo ecosystem |

---

## RESEARCH FRAMEWORK (for unknown platforms)

**Step 1: Web search**

```
"[platform name] Zalo ZNS integration"
"[platform name] loyalty Vietnam"
"[platform name] API webhook"
"[platform name] CRM member management Vietnam"
```

**Step 2: Answer 5 key questions**

1. Does it send Zalo messages (ZNS / broadcast)? What types?
2. Does it have loyalty? (points, tier, rewards?)
3. Does it have API/webhook to push data out?
4. Does it capture customer phone number?
5. Does it have its own branded mobile experience?

**Step 3: Assess across 5 dimensions**

| Dimension | Question | If YES | If NO |
|-|-|-|-|
| Messaging | Sends Zalo ZNS/broadcast? | Define boundary — who sends what | AdtimaBox owns all Zalo messaging |
| Loyalty | Has points/tier/rewards? | Migrate or sync? | AdtimaBox owns loyalty |
| CRM | Stores customer profiles? | Who is master record? | AdtimaBox is CRM |
| Transaction data | Records purchases + phone? | Push via API for point earning | Need bridge: UTC / Scan Bill / manual |
| Mobile experience | Has own app/mini program? | Consolidate or keep both? | AdtimaBox MiniApp is primary touchpoint |

**Step 4: Output**

```
PLATFORM ASSESSMENT: [Platform name]
Source: [URL searched]

What [platform] does in client's current flow: ...
What AdtimaBox REPLACES: ...
What AdtimaBox ADDS: ...
Overlap to clarify: ...
Recommended integration pattern: ...
Needs tech confirmation: ...
```

---

## INTEGRATION PATTERNS

**Pattern A — Platform as data source, AdtimaBox as Zalo engagement layer**

```
[POS/CRM/E-commerce] → pushes transaction/member data via API
→ AdtimaBox: loyalty + messaging + MiniApp
```

*Use when: client has transactional system but no Zalo layer*

**Pattern B — AdtimaBox as data collector, export to brand's CRM**

```
AdtimaBox collects Zalo data
→ exports to brand CRM via integration add-on (25–50M)
```

*Use when: client has enterprise CRM, wants AdtimaBox data fed in*

**Pattern C — Parallel systems with defined boundaries**

```
Platform A: orders / payments / transaction ZNS
AdtimaBox: loyalty / engagement ZNS / MiniApp
API bridge: transaction data → point earning
```

*Use when: both systems have overlapping capabilities*

---

## RED FLAGS — ALWAYS ESCALATE

* Platform sends Zalo ZNS → define messaging boundary before proposing
* Platform has own loyalty → decide: replace or sync; never run two loyalty programs without clear user logic
* POS doesn't capture phone number → loyalty from that channel not possible
* Client wants real-time sync → confirm AdtimaBox API can handle volume
* Custom-built platform → no standard connector; confirm feasibility with tech lead
* Legacy data import → always check consent first (→ `adtimabox-data-consent`)
