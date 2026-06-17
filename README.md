# AdtimaBox Sales AI

An AI sales assistant for Adtima's sales team — built as a multi-skill agent that handles sales planning, proposal generation (user journey, PPTX, quotation), compliance review, and client simulation over a real-time SSE chat interface.

## Architecture

```
Frontend (Next.js)
  └─ POST /chat/stream  →  SSE stream
       Backend (FastAPI)
         ├─ CentralAgent           — orchestrates the full pipeline
         │    ├─ Scoping           — extracts & validates the sales brief
         │    ├─ Market Strategy   — market insight + sales planning
         │    ├─ Product Solution  — AdtimaBox/CShub recommendation + Mermaid user journey
         │    ├─ Compliance        — policy review (pre-checkpoint reviewer)
         │    ├─ Client Simulator  — adversarial client Q&A
         │    ├─ Design            — wireframes / user-flow diagrams
         │    ├─ Proposal Assembler— assembles final proposal document
         │    └─ Data Masking      — anonymises sensitive data
         ├─ Checkpoint Manager     — human-approval gate before any artifact generation
         └─ Memory                 — feedback rules + salesperson profile (SQLite / AgentBase)
```

**LLM provider:** GreenNode MAAS (OpenAI-compatible endpoint), models `minimax/minimax-m2.5` and `qwen/qwen3-5-27b`.  
**Vector store / RAG:** LanceDB + `baai/bge-m3` embeddings (GreenNode-hosted, no local download needed).  
**Deployment target:** AgentBase Runtime (container on port 8080) + Next.js frontend (Vercel or static host).

## Quick Start

### Prerequisites

- **Python 3.11+** (backend)
- **Node.js 18+** with **yarn** (frontend)
- **GreenNode account** with MAAS access

### Step 1 — Clone and copy env

```bash
git clone <repo-url>
cd daidaidi-claw-hackathon
cp backend/.env.example backend/.env
```

### Step 2 — Get your GreenNode API key and model paths

