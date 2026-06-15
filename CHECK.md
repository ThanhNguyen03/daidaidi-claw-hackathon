# Implementation Check — Day 7 (Brainstorm + Deploy + Hardening) — re-check

> Audit date: 2026-06-15 (re-check). Scope: **Day 7 only**, **outstanding items only** (resolved tickets removed per request).
> Verified by imports, an isolated slowapi repro, and grep.

**Legend:** ⚠️ implemented but wrong/broken · ❌ not yet · ✅ (resolved — listed briefly at bottom)

---

## Verdict

Most Day-7 features are now present and wired. **But a new rate-limiting bug breaks the main API
endpoints at runtime**, and a few items remain. Fix the rate-limit bug first — right now the core
chat path returns 500.

---

## ⚠️ Outstanding — bugs

### 1. CRITICAL — rate limiting breaks the main endpoints (500 at request time)
- `main.py` decorates endpoints with `@limiter.limit(...)` but their only `request` parameter is a
  **Pydantic body model**, not Starlette's `Request`:
  - `chat_stream(request: ChatRequest)` (line 795) — `@limiter.limit("10/minute")`
  - `answer_question(request: AnswerQuestionRequest)` (line 1119) — `@limiter.limit("20/minute")`
  - `skip_question(request: SkipQuestionRequest)` (line 1159) — `@limiter.limit("20/minute")`
- slowapi requires a real `starlette.requests.Request` argument to read the client IP. With only a
  Pydantic `request`, it can't find one and raises → **HTTP 500**.
- **Confirmed by isolated repro** (FastAPI + slowapi + Pydantic `request` param → `status 500`).
- Impact: `/chat/stream` (primary entry, incl. brainstorm-via-chat), `/chat/answer`,
  `/chat/skip_question` all 500. The app imports fine but is broken when actually called.
- **Fix:** add a Starlette `Request` param and rename the body, e.g.
  `async def chat_stream(request: Request, payload: ChatRequest)` and update the body references
  from `request.` to `payload.` (do the same for the other two). Smoke-test each endpoint after.

### 2. Moderator + convergence are still placeholders (quality)
- `backend/mode/brainstorm.py`:
  - `select_next_speaker` — round-robin/less-active, **not relevance-based** (comment: "In
    production, this would use relevance scoring", line 73).
  - `check_convergence` — **naive string similarity**, not embedding/cosine > 0.9 (comment line 112).
  - ASK-LOCK is first-come, not moderator-prioritized by relevance.
- Plan (A.4 / C.5 §7) requires relevance selection + cosine convergence. Functional but not to spec.

### 3. Brainstorm timeouts / retention / transport (partial)
- 15-min freeze / 1-hr auto-end / 24h transcript retention: not evident (only the max-round cap).
- Brainstorm runs over HTTP, not the planned **WebSocket** (acceptable for the demo, but noted).

---

## ❌ Outstanding — not done

### 4. Stale, incorrect deploy artifacts still present
- `.github/workflows/deploy.yml` and `DEPLOYMENT.md` still describe the **non-existent** AgentBase
  flow (`@agentbase/cli`, `AGENTBASE_API_URL`/`AGENTBASE_API_KEY`, `ghcr.io`, `PORT=8000`). They
  won't deploy to AgentBase and will mislead. **Delete them** (or rewrite the workflow around the
  AgentBase scripts) — the correct guide is `DEPLOY.md`.
- The frontend CI job also uses `npm ci` (needs `package-lock.json`; project used yarn) and
  `npm run lint`/`type-check` (scripts may not exist) → that job likely fails regardless.

---

## Deploy status (your goal)

- **Backend image is now contract-correct** (port **8080** + curl-free `/health` check) and
  **`DEPLOY.md`** documents the real flow (IAM creds → managed Container Registry → `runtime.sh
  create`). Following `DEPLOY.md` it will deploy on AgentBase Runtime.
- **Caveat:** deploy will succeed but the deployed app's `/chat/*` endpoints will **500 until bug
  #1 is fixed** — fix the rate-limit signatures before (or right after) deploying, or the live
  agent won't respond.
- Do **not** rely on the GitHub workflow (#4); deploy via `DEPLOY.md`.

---

## ✅ Resolved since last check (removed from the active list)

- Brainstorm engine **wired into the app** (`main.py` imports/uses `get_brainstorm_manager` for
  brainstorm mode + endpoints).
- Frontend **`BrainstormView.tsx`** added and rendered in `page.tsx` (`mode === 'brainstorm'`).
- Frontend **`/health` route** added (`src/app/health/route.ts`).
- **Rate limiting present** (slowapi added) — but misconfigured, see bug #1.
- Backend **Dockerfile → port 8080** + stdlib health check.
- **`DEPLOY.md`** (correct AgentBase guide) + README Deployment section.

---

## Suggested fix order

1. **Fix the rate-limit signatures** (bug #1) — add `request: Request`, rename the Pydantic body; smoke-test `/chat/stream`, `/chat/answer`, `/chat/skip_question` return 200.
2. **Delete `.github/workflows/deploy.yml` + `DEPLOYMENT.md`** (or rewrite around AgentBase scripts).
3. Deploy via `DEPLOY.md`.
4. (Quality) upgrade moderator to relevance-based + embedding convergence + brainstorm timeouts.
