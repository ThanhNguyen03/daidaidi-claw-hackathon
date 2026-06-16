# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Backend (Python 3.11+, FastAPI + LangGraph)
```bash
cd backend
python -m venv venv && venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Run dev server (port 8000)
python -m uvicorn main:app --reload --port 8000

# Lint and format
ruff check .
ruff format .

# Tests
pytest
pytest tests/test_file.py::test_function -v   # single test
```

### Frontend (Next.js + TypeScript)
```bash
cd frontend
yarn install
yarn dev           # localhost:3000
yarn test
yarn build
```

### Environment Setup
Copy `.env.example` → `backend/.env` and set at minimum:
- `LLM_API_KEY` — GreenNode MAAS API key
- `MODEL_*` env vars (one per agent, e.g. `MODEL_SALES_ORCHESTRATOR=MiniMax-M2.5`)

Optional: `FIGMA_ACCESS_TOKEN`, `AGENTBASE_MEMORY_ID`, `GREENNODE_CLIENT_ID/SECRET`.

## Architecture

### Request Flow
```
Frontend (Next.js)
  └─ POST /chat/stream  →  SSE stream
       Backend (FastAPI)
         ├─ process_simple()     — chat mode: direct LLM call, streams tokens
         └─ process_with_agents()— all modes: SimpleAgentRunner pipeline
              ├─ A1: orchestrator.validate_before_dispatch() — brief validation, questions
              ├─ A2: orchestrator._create_execution_plan()  — pure routing, no execution
              ├─ G1: asyncio.gather() across parallel group (market_strategy, compliance, ...)
              └─ G2+: sequential per group (product_solution, design, ...)
```

### Agent System (`backend/agents/`)

**Adding or removing an agent** requires only two steps and zero changes to orchestrator code:
1. Edit `backend/config/agents.yaml` — add/set `enabled: false`.
2. Create `backend/agents/<name>/` with `prompt.md`, optionally `schema.py`, `tools.py`, `skills/`, `knowledge/`.

Each agent entry in `agents.yaml` declares:
- `model`: env-var key (e.g. `MODEL_COMPLIANCE`)
- `kind`: `generator` (produces artifact, checkpoint-gated) | `advisory` (read-only answer) | `reviewer` (hooks)
- `hooks`: `[pre_checkpoint_review]` for reviewer agents
- `critical`: whether failure halts the pipeline

**Registry** (`agents/registry.py`): loads the YAML, attempts to import from a hardcoded `real_agent_map`, falls back to `StubAgent`.

**BaseAgent** (`agents/base.py`): abstract class; every agent loads its system prompt from `prompt.md`, uses RAG helpers (`build_rag_context()`, `build_required_skill_context()`) to pull from the vector KB, and returns `AgentOutput`.

**Knowledge indexing**: on startup, `tools/ingest.py:ingest_all_agents()` indexes each agent's `knowledge/` and `skills/` folders into the LanceDB vector store. Unchanged files are skipped via hash check.

### State (`schemas/state.py`)
`SalesCaseState` is the shared pydantic model threaded through every agent:
- `messages` — conversation history
- `brief` — structured sales brief
- `outputs` — dict of `{agent_name: AgentOutput}`
- `visited` / `hop_depth` — anti-loop guard (reset per request in `main.py`)
- `constraints` — active `FeedbackRule` list injected per-agent at runtime
- `checkpoint` — pending human-approval gate
- `plan` — `ExecutionPlan` with `AgentTask` list and `parallel_group` integers

### SSE Events
The backend emits newline-delimited `data: {...}\n\n` JSON. Relevant event types:
- `session`, `user_message`, `content` — basic flow
- `agent_status` (thinking/completed/failed), `agent_message` — per-agent updates
- `question_card` — rendered by `QuestionCard.tsx`
- `checkpoint_card` — rendered by checkpoint UI, triggers human-approval flow
- `thinking_start`/`thinking_end` — wraps `<think>` blocks stripped from model output
- `constraint_added` — feedback rule saved to memory

### Checkpoint System (`checkpoint/manager.py`)
After agents run, `_maybe_create_checkpoint()` in `main.py` inspects outputs and creates a `Checkpoint` for generation actions: `generate_quote`, `generate_pptx`, `generate_userflow`, `generate_wireframe`. The compliance reviewer runs via `cpm.run_review_hooks()` **before** the checkpoint is shown to the user. Decisions (approve/edit/reject) are posted to `POST /workflow/interact` with `action=checkpoint_decision`.

### Memory (`repos/`, `memory/`)
- Default: SQLite (`repos/memory_sqlite.py`) for sessions, feedback rules, and profiles.
- Managed: AgentBase Memory when `AGENTBASE_MEMORY_ID` is set.
- `memory/constraint_injection.py`: merges active `FeedbackRule` objects into agent prompts.
- `memory/feedback_extractor.py`: detects feedback phrases in chat messages and saves them as `FeedbackRule` rows.

### Deployment Constraints
- Container must listen on **port 8080** (`PORT` env var, read in `main.py`).
- Must expose `GET /health → 200`.
- `GREENNODE_*` credentials are **auto-injected** by AgentBase Runtime — never put them in the deploy env file.
