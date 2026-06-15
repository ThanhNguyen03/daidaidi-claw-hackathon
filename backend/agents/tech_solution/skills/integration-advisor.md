\---

name: adtimabox-integration
description: >
AdtimaBox integration advisor — activate when a client mentions an existing tech platform (POS, CRM, e-commerce, loyalty, messaging) and the agent needs to assess how it interacts with AdtimaBox. For known platforms, load the specific platform skill (platform-haravan, platform-kiotviet). For unknown platforms, this skill provides a research and assessment framework. Triggers: "client uses \[platform]", "they already have loyalty", "have their own CRM", "currently using \[software]".
---

# AdtimaBox Integration Advisor

**Scope:** Assess how any 3rd party platform interacts with AdtimaBox.

**For known platforms → load the specific platform skill first:**

* Haravan → `platform-haravan`
* KiotViet → `platform-kiotviet`
* Salesforce → see "KNOWN PLATFORM: SALESFORCE CRM" section below
* More to be added as confirmed by Adtima tech team

**For unknown platforms → follow the research framework below.**

\---

## ADTIMABOX CAPABILITY ANCHORS

These AdtimaBox always owns — no 3rd party replaces them:

|Capability|Why|
|-|-|
|Zalo MiniApp branded experience|No other platform builds on Zalo MiniApp|
|ZBS Automation journey|Complex trigger-based Zalo messaging journeys|
|Loyalty tier + reward catalog on Zalo|Unless client platform has equivalent|
|Zalo OA follower sync + behavior segmentation|Only through Zalo ecosystem|

\---

## RESEARCH FRAMEWORK (for unknown platforms)

**Step 1: Web search**

```
"\[platform name] Zalo ZNS integration"
"\[platform name] loyalty Vietnam"
"\[platform name] API webhook"
"\[platform name] CRM member management Vietnam"
```

**Step 2: Answer 5 key questions**

1. Does it send Zalo messages (ZNS / broadcast)? What types?
2. Does it have loyalty? (points, tier, rewards?)
3. Does it have API/webhook to push data out?
4. Does it capture customer phone number?
5. Does it have its own branded mobile experience?

**Step 3: Assess across 5 dimensions**

|Dimension|Question|If YES|If NO|
|-|-|-|-|
|Messaging|Sends Zalo ZNS/broadcast?|Define boundary — who sends what|AdtimaBox owns all Zalo messaging|
|Loyalty|Has points/tier/rewards?|Migrate or sync?|AdtimaBox owns loyalty|
|CRM|Stores customer profiles?|Who is master record?|AdtimaBox is CRM|
|Transaction data|Records purchases + phone?|Push via API for point earning|Need bridge: UTC / Scan Bill / manual|
|Mobile experience|Has own app/mini program?|Consolidate or keep both?|AdtimaBox MiniApp is primary touchpoint|

**Step 4: Output**

```
PLATFORM ASSESSMENT: \[Platform name]
Source: \[URL searched]

What \[platform] does in client's current flow: ...
What AdtimaBox REPLACES: ...
What AdtimaBox ADDS: ...
Overlap to clarify: ...
Recommended integration pattern: ...
Needs tech confirmation: ...
```

\---

## INTEGRATION PATTERNS

**Pattern A — Platform as data source, AdtimaBox as Zalo engagement layer**

```
\[POS/CRM/E-commerce] → pushes transaction/member data via API
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

\---

## KNOWN PLATFORM: SALESFORCE CRM

**Platform context:** Enterprise CRM used by multinational brands (particularly pharma, FMCG, financial services) as the system of record for customer/HCP data, sales force automation, and campaign orchestration.

**Platform Assessment: Salesforce**

```
What Salesforce does in client's current flow:
- Stores HCP/customer master records (personal data, specialty, hospital affiliation, level)
- Manages MedRep (sales rep) call records and follow-up tasks
- Runs email marketing sequences
- Stores event registration and attendance data
- Triggers RMA (Remote Medical Activities) follow-up workflows
- Serves as the compliance-grade data store for regulated industries

What AdtimaBox REPLACES (in Zalo layer):
- Zalo channel communication (OA broadcast, ZNS, personalized messages)
- MiniApp branded experience (content hub, event hub, digital activities)
- Zalo-side HCP segmentation labels

What AdtimaBox ADDS (on top of Salesforce):
- Zalo engagement layer (reach HCPs where they are daily)
- Behavioral data from Zalo: content views, article engagement, event check-in, quiz participation
- HCP acquisition via Zalo (new HCPs not yet in Salesforce whitelist)

Overlap to clarify:
- Member master record: Salesforce is master; AdtimaBox is Zalo sub-record
- Event management: AdtimaBox handles Zalo-side event registration + check-in; Salesforce retains attendance records
- Messaging: Salesforce handles email; AdtimaBox handles all Zalo messages (no duplication)

Recommended integration pattern: Pattern D (two-way sync — see below)

Needs tech confirmation:
- Salesforce API endpoint availability and auth method (OAuth2 / API key)
- Real-time vs batch sync requirement
- Field mapping: which Zalo behavioral data maps to which Salesforce object
- Salesforce edition (data volume limits differ across Enterprise / Unlimited / Professional)
- Engineering resource availability on client side
```

**Pattern D — Two-Way Sync: Enterprise CRM ↔ AdtimaBox (Pharma / B2B HCP use case)**

```
Salesforce → AdtimaBox:
  - Push: HCP whitelist (phone numbers of pre-approved HCPs)
  - Push: Existing member records (for onboarding pre-fill and label setup)
  - Push: Approval decisions for new HCP registrations

AdtimaBox → Salesforce:
  - Push: All raw data logs from MiniApp and OA
    (registration data, event check-in, content engagement, message interaction, survey responses)
  - Trigger: Post-registration new member data
  - Trigger: Post-event attendance log
  - Trigger: Behavioral segments for follow-up automation in Salesforce
```

*Cost: Integration add-on 25–50M VND (scoped case by case)*
*Constraint: Salesforce-side engineering required; AdtimaBox Tech Team must assess before committing*
*Compliance: All data onshore; processed with HCP consent per Decree 13/2023/NĐ-CP*

---



* Platform sends Zalo ZNS → define messaging boundary before proposing
* Platform has own loyalty → decide: replace or sync; never run two loyalty programs without clear user logic
* POS doesn't capture phone number → loyalty from that channel not possible
* Client wants real-time sync → confirm AdtimaBox API can handle volume
* Custom-built platform → no standard connector; confirm feasibility with tech lead
* Legacy data import → always check consent first (→ `adtimabox-data-consent`)

