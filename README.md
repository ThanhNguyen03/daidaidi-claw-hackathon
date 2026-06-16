# Multi-Agent Sales AI Assistant

A multi-agent AI assistant for sales teams that supports sales planning, customer service, proposal generation, and tech advisory.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Frontend (Next.js)                           │
│                    Chat UI with 4 modes + checkpoint cards             │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │ SSE/WebSocket
┌─────────────────────────────────▼───────────────────────────────────────┐
│                        Backend (FastAPI + LangGraph)                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │ Orchestrator│  │   Agents    │  │ Validation  │  │   Memory    │    │
│  │ (Supervisor)│  │  (6 agents) │  │    Gate     │  │  (LangGraph)│    │
│  └──────┬──────┘  └──────┬──────┘  └─────────────┘  └──────┬──────┘    │
│         │                │                                   │          │
│         └────────────────┴───────────────────────────────────┘          │
│                                    │                                    │
│                     ┌──────────────▼──────────────┐                     │
│                     │   GreenNode MAAS (LLM)     │                     │
│                     │   - MiniMax M2.5           │                     │
│                     │   - Qwen 3                 │                     │
│                     │   - Gemma 4                │                     │
│                     └─────────────────────────────┘                     │
└─────────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- **Python 3.11+** (backend)
- **Node.js 18+** with **yarn** (frontend)
- **GreenNode Account** with MAAS access

### Step 1: Clone and Setup

```bash
# Clone the repository
git clone <repo-url>
cd daidaidi-claw-hackathon

# Copy environment files
cp .env.example .env
cp frontend/.env.example frontend/.env.production
```

### Step 2: Get Your GreenNode API Key and Model Paths

