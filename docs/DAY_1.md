# DAY 1 — Foundations & Contracts

> One-line goal: stand up the repo, the GreenNode LLM wrapper, the core schemas, and the persistence interfaces so that `POST /chat` runs one LLM call end-to-end with SSE streaming into a minimal Next.js chat — locally on the SQLite fallback, before any AgentBase creds exist.

## 1. Objective

Establish the skeleton everything else hangs off: a Python backend (LangGraph wrapped as a **GreenNodeAgentBaseApp**), a Next.js + assistant-ui frontend, the shared **Pydantic state/contract schemas** (B.2, C.5), the **GreenNode MAAS LLM wrapper** with per-agent model mapping, and the **repository interfaces** with dual implementations (AgentBase Memory primary / SQLite + LanceDB fallback). "Done" = a developer can clone, fill `.env`, and watch a streamed answer appear in the browser using only the SQLite fallback.

## 2. Prerequisites

- None (Day 1 is the foundation). Greenfield repo — all net-new.
- A GreenNode account is *helpful* for live testing but **not required**: the fallback path must run without it.

## 3. Task checklist

### Backend — scaffold & packaging
- [x] Create `backend/` package layout: `backend/__init__.py`, `backend/main.py`, `backend/llm/`, `backend/schemas/`, `backend/repos/`, `backend/config/`.
- [x] `backend/requirements.txt` — pin: `fastapi`, `uvicorn[standard]`, `pydantic>=2`, `python-dotenv`, `langgraph`, `langchain-core`, `openai`, `sse-starlette`, `httpx`, `tenacity`, `aiosqlite`, `lancedb`, `pytest`.
- [x] `backend/main.py` — FastAPI app wrapped per the GreenNodeAgentBaseApp Runtime Service Contract (configurable `PORT`/`HOST`, `/health` check). Endpoints: `GET /`, `GET /health`, `POST /chat`, `POST /chat/stream`.
- [x] CORS middleware allowing the frontend origin (`FRONTEND_URL` env).

### Backend — GreenNode LLM wrapper
- [x] `backend/llm/greennode.py` — OpenAI-compatible client pointed at `LLM_BASE_URL` (`https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1`).
  - [x] `GreenNodeClient` — thin wrapper over the OpenAI SDK; `create_completion(messages, stream, temperature, max_tokens)`.
  - [x] `get_llm_client(agent_name: str) -> GreenNodeClient` — resolves the model `path` from the per-agent `MODEL_*` env var.
  - [x] `validate_environment() -> dict` — reports whether key/base-url/model paths are present (drives `/health` + `/debug/config`).
  - [x] Retry transient errors (timeout/5xx/rate-limit) with backoff via `tenacity`.

### Backend — core schemas (B.2 + C.5)
- [x] `backend/schemas/state.py` — define `Brief`, `Question`, `NeedsRequest`, `AgentOutput`, `Ambiguity`, `ValidationReport`, `AgentTask`, `ExecutionPlan`, `CheckpointAction`, `Checkpoint`, `FeedbackRule`, `ProfileHistoryItem`, `SalespersonProfile`, and the top-level `SalesCaseState` (fields exactly per PLAN.md B.2: `brief, mode, validation_status, question_stack, plan, outputs, visited, hop_depth, profile, constraints, checkpoint`).
- [x] `backend/schemas/__init__.py` — re-export the public schema names.

### Backend — repository interfaces + dual impls (E + D.3)
- [x] `backend/repos/memory_repo.py` — abstract `MemoryRepo` (save/load session, save/load profile, save/load/delete feedback rules, list sessions); `SQLiteMemoryRepo` (fallback, auto-creates tables); `AgentBaseMemoryRepo` (primary, placeholder until SDK creds exist); `create_memory_repo(use_agentbase: bool)` factory + `get_memory_repo()` singleton.
- [x] Define the `KBRepo` and `ProfileRepo` interface stubs (bodies filled later days) so the swappable-interface contract from PLAN.md exists from Day 1.
- [x] `SQLiteCheckpointSaver` stub conforming to the LangGraph `CheckpointSaver` shape (`get`/`put`/`list` by `thread_id`) — wired for real in Day 2/4.

### Backend — env + docs
- [x] `.env.example` — `LLM_BASE_URL`, `LLM_API_KEY`, per-agent `MODEL_*` (orchestrator, tech_solution, market_strategy, account, adtimabox, design, validation), AgentBase IDs (optional), `FRONTEND_URL`, `SQLITE_DB_PATH`, `LANCEDB_PATH`, feature flags (`ENABLE_CHECKPOINT`, `ENABLE_BRAINSTORM`, `ENABLE_AUTO_APPROVE_SESSION`).
- [x] `README.md` — quick-start + a **step-by-step "get your GreenNode key + list model `path` IDs"** guide (incl. the `curl …/v1/models | jq '.data[].path'` snippet) and the rule that the model param = the model's `path` field.

