# DAY 2 — Orchestrator + Agent Registry + Routing

> One-line goal: a brief enters the Orchestrator (supervisor node), which dispatches to ≥2 config-driven stub agents and streams back an aggregated answer — with the anti-loop guard in place.

## 1. Objective

Build the multi-agent skeleton: the **Supervisor/Router** pattern (B.1) as a LangGraph graph, a **config-driven agent registry** (add/remove an agent = edit `config/agents.yaml`, never the core), the **standardized `AgentOutput` contract** in shared `SalesCaseState`, and the **anti-loop guard** (visited-set + hop-depth). "Done" = orchestrator plans → dispatches → aggregates, with all 6 agents present as structured stubs.

## 2. Prerequisites

- Day 1 schemas (`SalesCaseState`, `AgentOutput`, `NeedsRequest`), `get_llm_client`, `MemoryRepo`, `SQLiteCheckpointSaver` stub.

## 3. Task checklist

### Backend — agent contract & registry (cross-cutting convention)
- [x] `backend/agents/base.py` — `BaseAgent` contract: `name`, `model_key`, `system_prompt` (loaded from `prompt.md`), and `async run(state: SalesCaseState) -> AgentOutput`. Every agent returns the standardized `AgentOutput` (B.2 / B.4).
- [x] `backend/agents/registry.py` — `AgentRegistry` that loads `config/agents.yaml`, instantiates each agent (binding its `MODEL_*` key + prompt/skills/knowledge folder), and exposes `get(name)`, `all()`, `routing_descriptions()` (the short role line per agent the orchestrator routes on).
- [x] `config/agents.yaml` — one entry per agent: `name`, `model` (env key), `role` (one-line routing description), `enabled`. Include all 6: `orchestrator`, `market_strategy`, `tech_solution`, `account`, `adtimabox`, `design`. (AdtimaBox one-liner is a non-blocking confirmation per G — use a placeholder role now.)
- [x] Scaffold `backend/agents/<name>/{prompt.md, schema.py, tools.py, skills/, knowledge/}` for each of the 6 agents (prompts can be minimal stubs today).

### Backend — orchestrator supervisor + graph
- [x] `backend/agents/orchestrator.py` — supervisor node (A.3): owns the `ExecutionPlan`, reads returned `AgentOutput`s + `validation_status`, decides the next hop. It is a **node function re-entered at each routing point**, not a separate service (A.3 Q3). Honors/denies `NeedsRequest` based on the anti-loop guard (B.4).
- [x] `backend/agents/graph.py` — assemble the LangGraph `StateGraph` over `SalesCaseState`: orchestrator node + one node per registered agent + conditional edges via `Command(goto=...)`; attach the checkpointer (SQLite fallback from Day 1, AgentBase bridge later). Use `create_supervisor`-style wiring (B.1).
- [x] Anti-loop guard (A.1 / B.4): track `visited: list[str]` + `hop_depth: int` in state; **max hop depth default 4**; a repeat request for an already-run agent on the same sub-task is denied and surfaced to the user.

### Backend — dispatch patterns (A.1)
- [x] Sequential dependency (A→output→B) and independent fan-out (parallel) both supported; results aggregated into `state.outputs[agent_name]` keyed by agent name (B.2).
- [x] Stub each agent's `run()` to return a deterministic `AgentOutput(status=COMPLETE, payload=..., summary=...)` so routing can be exercised without real agent logic.

### Backend — wire into the API
- [x] Replace the Day-1 single-LLM `process_message` path with a graph invocation; stream the orchestrator's aggregated answer + per-agent `summary` lines over SSE.

### Frontend
- [x] `frontend/src/components/Sidebar.tsx` — live **"active agents" list** with status dots (idle / thinking / waiting-for-you / failed) fed from stream events (C.1).
- [x] Emit per-agent stream events (`{type:"agent_status", agent, status}`) so the sidebar can reflect dispatch in real time.

