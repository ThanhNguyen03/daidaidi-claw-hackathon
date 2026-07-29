# AdtimaBox Sales Agent — working notes

Multi-agent assistant that turns a sales rep's client brief into a preliminary
proposal for the Zalo ecosystem: strategy, solution design, compliance read,
pricing, and a branded HTML deck plus PPTX.

Live: **https://zah-28.123c.vn** · deploy with `bash deploy/deploy.sh`

---

## Ground truth about the architecture

Three documents describe this system and **only the code is accurate**. If you are
adding to any of them, reconcile rather than adding a fourth story:

| Source | What it claims |
|---|---|
| `README.md` | 7 agents with names matching nothing, including a "Client Data Masking Agent" that does not exist |
| `docs/workflow.jpg` | A 9-agent A1–A9 pipeline with an AE review step |
| **the code** | 7 skills, listed below |

The 7 skills registered in `backend/skills/registry.py`:

```
market_strategy      product_solution     compliance      client_simulator
design               proposal_assembler   wireframe_designer
```

`central_agent/` is the orchestrator — it is not a skill and is not in the registry.

### Request flow

```
POST /chat/stream
  ↓ pii/masking.py         mask before anything reads the message
  ↓ central_agent._plan    one LLM call: intent + brief extraction + skill plan
  ↓ gate.py                pure code: may we dispatch?
  ↓ Chốt 1                 confirm the brief (brief intent only)
  ↓ skills, in parallel groups
  ↓ Chốt 2                 confirm the direction, before rendering
  ↓ proposal_assembler + wireframe_designer
  ↓ _synthesize            streams the final answer
```

### Where a conversation lives

Two SQLite files, each with a table called `sessions`, and they are not the same thing:

| File | Written by | Holds |
|---|---|---|
| `data/app.db` | `database.py` | users, org rules, and the transcript the history sidebar lists — `messages_json`, brief, constraints |
| `data/sales_assistant.db` | `repos/memory_repo.py` | the whole serialised `SalesCaseState`, skill outputs included. Much the larger of the two |

`GET /user/sessions` reads the first; a resumed turn loads state from the second. So
anything that removes a conversation has to remove it from **both**, plus
`_session_store`, plus the PII alias table, plus the deck/PPTX files in
`data/artifacts/`. That is what `main.py:_purge_session_everywhere` is for — the
`DELETE /user/sessions[/{id}]` endpoints and the trash buttons in the sidebar both go
through it, and both `VACUUM` afterwards because a SQLite `DELETE` alone does not
shrink the file.

`DELETE /sessions/{id}` is the old endpoint and only drops the in-memory entry. The
history UI does not use it.

---

## Invariants — do not route around these

**The gate is code, not a prompt.** `backend/gate.py` decides whether specialist
skills may run. Three states: `CHAN_HOI_LAI` / `CHAY_CO_PHONG_DOAN` /
`CHAY_DAY_DU`. There is deliberately no parameter, config key or env var that
skips it. The only opt-out is the rep saying "cứ làm đi", and even then the
missing fields become labelled assumptions rather than disappearing.

This exists because the previous version put the check inside a prompt. When the
planner call 401s it falls back to "defaulting to execute mode" — and without the
gate that dispatched every skill against an empty brief.

Which fields are guarded is data in `backend/config/gate_fields.yaml`, editable
without a deploy. That the gate runs is not.

**PII masking is a system component.** `backend/pii/masking.py` runs at the top of
the request, before intent classification and before any model call. The spec in
`agents/sales_orchestrator_agent/reference/data-masking.md` places it after brief
validation; we run it earlier, because a validating agent has already read the raw
PII by then. Alias tables live in memory keyed by session and are deliberately kept
out of `SalesCaseState`, which is serialised to SQLite. Logs carry counts and
kinds, never values.

**One function reads knowledge.** `backend/knowledge/loader.py`. Skills never open
a reference file. Each `SKILL.md` declares its references in a "Reference Skills
List" table; a cheap selector call picks which the task needs and the whole file is
injected. Caches by mtime, dedupes per request by content hash, enforces a
character budget and logs what it dropped, and raises rather than letting a model
answer from general knowledge when a read fails.

