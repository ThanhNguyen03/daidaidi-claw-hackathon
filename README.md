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

- Python 3.11+
- Node.js 18+
- npm
- A GreenNode MAAS API key

### 1. Configure the backend

Copy the example environment file and fill in your values:

```bash
cp backend/.env.example backend/.env
```

At minimum, set:

```env
LLM_BASE_URL=https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1/
LLM_API_KEY=your_greennode_api_key_here
PORT=8000
FRONTEND_URL=http://localhost:3000
```

### 2. Run the backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend endpoints:

- API: `http://localhost:8000`
- Docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

### 3. Run the frontend

In a new terminal:

```bash
cd frontend
npm install
npm run dev
```

If needed, point the frontend to the backend:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Frontend URL:

- `http://localhost:3000`

### 4. Open the app

Open `http://localhost:3000` in your browser and start a chat session.

### Alternative: Run with Docker Compose

You can run both services together with:

```bash
docker compose up --build
```

This starts:

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

