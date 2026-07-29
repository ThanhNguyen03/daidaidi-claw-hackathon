# AdtimaBox Sales Agent

AdtimaBox Sales Agent is a multi-agent AI assistant built on GreenNode AgentBase for Adtima's sales team. It helps turn a client brief into a structured preliminary proposal for the Zalo ecosystem, faster and with less manual coordination.

## Description

### Problem
The rapid growth of Zalo has increased demand for AdtimaBox solutions. Many clients still struggle to understand how to use the ecosystem effectively, which leads to repetitive questions, long consultation cycles, and multiple rounds of clarification across Sales, Planners, Business Analysts, and Technical teams.

Today, each brief can take about one week and around nine working hours of internal effort before a preliminary proposal is ready.

### Target Users
The primary users are Adtima's Sales team, especially consultants and solution advisors working with FMCG and Pharmaceutical clients.

### How the Agent Solves It
AdtimaBox Sales Agent uses a multi-agent architecture with seven specialized agents:

- Requirement Elicitor
- Strategy Analyst
- Solution Designer
- Proposal Builder
- Client Debater
- Compliance Checker
- Client Data Masking Agent

The system is backed by a knowledge base that covers:

- Zalo ecosystem: Official Account, ZNS, Mini App, and Zalo Ads
- AdtimaBox capabilities
- FMCG and Pharmaceutical industry insights
- Vietnam advertising regulations
- Anonymized implementation case studies

When a client brief is submitted, the agents collaborate to clarify requirements, analyze business objectives, design a solution, validate compliance, and generate a preliminary proposal ready for Sales engagement.

### Business Value

- Cuts processing time from about nine working hours to three
- Improves efficiency by 66.7%
- Speeds up client response time
- Reduces dependency on subject-matter experts
- Standardizes consultation quality
- Turns internal knowledge into a scalable AI-powered pre-sales platform

## How to Run

### Prerequisites

- Python 3.11 (pinned in `backend/Dockerfile` and `backend/pyproject.toml`)
- Node.js 20+ (required — `@tailwindcss/postcss` v4 needs APIs missing on Node 18
  and breaks `next build`)
- npm
- An API key for the LLM provider currently wired in — see below

> The app runs on **Google Gemini through its OpenAI-compatible endpoint**, not
> GreenNode MAAS (`backend/llm/client.py` speaks plain OpenAI, so the provider is
> just env config — see `CLAUDE.md` → "Provider configuration"). Get a Gemini key
> from Google AI Studio.

### 1. Configure the backend

Copy the example environment file:

```bash
cp backend/.env.example backend/.env
```

`backend/.env.example` already ships with working defaults for the LLM provider —
you only need to fill in your key and adjust two values for local (non-Docker) use:

```env
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_API_KEY=your_gemini_api_key_here
PORT=8000
FRONTEND_URL=http://localhost:3000
```

`PORT` and `FRONTEND_URL` ship as `8080` and the production Vercel URL respectively
(the AgentBase Runtime and production defaults) — override them as above for local
dev, or just pass `--port 8000` to uvicorn as shown below and leave `PORT` alone.

Everything else in the file (`AGENTBASE_MEMORY_ID`, `MEMORY_STRATEGY_ID`,
`KB_VECTOR_ENABLED`, the per-skill `MODEL_*` overrides, etc.) is optional for a
local run — the app falls back to local SQLite/LanceDB storage and the model
defaults when those are unset.

### 2. Run the backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate      # Windows; use `source venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

`requirements.txt` pulls in `torch` + `sentence-transformers` for the local
embedding fallback, which is a slow install. If you don't need
`KB_VECTOR_ENABLED=true` (the default is `false` and nothing needs it — see
`CLAUDE.md`), you can install the trimmed `backend/requirements-prod.txt` instead.

Backend endpoints:

- API: `http://localhost:8000`
- Docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

### 3. Run the frontend

In a new terminal:

```bash
cd frontend
cp .env.example .env.local   # NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
npm install
npm run dev
```

Frontend URL:

- `http://localhost:3000`

### 4. Open the app

Open `http://localhost:3000` in your browser and start a chat session.

### Alternative: Run with Docker Compose

`docker-compose.yml` reads `LLM_BASE_URL`, `LLM_API_KEY`, and the `MODEL_*`
overrides from the **shell environment or a root-level `.env` file** — Compose does
not read `backend/.env`. Create one at the repo root (or export the vars in your
shell) before starting:

```env
# .env (repo root)
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_API_KEY=your_gemini_api_key_here
```

Then:

```bash
docker compose up --build
```

`docker-compose.yml` is the local-dev compose file (separate from
`docker-compose.prod.yml`, used only by `deploy/deploy.sh`) — it mounts your
source directories and runs `uvicorn --reload` / `npm run dev` inside the
containers, so edits on the host are picked up live. It starts:

- Backend on `http://localhost:8000`
- Frontend on `http://localhost:3000`

## Project Structure

```text
backend/
  main.py             FastAPI app and SSE endpoints
  central_agent/      Core orchestration logic
  skills/             Individual agent skills
  agents/             Agent knowledge files
  generation/         PPTX and user-flow generation
  repos/              Memory and knowledge store adapters

frontend/
  src/app/            Next.js pages
  src/components/     Chat UI components
  src/hooks/          SSE chat hook
  src/lib/            API helpers and types
```

## Notes

- The backend is designed to run on port `8000` locally.
- In AgentBase Runtime, the backend container listens on port `8080` as required by the platform.
- The frontend uses `NEXT_PUBLIC_API_URL` to talk to the backend.

