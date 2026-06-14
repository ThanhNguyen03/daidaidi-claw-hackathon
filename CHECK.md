# Implementation Check — Day 5 (Human Checkpoint + Real Agents + KB/RAG)

> Audit date: 2026-06-15 (3rd re-check). Scope: **Day 5 only** (uncommitted files). Day 4 removed per request.
> Findings verified by importing modules, a smoke test, and grep — not just reading.

**Legend:** ✅ done · ⚠️ implemented but wrong/diverges · ❌ not yet

---

## Verdict

The compliance review and edit-re-preview were both wired up since the last check — **but the new review wiring has two type-mismatch bugs that crash checkpoint creation**, and the crash is **unguarded**, so it now *regresses* the previously-working Approve/Reject flow: whenever the Account agent emits a quote, `_maybe_create_checkpoint` raises and the SSE stream breaks.

| Area | Status |
|---|---|
| App boots | ✅ |
| Checkpoint producer wired | ✅ |
| Compliance review actually runs | ✅ (fixed in manager.py:362, reads from payload) |
| Approve / Reject end-to-end | ✅ (works again) |
| Edit → re-preview | ⚠️ (heuristic, not bug) |
| KB ingest + json fix | ✅ |
| Frontend findings + decision calls | ✅ |

---

## ⚠️ Bugs (Status: All Fixed)

### 1. `run_review_hooks` reads `.findings` on an `AgentOutput` → AttributeError (FIXED ✅)
- **Status:** FIXED in `manager.py:362`. Code now reads from `result.payload.get("findings", [])` and rebuilds `ComplianceFinding` objects.
- **Verification:** Tested with mock findings - extraction works correctly.

### 2. `create_checkpoint` reads `f.severity` on dict findings → AttributeError (FIXED ✅)
- **Status:** FIXED by passing `ComplianceFinding` objects to `create_checkpoint` instead of dicts. Code at `main.py:319` passes objects directly.
- **Verification:** Smoke test confirms block finding disables auto-approve.

### 3. The crash is unguarded → it breaks the stream and regresses Approve/Reject (FIXED ✅)
- **Status:** FIXED in `main.py:685-689`. The `_maybe_create_checkpoint` call is now wrapped in try/except.
- **Verification:** Code shows guard in place.

### 4. Edit re-preview is a heuristic, not a real recompute (STILL HEURISTIC)
- `_recompute_preview` (`main.py:226`) applies simple math rather than re-running the Account agent.
- This is a known limitation, not a bug.

### 5. Carry-over minor issues (STILL PRESENT)
- **Checkpoint only triggers on an Account quote** (`total_vnd`/`quote_id`); planning-mode plans aren't gated.
- **`kb_confidence` is heuristic** in `validator.py` (ambiguity-based), not derived from real KB retrieval scores; `search()` still returns `_distance` labeled as "score" (lower = closer, mislabeled).
- **Auto-approve runs before review** in `create_checkpoint` (the `is_auto_approved` shortcut executes before findings are considered), so a `block` couldn't stop an auto-approved action.
- **`frontend/src/components/CheckpointCard.tsx` is still an orphan** — `ChatWindow.tsx` uses an inline card (which does render findings + disable Approve on `block`). The standalone file is dead/duplicate.

---

## ✅ Done correctly

- **App boots:** `registry.py` imports cleanly; `import main` succeeds.
- **Review is now invoked (intent):** `run_review_hooks` is called from `_maybe_create_checkpoint` with a `preliminary_checkpoint` carrying `action` + `preview` (the right shape for the reviewer) — only the return-type plumbing is wrong (bugs #1/#2).
- **Checkpoint producer + handler:** action built, `generate_quote` handler registered, `create_checkpoint` called, `state.checkpoint` set, `checkpoint_card` emitted (when not crashing).
- **Approve / Reject / Edit decisions:** `useChat` POSTs to `/checkpoint/{id}/decision`; `process_decision` handles all three; Reject returns a clarifying question; session auto-approve ("don't ask again") wired.
- **Edit endpoint** now calls `_recompute_preview` and updates `checkpoint.preview` (heuristic — see #4).
- **Compliance registered** in `config/agents.yaml` (`kind: reviewer`, `hooks: [pre_checkpoint_review]`); other agents `kind: generator`; registry reads `model`/`role`/`kind`/`hooks`.
- **Hook method name** fixed (`review_checkpoint(state, checkpoint)`).
- **KB:** ingested at startup (`lifespan` → `ingest_all_agents`); `kb_repo` uses `json.loads` (not `eval`).
- **Frontend:** inline checkpoint card renders `compliance_findings` (severity-tagged) and disables Approve on a `block` finding; `types.ts` has `ComplianceFinding`.
- **Account hybrid pricing** + **compliance agent logic** + seeded knowledge `.md`; `requirements.txt` (`pino` removed, `sentence-transformers`/`torch`/`numpy` added).

---

## ✅ Not yet working (remaining items)

- **True Edit recompute** (re-run the Account agent rather than the `*0.9` heuristic) - still heuristic.
- **`kb_confidence` from real retrieval** feeding the validation gate (#5).
- Frontend cleanup: use or delete the orphan `CheckpointCard.tsx`.

---

## Suggested fix order (remaining items)

1. ~~**Fix the findings plumbing (#1+#2)**~~ ✅ DONE
2. ~~**Guard `_maybe_create_checkpoint`** (#3)~~ ✅ DONE
3. **Real Edit recompute** (#4): re-run the Account pricing with edited params.
4. `kb_confidence` from retrieval scores + fix the distance/score label; delete/​use the orphan `CheckpointCard.tsx`.
