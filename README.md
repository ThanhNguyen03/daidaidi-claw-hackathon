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

# Copy environment file
cp .env.example .env
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
MODEL_VALIDATION=Gemma-4-2b
```

### Feature Flags

In `.env`:
- `ENABLE_CHECKPOINT=true` - Enable human approval checkpoints
- `ENABLE_BRAINSTORM=true` - Enable brainstorm mode
- `ENABLE_AUTO_APPROVE_SESSION=false` - Auto-approve same action type in session

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

### Adding New Agents

1. Add agent config in `config/agents.yaml`
2. Create agent folder in `backend/agents/<agent_name>/`
3. Add prompt in `backend/agents/<agent_name>/prompt.md`
4. Add knowledge files in `backend/agents/<agent_name>/knowledge/`

## Deployment

See [AgentBase Deployment Guide](./docs/deployment.md) for production deployment instructions.

## License

MIT