1. **Get API Key:**
   - Go to [GreenNode Console](https://console.greennode.ai/)
   - Navigate to API Keys or MAAS section
   - Create a new API key

2. **List Available Models:**
   ```bash
   # Replace YOUR_API_KEY with your actual key
   curl -H "Authorization: Bearer YOUR_API_KEY" \
     "https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1/models" -s | jq '.data[].path'
   ```
   
   You'll see models like:
   - `MiniMax-M2.5` (for reasoning/agentic tasks)
   - `Qwen3-8B` or `Qwen3-72B` (for tool-calling)
   - `Gemma-4-2b` or `Gemma-4-9b` (for fast validation)

3. **Update .env with your values:**
   ```
   LLM_API_KEY=your_actual_api_key
   MODEL_ORCHESTRATOR=MiniMax-M2.5
   MODEL_TECH_SOLUTION=MiniMax-M2.5
   MODEL_MARKET_STRATEGY=Qwen3-8B
   MODEL_ACCOUNT=Qwen3-8B
   MODEL_ADTIMABOX=Qwen3-8B
   MODEL_DESIGN=Gemma-4-2b
   MODEL_COMPLIANCE=Qwen3-8B
   MODEL_VALIDATION=Gemma-4-2b
   ```

### Step 3: Install Backend Dependencies

```bash
cd backend

# Create virtual environment (recommended)
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 4: Run Backend

```bash
# Start the backend server
python -m uvicorn main:app --reload --port 8000

# Server runs at http://localhost:8000
# API docs at http://localhost:8000/docs
```

### Step 5: Install and Run Frontend

```bash
cd ../frontend

# Install dependencies (using yarn as per requirement)
yarn install

# Start development server
yarn dev

# Frontend runs at http://localhost:3000
```

### Step 6: Test the Application

1. Open http://localhost:3000
2. Enter a name to identify yourself (demo mode, no auth)
3. Type a message to start chatting!

## Project Structure

```
├── backend/
│   ├── main.py                 # FastAPI app entry point
│   ├── config/
│   │   └── agents.yaml         # Agent configuration
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── state.py            # SalesCaseState schema
│   │   ├── agent.py            # AgentOutput schema
│   │   ├── question.py         # Question schema
│   │   └── validation.py       # ValidationReport schema
│   ├── llm/
│   │   ├── __init__.py
│   │   └── greennode.py        # GreenNode LLM wrapper
│   ├── repos/
│   │   ├── __init__.py
│   │   ├── memory_repo.py      # Memory repository interface
│   │   └── memory_sqlite.py    # SQLite fallback implementation
│   ├── agents/
│   │   ├── base.py             # Base agent contract
│   │   ├── registry.py         # Agent registry
│   │   ├── orchestrator.py     # Orchestrator supervisor
│   │   └── graph.py            # LangGraph state machine
│   └── api/
│       ├── __init__.py
│       └── chat.py             # Chat endpoints with SSE
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx        # Main chat page
│   │   │   ├── layout.tsx      # Root layout
│   │   │   └── api/
│   │   │       └── chat/
│   │   │           └── route.ts  # Chat API route (BFF)
│   │   ├── components/
│   │   │   ├── ChatWindow.tsx
│   │   │   ├── MessageBubble.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   └── ContextPanel.tsx
│   │   ├── lib/
│   │   │   └── types.ts        # Shared TypeScript types
│   │   └── hooks/
│   │       └── useChat.ts      # Chat hook with SSE support
│   ├── package.json
│   └── next.config.ts
│
├── .env.example
├── PLAN.md
└── README.md
```

## Modes

| Mode | Description |
|------|-------------|
| **Chat** | Q&A mode - minimal agent dispatch, answers from KB + memory |
| **Planning** | Builds structured sales plans with Market + Strategy agents |
| **Execute** | Full generation pipeline - proposals, wireframes, PPTX, quotes |
| **Brainstorm** | Group discussion among multiple agents |

## Available Agents

1. **Orchestrator** - Supervisor that routes requests and manages flow
2. **Market Insight/Sales Strategy** - Market analysis and sales planning
3. **Tech Solution** - Technical recommendations
4. **Account** - Pricing and quotations
5. **AdtimaBox** - Adtima platform integration
6. **Design** - Wireframes and visual design
7. **Compliance** - Policy & compliance advisor: flags policy risks, suggests compliant alternatives, and warns the salesperson before delivery (advisory + pre-checkpoint reviewer)

The agent pool is **config-driven and extensible** — add or remove an agent by editing `config/agents.yaml` and dropping in a `backend/agents/<name>/` folder, with no orchestrator-core changes (see PLAN.md §B.6). Each entry declares a `kind` (`generator` / `advisory` / `reviewer`) and optional `hooks`, so cross-cutting agents (like Compliance) plug in generically.

## Configuration

### Agent Models

Each agent can use a different model. Configure in `.env`:

```env
MODEL_ORCHESTRATOR=MiniMax-M2.5
MODEL_TECH_SOLUTION=MiniMax-M2.5
MODEL_MARKET_STRATEGY=Qwen3-8B
MODEL_ACCOUNT=Qwen3-8B
MODEL_ADTIMABOX=Qwen3-8B
MODEL_DESIGN=Gemma-4-2b
MODEL_COMPLIANCE=Qwen3-8B
MODEL_VALIDATION=Gemma-4-2b
```

### Feature Flags

In `.env`:
- `ENABLE_CHECKPOINT=true` - Enable human approval checkpoints
- `ENABLE_BRAINSTORM=true` - Enable brainstorm mode
- `ENABLE_AUTO_APPROVE_SESSION=false` - Auto-approve same action type in session

### AgentBase Managed Services (optional)

The KB embeddings default to the GreenNode-hosted `baai/bge-m3` model, so the
container does not need to download Hugging Face weights at startup. If you
switch the provider back to local, it will fall back to `sentence-transformers`.

By default the app runs on the **local fallbacks** (SQLite for memory, LanceDB for
the vector store) — you do **not** need any AgentBase credentials to develop or
demo. Configure these only when you want the managed **Memory** / **MCP Gateway**
services.

> **Important — how AgentBase auth actually works.** AgentBase services do **not**
> use a per-service URL + API key. There is **no** `AGENTBASE_MEMORY_URL` or
> `AGENTBASE_MEMORY_API_KEY`. Instead:
> - **Base URLs are fixed** and known by the SDK (Memory = `https://agentbase.api.vngcloud.vn/memory`) — you never set them.
> - **Auth is IAM-based**: `GREENNODE_CLIENT_ID` + `GREENNODE_CLIENT_SECRET` (+ optional `GREENNODE_AGENT_IDENTITY`).
>   - **On AgentBase Runtime** these are **auto-injected** into the container — leave them unset.
>   - **For local development** provide them via a `.greennode.json` file (read by the SDK / `.claude/skills/agentbase/scripts/*`) — recommended — or as env vars.
> - **A memory is a resource you create** and reference by its **ID** (e.g. `mem_abc123`). That ID — `AGENTBASE_MEMORY_ID` — is what the LangGraph bridge needs; it is **not** an API key.

**Step 1 — create a memory** (gives you the `mem_...` ID + a strategy ID):

```bash
bash .claude/skills/agentbase/scripts/memory.sh create \
  --name sales-assistant \
  --description "Multi-agent sales assistant memory" \
  --expiry-days 30 \
  --strategy-name user-prefs \
  --strategy-type USER_PREFERENCE \
  --namespace-template "/strategies/{memoryStrategyId}/actors/{actorId}" \
  --auto-generate
# Note the returned memory id (mem_...) and strategy id (strat_...)
```

**Step 2 — put the IDs in `.env`** (auth via `.greennode.json` or IAM env vars):

```env
# IAM credentials — LOCAL DEV ONLY (auto-injected on AgentBase Runtime)
GREENNODE_CLIENT_ID=your_iam_client_id
GREENNODE_CLIENT_SECRET=your_iam_client_secret

# The memory you created above — this was the previously-missing variable
AGENTBASE_MEMORY_ID=mem_xxxxxxxxxxxx
MEMORY_STRATEGY_ID=strat_xxxxxxxxxxxx
```

The LangGraph checkpointer bridge then uses it as
`AgentBaseMemoryEvents(memory_id=AGENTBASE_MEMORY_ID)`. Requests must also carry
the `X-GreenNode-AgentBase-User-Id` and `X-GreenNode-AgentBase-Session-Id` headers
(mapped to `actor_id` / `thread_id`). If `AGENTBASE_MEMORY_ID` is unset, the app
falls back to the local SQLite checkpointer automatically.

### Figma Design Output (optional)

The Design agent can render design artifacts from Figma. By default it uses an
**HTML low-fi fallback** (no Figma needed). To enable the Figma path, provide a
**Personal Access Token (PAT)** — an **EDU / education-plan PAT works**.

> **What a PAT can and cannot do.** A PAT authenticates the Figma **REST API**:
> - ✅ **Read** files/nodes and **export/render** frames to **PNG / SVG / PDF** — this is the design *output* we use.
> - ✅ Post comments.
> - ❌ **It cannot create a file or draw new wireframe content from scratch** — the REST API has no write-content endpoint. Generating brand-new design nodes requires the Figma **Plugin API** (the `use_figma` MCP), not a PAT.
> - ❌ Writing local variables is **Enterprise-plan only** (EDU is not Enterprise).
>
> So the PAT-backed flow is: **build a wireframe template file in Figma once → the agent fills/duplicates → exports the frames as images** for the proposal.

**Setup:**

1. In Figma: **Settings → Security → Personal access tokens → Generate new token**. Scopes: `files:read` (required for export), `file_comments:write` (optional).
2. Build a template Figma file and copy its key from the URL: `https://www.figma.com/file/<FILE_KEY>/...`.
3. Add to `.env`:

```env
FIGMA_ACCESS_TOKEN=figd_xxxxxxxxxxxxxxxxxxxxxxxx
FIGMA_FILE_KEY=your_template_file_key
```

If `FIGMA_ACCESS_TOKEN` is unset, the Design agent automatically uses the HTML
low-fi fallback. For true generative wireframes (creating nodes), use the
`use_figma` MCP / Figma plugin path instead — see `docs/DAY_6.md`.

## Development

### Running Tests

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
yarn test
```

### Adding / Removing Agents

The pool is **open for extension, closed for modification** — none of the steps
below touch the orchestrator or graph code (see PLAN.md §B.6).

1. Add an entry in `config/agents.yaml` with:
   - `model` (env key, e.g. `MODEL_COMPLIANCE`), `role` (one-line routing description),
   - `kind`: `generator` (produces an artifact, checkpoint-gated) | `advisory` (answers/advises, read-only) | `reviewer` (inspects another agent's output via a hook),
   - optional `hooks`: e.g. `[pre_checkpoint_review]` for reviewer agents,
   - `critical`: whether its failure should halt the pipeline, and `enabled`.
2. Create the agent folder `backend/agents/<agent_name>/` with `prompt.md`, `schema.py` (payload shape), `tools.py`, `skills/`, `knowledge/`.
3. Add the model path to `.env` (`MODEL_<AGENT_NAME>`).
4. Drop knowledge `.md` files into `backend/agents/<agent_name>/knowledge/`.

To **remove** an agent: set `enabled: false` (or delete the entry + folder). Reviewer
agents un-subscribe from their hook automatically — no other agent is affected.

## Deployment (AgentBase)

The **backend** deploys on **AgentBase Runtime** as a Custom Agent container; the
**frontend** (Next.js) deploys separately and points at the backend endpoint.

Env split:
- Backend: `.env.production` at the repo root
- Frontend: `frontend/.env.production` or a Vercel project environment variable

> 📘 **Full step-by-step guide: [`DEPLOY.md`](./DEPLOY.md).** The quick version is below.

**Runtime Service Contract (HARD requirements):**
1. The container must **listen on port `8080`** — the platform routes traffic there.
   (`backend/Dockerfile` pins `ENV PORT=8080`; `main.py` reads `PORT`.)
2. It must expose **`GET /health` → 200**.

**Auth model:** you deploy using **IAM service-account** credentials in `.greennode.json`
(verify with `bash .claude/skills/agentbase/scripts/check_credentials.sh iam`). There is **no**
`AGENTBASE_API_KEY`. The runtime **auto-injects** `GREENNODE_CLIENT_ID`,
`GREENNODE_CLIENT_SECRET`, `GREENNODE_AGENT_IDENTITY`, `GREENNODE_ENDPOINT_URL` into the
container — **do not put these in your deploy env file**.

**Quick steps** (details + redeploy/rollback in `DEPLOY.md`):

```bash
# 1. Build (amd64) and push to the AgentBase managed Container Registry
docker build --platform linux/amd64 -t sales-assistant-backend:latest ./backend
bash .claude/skills/agentbase/scripts/cr.sh repo get
bash .claude/skills/agentbase/scripts/cr.sh credentials docker-login
docker tag sales-assistant-backend:latest <registryUrl>/<repoName>/sales-assistant-backend:latest
docker push <registryUrl>/<repoName>/sales-assistant-backend:latest

# 2. Create the runtime (env file must NOT contain GREENNODE_* or PORT)
bash .claude/skills/agentbase/scripts/runtime.sh create \
  --name sales-assistant-backend \
  --image <registryUrl>/<repoName>/sales-assistant-backend:latest \
  --flavor 1x1-general --env-file deploy.env --from-cr --network-mode PUBLIC

# 3. Get the endpoint + health-check
bash .claude/skills/agentbase/scripts/runtime.sh endpoints list <RUNTIME_ID>
curl -s -o /dev/null -w "%{http_code}\n" "<endpoint-url>/health"   # expect 200
```

> ⚠️ The repo also contains `.github/workflows/deploy.yml` and `DEPLOYMENT.md` that use a
> non-AgentBase flow (`@agentbase/cli` + `AGENTBASE_API_KEY` + `ghcr.io`). That mechanism does
> **not** exist for AgentBase — use `DEPLOY.md` instead. See `CHECK.md`.

## License

MIT

## License

MIT
