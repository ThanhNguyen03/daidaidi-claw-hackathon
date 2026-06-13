# DAY 5 — Human Checkpoint + Real Agent Logic + KB/RAG

> One-line goal: a Planning/Execute flow produces a previewed plan/quotation gated by a working checkpoint — Approve executes, Edit re-previews, Reject asks-only — and agents now answer from per-agent knowledge via RAG.

## 1. Objective

Make agents *real* and gate every side-effecting generation behind the **human checkpoint** (A.2). Add per-agent **KB/RAG** (LanceDB + bge embeddings/rerank) and the **hybrid Account pricing** (deterministic rate-card + grounded LLM estimate). "Done" = an end-to-end previewed artifact is produced only after explicit approval, with correct Edit/Reject semantics.

## 2. Prerequisites

- Day 2 agents/registry/graph; Day 3 validation gate; Day 4 memory + constraint injection.
- Day 1 `Checkpoint`/`CheckpointAction` schemas + `KBRepo` interface stub.

## 3. Task checklist

### Backend — checkpoint manager (A.2 / C.4 / G Q10)
- [ ] `backend/checkpoint/manager.py` — uses LangGraph **interrupt-before-tool**: every checkpoint maps to exactly **one side-effecting tool call** (MCP write / file gen / pricing commit); read-only steps never checkpoint (A.2).
- [ ] State machine: `PreviewBuilt → AwaitingDecision → {Executing (APPROVE) | Recompute (EDIT) | Rejected (REJECT)}`.
  - **Edit:** re-run only the preview computation, show the card again, **never auto-execute**.
  - **Reject:** MUST NOT call the tool; post one clarifying question ("Action rejected — how would you like to adjust?"); volunteer nothing new unless asked.
- [ ] **Session-scoped auto-approve** (Q10 / A.1): per-action-type opt-in "Don't ask again for [type] this session"; auto-approves that type for the rest of the session, **re-armed on new session**; irreversible/external actions (`send_external`) are excluded and always checkpoint.
- [ ] No hard auto-reject timeout (A.2 Q2): checkpoint persists as `AWAITING` via the checkpointer; soft visual reminder only.

### Backend — KB / RAG (E / G Q3)
- [ ] `backend/repos/kb_repo.py` — `KBRepo` impl over **LanceDB**; `KBRepo` is the swappable interface (pgvector later).
- [ ] `backend/kb/ingest.py` — ingest per-agent `agents/<name>/knowledge/*.md` with **pluggable loaders** (md now; PDF/CSV/PNG = future). Embeddings via GreenNode **`bge-m3`**, rerank via **`bge-reranker-v2-m3`** (multilingual incl. Vietnamese).
- [ ] Add RAG retrieval into `BaseAgent.run()`; feed `kb_confidence` back to the validation gate (C.5 §1 low-confidence → ask not hallucinate).

### Backend — flesh out agents + Account hybrid pricing (G Q6–7)
- [ ] Replace the Day-2 stubs with real prompts/logic for Market/Strategy, Tech Solution, Account, Design (intent), AdtimaBox.
- [ ] `backend/agents/account/pricing.py` — **hybrid**: deterministic **rate-card lookup** for listed items (LLM narrates/explains) + **LLM suggestion grounded in use-case KB/search** for custom features not on the rate-card (flagged as an estimate). Both pass through the checkpoint.
- [ ] Seed a demo `rate-card` (e.g. `backend/agents/account/knowledge/rate_card.md` or `.csv`).

### Backend — Compliance agent: advisory + pre-checkpoint review (B.6)
- [ ] Ingest policy KB into `backend/agents/compliance/knowledge/` (company policy, product policy, regulatory/industry rules as `.md`) via the same `ingest.py` loaders.
- [ ] `backend/agents/compliance/` — implement both modes: **advisory** (answer policy questions on intent match, grounded in the policy KB) and **reviewer** (the `pre_checkpoint_review` hook defined Day 2).
- [ ] Define the Compliance payload in `backend/agents/compliance/schema.py`: `{ findings: [{severity: "block"|"warn"|"info", policy_ref, message, suggestion}], overall: "ok"|"warn"|"block" }`.
- [ ] Orchestrator runs subscribed `reviewer` agents at `pre_checkpoint_review` **generically** (no name special-casing): scan the pending plan/quote → attach `findings` to the `Checkpoint` before it is shown. A `block` finding disables `auto_approve_session` for that card and surfaces the reason; `warn`/`info` are shown but non-blocking. Compliance never side-effects (advisory only).

### Frontend — Compliance findings surfacing
- [ ] Render Compliance `findings` inside the **CheckpointCard** (severity-tagged) and in the **Context-panel advisories** list, so policy guidance appears exactly where the salesperson decides.

### Frontend — checkpoint card (C.4)
- [ ] `frontend/src/components/CheckpointCard.tsx` — neutral/action style (distinct from yellow question card): human-readable **preview**, **editable inline parameters**, buttons **Approve** (primary) / **Edit** (re-previews) / **Reject** (collapses to rejected state + posts the single clarifying question). Optional "don't ask again for this action this session" checkbox.

## 4. Key interfaces / contracts introduced today

- Checkpoint state machine + `Checkpoint.status ∈ {AWAITING, APPROVED, EDITED, REJECTED}`, `auto_approve_session`.
- `KBRepo` (LanceDB) + `ingest()` pluggable loaders + bge embeddings/rerank.
- `account/pricing.py` hybrid: `lookup_rate_card()` + `estimate_custom_feature()` (flagged estimate).
- Compliance `findings` payload + generic `pre_checkpoint_review` hook execution; findings attached to `Checkpoint`; `block` disables auto-approve.
- Stream events: `{type:"checkpoint_card", checkpoint:{...}}` (now includes `findings`), decision endpoint `POST /checkpoint/{id}/decision {approve|edit(params)|reject}`.

## 5. Deliverable & verification

**Deliverable:** Planning/Execute flow produces a previewed plan/quotation gated by a working checkpoint **with Compliance findings attached**; edit re-previews; reject asks-only.

**Verify:**
1. Execute mode → request a quotation → a checkpoint card shows the preview (e.g. "Quotation 180M VND") with **no side effect** yet.
2. **Approve** → the tool runs and the artifact is produced/committed.
3. **Edit** budget 200M→150M → preview recomputes and the card reappears; confirm it did **not** auto-execute.
4. **Reject** → card collapses; agent posts exactly one clarifying question and proposes nothing new.
5. Check "don't ask again for quotations this session" → next quotation this session auto-approves; start a new session → it asks again. Confirm `send_external` always checkpoints regardless.
6. Ask a question answerable from a per-agent `knowledge/*.md` → answer cites/uses the KB; ask something outside the KB → low `kb_confidence` triggers a question instead of a hallucination.
7. Quote a listed item (rate-card hit, narrated) vs a custom feature (LLM estimate, **flagged as estimate**).
8. **Compliance advisory:** ask "is offering a 30% discount to a competitor's client allowed?" → Compliance answers from the policy KB.
9. **Compliance review:** generate a quote/plan that violates a seeded policy → the checkpoint card shows a `warn`/`block` finding + suggested compliant alternative; a `block` finding prevents "don't ask again" auto-approve and shows the reason.
10. Disable `compliance` in `agents.yaml` → reviews stop with no other behavior change (proves the hook is generic, not wired into the core).

## 6. Out of scope / deferred

- Actual PPTX/userflow/wireframe **generation** behind the checkpoint → **Day 6** (today the "tool" can be a stub/preview).
- MCP gateway registration → **Day 6**.
- Brainstorm mode → **Day 7**.
