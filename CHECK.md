# Implementation Check — Days 1–3 (vs PLAN.md & docs/DAY_1–3.md)

> Audit date: 2026-06-14. Scope: **only the 3 days marked complete** (Day 1 Foundations,
> Day 2 Orchestrator/registry, Day 3 Validation/QuestionStack). Days 4–7 are intentionally
> out of scope here (not started). Backend + frontend.

**Legend:** ✅ matches plan · ⚠️ implemented but **wrong / diverges from plan**

---

## Summary

| Day | Status | Headline |
|---|---|---|
| Day 1 — Foundations | ✅ mostly | Solid; `pino` dep + blocking sqlite + Day-1 persistence classes are dead code |
| Day 2 — Orchestrator + registry | ⚠️ partial | Works, but **LangGraph never invoked**; `agents.yaml`/registry diverge from spec |
| Day 3 — Validation + QuestionStack | ✅ mostly | Strong; one frontend wiring gap + a duplicated component |

Bottom line: the 3 days are **functionally ~90% there**, but a few Day-1/2 divergences will block Day 4–5 if not fixed first (chiefly: the real LangGraph isn't on the request path).

---

## ⚠️ Implemented WRONG / diverges from the plan

### 1. LangGraph `StateGraph` is built but **never used** — `main.py` runs `SimpleAgentRunner` (Day 2)
- **Where:** `backend/main.py:37,161` (`get_simple_runner()`). The real graph (`AgentGraph`, `get_graph()`) lives in `backend/agents/graph.py` but nothing on the request path calls it.
- **Plan says:** PLAN §E + §B.1 and DAY_2 choose **LangGraph** as the execution path specifically for `interrupt-before-tool` HITL + durable checkpointer + resume.
- **Why it matters:** the Day-5 human checkpoint (interrupt-before-tool) and Day-4 resume **depend on the real graph**. `SimpleAgentRunner` can't interrupt/resume — fixing this later is harder than now.
- **Fix:** route `/chat/stream` through `AgentGraph.run_stream()`; keep `SimpleAgentRunner` only as a no-LangGraph fallback.

### 2. `config/agents.yaml` + registry diverge from the agent-contract spec (Day 2)
- **Where:** `backend/config/agents.yaml`, `backend/agents/registry.py`.
- **Actual fields:** `name`, `description`, `model_env`, `system_prompt`, `enabled`, `is_critical` (orchestrator only), `knowledge_dir`, `skills_dir`.
- **DAY_2 §4 says** the entry keys are `name, model, role, enabled`.
- **Divergences:**
  - `description` vs `role`, `model_env` vs `model` — pick canonical names and make PLAN/DAY_2 and the code agree.
  - `is_critical` is read from YAML but **not propagated into `AgentTask`** (so the B.5 critical/non-critical failure policy has no data to act on).
  - `validation` is a **top-level key outside the `agents:` block** — inconsistent structure (it's a pre-pass; document that explicitly).
- **Fix:** reconcile field names; have the registry read `is_critical` into the task.

### 3. Day-1 persistence classes are **dead code** — everything is in-memory (Day 1/2)
- **Where:** `main.py:108` `_session_store: dict` (in-memory); `graph.py:128` `MemorySaver()` (in-memory).
- **Plan says:** Day 1 built `SQLiteMemoryRepo` + `SQLiteCheckpointSaver` behind the repo interface — but neither is ever called. Sessions vanish on restart.
- **Note:** full persistence wiring is legitimately Day 4, so this is flagged (not a Day-1 failure) — but be aware the Day-1 deliverable "runs on the SQLite fallback" is only true at the *interface* level, not on the request path.

### 4. `requirements.txt` has a wrong dependency: `pino>=0.2.0` (Day 1)
- **Where:** `backend/requirements.txt`.
- **Issue:** `pino` is a **Node.js** logger; the PyPI `pino` is an unrelated, stale package. `python-json-logger` (the right one) is already present.
- **Fix:** remove `pino`.

### 5. SQLite repos use **blocking** `sqlite3` inside `async` methods (Day 1)
- **Where:** `backend/repos/memory_repo.py` — `import sqlite3` inside `async def save_session/...`. `aiosqlite` is in requirements but unused.
- **Issue:** blocks the event loop; the `async` signatures are misleading.
- **Fix:** switch to `aiosqlite`, or document the methods are intentionally sync for the demo.

### 6. Frontend: `QuestionCard.tsx` exists but is **not used** (Day 3)
- **Where:** `frontend/src/components/QuestionCard.tsx` is complete, but `ChatWindow.tsx` defines and renders its **own inline** question card instead. (Same pattern for the checkpoint card — inlined in `ChatWindow`, no `CheckpointCard.tsx`.)
- **Issue:** two copies will drift.
- **Fix:** import and use the standalone `QuestionCard`.

### 7. Frontend: free-text answers don't call `/chat/answer_free_text` (Day 3)
- **Where:** `useChat.ts` — the free-text reply path falls back to `sendMessage()`; the backend endpoint `POST /chat/answer_free_text` (maps free text → brief fields) is never called.
- **Issue:** DAY_3 verify step 5 ("F&B, around 150 triệu" → mapped to `industry`/`budget_vnd`) won't work through the UI.
- **Fix:** wire the free-text reply to `/chat/answer_free_text`.

---

## ✅ Correct & matching the plan

**Day 1 — Foundations**
- `main.py`: `GET /`, `GET /health`, `POST /chat`, `POST /chat/stream`, `/sessions/*`; SSE event envelope; `PORT`/`HOST` from env.
- `llm/greennode.py`: `GreenNodeClient`, `get_llm_client(agent)` resolving `MODEL_*`, `validate_environment()`, tenacity retry.
- `schemas/state.py`: **all** required schemas present (`Brief`, `Question`, `NeedsRequest`, `AgentOutput`, `Ambiguity`, `ValidationReport`, `AgentTask`, `ExecutionPlan`, `CheckpointAction`, `Checkpoint`, `FeedbackRule`, `ProfileHistoryItem`, `SalespersonProfile`, `SalesCaseState`).
- `repos/memory_repo.py`: `MemoryRepo` + `SQLiteMemoryRepo` + `SQLiteCheckpointSaver`; `AgentBaseMemoryRepo` correctly reads `AGENTBASE_MEMORY_ID` + IAM (earlier fix landed).
- Frontend: Next.js App Router + assistant-ui + `ai` + lucide; identity screen (chosen name, no auth); BFF `api/chat/route.ts` proxies SSE (key stays server-side); `useChat` handles all SSE event types; `types.ts` mirrors.

**Day 2 — Orchestrator + registry**
- `agents/base.py`: `BaseAgent` (name, model_key, prompt from `prompt.md`, `async run()->AgentOutput`) + `StubAgent`.
- `agents/registry.py`: `AgentRegistry` with `get/all/routing_descriptions`.
- `agents/orchestrator.py`: supervisor logic + **anti-loop guard** (`visited` + `hop_depth`, max 4) + honors/denies `NeedsRequest`.
- 6 agent folders with `prompt.md`; per-agent `agent_status` SSE → `Sidebar.tsx` status dots (idle/thinking/waiting/failed colors).
- Day-2 deliverable (brief → orchestrator → ≥2 agents → aggregated stream) works via `SimpleAgentRunner`.

**Day 3 — Validation + QuestionStack**
- `validation/validator.py`: Gemma-4 pre-pass → `ValidationReport`; LLM ambiguity detection; severity / `revalidation_impact` (critical vs non-critical fields).
- `validation/question_stack.py`: `QuestionStack` (push/next_batch, mandatory-first, dedup) + `QuestionManager` (generate from validation, `map_answers`, free-text mapping incl. "150 triệu"→VND, `skip_optional` with assumption).
- Orchestrator `validate_before_dispatch` gate (BLOCKED/PENDING/READY) blocks dispatch; severity-gated re-validation.
- API: `POST /chat/answer`, `/chat/skip_question`, `/chat/answer_free_text`.
- Frontend `QuestionCard` styling (yellow left-border + `?`, numbered, required vs optional+assumption, Skip, free-text path).

---

## Suggested fix order (Days 1–3 only)

1. **Remove `pino`** from `requirements.txt` (1 line).
2. **Reconcile `agents.yaml`/registry field names** + read `is_critical` into `AgentTask`.
3. **Wire `/chat/stream` through the real LangGraph** (unblocks Day-4 resume & Day-5 checkpoint interrupts).
4. **Frontend:** use the standalone `QuestionCard`; wire free-text answers to `/chat/answer_free_text`.
5. (Optional now) switch SQLite repos to `aiosqlite`.
