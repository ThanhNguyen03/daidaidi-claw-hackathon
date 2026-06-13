# DAY 4 — Memory & Learning

> One-line goal: "don't suggest discount anymore" is parsed into a typed constraint, persisted cross-session, and **provably suppresses** discount suggestions in a brand-new session.

## 1. Objective

The most important day for the demo's "wow": durable **short-term** session state (LangGraph checkpointer bridge) + **long-term learning** (feedback rules, profile, KB facts) that is **structurally injected** into agent prompts — not "hopefully remembered" (A.3 / D). "Done" = feedback persists across sessions and demonstrably changes agent behavior, with the active constraints visible in the Context panel.

## 2. Prerequisites

- Day 1 `MemoryRepo` + `SQLiteCheckpointSaver` + `FeedbackRule`/`SalespersonProfile` schemas.
- Day 2 orchestrator + agent prompts (injection target).
- Day 3 QuestionStack (style/`question_frequency` signals come from here).

## 3. Task checklist

### Backend — short-term memory (D.1)
- [ ] Wire the **checkpointer** into the graph keyed by `thread_id = session_id`: AgentBase Memory bridge (`AgentBaseMemoryEvents(memory_id=AGENTBASE_MEMORY_ID)` as a `CheckpointSaver`, IAM auth auto-injected on Runtime) **primary**, `SQLiteCheckpointSaver` **fallback** — both behind `MemoryRepo` so the app runs with or without the platform. Requests must carry `X-GreenNode-AgentBase-User-Id` (→ `actor_id`) + `X-GreenNode-AgentBase-Session-Id` (→ `thread_id`); error out if missing (no silent defaults).
- [ ] Rolling **session summary** + bounded message window to keep token use bounded on long chats (D.1).
- [ ] Persist/resume `SalesCaseState` so a pending checkpoint or open question survives a reload (durable thread state).

### Backend — feedback extractor → typed rules (D.2)
- [ ] `backend/memory/feedback_extractor.py` — `async extract(message, context) -> Optional[FeedbackRule]`: classify a user utterance as `rule | preference | fact`; build `FeedbackRule{type ∈ NEGATIVE_CONSTRAINT/POSITIVE_CONSTRAINT/PREFERENCE, scope:[agents], rule, source_quote, active}`.
- [ ] Persist via `MemoryRepo.save_feedback_rule`; load active rules per salesperson on every turn (`load_feedback_rules(salesperson_id, active_only=True)`).
- [ ] **Constraint injection** (D.2): prepend active in-scope rules to the system prompt of the relevant agents (e.g. Account + Orchestrator) so a discount suggestion is never even generated. Make injection a shared helper used by `BaseAgent`.

### Backend — profile & learning (C.5 §4 / D.3)
- [ ] `backend/memory/profile.py` — create/update `SalespersonProfile` after each decision (chosen solution, accepted/rejected proposal, question helpfulness, style signals).
- [ ] Style learning: infer `terse|balanced|detailed` from answer length/format → adapt question phrasing + answer verbosity.
- [ ] `question_frequency = useful_answers / total_questions_asked`; **frustration detection** ("why do you keep asking") lowers it and biases toward stated assumptions.
- [ ] **History-based suggested answers** (C.5 §6): when a profile exists, pre-fill likely answers ("Last time you chose Solution A — same this time?") so the user confirms instead of typing.

### Frontend — Context panel (C.1)
- [ ] `frontend/src/components/ContextPanel.tsx` — collapsible right panel showing: brief summary, **active constraints** (learned feedback rules so the user sees *why* the agent behaves a certain way), and a revoke affordance (toggles `FeedbackRule.active`).

## 4. Key interfaces / contracts introduced today

- `extract(message, context) -> FeedbackRule`; `FeedbackRule` persisted + loaded via `MemoryRepo`.
- Constraint-injection helper on `BaseAgent` (active rules prepended to system prompt).
- Profile updates: `style`, `question_frequency`, `preferences`, `history`, `constraints`.
- Checkpointer keyed by `thread_id = session_id` (AgentBase primary / SQLite fallback).
- Stream/REST: endpoint to list + revoke active constraints for the Context panel.

## 5. Deliverable & verification

**Deliverable:** "don't suggest discount" persists and provably suppresses discounts next session.

**Verify:**
1. In session A, say "don't suggest discount anymore" → a `NEGATIVE_CONSTRAINT` rule (`scope:[account, orchestrator]`) is created and shown in the Context panel.
2. Start a **new session** (same salesperson) and ask for a quotation → Account agent produces no discount suggestion; inspect the injected system prompt to confirm the rule is present.
3. Toggle the rule off in the Context panel → discount suggestions become possible again (revocable + transparent).
4. Kill and restart the backend → reopen the session → state resumes from the checkpointer (pending question/checkpoint intact).
5. Answer questions tersely a few times → later question phrasing/answer verbosity adapts (`style: terse`); spam-answer to trigger frustration detection → `question_frequency` drops.
6. With AgentBase env unset, all of the above still works on the SQLite fallback.

## 6. Out of scope / deferred

- KB/RAG retrieval of learned *facts* via embeddings → **Day 5** (LanceDB + bge).
- Human checkpoint state machine → **Day 5**.
- 24h brainstorm transcript retention → **Day 7**.