There is no vector search on this path. At ~250KB of corpus a declared lookup table
is more accurate and far easier to debug — you can read the log and see exactly
what the model was given. `KB_VECTOR_ENABLED=true` re-enables the old LanceDB
ingest, but nothing needs it.

**Instruction is not enforcement.** The planner is told not to build deliverables
for a lookup or a coaching turn. It classifies correctly and plans an assembler
anyway. Render skills are stripped in code after the plan comes back.

**The deck renders the assembler's output, so it runs after it.** `proposal_assembler`
and `wireframe_designer` get one plan group each, in `_SEQUENTIAL_ORDER`. They used to
share a group, justified as "the deck should not wait for the assembler" — it waited
anyway (`LLM_MAX_CONCURRENCY=1` serialises the pair) and `previous_outputs` is
snapshotted before a group runs, so the deck could never see the assembler no matter
who finished first. It fell back to the raw analysis outputs, and thin input does not
make a thin deck: extraction is told to skip any slide it has no source for, so it
returned one cover slide.

Four code paths arrange that plan. The arrangement pass at the end of `_plan` is the
last word — it used to collapse every sequential skill into a single final group and
silently undid the other three.

**The proposal document has exactly one section scheme: 7 sections, defined in
`proposal_assembler_agent/SKILL.md` and mirrored exactly in
`wireframe_designer_agent/SKILL.md`'s slide map** (Section 5 = Compliance, Section 6 =
Investment — the deck's compliance gate keys off "SECTION 5" verbatim, so the two
files cannot drift). `product_solution` owns the journey and Mermaid diagram in
Section 3 on every turn; `design` only contributes there when the rep explicitly asked
for design artifacts, and never duplicates what `product_solution` already produced.
The synthesizer's own non-assembled fallback answer (when there is no formal
`proposal_assembler` output to stream) uses the same 7-section shape for consistency,
even though it is a different code path and not read by the deck extractor.

**Compliance emits one machine-readable token, and everything reads the same one.**
`compliance/skill.py` requires a `VERDICT: CLEAR|CONDITIONS|BLOCKED` line — exactly
that word, alone on its line — and regex-extracts it into `payload["verdict"]`. This
existed as three different spellings before ("CLEAR TO PROCEED", "PROCEED WITH
CONDITIONS", a bare "CLEAR / CONDITIONS / BLOCKED" in the same reference file
contradicting its own template 114 lines up) and nothing downstream could gate on any
of them despite the SKILL.md's workflow claiming to "gate downstream." An unrecognised
or missing verdict defaults to `CONDITIONS`, never `CLEAR` — an unreadable verdict
should read as "not fully cleared."

---

## Adding a skill

1. `backend/agents/<name>_agent/SKILL.md` — role, workflow, and a **Reference Skills
   List** table. The loader parses that table; a skill without one gets no knowledge.
   Fill the Purpose column with something real — the selector has nothing else to go on.
2. `backend/agents/<name>_agent/reference/*.md`
3. `backend/skills/<name>/skill.py`, subclassing `BaseSkill`
4. Register in `backend/skills/registry.py`
5. Map the directory in `knowledge/loader.py:AGENT_DIRS` **and**
   `tools/ingest.py:AGENT_SOURCE_PRIORITY`
6. Add `MODEL_<NAME>` to `llm/greennode.py:MODEL_MAPPING`

Hard constraints belong in `SKILL.md`, not in a reference — a reference may not be
selected. The "Zalo Ads is not in the portfolio" rule is the example: it went
missing once and the agent started quoting CPM for a product Adtima does not sell.

---

## Provider configuration

Runs on Google Gemini through its OpenAI-compatible endpoint. `llm/greennode.py`
speaks plain OpenAI, so switching provider is env-only.

```
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_REASONING_EFFORT=low
LLM_MAX_CONCURRENCY=1
LLM_RETRY_ATTEMPTS=6
LLM_RETRY_MAX_WAIT_S=60
TURN_BUDGET_S=600
```

