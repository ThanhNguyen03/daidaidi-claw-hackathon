# Implementation Check — Day 4 (Memory & Learning)

> Audit date: 2026-06-14. Scope: **Day 4 only** (uncommitted files). Days 1–3 removed per request.
> Files reviewed: `backend/memory/{feedback_extractor,constraint_injection,profile}.py`,
> `backend/agents/base.py`, `backend/main.py`, `frontend/src/components/ContextPanel.tsx`,
> `frontend/src/{app/page.tsx,hooks/useChat.ts,lib/types.ts}`.

**Legend:** ✅ done · ⚠️ implemented but wrong/diverges · ❌ not yet

---

## Verdict

The **plumbing is mostly there and the frontend is solid**, but the **two mechanisms that make Day 4 actually work are not wired**, and there is **one runtime-crash bug**. As-is, the headline deliverable — *"don't suggest discount" provably suppresses discounts next session"* — **cannot be demonstrated**.

| Area | Status |
|---|---|
| Feedback extractor | ⚠️ works but regex-based (plan said LLM) |
| Constraint **injection into agents** | ❌ helper exists, **never called** in dispatch |
| Cross-session persistence (sessions) | ❌ `save_session` never called → resume 404s |
| Durable checkpointer | ⚠️ in-memory `MemorySaver`, not SQLite/AgentBase |
| Profile learning | ⚠️ **crashes** (schema mismatch) |
| Context panel (frontend) | ✅ fully built + wired |
| Constraint list/revoke endpoints + SSE | ✅ done |

---

## ⚠️ Bugs / implemented wrong

### 1. Constraints are saved but **never injected** — the core deliverable doesn't work
- **Where:** `memory/constraint_injection.py::inject_constraints` and `agents/base.py::get_prompt_with_constraints` exist, but a grep shows **no caller** in `main.py` / `orchestrator.py` / `graph.py` / `SimpleAgentRunner`. `state.constraints` is **never populated** from `load_feedback_rules(...)` during a turn.
- **Compounding:** agents are still `StubAgent`s that return canned data and **ignore the system prompt entirely**, so even if injected nothing changes.
- **Effect:** DAY_4 verify steps 1–3 fail past "rule is created". The rule shows in the Context panel but does **not** influence any agent output.
- **Fix:** on each turn, `state.constraints = await memory_repo.load_feedback_rules(salesperson_id, active_only=True)`; pass them through dispatch and call `agent.get_prompt_with_constraints(...)`. (Full proof needs real agents — Day 5 — but at minimum wire the injection now and assert the rule appears in the composed prompt.)

### 2. Sessions are never persisted → resume endpoint always 404s
- **Where:** `main.py` still stores sessions in the in-memory `_session_store` dict (`update_session`). `MemoryRepo.save_session()` is defined but **never called** from the chat path. The resume endpoint `GET /memory/session/{id}` calls `repo.load_session()` — which reads SQLite that nothing ever wrote to.
- **Effect:** DAY_4 verify step 4 (kill/restart → resume) **fails**; "new session, same salesperson" only works for *constraints/profile* (those are saved), not session state.
- **Fix:** persist `SalesCaseState` via `memory_repo.save_session(state)` at end of each turn (and load on resume).

### 3. Checkpointer is in-memory `MemorySaver`, not the required durable saver
- **Where:** `agents/graph.py:128` `self.checkpointer = MemorySaver()` (unchanged this day).
- **Plan (DAY_4 task 1):** wire `AgentBaseMemoryEvents(memory_id=...)` primary / `SQLiteCheckpointSaver` fallback, keyed by `thread_id = session_id`.
- **Effect:** graph state is lost on restart even though `/chat/stream` now uses the graph when `ENABLE_CHECKPOINT=true`. The `SQLiteCheckpointSaver` built on Day 1 is still unused.

### 4. `profile.py` crashes at runtime — `ProfileHistoryItem` schema mismatch
- **Where:** `memory/profile.py:121` builds `ProfileHistoryItem(case=…, question=…, answer=…, helpful=…, timestamp=…)`.
- **Actual schema** (`schemas/state.py`, unchanged): `ProfileHistoryItem(case_id, summary, chosen_solution, outcome)`. The required `case_id`/`summary` are missing → **Pydantic `ValidationError`** whenever `update_from_answer` runs (i.e. `POST /memory/profile/{id}/learn` with an answer).
- **Also:** `get_suggested_answer` reads `item.question` / `item.answer`, which don't exist on the schema → `AttributeError`.
- **Fix:** either add those fields to `ProfileHistoryItem` or map to the existing fields.

