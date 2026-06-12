# DAY 2 — Orchestrator + Agent Registry + Routing

> One-line goal: a brief enters the Orchestrator (supervisor node), which dispatches to ≥2 config-driven stub agents and streams back an aggregated answer — with the anti-loop guard in place.

## 1. Objective

Build the multi-agent skeleton: the **Supervisor/Router** pattern (B.1) as a LangGraph graph, a **config-driven agent registry** (add/remove an agent = edit `config/agents.yaml`, never the core), the **standardized `AgentOutput` contract** in shared `SalesCaseState`, and the **anti-loop guard** (visited-set + hop-depth). "Done" = orchestrator plans → dispatches → aggregates, with all 6 agents present as structured stubs.

## 2. Prerequisites

- Day 1 schemas (`SalesCaseState`, `AgentOutput`, `NeedsRequest`), `get_llm_client`, `MemoryRepo`, `SQLiteCheckpointSaver` stub.

## 3. Task checklist

### Backend — agent contract & registry (cross-cutting convention)
- [ ] `backend/agents/base.py` — `BaseAgent` contract: `name`, `model_key`, `system_prompt` (loaded from `prompt.md`), and `async run(state: SalesCaseState) -> AgentOutput`. Every agent returns the standardized `AgentOutput` (B.2 / B.4).
- [ ] `backend/agents/registry.py` — `AgentRegistry` that loads `config/agents.yaml`, instantiates each agent (binding its `MODEL_*` key + prompt/skills/knowledge folder), and exposes `get(name)`, `all()`, `routing_descriptions()` (the short role line per agent the orchestrator routes on).
- [ ] `config/agents.yaml` — one entry per agent: `name`, `model` (env key), `role` (one-line routing description), `enabled`. Include all 6: `orchestrator`, `market_strategy`, `tech_solution`, `account`, `adtimabox`, `design`. (AdtimaBox one-liner is a non-blocking confirmation per G — use a placeholder role now.)
- [ ] Scaffold `backend/agents/<name>/{prompt.md, schema.py, tools.py, skills/, knowledge/}` for each of the 6 agents (prompts can be minimal stubs today).

### Backend — orchestrator supervisor + graph
- [ ] `backend/agents/orchestrator.py` — supervisor node (A.3): owns the `ExecutionPlan`, reads returned `AgentOutput`s + `validation_status`, decides the next hop. It is a **node function re-entered at each routing point**, not a separate service (A.3 Q3). Honors/denies `NeedsRequest` based on the anti-loop guard (B.4).
- [ ] `backend/agents/graph.py` — assemble the LangGraph `StateGraph` over `SalesCaseState`: orchestrator node + one node per registered agent + conditional edges via `Command(goto=...)`; attach the checkpointer (SQLite fallback from Day 1, AgentBase bridge later). Use `create_supervisor`-style wiring (B.1).
- [ ] Anti-loop guard (A.1 / B.4): track `visited: list[str]` + `hop_depth: int` in state; **max hop depth default 4**; a repeat request for an already-run agent on the same sub-task is denied and surfaced to the user.

### Backend — dispatch patterns (A.1)
- [ ] Sequential dependency (A→output→B) and independent fan-out (parallel) both supported; results aggregated into `state.outputs[agent_name]` keyed by agent name (B.2).
- [ ] Stub each agent's `run()` to return a deterministic `AgentOutput(status=COMPLETE, payload=..., summary=...)` so routing can be exercised without real agent logic.

### Backend — wire into the API
- [ ] Replace the Day-1 single-LLM `process_message` path with a graph invocation; stream the orchestrator's aggregated answer + per-agent `summary` lines over SSE.

### Frontend
- [ ] `frontend/src/components/Sidebar.tsx` — live **"active agents" list** with status dots (idle / thinking / waiting-for-you / failed) fed from stream events (C.1).
- [ ] Emit per-agent stream events (`{type:"agent_status", agent, status}`) so the sidebar can reflect dispatch in real time.

## 4. Key interfaces / contracts introduced today

- `BaseAgent.run(state) -> AgentOutput`; `AgentRegistry` (`get/all/routing_descriptions`).
- `config/agents.yaml` keys: `name, model, role, enabled`.
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