### Backend — scalable agent pool: extension contract + Compliance stub (B.6) — ADDED
> Extends the completed Day-2 work. Keeps the pool **open for extension, closed for modification**: add/remove an agent via config + folder only, never editing the orchestrator/graph.
- [ ] Extend the `config/agents.yaml` entry schema with `kind` (`generator|advisory|reviewer`), optional `hooks: [...]`, and `critical` (B.5). Update `registry.py` to read these; existing 6 agents default `kind: generator`/`advisory` as appropriate — **no behavior change** for them.
- [ ] Define generic **hook points** in the orchestrator: `pre_checkpoint_review` (and `post_brief_validate`). A `reviewer` agent that subscribes via `hooks:` is invoked generically at that point — the orchestrator **never special-cases an agent name**. (Hook *runs* land Day 5; define the plumbing + no-op now.)
- [ ] Register **Compliance** as the 7th agent: add `compliance` to `agents.yaml` (`kind: reviewer`, `hooks: [pre_checkpoint_review]`, `model: MODEL_COMPLIANCE`, `critical: false`, role per B.6) + scaffold `backend/agents/compliance/{prompt.md, schema.py, tools.py, skills/, knowledge/}`; stub `run()` returns a deterministic `AgentOutput` (empty `findings`).
- [ ] Add `MODEL_COMPLIANCE` to `.env.example` (Qwen 3 path) + README "Available Agents".

## 4. Key interfaces / contracts introduced today

- `BaseAgent.run(state) -> AgentOutput`; `AgentRegistry` (`get/all/routing_descriptions`).
- `config/agents.yaml` keys: `name, model, role, enabled` + (B.6) `kind` (`generator|advisory|reviewer`), `hooks`, `critical`.
- Orchestrator **hook points**: `pre_checkpoint_review`, `post_brief_validate` (reviewer agents subscribe via `hooks:`; orchestrator never special-cases a name).
- Orchestrator routing contract: consumes `AgentOutput.status` ∈ {COMPLETE, NEEDS_INPUT, NEEDS_AGENT, FAILED} and `NeedsRequest{agent, reason, context}`.
- Anti-loop guard: `visited`, `hop_depth` (default max 4).
- Graph: LangGraph `StateGraph[SalesCaseState]` + `Command(goto=...)` handoff + checkpointer.

## 5. Deliverable & verification

**Deliverable:** brief → orchestrator → dispatches to ≥2 stub agents → aggregated answer streamed.

**Verify:**
1. `POST /chat/stream` with a brief that should fan out (e.g. "Plan a launch for an F&B client") → SSE shows orchestrator selecting ≥2 agents, `agent_status` events, then an aggregated answer.
2. Add/remove an agent purely by editing `config/agents.yaml` (`enabled: false`) — restart, confirm routing changes with **no code edits** (config-driven requirement).
3. Force a loop (stub an agent to keep emitting `NEEDS_AGENT` for an already-visited agent) → orchestrator denies after the guard trips and surfaces the denial to the user.
4. `state.outputs` is keyed by agent name and readable by a downstream node (`state.outputs["tech_solution"].payload`).

## 6. Out of scope / deferred

- Validation gate / QuestionStack (orchestrator currently dispatches without gating) → **Day 3**.
- Real agent reasoning + KB → **Day 5**.
- Brainstorm moderator turn-selection → **Day 7**.
- Real checkpointer persistence/resume across sessions → **Day 4**.

## Implementation Notes

### Day 2 Complete ✅
All checklist items completed as of 2026-06-13.

### Architecture Overview
```
backend/
├── agents/
│   ├── base.py          # BaseAgent + StubAgent
│   ├── registry.py     # Config-driven AgentRegistry
│   ├── orchestrator.py # Supervisor node logic
│   ├── graph.py       # LangGraph assembly + SimpleAgentRunner
│   ├── __init__.py
│   └── {agent}/
│       └── prompt.md  # System prompts for each agent
└── config/
    └── agents.yaml    # Agent configuration
```

### Key Components

1. **BaseAgent** - Abstract contract for all agents
2. **StubAgent** - Returns deterministic sample data for testing
3. **AgentRegistry** - Loads agents from YAML config
4. **Orchestrator** - Supervisor logic with anti-loop guard
5. **SimpleAgentRunner** - Simple sequential execution for Day 2
6. **AgentGraph** - Full LangGraph assembly (for future days)

### Frontend Updates
- `useChat.ts` - Now tracks `activeAgents` state
- `Sidebar.tsx` - Displays agent status with colored dots
- SSE events now include `agent_status` type

### Testing the Dispatch
```bash
# Use planning mode to trigger multi-agent dispatch
curl -N -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Create a sales plan for an F&B client with 180M VND budget",
    "salesperson_id": "sp_test",
    "mode": "planning"
  }'
```

### Anti-Loop Behavior
- Max hop depth: 4 (configurable in Orchestrator)
- When agent requests another already-visited agent:
  - If depth < 4: Ask user "Do you want to consult X again?"
  - If depth >= 4: Deny with "Maximum hop depth reached"