1. Go to [GreenNode Console](https://console.greennode.ai/) → MAAS → API Keys → create a key.
2. List available models:
   ```bash
   curl -H "Authorization: Bearer YOUR_API_KEY" \
     "https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1/models" -s | jq '.data[].id'
   ```
3. Fill in `backend/.env`:
   ```env
   LLM_API_KEY=your_actual_api_key
   MODEL_ORCHESTRATOR=minimax/minimax-m2.5
   MODEL_MARKET_STRATEGY=qwen/qwen3-5-27b
   MODEL_PRODUCT_SOLUTION=qwen/qwen3-5-27b
   MODEL_COMPLIANCE=qwen/qwen3-5-27b
   MODEL_DESIGN=minimax/minimax-m2.5
   MODEL_VALIDATION=minimax/minimax-m2.5
   ```

### Step 3 — Backend

```bash
cd backend
python -m venv venv && venv\Scripts\activate   # Windows
# source venv/bin/activate                     # Mac/Linux
pip install -r requirements.txt

python -m uvicorn main:app --reload --port 8000
# API at http://localhost:8000  |  Docs at /docs
```

### Step 4 — Frontend

```bash
cd frontend
yarn install
yarn dev
# UI at http://localhost:3000
```

Open http://localhost:3000, enter a name (demo mode — no real auth), and start chatting.

## Project Structure

```
├── backend/
│   ├── main.py                      # FastAPI app, SSE /chat/stream endpoint
│   ├── central_agent/
│   │   ├── agent.py                 # CentralAgent — main pipeline orchestrator
│   │   └── SKILL.md                 # System prompt for the central agent
│   ├── skills/                      # One folder per skill
│   │   ├── base.py                  # BaseSkill contract
│   │   ├── registry.py              # Skill registry
│   │   ├── scoping/
│   │   ├── market_strategy/
│   │   ├── product_solution/
│   │   ├── compliance/
│   │   ├── client_simulator/
│   │   ├── design/
│   │   ├── proposal_assembler/
│   │   └── data_masking/
│   ├── agents/                      # Per-agent SKILL.md knowledge files
│   │   ├── sales_orchestrator_agent/
│   │   ├── market_strategy_agent/
│   │   ├── product_solution_agent/
│   │   ├── compliance_policy_agent/
│   │   └── ...
│   ├── checkpoint/
│   │   ├── manager.py               # Human-approval checkpoint state machine
│   │   └── compliance.py            # Pre-checkpoint compliance review hook
│   ├── memory/
│   │   ├── constraint_injection.py  # Injects learned feedback rules into prompts
│   │   └── feedback_extractor.py    # Detects & saves feedback rules from chat
│   ├── repos/
│   │   ├── memory_repo.py           # Memory repository interface
│   │   ├── memory_sqlite.py         # SQLite fallback (default)
│   │   ├── kb_repo.py               # Vector-store KB interface
│   │   └── embeddings.py            # Embedding provider (GreenNode bge-m3)
│   ├── generation/
│   │   ├── pptx.py                  # python-pptx deck generation
│   │   └── userflow.py              # Mermaid / FigJam user-flow generation
│   ├── schemas/
│   │   └── state.py                 # SalesCaseState (shared pipeline state)
│   ├── llm/
│   │   └── greennode.py             # GreenNode MAAS wrapper (OpenAI-compatible)
│   ├── config/
│   │   └── agents.yaml              # Agent/skill enable flags and model keys
│   ├── Dockerfile
│   └── requirements.txt
│
└── frontend/
    └── src/
        ├── app/
        │   ├── page.tsx             # Main chat page
        │   └── layout.tsx
        ├── components/
        │   ├── ChatWindow.tsx       # Message list + composer
        │   ├── MessageBubble.tsx    # Markdown render, Mermaid diagrams
        │   ├── Sidebar.tsx          # Mode switcher, agent status, theme toggle
        │   ├── ContextPanel.tsx     # Brief summary, constraints, artifacts
        │   ├── QuestionCard.tsx     # Inline question cards (yellow border)
        │   ├── BrainstormView.tsx   # Group-chat brainstorm UI
        │   └── MobileNav.tsx
        ├── hooks/
        │   └── useChat.ts           # SSE-backed chat hook
        └── lib/
            ├── types.ts
            └── api.ts
```

## Skills

| Skill | What it does |
|-------|-------------|
| **Scoping** | Extracts and validates the sales brief; asks clarifying questions |
| **Market Strategy** | Market insight, competitor analysis, sales planning |
| **Product Solution** | AdtimaBox / Zalo Mini App package recommendation + Mermaid user-journey diagram |
| **Compliance** | Flags policy risks in proposals; runs as a pre-checkpoint reviewer |
| **Client Simulator** | Adversarial client Q&A to stress-test the proposal |
| **Design** | Wireframes and user-flow diagrams (FigJam / HTML fallback) |
| **Proposal Assembler** | Merges all skill outputs into a final proposal document |
| **Data Masking** | Anonymises sensitive client data before external processing |

## Modes

| Mode | Behaviour |
|------|-----------|
| **Chat** | Q&A / advisory — minimal skill dispatch, answers from KB + memory |
| **Planning** | Builds a structured sales plan; dispatches Market Strategy |
| **Execute** | Full pipeline — proposal, user journey, PPTX, quotation; all gated by human checkpoint |
| **Brainstorm** | Multi-agent group discussion; orchestrator acts as moderator |

## Human Checkpoint

Before any artifact is generated (PPTX, quotation, wireframe), the backend emits a `checkpoint_card` SSE event. The frontend renders an inline card with **Approve / Edit / Reject** controls. Compliance findings attach to the card automatically (block/warn/info severity). The pipeline does not execute until the user approves.

## SSE Event Types

| Event | Description |
|-------|-------------|
| `session` | Session established |
| `user_message` | User turn echoed |
| `content` | Streaming token from the current agent |
| `agent_status` | `thinking` / `completed` / `failed` per skill |
| `agent_message` | Full message from a skill |
| `question_card` | Rendered by `QuestionCard.tsx` — asks for missing brief info |
| `checkpoint_card` | Human-approval gate before generation |
| `thinking_start` / `thinking_end` | Wraps `<think>` blocks (stripped from output) |
| `constraint_added` | Feedback rule saved to memory |

## Configuration

All options live in `backend/.env` (copy from `.env.example`):

```env
# GreenNode MAAS
LLM_BASE_URL=https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1/
LLM_API_KEY=your_key

# Model per skill (use model IDs from the /v1/models list)
MODEL_ORCHESTRATOR=minimax/minimax-m2.5
MODEL_MARKET_STRATEGY=qwen/qwen3-5-27b
MODEL_PRODUCT_SOLUTION=qwen/qwen3-5-27b
MODEL_COMPLIANCE=qwen/qwen3-5-27b
MODEL_DESIGN=minimax/minimax-m2.5
MODEL_VALIDATION=minimax/minimax-m2.5

# Feature flags
ENABLE_CHECKPOINT=true
ENABLE_BRAINSTORM=true
ENABLE_AUTO_APPROVE_SESSION=false

# KB embeddings — defaults to GreenNode-hosted bge-m3 (no local download)
KB_EMBEDDING_PROVIDER=greennode
KB_EMBEDDING_MODEL=baai/bge-m3

# Storage (defaults — no external infra needed for local dev)
SQLITE_DB_PATH=./data/sales_assistant.db
LANCEDB_PATH=./data/kb_runtime_cache

# Runtime
PORT=8080
FRONTEND_URL=http://localhost:3000
```

## AgentBase Managed Services (optional)

By default the app runs on **local fallbacks** (SQLite for memory, LanceDB for the vector store) — no AgentBase credentials needed for local development.

To enable the managed **Memory** service:

> **Auth model:** AgentBase uses IAM credentials (`GREENNODE_CLIENT_ID` + `GREENNODE_CLIENT_SECRET`), not a per-service API key. On **AgentBase Runtime** these are auto-injected — leave them unset in the deploy env file. For local dev, put them in `.greennode.json`.

1. Create a memory resource:
   ```bash
   bash .claude/skills/agentbase/scripts/memory.sh create \
     --name sales-assistant \
     --strategy-type USER_PREFERENCE \
     --auto-generate
   # Note the returned mem_... and strat_... IDs
   ```

2. Add to `.env`:
   ```env
   AGENTBASE_MEMORY_ID=mem_xxxxxxxxxxxx
   MEMORY_STRATEGY_ID=strat_xxxxxxxxxxxx
   # LOCAL DEV ONLY — auto-injected on Runtime:
   GREENNODE_CLIENT_ID=your_iam_client_id
   GREENNODE_CLIENT_SECRET=your_iam_client_secret
   ```

If `AGENTBASE_MEMORY_ID` is unset, the app falls back to SQLite automatically.

## Deployment (AgentBase Runtime)

> Full walkthrough: [`DEPLOY.md`](./DEPLOY.md)

**Hard requirements:**
- Container must listen on **port 8080** (`PORT` env var, set in `Dockerfile`).
- Must expose `GET /health → 200`.
- Do **not** include `GREENNODE_*` or `PORT` in the deploy env file — they are auto-injected.

```bash
# 1. Build (amd64) and push to the AgentBase Container Registry
docker build --platform linux/amd64 -t sales-ai-agent:latest ./backend
bash .claude/skills/agentbase/scripts/cr.sh credentials docker-login
docker tag sales-ai-agent:latest <registryUrl>/<repoName>/sales-ai-agent:latest
docker push <registryUrl>/<repoName>/sales-ai-agent:latest

# 2. Create the runtime service
bash .claude/skills/agentbase/scripts/runtime.sh create \
  --name sales-ai-agent \
  --image <registryUrl>/<repoName>/sales-ai-agent:latest \
  --flavor runtime-s2-general-2x4 \
  --env-file backend/.env.production \
  --from-cr --network-mode PUBLIC

# 3. Verify
curl -s -o /dev/null -w "%{http_code}\n" "<endpoint-url>/health"   # expect 200
```

## CI/CD

Two GitHub Actions workflows trigger on merge to `main`:

- `.github/workflows/backend-deploy.yml` — watches `backend/**`
- `.github/workflows/frontend-deploy.yml` — watches `frontend/**`

Required GitHub secrets:

| Secret | Used by |
|--------|---------|
| `GREENNODE_CLIENT_ID` | Backend deploy |
| `GREENNODE_CLIENT_SECRET` | Backend deploy |
| `AGENTBASE_RUNTIME_ID` | Backend deploy |
| `VERCEL_TOKEN` | Frontend deploy |
| `VERCEL_ORG_ID` | Frontend deploy |
| `VERCEL_PROJECT_ID` | Frontend deploy |

## Development

```bash
# Backend lint + format
cd backend
ruff check .
ruff format .

# Backend tests
pytest
pytest tests/test_file.py::test_function -v

# Frontend tests
cd frontend
yarn test
yarn build
```

## License

MIT