**`LLM_MAX_CONCURRENCY` is enforced twice, and both are needed.** `llm/client.py`
holds a threading semaphore around every completion — that is what protects the
provider. `central_agent/agent.py` holds an asyncio one around every *skill* — that
is what makes the per-skill timeout mean anything. Without the second, a group's
skills all started their 270s clock at task-creation time while only one could talk
to the provider, so the ones at the back of the queue expired having sent no request
at all. See the entry in "Bugs that bit us".

**`TURN_BUDGET_S` bounds the analysis phase**, because serialised admission removed
the accidental bound that the spurious timeouts used to provide. Once it is spent the
queued analysis skills are skipped, announced as skipped, and the answer is built
from what finished. `proposal_assembler` and `wireframe_designer` are exempt — they
are the deliverable, and skipping one of those means the rep waited out the whole
budget for nothing.

**Every LLM call runs on its own thread pool (`llm/pool.py`), separate from the
default executor `asyncio.to_thread` uses for DB and file I/O.** `llm/client.py`'s
`_INFLIGHT` semaphore parks a worker thread for the whole time it waits on a slot, and
the synthesis stream worker holds one for an entire token stream — on the default
pool (`min(32, cpu+4)`, as few as 6 threads on a 2-vCPU box) that was enough to starve
session saves and deck writes queued behind them. Concurrency at the provider is still
capped at `LLM_MAX_CONCURRENCY` either way; only which pool the waiting happens on
changed. The default executor itself is widened in `lifespan` (`IO_POOL_WORKERS`,
default 16) for the same reason, on the DB/file side.

Measured on this key's free tier — do not re-litigate these without re-measuring:

| Model | Result |
|---|---|
| `gemini-3.6-flash` | 200 in ~2.1s — the workhorse |
| `gemini-3.5-flash-lite` | 200 in ~1.4s — planner, selector, deck extraction |
| `gemini-3.1-pro-preview` | **429 immediately.** Pro is unusable on free tier |
| `gemini-2.5-flash` | **404** despite being listed by `/v1beta/openai/models` |

**`LLM_REASONING_EFFORT=low` is load-bearing.** Gemini 3.x reasons by default and
draws those tokens from the same `max_tokens` budget as the answer. Without it the
planner prompt never returned inside 150s, and `gemini-3.5-flash` came back
`finish_reason: length` having produced nothing.

