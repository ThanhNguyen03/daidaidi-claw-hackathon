# DAY 6 — Generation (PPTX + Userflow) + Modes

> One-line goal: an end-to-end proposal runs brief → validate → plan → approve → **PPTX deck + userflow preview** (+ quotation), with all 4 modes wired to their subgraphs.

## 1. Objective

Turn approved checkpoints into real artifacts in the **priority order from G Q12**: (1) PPTX deck, (2) userflow, then quotation export, then wireframe if time allows. Put generation behind swappable interfaces (`DesignBackend`, MCP gateway) and finish wiring the **4 modes** (Chat/Planning/Execute/Brainstorm) to subgraphs/prompts. "Done" = a previewed deck + userflow are produced after approval.

## 2. Prerequisites

- Day 5 checkpoint manager (every generation is gated) + real agents + KB.
- Day 2 graph/modes scaffolding; Day 1 MCP-fallback notion.

## 3. Task checklist

### Backend — PPTX generation (priority 1, E)
- [ ] `backend/generation/pptx.py` — **python-pptx**: open a branded master `.pptx`, preserve theme/layout, fill placeholders from the approved plan/proposal. Preview-quality first; real downloadable file is the stretch goal (PLAN.md output-fidelity note).
- [ ] Register the generation as the side-effecting tool behind the Day-5 checkpoint (`CheckpointAction.type = "generate_pptx"`).

### Backend — userflow generation (priority 2, G Q12)
- [ ] `backend/generation/userflow.py` — produce a **Mermaid** flow (and/or FigJam flow); render to a preview the frontend can display.

### Backend — Design agent behind `DesignBackend` (E / G Q4)
- [ ] `backend/design/backend.py` — `DesignBackend` interface; demo impl = **FigJam wireframe**, with an **HTML low-fi fallback** when no Figma access. Full Figma + OAuth is a deferred swap (G platform decisions).
- [ ] Quotation export (priority 3) + wireframe (priority 4, if time) behind the same checkpoint pattern.

### Backend — MCP integration (E)
- [ ] Register **PPTX** and **FigJam/Figma** MCP servers via the **AgentBase MCP Resource Gateway** (managed auth/policy); keep a **direct Python MCP client** as the local-dev fallback behind the same interface.

### Backend — wire the 4 modes (C.2)
- [ ] `chat` → read-only Q&A, no checkpoints; `planning` → Market+Strategy, checkpoint before finalizing plan; `execute` → full generation pipeline + checkpoint before every side effect; `brainstorm` → moderator subgraph (logic lands Day 7). Switching mode changes system prompt + active subgraph but **does not wipe session state** (the brief carries across modes).

### Frontend
- [ ] Artifacts area in the Context panel (C.1): preview + download for generated PPTX / userflow / quotation.
- [ ] Render Mermaid userflow + PPTX preview thumbnails inline.

## 4. Key interfaces / contracts introduced today

- `generation/pptx.py`, `generation/userflow.py`; `DesignBackend` interface (FigJam / HTML-lo-fi impls).
- `CheckpointAction.type ∈ {generate_pptx, generate_userflow, generate_quote, generate_wireframe}`.
- MCP gateway registration (PPTX, FigJam/Figma) + direct-client fallback.
- Mode→subgraph/prompt mapping (state preserved across mode switches).

## 5. Deliverable & verification

**Deliverable:** end-to-end proposal — brief → validate → plan → approve → PPTX deck + userflow preview (+ quotation).

**Verify:**
1. Execute mode, full brief → validate passes → plan previewed + approved → **PPTX deck** generated and previewable/downloadable.
2. Same flow yields a **userflow** (Mermaid/FigJam) preview.
3. Quotation export works behind its checkpoint; attempt a wireframe via `DesignBackend` (FigJam, or HTML low-fi when no Figma access).
4. With the MCP gateway unconfigured, generation still runs via the direct-client/local fallback.
5. Switch Planning→Execute mid-session → the brief and prior outputs are preserved (no state wipe).
6. Confirm every generation was gated by a Day-5 checkpoint (no silent side effects).

## 6. Out of scope / deferred

- Brainstorm moderator/turn-selection/convergence → **Day 7**.
- Deployment to AgentBase Runtime → **Day 7**.
- Real (non-preview) downloadable fidelity is a stretch goal, not required today.