### Frontend — minimal chat
- [x] `frontend/package.json` — Next.js (App Router) + React + `@assistant-ui/react` + `ai` + `lucide-react` + TypeScript.
- [x] `frontend/src/app/layout.tsx`, `frontend/src/app/page.tsx` — identity screen (chosen name/id, no auth — G Q9) → minimal chat canvas.
- [x] `frontend/src/app/api/chat/route.ts` — BFF route that proxies SSE to the FastAPI backend (keeps `LLM_API_KEY` server-side — C recommendation).
- [x] `frontend/src/hooks/useChat.ts` — consume the SSE stream and append tokens.
- [x] `frontend/src/lib/types.ts` — TS mirrors of the request/response + stream-event shapes.

### Agent folder conventions (cross-cutting)
- [x] Create `backend/agents/<name>/{prompt.md, knowledge/, skills/}` directories for all 6 agents + orchestrator.

## 4. Key interfaces / contracts introduced today

- **Schemas:** `SalesCaseState`, `AgentOutput`, `Question`, `ValidationReport`, `FeedbackRule`, `SalespersonProfile` (the contracts every later day depends on).
- **LLM:** `get_llm_client(agent)`, `MODEL_*` env mapping, model param = `path`.
- **Persistence:** `MemoryRepo` (+ `SQLiteMemoryRepo` fallback, `AgentBaseMemoryRepo` primary), `create_memory_repo()`, `SQLiteCheckpointSaver` stub.
- **KB:** `KBRepo` (+ `LanceDBKBRepo` stub, `AgentBaseKBRepo` placeholder).
- **Profile:** `ProfileRepo` (+ `SQLiteProfileRepo` stub, `AgentBaseProfileRepo` placeholder).
- **Transport:** SSE event envelope `{type: "session"|"user_message"|"content"|"done"|"error", ...}`.

## 5. Deliverable & verification

**Deliverable:** `POST /chat` runs one LLM call end-to-end with SSE streaming to a minimal Next.js chat; runs locally on the SQLite fallback even before AgentBase creds exist.

**Verify:**
1. `cp .env.example .env`, fill `LLM_API_KEY` + `MODEL_*` paths.
2. `cd backend && pip install -r requirements.txt && uvicorn main:app --reload --port 8000`.
3. `GET http://localhost:8000/health` → `{status: healthy, llm_configured: true}`.
4. `curl -N -X POST :8000/chat/stream -d '{"message":"Xin chào","salesperson_id":"sp_test","mode":"chat"}'` → streamed `data:` chunks ending in `{"type":"done"}` (Vietnamese in → Vietnamese out — G Q5).
5. `cd frontend && yarn && yarn dev` → open `:3000`, enter a name, send a message, watch tokens stream in.
6. With AgentBase env unset, the app still works (SQLite fallback) — confirm no crash and `create_memory_repo(use_agentbase=False)` is used.

## 6. Out of scope / deferred

- No real orchestrator/agent dispatch yet (single LLM call only) → **Day 2**.
- No validation gate / question cards → **Day 3**.
- No persistence wired into the request path beyond the interface (in-memory store is acceptable today) → **Day 4**.
- AgentBase Memory live integration remains a placeholder → **Day 4/7**.

## Implementation Notes

### Day 1 Complete ✅
All checklist items completed as of 2026-06-12.

### Known Limitations (to be addressed in later days)
1. **LLM Retry**: Retry logic added via `tenacity` but only for non-streaming calls. Streaming retry requires higher-level handling.
2. **KB Repo**: LanceDB implementation is stub-only (no embeddings). Full RAG in Day 5.
3. **Profile Repo**: SQLite implementation delegates to MemoryRepo for now.
4. **Session Storage**: Currently in-memory (`_session_store` dict). Full persistence in Day 4.
5. **Frontend BFF**: Basic proxy implemented. Could add auth/validation layer later.

### File Structure Created
```
backend/
├── __init__.py
├── main.py
├── requirements.txt
├── config/
│   └── agents.yaml
├── schemas/
│   ├── __init__.py
│   └── state.py
├── llm/
│   ├── __init__.py
│   └── greennode.py
├── repos/
│   ├── __init__.py
│   ├── memory_repo.py
│   ├── kb_repo.py
│   └── profile_repo.py
└── agents/
    ├── orchestrator/
    │   └── prompt.md
    ├── tech_solution/
    │   ├── knowledge/
    │   └── skills/
    ├── market_strategy/
    │   ├── knowledge/
    │   └── skills/
    ├── account/
    │   ├── knowledge/
    │   └── skills/
    ├── adtimabox/
    │   ├── knowledge/
    │   └── skills/
    └── design/
        ├── knowledge/
        └── skills/

frontend/
├── package.json
├── tsconfig.json
├── next.config.js
└── src/
    ├── app/
    │   ├── layout.tsx
    │   ├── page.tsx
    │   ├── globals.css
    │   └── api/
    │       └── chat/
    │           └── route.ts
    ├── components/
    │   ├── ChatWindow.tsx
    │   ├── MessageBubble.tsx
    │   └── Sidebar.tsx
    ├── hooks/
    │   └── useChat.ts
    └── lib/
        └── types.ts
```