**The project moved to paid Tier 1 on 2026-07-28** (billing linked, $250/mo cap).
Tier 1 ceilings for the models this app uses are roughly 50-500x the free-tier ones
below — `gemini-3.6-flash` alone went from 5 RPM/20 RPD to 1,000 RPM/10,000 RPD.
`config/model_limits.yaml` has been updated to the Tier 1 numbers (read off AI
Studio's Rate Limit page, the same way the originals were). The paragraphs below
describe the free-tier regime the concurrency/retry/fallback settings were designed
against; nothing about those settings changed with the upgrade — Tier 1 makes them
more conservative than necessary, not wrong, and loosening `LLM_MAX_CONCURRENCY` or
`LLM_FALLBACK_MODELS` is a deliberate decision to make later, not a side effect of
updating the quota display. One thing the upgrade *does* explain: `out_of_quota_today`
firing right after the upgrade was chasing the old free-tier ceiling, not a real
Tier-1 problem — AI Studio's own 28-day peak-usage chart for this project never
showed more than 25 RPD on `gemini-3.6-flash`, well under either ceiling.

**Rate limits were the main operational risk on free tier.** A full proposal turn
fans out to planner, selectors, four specialists, assembler and synthesis. Six
concurrent requests draw a 429 on free tier; a whole run produced 28 of them and
failed four skills. Hence concurrency 1 and the long retry ceiling — kept as-is
after the Tier 1 upgrade until there's a reason to re-measure and loosen them.

**Requests-per-day was the limit that actually stopped a demo on free tier, and
retrying could not fix it.** Measured 2026-07-26: `gemini-3.6-flash` at 25/20 RPD
while `gemini-3.5-flash-lite` sat at 246/500, and the five skills pinned to
3.6-flash all failed while the two on flash-lite sailed through. So
`LLM_FALLBACK_MODELS` moves a call to the next model once one is spent, and the 429
body is read to tell a per-minute limit (wait it out) from a per-day one (switch
immediately — six attempts across three models would hit the 270s skill timeout
before reaching the last). Both mechanisms stay in place post-upgrade; they just
fire far less often now.

```
LLM_FALLBACK_MODELS=gemini-3.5-flash-lite,gemini-3.5-flash
```

Which model each skill is on, what has been spent, and a picker to move a skill — or
everything — elsewhere: `GET /models`, `POST /models/select`, and the Model & Quota
panel behind the CPU icon in the sidebar. `agent_status` events carry the model that
actually served the call, which is the only way to see a fallback having fired.

The usage figures are **counted by this app**, in `llm/usage.py`. Google exposes no
API for remaining quota — AI Studio's Rate Limit page is not reachable from code — so
the ceilings are declared in `config/model_limits.yaml` (editable without a deploy,
like `gate_fields.yaml`) and every count is a lower bound: the same key used from a
browser is invisible here. The exception is the `out_of_quota_today` state, which is
read straight out of a 429 that named a per-day limit.

An override from the panel is in memory only and dies with the container. That is
deliberate — it exists to get through the next few turns, while `MODEL_<NAME>` in
`.env.production` stays the source of truth.

---

## Deployment

`deploy/deploy.sh` ships a tarball over SSH — the server **cannot reach the
internal GitLab host**, though github.com resolves fine, so a server-side `git
pull` is not an option. `.gitlab-ci.yml` calls the same script so CI and a laptop
deploy cannot drift.

```bash
bash deploy/deploy.sh              # sync + rebuild changed layers + restart + verify
bash deploy/deploy.sh backend      # one service
bash deploy/deploy.sh --no-build   # config-only change
bash deploy/deploy.sh --logs       # tail live
```

`backend/.env.production` lives only on the server, is gitignored, and is backed up
and restored around extraction so a redeploy cannot clobber the key.

Host is Rocky 9 at `118.102.2.128`, **SSH on port 2222**. Host nginx terminates TLS
with the pre-installed `*.123c.vn` wildcard cert and proxies `/` to the frontend and
`/api/` to the backend; both containers bind to `127.0.0.1` only. See
`deploy/README.md` for the operational detail.

---

## Reading the logs

Every turn should produce this trail. If a line is missing, that stage did not run.

```
[pii]        masked 3 item(s): CONTACT×1, EMAIL×1, PHONE×1
[intent]     lookup
[gate]       CHAY_DAY_DU missing=- reason=intent 'lookup' does not pass through the gate
[plan]       intent=lookup: dropped ['proposal_assembler'] — no deliverable requested
[knowledge]  product_solution: selected ['product-advisor.md']
[knowledge]  turn <session>:<n>: 2 unique doc(s) | reused: domain-knowledge.md×2
[agents]     ran: product_solution
```

`PYTHONUNBUFFERED=1` is set in compose; without it these lines arrive minutes late.

---

## Known dead code

Present, unreferenced, and safe to delete when someone has time. Roughly 1,000 lines.
(`main.py` already lost ~510 lines this way — `_maybe_create_checkpoint`,
`_extract_agent_content`, `process_simple`, the sync `get_or_create_session`, and their
supporting constants/prompt — all provably zero-caller before deletion.)

| Path | Note |
|---|---|
| `validation/validator.py` | No callers. The BRD critiques its `MANDATORY_FIELDS`; `gate.py` supersedes it |
| `mode/brainstorm.py` | Mode is "coming soon" in the UI |
| `generation/pptx.py`, `generation/userflow.py` | Superseded by `pptx_adtimabox.py` and inline Mermaid |
| `kb/ingest.py` | Duplicates `tools/ingest.py` |
| `design/backend.py` | Figma integration, never wired |
| `agents/predict-agent/` | A fortune-telling bot. Off-topic; hide it before judging |

---

## Bugs that bit us, so they are not reintroduced

- **A queued skill was spending its whole timeout in the queue.** Every skill in a
  plan group got its own `asyncio.wait_for(..., 270s)` the moment its task was created,
  but `llm/client.py`'s semaphore let exactly one of them reach the provider. So a
  five-skill group cost 270s *per queued skill* and reported the ones that never ran as
  failures — which is most of what "a run produced 28 rate-limit errors and failed four
  skills" actually was. The clock now starts when a skill is admitted, not when it is
  queued, and the sidebar shows the queued ones as `waiting` rather than `thinking`.
- **Blocking SQLite on the event loop stalls every open stream.** The sidebar polled
  `/user/sessions` every 5s — 12 requests a minute per tab — and the handler read
  sqlite3 synchronously, so each poll froze the SSE stream the rep was watching. The
  list is event-driven now (`session_updated`, fired at both ends of a turn, plus a 60s
  fallback) and every session read and write goes through `asyncio.to_thread`.
  `updated_at` is the last column of a row whose `messages_json` spills to overflow
  pages, so the list query had to walk that chain per row; `idx_sessions_user_updated`
  keeps it out of the row entirely.
- **Both session writes are upserts, so deleting mid-turn resurrected the row.** The
  save at the end of a turn runs long after the rep could have deleted the
  conversation — which is exactly what they do to a turn that looks stuck. A bounded
  tombstone list in `main.py` suppresses that final write, and a new turn on the same
  id retracts the tombstone, because a second tab still using the session outranks the
  delete.
- **The deck HTML was re-serialised into the state row on every later turn.** Same
  shape as the `pptx_bytes` bug below, minus the crash: `html_content` sat in
  `wireframe_designer`'s payload, so a few hundred KB of HTML was rewritten into
  `sales_assistant.db` on every subsequent message, for a string nothing reads again.
  It goes to disk in `ARTIFACTS_DIR` now, like the PPTX beside it, which also means the
  deck link survives a restart instead of 404ing.
- **`pyyaml` is a hard dependency.** `tools/ingest.py` imports it to read
  `config/agents.yaml` and returns `[]` on ImportError — the entire knowledge base
  goes unindexed with only a stdout warning. It was absent from `requirements.txt`
  and worked by accident because `transformers` pulled it in.
- **Never infer a resume from message text.** The UI restarts a paused pipeline by
  sending "Tiếp tục", which is exactly what the casual-chat detector matches. The
  request carries an explicit `resume` flag; trust it.
- **Never decide language from the current message alone.** Those same nudges are
  system-generated, and judging on them answered Vietnamese reps in English. Use
  `_is_vietnamese(message, state)`, which falls back through their own turns.
- **Binary never goes in `SalesCaseState`.** It is serialised to JSON on every save;
  leaving PPTX bytes there broke persistence with "invalid utf-8 sequence", and every
  session that generated a deck silently stopped being saved.
- **A degraded artifact must announce itself.** Slide extraction falls back to a bare
  cover-and-closing scaffold and used to report success, so the first sign of trouble
  was a rep opening a two-page proposal. It also returned `content=""`, so the answer
  writer knew nothing about the deck and invented a seven-slide table of contents for a
  file that held two. A skill that builds something reports what it actually built.
- **A skill that returns FAILED is not "completed".** The `agent_status` event said
  completed whenever the coroutine returned without raising, so a run where all five
  skills 429'd their way to `RetryError` showed the rep a full column of green ticks and
  only the final message admitted otherwise.
- **`LLM_RETRY_ATTEMPTS` governed nothing that mattered.** The non-streaming retry
  decorator carried a hardcoded 5 attempts and a 30s ceiling, and every skill call is
  non-streaming — so the one knob documented for a rate-limited tier only ever reached
  the synthesis handshake. Both paths read the env vars now.
- **A JSON parse failure is not a provider outage.** Every exception around the planner
  call was reported to the rep as one, ending the turn with nothing. Gemini writing
  Vietnamese emits the occasional malformed `\u` escape — two turns in three died that
  way — so `skills/base.py:loads_lenient` repairs the escapes and a `JSONDecodeError`
  now falls through to the contextual plan. Only transport errors are an outage.
- **Never re-import a module-level name inside a function.** A `from checkpoint.manager
  import get_checkpoint_manager` in one branch of `checkpoint_decision` made the name
  local for the whole function, so the unconditional call below it raised
  `UnboundLocalError` and `POST /checkpoint/{id}/decision` returned 500 every time. The
  UI uses `/workflow/interact`, which is why nobody noticed.
- **`desired_outputs` is sticky for the session.** Once a proposal is requested, every
  later turn tries to build one unless the intent guard stops it.
- **Next.js standalone binds to `$HOSTNAME`**, which Docker sets to the container ID —
  it listened on the container IP only. And busybox `wget` resolves `localhost` to
  `::1` first. Both are pinned in `docker-compose.prod.yml`.
- **`core.autocrlf` is on for the team's Windows checkouts.** `.gitattributes` pins LF
  for shell, compose and nginx files; without it a fresh clone hands `deploy.sh` CRLF
  and bash refuses it.
- **Per-call state cannot live on `self` inside a skill.** `BaseSkill` instances are
  process-wide singletons (`skills/registry.py`) serving every concurrent turn —
  writing `self.last_call_truncated` in `_call_llm` for one turn to read looked like
  the natural place, until it was clear a second turn's call could overwrite the flag
  before the first turn read it. `_call_llm` returns `(text, truncated)` instead;
  nothing about a single call is ever stored on the shared instance.
- **A truncated reply was indistinguishable from a whole one.** Nothing checked
  `finish_reason`, so a skill's answer cut off by `max_tokens` still came back
  `status="COMPLETE"` and got assembled into the proposal as if it were finished.
  `_call_llm`'s second return value is `True` on `finish_reason == "length"`; every
  skill wraps it as `status="PARTIAL"` and appends a note to its own summary.
- **`tableLayout: 'fixed'` silently defeated the overflow-x-auto wrapper built to fix
  wide tables.** Fixed layout forces every column into the container width no matter
  what the wrapper allows, so a 5-column ratecard in a narrow chat bubble squeezed
  every figure into single-digit pixel columns instead of scrolling — the wrapper
  never got the chance to activate. `tableLayout: 'auto'` + `width: max-content` +
  `minWidth: '100%'` on the `<table>` is what actually lets the wrapper do its job.
- **A modal card without its own opaque background reads as broken, not just
  translucent.** `--color-surface` is 60% alpha in the (default) dark theme, and two
  modals painted their card with it and no `backdrop-filter` — 16-20% of the page
  behind them showed through unblurred, directly behind dense numeric quota rows.
  A separate bare-`header`/`form` CSS selector then made the modal's own header *more*
  transparent than its body. Modals get an opaque `--color-surface-solid` card plus a
  blurred scrim (`.modal-card`/`.modal-scrim`); the frosted-chrome selector is scoped
  to an explicit `.app-chrome` class so it never lands on a modal by accident again.
- **The entire session history and agent status list were unreachable on a phone.**
  The sidebar was hard-wrapped in `hidden md:block`, and the mobile drawer that stood
  in for it carried only two mode buttons — seven of eight sidebar capabilities,
  Model & Quota included, had no mobile path at all. The sidebar is one off-canvas
  component now (`fixed` + `translate-x`), shared by desktop and the mobile drawer, so
  there is only ever one place to fix.
- **An unlayered CSS rule beats a layered one regardless of specificity.** Moving
  `text-xs`/`sm`/`base`/`lg` into Tailwind v4's `@theme` block (to fix a line-height
  bug) dropped the `!important` a hand-written `.text-xs{font-size:...!important}`
  used to carry — and `@theme` utilities live in a Tailwind cascade layer, which loses
  to *any* unlayered rule no matter how low its specificity. `globals.css` had a
  pre-existing unlayered `h1, h2, .text-xl, ... {font-size: 22px}` headline rule that
  bare-matched every `<h2>` element, so it started winning outright — Sidebar's
  "Active Agents", ChatWindow's mode header, every small-text heading rendered at
  22-26px instead of its intended size. Every `<h1>`/`<h2>` in the codebase already
  carries its own explicit sizing class, so the fix removed the bare element selectors
  entirely rather than narrowing them — nothing relied on them.
