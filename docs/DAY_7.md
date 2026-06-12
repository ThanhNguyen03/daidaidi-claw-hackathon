# DAY 7 — Brainstorm Mode + Deploy + Hardening

> One-line goal: a deployed demo runs across all 4 modes, including a stable 3-agent + user brainstorm with working token/round controls.

## 1. Objective

Ship the last mode and make the whole thing deployable and robust: **Brainstorm** (moderator turn-selection, convergence detection, ASK-LOCK, timeouts, group-chat UI — A.4 / C.3 / C.5 §7), **deploy** the backend as a Custom Agent on AgentBase Runtime + the frontend separately, and **harden** (parallel partial-failure handling, retries, secrets off client, rate-limit). "Done" = a deployed, demo-able system across all 4 modes.

## 2. Prerequisites

- Days 1–6 complete (orchestrator, validation, memory, checkpoint, generation, modes).
- AgentBase account/creds for the deploy step (frontend host decision is a non-blocking G item).

## 3. Task checklist

### Backend — brainstorm moderator (A.4 / B.3)
- [ ] `backend/brainstorm/moderator.py` — Orchestrator-as-**light moderator** (A.2 Q5): frames the question, **relevance-based next-speaker selection** (not blind round-robin), manages turns over an append-only `transcript` channel in state.
- [ ] **Convergence/repeat detector** (A.4): embed each new opinion; cosine-sim to that agent's last 3 points `> ~0.9` = repeat; **>3 repeats → auto-stop** and request user input. **Max-round cap** (e.g. 8) as a hard backstop.
- [ ] **ASK-LOCK** (C.5 §7): single mutex `ask_lock` in brainstorm state; only the lock-holder may question the user; **moderator-prioritized by relevance** (not strict FIFO — G Q8); each agent still batches its questions.
- [ ] **Timeouts** (A.4): no user reply >15 min → **freeze**; >1 hr total → **auto-end**. **Transcript retention 24h** then purge (config flag).

### Backend — error handling & hardening (B.5)
- [ ] Parallel fan-out partial-failure: a failing agent returns `status=FAILED` (does not abort others); **1 automatic retry w/ backoff** for transient errors. After the barrier: critical failure → surface + offer retry/skip; non-critical → proceed and note the gap honestly.
- [ ] Basic rate-limit on the API; confirm secrets (`LLM_API_KEY`) stay server-side (BFF route only).

### Frontend — brainstorm group chat (C.3)
- [ ] `frontend/src/components/BrainstormView.tsx` — each agent has its own **avatar/name/colored bubble**; user bubble distinct; moderator lines styled neutral/system.
- [ ] **Add-members modal** (messaging-app style): checkboxes of available agents; add/remove participants before/while brainstorming.
- [ ] **User interjection** first-class: user can type any time → injected into shared transcript → moderator re-routes. While an agent holds the ASK-LOCK, composer shows "Tech agent is asking you →" and others visibly wait.
- [ ] Subtle **round / token meter** showing progress toward the max-round cap.

### Deploy (G Q11)
- [ ] Backend: Docker build → push to **Container Registry** → **AgentBase Runtime** create (Custom Agent, PUBLIC or VPC). Health check + auto-injected creds per the Runtime Service Contract.
- [ ] Frontend deployed separately (host per the non-blocking G confirmation).
- [ ] Smoke-test via `/agentbase-monitor` (logs + metrics).
- [ ] Seed data + a written **demo script** covering all 4 modes.

## 4. Key interfaces / contracts introduced today

- `moderator.py`: relevance-based speaker selection, convergence detector, `ask_lock` mutex, freeze/auto-end timeouts, 24h retention flag.
- B.5 error policy: `FAILED` isolation + 1 retry + critical-vs-non-critical post-barrier decision.
- Deploy artifacts: `Dockerfile`, Container Registry image, Runtime runtime config.
- Stream/WS: brainstorm uses **WebSocket** for bidirectional multi-party chat (SSE remains for one-way token streams — E).

## 5. Deliverable & verification

**Deliverable:** deployed demo run across all 4 modes; brainstorm with 3 agents + user, stable token/round controls.

**Verify:**
1. Start a brainstorm with 3 selected agents → moderator frames the question, picks relevant speakers (not all every round), bubbles render per-agent.
2. Force repeated opinions → convergence detector auto-stops at >3 repeats and asks the user; confirm the max-round cap also halts a runaway.
3. Two agents want to ask the user → only the lock-holder asks (moderator-prioritized); the other waits with the visible "waiting" state; lock releases after answer.
4. No user reply >15 min → thread freezes; (simulate) >1 hr → auto-ends; transcript viewable for 24h then purged.
5. Kill one agent mid parallel fan-out → others complete; critical failure surfaces with retry/skip; non-critical proceeds with an honest gap note.
6. Deploy backend to AgentBase Runtime + frontend separately → run the full demo script across Chat/Planning/Execute/Brainstorm; confirm health + logs in `/agentbase-monitor` and that `LLM_API_KEY` is never exposed to the client.

## 6. Out of scope / deferred (post-hackathon)

- Identity/OAuth2 for full Figma (FigJam covers wireframes; `DesignBackend` keeps the upgrade quick).
- Admin UI to manage per-agent skills/knowledge (filled manually for the demo).
- Swap to Postgres + pgvector + Redis behind the existing repo interfaces.
- Non-preview, fully downloadable artifact fidelity (stretch goal).