### 5. Duplicate event streaming in graph mode
- **Where:** `main.py` — in the `use_full_graph` branch events are yielded at lines 181–183, then the `for event in stream_events` loop at 201–203 runs **unconditionally** and yields them all again. The comment ("only reached when using SimpleAgentRunner") is wrong — it's not in an `else`.
- **Effect:** every SSE event is emitted twice when `ENABLE_CHECKPOINT=true` (the default in `.env.example`).
- **Fix:** put 201–203 in an `else`, or skip when `use_full_graph`.

### 6. Graph branch discards agent outputs
- **Where:** `main.py:186` sets `final_state = state` in the graph branch; the graph's internal/streamed state isn't propagated back, so `final_state.outputs` (used for the summary at 206–225) is likely empty in graph mode.

---

## ⚠️ Divergences from the plan (work, but not as specified)

7. **Feedback extractor is regex/keyword, not LLM.** DAY_4 §D.2 specifies `async extract(...)` LLM classification; the impl is synchronous regex (`NEGATIVE/POSITIVE/PREFERENCE_PATTERNS`). It handles the demo phrase ("don't suggest discount…") but generic NL feedback will be missed or mis-scoped. Also the signature is sync, not `async`.
8. **Rolling summary + bounded message window not implemented.** `summary` is a crude one-line overwrite (`main.py:223`); the agent path appends messages unbounded (no window, no LLM rolling summary).
9. **History-based suggested answers not wired.** `get_suggested_answer` exists but is never called by `QuestionManager`, and is broken per bug #4.
10. **Feedback only extracted after validation passes.** The `if not should_dispatch: return` (main.py:423) happens *before* the feedback block (438+), so feedback typed while a question card is open is dropped. OK in chat mode (validation READY), fragile elsewhere.
11. **No `X-GreenNode-AgentBase-User-Id` / `Session-Id` header handling** (DAY_4 task 1). Minor while on the SQLite fallback.

---

## ✅ Done correctly

- `memory/feedback_extractor.py`: builds a valid `FeedbackRule` (type/scope/rule/source_quote/active), sensible scope inference (`discount → [account, orchestrator]`), `is_feedback_message` gate, singleton.
- `memory/constraint_injection.py`: `inject_constraints`, `get_constraints_for_agent`, `format_constraint_summary` — correct logic (just not called from dispatch).
- `agents/base.py`: `get_prompt_with_constraints` helper + the B.6 fields (`kind`, `hooks`, `is_critical`) now on `BaseAgent`/`StubAgent`.
- `main.py` endpoints: `GET /memory/constraints/{sp}`, `POST /memory/constraints/{rule_id}/toggle`, `GET /memory/profile/{sp}`, `POST /memory/profile/{sp}/learn`, `GET /memory/sessions/{sp}`, `GET /memory/session/{id}`; feedback extraction + `constraint_added` SSE inside `/chat/stream`; frustration detection persisted.
- `/chat/stream` now routes through the real LangGraph when `ENABLE_CHECKPOINT=true` (addresses the earlier "graph never used" finding — though see bugs #3/#5/#6).
- **Frontend (fully wired):** `ContextPanel.tsx` (brief summary, active constraints with revoke `X`, negative/positive coloring, empty-state hint); `useChat.ts` `constraints` state + `loadConstraints` + `revokeConstraint` + `constraint_added` handler; `page.tsx` mounts the panel and loads constraints/profile on identify; `types.ts` exports `FeedbackRule`.

---

## ❌ Not yet implemented (Day-4 scope)

- Durable checkpointer (SQLite/AgentBase bridge) keyed by `thread_id`.
- Actual constraint **injection into running agents** + populating `state.constraints` per turn.
- Cross-session **session-state** persistence (`save_session` on the chat path).
- Rolling LLM summary + bounded message window.
- Working profile learning (blocked by bug #4) + history-based suggested answers.

---

## Suggested fix order (Day 4)

1. **Fix `ProfileHistoryItem`** (bug #4) — unblocks profile learning; quick schema reconcile.
2. **Wire constraint injection** (bug #1): load active rules into `state.constraints` each turn and apply via `get_prompt_with_constraints` in dispatch. (Visible proof: assert the rule text appears in the composed prompt, even with stub agents.)
3. **Persist sessions** (bug #2): call `memory_repo.save_session(state)` per turn so resume works.
4. **De-dupe graph streaming** (bug #5) and fix `final_state` capture (bug #6).
5. **Swap checkpointer** to `SQLiteCheckpointSaver` (bug #3) for restart-resume.
6. (Later) upgrade the feedback extractor to the LLM-based `async extract` per §D.2; add rolling summary + bounded window.
