# DAY 3 — Validation & Active Questioning (QuestionStack)

> One-line goal: an incomplete brief is caught by the validation pre-pass, turned into ONE batched, prioritized question card, and only dispatches to agents once the brief is `READY`.

## 1. Objective

Implement the **validation gate** (C.5) so the Orchestrator never dispatches while mandatory questions are open. A cheap fast-model (Gemma 4) pre-pass emits a `ValidationReport` (missing/ambiguity/severity); the `QuestionStack` batches + prioritizes questions, maps answers back to brief fields, and re-validates until `READY` or `BLOCKED`. "Done" = the C.5 §3 sequence diagram works end-to-end with a distinct question-card UI.

## 2. Prerequisites

- Day 1 schemas (`ValidationReport`, `Question`, `Ambiguity`, `Brief`).
- Day 2 orchestrator + graph + registry (the gate plugs in *before* dispatch).

## 3. Task checklist

### Backend — validation pre-pass (C.5 §1)
- [x] `backend/validation/validator.py` — `async validate(brief, profile) -> ValidationReport` using the **Gemma 4** fast model (`MODEL_VALIDATION`). Emits `missing_required`, `ambiguities[{field, interpretations, why}]`, `kb_confidence`, `out_of_scope`, `status ∈ {READY,PENDING,BLOCKED}`.
- [x] Trigger conditions (C.5 §1): missing mandatory field, ≥2 plausible interpretations, KB confidence `< 0.7`, out-of-scope, first interaction with a new salesperson, post-correction recovery.
- [x] **Severity / `revalidation_impact` classifier** (C.5 §6): tag each field so the orchestrator knows non-critical edits (budget 100M→200M) skip re-validation while critical edits (industry/tech-stack switch) force it.

### Backend — QuestionStack (C.5 §2)
- [x] `backend/validation/question_stack.py` — `QuestionStack`:
  - `push(questions)`, `next_batch() -> list[Question]` (unanswered, sorted by priority, **mandatory first**, dedup already-asked).
  - `map_answers(answers)` → set `Question.answer`/`answered`, write through to the matching `Brief.target_field` (LLM-assisted mapping when the user replies in free text — C.5 §5).
  - Re-ask only the *remaining* unanswered questions on a partial answer (C.5 §6); never re-ask an answered one.
- [x] Optional questions always carry a stated `assumption` + Skip = implicit approval of that assumption (C.5 §6).

### Backend — orchestrator gate (C.5 §3)
- [x] Insert a validation node before dispatch: `BLOCKED` → stop + tell user what's critically missing; `PENDING` → push to QuestionStack, emit one batched question message, **do not dispatch**; `READY` → dispatch per plan (Day 2).
- [x] On brief update, run the **severity-gated** re-validation logic.

### Frontend — question card (C.5 §5, C.1)
- [x] `frontend/src/components/QuestionCard.tsx` — visually distinct (**yellow left-border + `?` icon**), numbered list; mandatory tagged `(required)`, optional tagged `(optional — if skipped, I'll assume: …)` with a **Skip** affordance.
- [x] Per-question inline quick-reply field **and** a free-text reply path (backend maps free text → `target_field`).
- [x] Ensure question cards are visually distinct from (future) checkpoint cards (C.5-UI note: yellow/`?` vs neutral/action).

## 4. Key interfaces / contracts introduced today

- `validate(brief, profile) -> ValidationReport` (Gemma 4 pre-pass).
- `QuestionStack.next_batch()` / `map_answers()`; `Question` fields `priority, is_mandatory, assumption, target_field, asked_count, answered, answer`.
- Orchestrator gate states: `PENDING` (ask, don't dispatch) / `READY` (dispatch) / `BLOCKED` (stop + notify).
- `revalidation_impact` field tagging on the validation pre-pass.
- Stream events: `{type:"question_card", questions:[...]}`.

## 5. Deliverable & verification

**Deliverable:** incomplete brief → batched questions → answers → dispatch (the C.5 §3 sequence diagram working).

**Verify:**
1. Send a brief missing `industry` + `budget` → backend returns ONE question card (mandatory `industry` listed before optional `budget`), and **no agent dispatch occurs**.
2. Answer only `industry` (partial) → re-validate → only `budget` is re-asked (optional, with stated assumption + Skip).
3. Skip the optional question → orchestrator proceeds using the stated assumption; verify the assumption was recorded as implicit approval.
4. Provide a critically-missing-only brief → status `BLOCKED` → user told exactly what's missing, still no dispatch.
5. Reply in free text ("F&B, around 150 triệu") → answers correctly mapped to `industry` and `budget_vnd`.
6. Edit budget 100M→200M (non-critical) → no re-validation; switch industry (critical) → re-validation fires.

## 6. Out of scope / deferred

- Learning from question helpfulness / `question_frequency` tuning / frustration detection → **Day 4** (C.5 §4 learning).
- History-based pre-filled suggested answers → **Day 4** (needs profile).
- ASK-LOCK (brainstorm one-agent-asks-at-a-time) → **Day 7** (C.5 §7).

---

## Implementation Notes

### Day 3 Complete ✅
All checklist items completed as of 2026-06-14.

### Architecture Overview

```
backend/
├── validation/
│   ├── __init__.py
│   ├── validator.py       # ValidationService with Gemma 4
│   └── question_stack.py  # QuestionStack + QuestionManager
└── agents/
    └── orchestrator.py    # Updated with validate_before_dispatch()
```

### Key Components

1. **ValidationService** (`validator.py`)
   - `validate()` - Main validation using Gemma 4
   - `_detect_ambiguities()` - LLM-powered ambiguity detection
   - `validate_with_severity()` - Severity-gated re-validation (C.5 §6)

2. **QuestionStack** (`question_stack.py`)
   - `push()` - Add questions with deduplication
   - `next_batch()` - Get prioritized questions (mandatory first)
   - `map_answers()` - Map answers to brief fields
   - `map_free_text_answer()` - Parse free text (e.g., "F&B, 150 triệu")

3. **QuestionManager** (`question_stack.py`)
   - `generate_questions_from_validation()` - Create questions from validation report
   - `skip_optional()` - Skip optional question with assumption

4. **Orchestrator** (`orchestrator.py`)
   - `validate_before_dispatch()` - C.5 §3 gate implementation
   - `handle_validation_response()` - Process user answers
   - `handle_severity_gated_revalidation()` - Non-critical edits skip validation

### API Endpoints (Day 3)

- `POST /chat/answer` - Answer a single question
- `POST /chat/skip_question` - Skip optional question
- `POST /chat/answer_free_text` - Answer multiple via free text

### SSE Events

- `{type: "question_card", questions: [...]}` - Question card to display
- `{type: "error", error: "..."}` - Blocked status

### Testing the Validation Gate

```bash
# Test 1: Missing mandatory field - should show questions
curl -N -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Create a sales plan",
    "salesperson_id": "sp_test",
    "mode": "planning"
  }'

# Test 2: Complete brief - should dispatch to agents  
curl -N -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Create a sales plan for F&B client",
    "salesperson_id": "sp_test",
    "mode": "planning",
    "brief": {"industry": "F&B", "goal": "Q3 launch"}
  }'

# Test 3: Free text answer mapping
curl -X POST http://localhost:8000/chat/answer_free_text \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_xxx",
    "message": "F&B, 150 triệu, Q3 launch",
    "salesperson_id": "sp_test",
    "mode": "planning"
  }'
```