- **A planner intent with no matching branch falls through to "run everything."**
  `_resolve_intent()` can legitimately return `"casual"` (an ambiguous "tôi muốn làm
  việc khác"), but `_build_contextual_skill_plan()` had no case for it, so it fell to
  the default branch — every core skill, then the sticky `desired_outputs` safety net
  chained on `proposal_assembler` + the deck. Same gap in the `conversational` tuple
  gating Chốt 1: it listed `("lookup", "coaching")` and forgot `"casual"`, so a message
  the planner itself correctly classified as small talk still re-ran the full brief
  pipeline. Result: once a proposal existed, almost any follow-up message rebuilt the
  whole thing. `casual` now short-circuits both checks; an empty skill plan lets
  `_synthesize` answer from conversation history alone instead of dispatching nothing
  useful into a five-skill re-run.
- **A message timestamp with no UTC offset is read as local time by the browser.**
  Every `state.messages[...]["timestamp"]` was stamped with naive `datetime.now()` —
  the server's system clock (UTC, since nothing sets `TZ`), serialised via
  `.isoformat()` with no trailing `Z`/`+00:00`. `new Date(message.timestamp)` on the
  frontend has no offset to go on, so it parses the string as if it were *already* in
  the viewer's local zone (Asia/Ho_Chi_Minh, UTC+7) — a message the server stamped at
  20:00 UTC (03:00 the next day in Vietnam) rendered as 20:00 that same day, a whole
  calendar date off whenever the 7-hour gap crossed midnight. Fixed at the source:
  every one of the 12 call sites across `central_agent/agent.py`, `main.py`,
  `cs_agent/agent.py`, and `memory/profile.py` now stamps `datetime.now(timezone.utc)`,
  which serialises with an explicit offset the browser can actually convert from.
- **A casual-reply picker judged language from one message, not the conversation.**
  `_is_vietnamese()` was written specifically to fall back through a rep's own earlier
  messages, because a single system-generated nudge or a short reply carries no
  language signal on its own — but `_casual_reply()` (the greeting/small-talk path)
  never used it, and instead re-implemented the single-message check it was meant to
  replace. A one-word opener like "alo" mid-conversation has no Vietnamese diacritics,
  so it answered a Vietnamese rep in English partway through their own session.
  `_casual_reply` now takes `state` and calls `_is_vietnamese(message, state)` like
  every other language decision in this file.
- **A scope parameter that only one caller ever sets is not a filter, it's a
  constant.** `get_active_rules(scope)` in `database.py` does real filtering —
  `scope IN ('all', ?)` — but both call sites in the codebase (the planner and
  the final synthesizer) always passed the literal string `"all"`, which the
  function special-cases to mean "no filter, return every active rule". So the
  Admin Panel's per-skill scope picker ("Compliance", "Product Solution", ...)
  never actually narrowed anything — and more importantly, neither the planner
  nor the synthesizer is the thing that writes a proposal's compliance section
  or strategy section. A rule scoped to "Compliance" never reached
  `compliance/skill.py` at all; it only ever reached two calls that don't own
  that content. `BaseSkill._fetch_org_rules()` now calls
  `get_active_rules(self.name)` from inside each of the 6 skills that build
  their own system prompt, which is what makes the scope picker real. Also had
  zero observability — nothing logged when a rule was or wasn't injected — so
  there was no way to confirm from outside that it worked; a `[org_rules]` line
  now prints wherever a rule is actually injected.

---

## Style

Match the surrounding code. Comments explain **why**, especially where the
non-obvious choice was deliberate — most of the comments in `gate.py`,
`knowledge/loader.py` and `pii/masking.py` exist because the obvious alternative was
tried and failed. Reply to the user in Vietnamese; keep code and comments in English.
