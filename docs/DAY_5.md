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

### Frontend — checkpoint card (C.4)
- [ ] `frontend/src/components/CheckpointCard.tsx` — neutral/action style (distinct from yellow question card): human-readable **preview**, **editable inline parameters**, buttons **Approve** (primary) / **Edit** (re-previews) / **Reject** (collapses to rejected state + posts the single clarifying question). Optional "don't ask again for this action this session" checkbox.

## 4. Key interfaces / contracts introduced today

- Checkpoint state machine + `Checkpoint.status ∈ {AWAITING, APPROVED, EDITED, REJECTED}`, `auto_approve_session`.
- `KBRepo` (LanceDB) + `ingest()` pluggable loaders + bge embeddings/rerank.
- `account/pricing.py` hybrid: `lookup_rate_card()` + `estimate_custom_feature()` (flagged estimate).
- Stream events: `{type:"checkpoint_card", checkpoint:{...}}`, decision endpoint `POST /checkpoint/{id}/decision {approve|edit(params)|reject}`.

## 5. Deliverable & verification

**Deliverable:** Planning/Execute flow produces a previewed plan/quotation gated by a working checkpoint; edit re-previews; reject asks-only.

**Verify:**
1. Execute mode → request a quotation → a checkpoint card shows the preview (e.g. "Quotation 180M VND") with **no side effect** yet.
2. **Approve** → the tool runs and the artifact is produced/committed.
3. **Edit** budget 200M→150M → preview recomputes and the card reappears; confirm it did **not** auto-execute.
4. **Reject** → card collapses; agent posts exactly one clarifying question and proposes nothing new.
5. Check "don't ask again for quotations this session" → next quotation this session auto-approves; start a new session → it asks again. Confirm `send_external` always checkpoints regardless.
6. Ask a question answerable from a per-agent `knowledge/*.md` → answer cites/uses the KB; ask something outside the KB → low `kb_confidence` triggers a question instead of a hallucination.
7. Quote a listed item (rate-card hit, narrated) vs a custom feature (LLM estimate, **flagged as estimate**).

## 6. Out of scope / deferred

- Actual PPTX/userflow/wireframe **generation** behind the checkpoint → **Day 6** (today the "tool" can be a stub/preview).
- MCP gateway registration → **Day 6**.
- Brainstorm mode → **Day 7**.
