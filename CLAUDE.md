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
```

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

**Rate limits are the main operational risk.** A full proposal turn fans out to
planner, selectors, four specialists, assembler and synthesis. Six concurrent
requests draw a 429; a whole run on free tier produced 28 of them and failed four
skills. Hence concurrency 1 and the long retry ceiling. Before a demo, either buy
quota or run a session in advance and present that.

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

Present, unreferenced, and safe to delete when someone has time. Roughly 1,500 lines.

| Path | Note |
|---|---|
| `main.py:_maybe_create_checkpoint` | ~260 lines, no callers. The live checkpoints are built in `central_agent/agent.py` |
| `validation/validator.py` | No callers. The BRD critiques its `MANDATORY_FIELDS`; `gate.py` supersedes it |
| `mode/brainstorm.py` | Mode is "coming soon" in the UI |
| `generation/pptx.py`, `generation/userflow.py` | Superseded by `pptx_adtimabox.py` and inline Mermaid |
| `kb/ingest.py` | Duplicates `tools/ingest.py` |
| `design/backend.py` | Figma integration, never wired |
| `agents/predict-agent/` | A fortune-telling bot. Off-topic; hide it before judging |

---

## Bugs that bit us, so they are not reintroduced

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
  was a rep opening a two-page proposal.
- **`desired_outputs` is sticky for the session.** Once a proposal is requested, every
  later turn tries to build one unless the intent guard stops it.
- **Next.js standalone binds to `$HOSTNAME`**, which Docker sets to the container ID —
  it listened on the container IP only. And busybox `wget` resolves `localhost` to
  `::1` first. Both are pinned in `docker-compose.prod.yml`.
- **`core.autocrlf` is on for the team's Windows checkouts.** `.gitattributes` pins LF
  for shell, compose and nginx files; without it a fresh clone hands `deploy.sh` CRLF
  and bash refuses it.

---

## Style

Match the surrounding code. Comments explain **why**, especially where the
non-obvious choice was deliberate — most of the comments in `gate.py`,
`knowledge/loader.py` and `pii/masking.py` exist because the obvious alternative was
tried and failed. Reply to the user in Vietnamese; keep code and comments in English.
