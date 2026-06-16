"""
Main FastAPI Application
========================
Entry point for the multi-agent sales assistant backend.
Provides REST API and SSE streaming endpoints.
"""

import os
import json
import uuid
from datetime import datetime
from typing import Optional, AsyncGenerator, Any, List, Literal

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import uvicorn

from dotenv import load_dotenv

load_dotenv()

# Import schemas
from schemas.state import (
    SalesCaseState,
    Brief,
    FeedbackRule,
    CheckpointAction,
)

# Import repositories
from repos.memory_repo import get_memory_repo, SQLiteMemoryRepo

# Import LLM
from llm.greennode import get_llm_client

# Import agent system (Day 2)
from agents.registry import get_registry
from agents.graph import get_simple_runner
from agents.sales_orchestrator_agent.agent import get_sales_orchestrator

# Import validation (Day 3)
from validation.question_stack import get_question_manager

# Import memory (Day 4)
from memory.feedback_extractor import get_feedback_extractor
from memory.profile import get_profile_manager

# Import checkpoint (Day 5)
from checkpoint.manager import get_checkpoint_manager

# Import generation (Day 6)
from generation.pptx import create_pptx_generator
from generation.userflow import create_userflow_generator
from design.backend import get_default_backend

# =============================================================================
# Configuration
# =============================================================================

APP_NAME = "Multi-Agent Sales Assistant"
APP_VERSION = "0.6.0"  # Day 6 version
DEBUG = os.getenv("DEBUG", "true").lower() == "true"
ACTIVE_MODE = "chat"
COMING_SOON_MODES = {"planning", "execute", "brainstorm"}


def _normalize_mode(mode: Optional[str]) -> str:
    """Keep the runtime on chat mode while preserving compatibility with legacy inputs."""
    normalized = (mode or ACTIVE_MODE).strip().lower()
    return ACTIVE_MODE if normalized != ACTIVE_MODE else ACTIVE_MODE


# =============================================================================
# FastAPI App
# =============================================================================

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup/shutdown."""
    # Startup: index all agent skills + knowledge into the KB vector store (idempotent).
    # Files that haven't changed since last run are skipped via hash check.
    print("Starting up: indexing agent skills/knowledge into the KB vector store...")
    try:
        from tools.ingest import ingest_all_agents
        await ingest_all_agents(force=False)
    except Exception as e:
        print(f"Warning: knowledge ingest failed (non-fatal): {e}")

    # Startup: register checkpoint review hooks
    print("Starting up: Registering checkpoint review hooks...")
    try:
        from checkpoint.manager import get_checkpoint_manager
        from agents.compliance_policy_agent.agent import get_compliance_agent

        cpm = get_checkpoint_manager()
        compliance_agent = get_compliance_agent()

        from checkpoint.manager import ComplianceReviewHook
        hook = ComplianceReviewHook(compliance_agent)
        cpm.register_review_hook(hook)
        print("Checkpoint review hook registered")
    except Exception as e:
        print(f"Warning: Failed to register review hook: {e}")

    yield  # App runs here

    # Shutdown
    print("Shutting down...")


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="AI-powered sales assistant with multi-agent orchestration",
    debug=DEBUG,
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting configuration (Day 7)
limiter = Limiter(key_func=get_remote_address)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."}
    )


# =============================================================================
# Request/Response Models
# =============================================================================


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    message: str = Field(..., description="User's message")
    session_id: Optional[str] = Field(
        None, description="Session ID (create new if not provided)"
    )
    salesperson_id: str = Field(..., description="Salesperson identifier")
    mode: str = Field(
        "chat", description="Active mode is chat; other modes are coming soon"
    )
    brief: Optional[Brief] = Field(None, description="Initial brief data")
    context: Optional[dict] = Field(None, description="Additional context")


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""

    session_id: str
    message: str
    agent: str
    done: bool = False


# =============================================================================
# State Management
# =============================================================================

# In-memory state store
_session_store: dict[str, SalesCaseState] = {}

# =============================================================================
# Artifact Store
# =============================================================================

_artifact_store: dict[str, dict] = {}
ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "data", "artifacts")


def get_or_create_session(
    session_id: Optional[str], salesperson_id: str, mode: str = "chat"
) -> SalesCaseState:
    """Get existing session or create new one."""
    mode = _normalize_mode(mode)
    # First check in-memory store
    if session_id and session_id in _session_store:
        state = _session_store[session_id]
        state.mode = _normalize_mode(state.mode)
        return state

    # Create new session (resume from DB happens via separate endpoint)
    new_session = SalesCaseState(
        session_id=session_id or f"sess_{uuid.uuid4().hex[:12]}",
        salesperson_id=salesperson_id,
        mode=mode,
        validation_status="PENDING",
    )
    _session_store[new_session.session_id] = new_session
    return new_session


async def get_or_create_session_async(
    session_id: Optional[str], salesperson_id: str, mode: str = "chat"
) -> SalesCaseState:
    """Async version: Get existing session or create new one. Tries in-memory, then database."""
    mode = _normalize_mode(mode)
    # First check in-memory store
    if session_id and session_id in _session_store:
        state = _session_store[session_id]
        state.mode = _normalize_mode(state.mode)
        return state

    # Try loading from database (Day 4: cross-session resume)
    if session_id:
        try:
            memory_repo = get_memory_repo()
            state = await memory_repo.load_session(session_id)
            if state:
                # Found in database, also put in memory
                state.mode = _normalize_mode(state.mode)
                _session_store[session_id] = state
                return state
        except Exception as e:
            print(f"Warning: Failed to load session from DB: {e}")

    # Create new session
    new_session = SalesCaseState(
        session_id=session_id or f"sess_{uuid.uuid4().hex[:12]}",
        salesperson_id=salesperson_id,
        mode=mode,
        validation_status="PENDING",
    )
    _session_store[new_session.session_id] = new_session
    return new_session


def update_session(state: SalesCaseState) -> None:
    """Update session in store."""
    _session_store[state.session_id] = state


async def get_session_or_404(session_id: str) -> SalesCaseState:
    """
    Return a session from memory or persistent storage.

    Several workflow endpoints mutate session state after the initial chat turn.
    They must survive runtime restarts and multi-request flows, so we fall back
    to the shared memory repo instead of only trusting the in-process dict.
    """
    if session_id in _session_store:
        return _session_store[session_id]

    memory_repo = get_memory_repo()
    state = await memory_repo.load_session(session_id)
    if state:
        _session_store[session_id] = state
        return state

    raise HTTPException(status_code=404, detail="Session not found")


async def persist_session_best_effort(state: SalesCaseState, context: str) -> None:
    """Persist session state without breaking the request on storage issues."""
    try:
        await get_memory_repo().save_session(state)
    except Exception as exc:
        print(f"Warning: failed to persist session after {context}: {exc}")


def serialize_workflow_state(state: SalesCaseState) -> dict[str, Any]:
    """Return the standard FE payload after a workflow mutation."""
    return {
        "brief": state.brief.model_dump(mode="json") if state.brief else None,
        "validation_status": state.validation_status,
    }


def _json_default(value: Any) -> Any:
    """Make SSE payloads resilient to datetimes and Pydantic objects."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, set):
        return list(value)
    return str(value)


def _sse_data(payload: dict[str, Any]) -> str:
    """Serialize a server-sent event payload safely."""
    return f"data: {json.dumps(payload, default=_json_default)}\n\n"


# =============================================================================
# Agent-Based Processing (Day 2)
# =============================================================================


# Day 5: Checkpoint-triggering action types
CHECKPOINT_TRIGGER_TYPES = {"generate_quote", "generate_pptx", "generate_wireframe", "generate_userflow"}


async def _recompute_preview(state: SalesCaseState, params: dict) -> Optional[dict]:
    """
    Re-compute the preview/quote with updated parameters.

    This is called when user edits checkpoint params.
    For now, we simply update the total based on params.
    In a full implementation, we'd re-run the Account agent.
    """
    # Get current payload from state
    product_output = state.outputs.get("product_solution")
    if not product_output:
        return None

    payload = product_output.payload.copy() if product_output.payload else {}

    # Simple re-computation: update values based on params
    # In production, this would re-run the product solution agent with new params
    if "budget" in params:
        # Budget was edited - update the total to be within budget
        try:
            budget = int(params["budget"])
            # Estimate a new total that's slightly under budget
            payload["total_vnd"] = int(budget * 0.9)
        except (ValueError, TypeError):
            pass

    if "discount_percent" in params:
        try:
            discount = float(params["discount_percent"])
            # Apply new discount to original total
            original = payload.get("original_total_vnd", payload.get("total_vnd", 0))
            payload["total_vnd"] = int(original * (1 - discount / 100))
            payload["discount_percent"] = discount
        except (ValueError, TypeError):
            pass

    return payload


async def _maybe_create_checkpoint(state: SalesCaseState) -> Optional[Any]:
    """
    Check if agent outputs contain a checkpoint-triggering action and create checkpoint.

    Day 5-6: This creates a checkpoint when:
    - Account agent outputs a quote (generate_quote)
    - Plan agent outputs a plan (generate_pptx, generate_userflow)
    - Design agent outputs wireframe requirements (generate_wireframe)
    """
    # Check whether any agent output requires human approval.
    # Mode no longer controls checkpointing; the output type does.

    # Get checkpoint manager
    cpm = get_checkpoint_manager()

    # Register handlers for checkpoint actions
    async def handle_generate_quote(params: dict) -> dict:
        """Execute quote generation (Day 6)."""
        quote_id = params.get("quote_id", f"Q{uuid.uuid4().hex[:8].upper()}")
        artifact_id = f"quote_{uuid.uuid4().hex[:10]}"
        # Build a simple text quote
        lines = [f"QUOTATION #{quote_id}\n"]
        for item in params.get("items", []):
            lines.append(f"  - {item.get('name', '?')}: {item.get('price', 0):,} VND")
        total = params.get("total_vnd", 0)
        lines.append(f"\nTotal: {total:,} VND")
        content = "\n".join(lines).encode("utf-8")

        _artifact_store[artifact_id] = {
            "storage": "memory",
            "content": content,
            "filename": f"quote_{quote_id}.txt",
            "media_type": "text/plain",
            "type": "quote",
            "title": f"Quotation #{quote_id}",
        }
        return {
            "status": "executed",
            "quote_id": quote_id,
            "total_vnd": total,
            "artifact_id": artifact_id,
            "download_url": f"/artifact/{artifact_id}",
        }

    async def handle_generate_pptx(params: dict) -> dict:
        """Execute PPTX generation (Day 6). Saves file to disk, returns download URL."""
        artifact_id = f"pptx_{uuid.uuid4().hex[:10]}"
        os.makedirs(ARTIFACTS_DIR, exist_ok=True)
        output_path = os.path.join(ARTIFACTS_DIR, f"{artifact_id}.pptx")

        pptx_gen = create_pptx_generator()
        result = await pptx_gen.generate(
            plan_data=params,
            client_name=params.get("client_name", "Client"),
            output_path=output_path,
        )

        if result.get("status") == "success" and result.get("file_path"):
            client_name = params.get("client_name", "Client")
            _artifact_store[artifact_id] = {
                "storage": "file",
                "path": output_path,
                "filename": f"proposal_{client_name}.pptx",
                "media_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                "type": "pptx",
                "title": f"PPTX Proposal â€” {client_name}",
            }
            result["artifact_id"] = artifact_id
            result["download_url"] = f"/artifact/{artifact_id}"
        elif result.get("fallback"):
            # python-pptx not available â€” save fallback text
            content = (result.get("preview") or "").encode("utf-8")
            _artifact_store[artifact_id] = {
                "storage": "memory",
                "content": content,
                "filename": f"proposal_{params.get('client_name', 'Client')}.md",
                "media_type": "text/markdown",
                "type": "pptx",
                "title": f"Proposal (text fallback) â€” {params.get('client_name', 'Client')}",
            }
            result["artifact_id"] = artifact_id
            result["download_url"] = f"/artifact/{artifact_id}"

        return result

    async def handle_generate_userflow(params: dict) -> dict:
        """Execute userflow generation (Day 6). Registers Mermaid artifact."""
        userflow_gen = create_userflow_generator()
        result = await userflow_gen.generate(
            plan_data=params,
            format=params.get("format", "mermaid"),
        )

        if result.get("status") == "success":
            artifact_id = f"flow_{uuid.uuid4().hex[:10]}"
            if result.get("format") == "mermaid" and result.get("code"):
                content = result["code"].encode("utf-8")
                _artifact_store[artifact_id] = {
                    "storage": "memory",
                    "content": content,
                    "filename": "userflow.mmd",
                    "media_type": "text/plain",
                    "type": "userflow",
                    "title": "Userflow Diagram (Mermaid)",
                }
                result["artifact_id"] = artifact_id
                result["download_url"] = f"/artifact/{artifact_id}"

        return result

    async def handle_generate_wireframe(params: dict) -> dict:
        """Execute wireframe generation (Day 6). Registers HTML/FigJam artifact."""
        design_backend = get_default_backend()
        result = await design_backend.generate_wireframe(
            requirements=params,
            output_format=params.get("output_format", "html"),
        )

        if result.get("status") == "success" and result.get("content"):
            artifact_id = f"wire_{uuid.uuid4().hex[:10]}"
            content = result["content"]
            if isinstance(content, str):
                content = content.encode("utf-8")
            _artifact_store[artifact_id] = {
                "storage": "memory",
                "content": content,
                "filename": "wireframe.html",
                "media_type": "text/html",
                "type": "wireframe",
                "title": f"Wireframe â€” {params.get('brand_name', 'Brand')}",
            }
            result["artifact_id"] = artifact_id
            result["download_url"] = f"/artifact/{artifact_id}"

        return result

    # Register all handlers
    cpm.register_handler("generate_quote", handle_generate_quote)
    cpm.register_handler("generate_pptx", handle_generate_pptx)
    cpm.register_handler("generate_userflow", handle_generate_userflow)
    cpm.register_handler("generate_wireframe", handle_generate_wireframe)

    # Determine what kind of generation to checkpoint based on outputs
    payload = None
    action_type = None
    action_description = None

    # Check for quote output from product solution agent
    product_output = state.outputs.get("product_solution")
    if product_output:
        product_payload = product_output.payload or {}
        pricing_breakdown = product_payload.get("pricing_breakdown") or {}
        if pricing_breakdown.get("total_vnd") or product_payload.get("quote_id"):
            payload = {
                "quote_id": product_payload.get("quote_id", "PENDING"),
                "items": pricing_breakdown.get("items", []),
                "total_vnd": pricing_breakdown.get("total_vnd", 0),
                "valid_until": pricing_breakdown.get("valid_until"),
                "payment_terms": product_payload.get("payment_terms", "To be confirmed"),
            }
            action_type = "generate_quote"
            action_description = f"Generate quotation for {payload.get('total_vnd', 0):,} VND"

    # Check for plan output from plan agent (or other agent with plan data)
    if not payload:
        for agent_name, output in state.outputs.items():
            if not output or not output.payload:
                continue
            agent_payload = output.payload

            # Check if this is a plan/proposal output (flexible detection)
            # Also check for key fields that indicate a structured plan/proposal
            is_plan_output = (
                agent_payload.get("plan") or
                agent_payload.get("solutions") or
                agent_payload.get("title") or
                agent_payload.get("proposal") or
                agent_payload.get("recommendations") or  # Common StubAgent output
                agent_payload.get("deliverables")  # Common StubAgent output
            )

            if is_plan_output:
                payload = agent_payload
                # Day 6: Check for explicit user journey/flow first
                # If found, generate userflow. Otherwise generate PPTX.
                # For demo: also check for 'journey', 'steps', 'process' keys
                has_userflow_data = (
                    agent_payload.get("user_journey") or
                    agent_payload.get("flow") or
                    agent_payload.get("journey") or
                    agent_payload.get("steps") or
                    agent_payload.get("process")
                )
                if has_userflow_data:
                    action_type = "generate_userflow"
                    action_description = "Generate userflow diagram"
                else:
                    # For any plan/proposal, generate both PPTX AND userflow
                    # Userflow will use fallback data from the plan
                    action_type = "generate_userflow"
                    action_description = "Generate userflow diagram + PPTX deck"
                    # Add fallback user journey data to payload
                    if "recommendations" in agent_payload:
                        payload["user_journey"] = [
                            f"Review {agent_payload.get('target_segment', 'proposal')}",
                            "Analyze recommendations",
                            "Select solution",
                            "Proceed with implementation"
                        ]
                break

    # Check for design output
    if not payload:
        design_output = state.outputs.get("design")
        if design_output:
            design_payload = design_output.payload or {}
            if design_payload.get("wireframe") or design_payload.get("requirements"):
                payload = design_payload
                action_type = "generate_wireframe"
                action_description = "Generate wireframe design"

    # If no generation action found, skip checkpoint
    if not payload or not action_type:
        return None

    # Create the checkpoint
    action = CheckpointAction(
        type=action_type,
        description=action_description,
        parameters=payload,
    )

    # Day 5: Run compliance review BEFORE creating checkpoint
    # Create a preliminary checkpoint for the review
    from schemas.state import Checkpoint as CheckpointSchema
    preliminary_checkpoint = CheckpointSchema(
        id=f"preview_{uuid.uuid4().hex[:8]}",
        action=action,
        status="AWAITING",
        preview=payload,
    )

    # Run the compliance review hooks
    compliance_findings = await cpm.run_review_hooks(state, preliminary_checkpoint)

    # Pass ComplianceFinding objects directly to create_checkpoint
    # (it will handle serialization when storing)
    checkpoint = await cpm.create_checkpoint(
        session_id=state.session_id,
        action=action,
        preview=payload,
        compliance_findings=compliance_findings,  # Pass objects, not dicts
    )

    # Attach to state
    state.checkpoint = checkpoint

    return checkpoint


def _extract_agent_content(agent_name: str, output) -> str:
    """
    Pull the user-facing text out of an AgentOutput.payload so it can be
    streamed directly to the chat window.
    """
    payload = getattr(output, "payload", {}) or {}

    # product_solution: full solution narrative under "solution_summary"
    if "content" in payload:
        return str(payload["content"])

    # market_strategy: full LLM text under "strategy"
    if "strategy" in payload:
        return str(payload["strategy"])

    # product_solution: recommendations (string or list)
    if "recommendations" in payload:
        recs = payload["recommendations"]
        if isinstance(recs, str):
            return recs
        if isinstance(recs, list):
            lines = []
            for r in recs:
                if isinstance(r, dict):
                    lines.append(f"- **{r.get('category', '')}**: {r.get('item', '')}")
                else:
                    lines.append(f"- {r}")
            return "\n".join(lines)

    # compliance agent: findings list or narrative
    if "findings" in payload:
        findings = payload["findings"]
        if isinstance(findings, str):
            return findings
        if isinstance(findings, list):
            lines = [f"**Compliance Review â€” {agent_name}**\n"]
            for f in findings:
                if isinstance(f, dict):
                    severity = f.get("severity", "info").upper()
                    lines.append(f"- [{severity}] {f.get('message', str(f))}")
                else:
                    lines.append(f"- {f}")
            return "\n".join(lines)

    # client_simulator: structured adversarial review
    if "objections" in payload:
        lines = [f"**Client Simulator Review â€” {agent_name}**\n"]
        scores = payload.get("scores", {})
        if scores:
            score_str = " | ".join(f"{k.replace('_', ' ').title()}: {v}/5" for k, v in scores.items())
            lines.append(f"*Scores: {score_str}*\n")
        for obj in payload.get("objections", []):
            if isinstance(obj, dict):
                lines.append(f"- [{obj.get('severity','').upper()}] {obj.get('text', str(obj))}")
        for wp in payload.get("weak_points", []):
            lines.append(f"âš  {wp}")
        for risk in payload.get("risks", []):
            lines.append(f"ðŸš¨ {risk}")
        if payload.get("recommendations"):
            lines.append("\n**Recommendations before AE review:**")
            for rec in payload["recommendations"]:
                lines.append(f"- {rec}")
        return "\n".join(lines)

    # compliance: narrative field
    if "narrative" in payload:
        return str(payload["narrative"])

    # requirement elicitation: normalized brief / clarification summary
    if "requirement_summary" in payload:
        return str(payload["requirement_summary"])

    if "next_questions" in payload:
        questions = payload["next_questions"]
        if isinstance(questions, list) and questions:
            lines = ["**Need a few clarifications before proceeding:**"]
            for q in questions:
                if isinstance(q, dict):
                    lines.append(f"- {q.get('text', str(q))}")
                else:
                    lines.append(f"- {q}")
            return "\n".join(lines)

    # product_solution / integration: integration summary
    if "integration" in payload:
        return str(payload["integration"])

    if "solution_summary" in payload:
        return str(payload["solution_summary"])

    if "pricing_breakdown" in payload:
        pricing = payload["pricing_breakdown"] or {}
        lines = [f"**BÃ¡o giÃ¡ / Solution**\n"]
        for item in pricing.get("items", []):
            price = item.get("price", 0)
            lines.append(
                f"- {item.get('name', '?')}: **{price:,.0f} VND** / {item.get('unit', '')}"
                + (" *(Æ°á»›c tÃ­nh)*" if item.get("is_estimate") else "")
            )
        if pricing.get("subtotal") is not None:
            lines.append(f"\n**Subtotal:** {pricing.get('subtotal'):,.0f} VND")
        if pricing.get("total_vnd") is not None:
            lines.append(f"**Tá»•ng cá»™ng:** {pricing.get('total_vnd'):,.0f} VND")
        if pricing.get("valid_until"):
            lines.append(f"Hiá»‡u lá»±c Ä‘áº¿n: {pricing['valid_until']}")
        return "\n".join(lines)

    # product solution / quote: render as markdown table
    if "quote_id" in payload:
        lines = [f"**BÃ¡o giÃ¡ #{payload['quote_id']}**\n"]
        for item in payload.get("items", []):
            price = item.get("price", 0)
            lines.append(
                f"- {item.get('name', '?')}: **{price:,.0f} VND** / {item.get('unit', '')} "
                + ("*(Æ°á»›c tÃ­nh)*" if item.get("is_estimate") else "")
            )
        total = payload.get("total_vnd", 0)
        lines.append(f"\n**Tá»•ng cá»™ng: {total:,.0f} VND**")
        if payload.get("valid_until"):
            lines.append(f"Hiá»‡u lá»±c Ä‘áº¿n: {payload['valid_until']}")
        if payload.get("payment_terms"):
            lines.append(f"Äiá»u khoáº£n thanh toÃ¡n: {payload['payment_terms']}")
        return "\n".join(lines)

    # fallback: use summary
    return output.summary or ""


async def process_with_agents(
    state: SalesCaseState,
    message: str,
) -> AsyncGenerator[str, None]:
    """
    Process message using the multi-agent system.

    This uses the SimpleAgentRunner from Day 2 which provides
    proper agent dispatch, anti-loop guard, and status streaming.

    Chat-only runtime behavior:
    - Validation runs first.
    - The orchestrator decides which specialist agents to invoke.
    - Checkpoints are created from the produced output type, not from mode.

    NOTE: When ENABLE_CHECKPOINT is true, this will use the full LangGraph
    AgentGraph which supports interrupt-before-tool HITL and durable checkpointer
    for resume. This is needed for checkpoint functionality.
    """
    # Add user message to state
    state.messages.extend(
        [
            {
                "role": "user",
                "content": message,
                "timestamp": datetime.now().isoformat(),
            },
        ]
    )

    # Day 7: Handle modes differently
    # chat mode: simple processing (no agents), handled in process_simple
    # brainstorm mode: use BrainstormManager for multi-agent discussion

    # For planning/execute modes, use agents
    # Always use SimpleAgentRunner (full LangGraph has issues with duplicate routes)
    use_full_graph = False

    # Day 4: Load active constraints into state for injection
    try:
        memory_repo = get_memory_repo()
        constraints = await memory_repo.load_feedback_rules(
            state.salesperson_id, active_only=True
        )
        state.constraints = constraints
    except Exception as e:
        print(f"Warning: Failed to load constraints: {e}")
        state.constraints = []

    # Day 7: Handle brainstorm mode - use BrainstormManager for multi-agent discussion
    if state.mode == "brainstorm":
        from mode.brainstorm import get_brainstorm_manager

        # Get or create brainstorm session
        manager = get_brainstorm_manager()
        brain_state = manager.get_session(state.session_id)

        if brain_state is None:
            # Create new session with participants from state
            participants = state.participants if state.participants else ["sales_orchestrator"]
            brain_state = manager.create_session(
                session_id=state.session_id,
                participants=participants,
                max_rounds=8
            )
            yield _sse_data({'type': 'brainstorm_start', 'session_id': state.session_id, 'participants': participants})

        # Add user message to brainstorm
        brain_state.add_message(speaker="user", content=message, is_user=True)

        # Run brainstorm round - select next speaker and get their response
        next_speaker = brain_state.select_next_speaker()

        if next_speaker:
            yield _sse_data({'type': 'speaker_turn', 'speaker': next_speaker})

            # Get agent response for the speaker
            runner = get_simple_runner()
            state.messages.append({
                "role": "user",
                "content": f"[Brainstorm] {message}",
                "timestamp": datetime.now().isoformat(),
            })

            # Run the agent to generate response
            final_state, stream_events = await runner.run(state)

            # Stream events and capture agent output
            agent_output = ""
            for event in stream_events:
                yield _sse_data(event)
                if event.get("type") == "content":
                    agent_output += event.get("content", "")

            # Add agent response to brainstorm
            if agent_output:
                brain_state.add_message(speaker=next_speaker, content=agent_output)

        # Check for convergence or timeouts
        should_stop, reason = brain_state.check_timeouts()
        if not should_stop and brain_state.check_convergence():
            should_stop = True
            reason = "convergence"

        if should_stop:
            brain_state.is_ended = True
            summary = brain_state.get_summary()
            yield _sse_data({'type': 'brainstorm_end', 'reason': reason, 'summary': summary})
        else:
            # Continue - prompt next speaker
            yield _sse_data({'type': 'continue', 'next_speaker': brain_state.current_speaker})

        return

    if use_full_graph:
        # Use full AgentGraph with LangGraph (for Day 4-5 checkpoint + resume)
        from agents.graph import get_graph

        graph = get_graph()
        config = {"configurable": {"thread_id": state.session_id}}

        stream_events = []
        async for event in graph.run_stream(state, config=config):
            stream_events.append(event)
            yield _sse_data(event)

        # Get final state from the graph (graph updates state in place)
        # Copy graph outputs back to our state
        final_state = state
        for event in stream_events:
            if event.get("type") == "agent_status" and event.get("status") == "completed":
                agent_name = event.get("agent")
                # Find the output in the last event
                pass
    else:
        # Get the simple runner (handles agent dispatch)
        runner = get_simple_runner()

        # Run the agent system
        final_state, stream_events = await runner.run(state)

        # Check if stream_events already contains an assistant-visible message
        # (e.g. casual_chat reply, NEEDS_INPUT prompt, question_card)
        # so we don't emit a duplicate fallback below.
        already_has_assistant = any(
            e.get("type") in ("assistant_message", "question_card")
            for e in stream_events
        )

        # Stream status events but hold the "done" until after content
        for event in stream_events:
            if event.get("type") != "done":
                yield _sse_data(event)

        # Stream each completed agent's real output as a separate agent_message
        emitted_agent_message = False
        for agent_name, output in final_state.outputs.items():
            if agent_name == "sales_orchestrator":
                continue
            if not output or not hasattr(output, "status"):
                continue
            if output.status != "COMPLETE":
                continue

            content_text = _extract_agent_content(agent_name, output)
            if not content_text:
                continue

            yield _sse_data({'type': 'agent_message', 'agent': agent_name, 'content': content_text})
            emitted_agent_message = True

            # Record in session history
            state.messages.append(
                {
                    "role": "assistant",
                    "content": content_text,
                    "agent": agent_name,
                    "timestamp": datetime.now().isoformat(),
                }
            )

        if not emitted_agent_message and not already_has_assistant:
            fallback_summary = ""
            orch_output = final_state.outputs.get("sales_orchestrator")
            if orch_output and getattr(orch_output, "summary", ""):
                fallback_summary = str(orch_output.summary)
            elif final_state.summary:
                fallback_summary = str(final_state.summary)

            if fallback_summary:
                yield _sse_data({
                    'type': 'assistant_message',
                    'agent': 'sales_orchestrator',
                    'content': fallback_summary,
                })

        # Update state
        state.outputs = final_state.outputs
        state.summary = (
            f"User: {message[:30]}... â†’ Agents: {', '.join(final_state.outputs.keys())}"
        )

        yield _sse_data({'type': 'done'})


# =============================================================================
# Simple LLM Processing (Day 1 fallback)
# =============================================================================

ORCHESTRATOR_SYSTEM_PROMPT = """You are a Sales AI Assistant Ã¢â‚¬â€ a knowledgeable advisor for sales teams.

## Your Role

You coordinate the specialist agents internally and answer only from the
evidence, context, and tools already available in the session.

Do NOT invent missing details, do NOT assume unavailable values, and do NOT
answer execute-level requirements unless the context is sufficient.

## When User Shares a Sales Brief

If the brief is incomplete, ask for the missing details BEFORE giving advice.
Key fields to check:
- Client/company name
- Industry / product being sold
- Target audience
- Budget range
- Goals or KPIs
- Current tech stack (CRM, Zalo OA, etc.)

Once you have enough context, coordinate the specialists and present a
comprehensive, direct response with only grounded information.

## Response Guidelines

- Be helpful, professional, and thorough Ã¢â‚¬â€ give real substance, not placeholders
- Respond in the user's language (Vietnamese if they write in Vietnamese)
- Use markdown headers and bullet points for readability
- Never promise future actions you cannot take in this turn
- Never expose hidden mode names to the user
"""


class _ThinkFilter:
    """Streaming filter that strips <think>...</think> blocks from LLM output.

    Emits (type, content) tuples:
      ("think_start", "")  â€” first <think> tag encountered
      ("think", content)   â€” text inside a <think> block (caller may discard)
      ("think_end", "")    â€” closing </think> tag
      ("content", content) â€” regular response text to stream to the client
    """

    OPEN = "<think>"
    CLOSE = "</think>"

    def __init__(self) -> None:
        self._buf = ""
        self._in_think = False

    def push(self, token: str) -> list[tuple[str, str]]:
        self._buf += token
        events: list[tuple[str, str]] = []
        while True:
            if self._in_think:
                pos = self._buf.find(self.CLOSE)
                if pos >= 0:
                    if pos > 0:
                        events.append(("think", self._buf[:pos]))
                    events.append(("think_end", ""))
                    self._buf = self._buf[pos + len(self.CLOSE):]
                    self._in_think = False
                else:
                    safe = max(0, len(self._buf) - len(self.CLOSE))
                    if safe > 0:
                        events.append(("think", self._buf[:safe]))
                        self._buf = self._buf[safe:]
                    break
            else:
                pos = self._buf.find(self.OPEN)
                if pos >= 0:
                    if pos > 0:
                        events.append(("content", self._buf[:pos]))
                    events.append(("think_start", ""))
                    self._buf = self._buf[pos + len(self.OPEN):]
                    self._in_think = True
                else:
                    safe = max(0, len(self._buf) - len(self.OPEN))
                    if safe > 0:
                        events.append(("content", self._buf[:safe]))
                        self._buf = self._buf[safe:]
                    break
        return events

    def flush(self) -> list[tuple[str, str]]:
        if not self._buf:
            return []
        kind = "think" if self._in_think else "content"
        result = [(kind, self._buf)]
        self._buf = ""
        return result


async def process_simple(
    state: SalesCaseState,
    message: str,
) -> AsyncGenerator[str, None]:
    """
    Process message with simple LLM call (chat mode fallback).
    Uses sales_orchestrator system prompt. Strips <think> reasoning blocks and
    emits thinking_start / thinking_end SSE events instead.
    """
    try:
        client = get_llm_client("sales_orchestrator")
    except ValueError as e:
        yield _sse_data({'type': 'error', 'error': str(e)})
        return

    # Record user message in session history before calling the LLM
    state.messages.append(
        {
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat(),
        }
    )

    # Build messages: system prompt + rolling history (last 10 turns)
    llm_messages = [{"role": "system", "content": ORCHESTRATOR_SYSTEM_PROMPT}]
    llm_messages += [
        {"role": msg["role"], "content": msg["content"]}
        for msg in state.messages[-10:]
    ]

    # Append brief context to the last user message when available
    if state.brief:
        context_parts = []
        if state.brief.industry:
            context_parts.append(f"Industry: {state.brief.industry}")
        if state.brief.budget_vnd:
            context_parts.append(f"Budget: {state.brief.budget_vnd:,} VND")
        if context_parts:
            llm_messages[-1]["content"] += f"\n\nContext: {', '.join(context_parts)}"

    try:
        stream = client.create_completion(
            messages=llm_messages,
            stream=True,
            temperature=0.7,
            max_tokens=4000,
        )

        tf = _ThinkFilter()
        accumulated = ""

        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                token = chunk.choices[0].delta.content
                for kind, text in tf.push(token):
                    if kind == "think_start":
                        yield _sse_data({'type': 'thinking_start'})
                    elif kind == "think_end":
                        yield _sse_data({'type': 'thinking_end'})
                    elif kind == "content" and text:
                        accumulated += text
                        yield _sse_data({'type': 'content', 'content': text})
                    # "think" text is silently discarded

        for kind, text in tf.flush():
            if kind == "content" and text:
                accumulated += text
                yield _sse_data({'type': 'content', 'content': text})

        if accumulated:
            state.messages.append(
                {
                    "role": "assistant",
                    "content": accumulated,
                    "agent": "sales_orchestrator",
                    "timestamp": datetime.now().isoformat(),
                }
            )

    except Exception as e:
        yield _sse_data({'type': 'error', 'error': str(e)})

    yield _sse_data({'type': 'done'})


# =============================================================================
# API Endpoints
# =============================================================================


@app.get("/")
async def root():
    """Root endpoint with app info."""
    return {
        "name": APP_NAME,
        "version": APP_VERSION,
        "status": "running",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    # Check LLM configuration
    from llm.greennode import validate_environment

    llm_status = validate_environment()

    # Check agent registry
    registry = get_registry()
    agents = registry.all_names()

    return {
        "status": "healthy",
        "llm_configured": llm_status["valid"],
        "agents_loaded": len(agents),
        "agent_names": agents,
    }


@app.post("/chat")
async def chat(request: ChatRequest):
    """Chat endpoint - non-streaming."""
    # Get or create session
    state = get_or_create_session(
        session_id=request.session_id,
        salesperson_id=request.salesperson_id,
        mode=request.mode,
    )

    if request.brief:
        state.brief = request.brief

    state.messages.append(
        {
            "role": "user",
            "content": request.message,
            "timestamp": datetime.now().isoformat(),
        }
    )

    try:
        orchestrator = get_sales_orchestrator()
        validation_output, should_dispatch = await orchestrator.validate_before_dispatch(
            state
        )

        if not should_dispatch:
            response_text = validation_output.summary or ""
        else:
            runner = get_simple_runner()
            final_state, _ = await runner.run(state)
            response_text = ""

            for agent_name, output in final_state.outputs.items():
                if agent_name == "sales_orchestrator":
                    continue
                if not output or getattr(output, "status", None) != "COMPLETE":
                    continue
                response_text = _extract_agent_content(agent_name, output)
                if response_text:
                    break

            if not response_text:
                orch_output = final_state.outputs.get("sales_orchestrator")
                if orch_output and getattr(orch_output, "summary", ""):
                    response_text = str(orch_output.summary)
                else:
                    response_text = (
                        final_state.summary
                        or validation_output.summary
                        or "No response"
                    )
    except Exception as e:
        response_text = f"Error: {str(e)}"

    return ChatResponse(
        session_id=state.session_id,
        message=response_text,
        agent="sales_orchestrator",
        done=True,
    )

@app.post("/chat/stream")
@limiter.limit("10/minute")  # Rate limit: 10 requests per minute
async def chat_stream(request: Request, payload: ChatRequest):
    """
    Chat endpoint - streaming via SSE.
    Uses the multi-agent system (Day 2).
    """
    requested_mode = (payload.mode or ACTIVE_MODE).strip().lower()
    if requested_mode != ACTIVE_MODE:
        async def coming_soon_stream():
            yield _sse_data({'type': 'session', 'session_id': payload.session_id or f'sess_{uuid.uuid4().hex[:12]}'})
            yield _sse_data({'type': 'user_message', 'content': payload.message})
            yield _sse_data({'type': 'content', 'content': 'Planning, execute, and brainstorm modes are coming soon. Chat mode is the only active mode for now.'})
            yield _sse_data({'type': 'done'})

        return StreamingResponse(
            coming_soon_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Get or create session
    state = get_or_create_session(
        session_id=payload.session_id,
        salesperson_id=payload.salesperson_id,
        mode=payload.mode,
    )

    if payload.brief:
        state.brief = payload.brief

    # Always sync the mode on the session â€” user may have switched modes
    # between requests while keeping the same session (brief/history carries over).
    state.mode = ACTIVE_MODE

    # Reset per-request agent state so agents re-run on every new message.
    # Without this, state.plan and state.visited accumulate across turns and
    # _get_next_task returns None on the 2nd+ message (all agents "visited").
    state.plan = None
    state.visited = []
    state.hop_depth = 0

    async def event_generator():
        try:
            # Send session info first
            yield _sse_data({'type': 'session', 'session_id': state.session_id})

            # Send user message event
            yield _sse_data({'type': 'user_message', 'content': payload.message})
            assistant_emitted = False

            feedback_extractor = get_feedback_extractor()
            memory_repo = get_memory_repo()
            profile_manager = get_profile_manager()

            # Check if message contains feedback
            if feedback_extractor.is_feedback_message(payload.message):
                rule = feedback_extractor.extract(
                    payload.message,
                    {"salesperson_id": state.salesperson_id}
                )
                if rule:
                    # Save the feedback rule
                    await memory_repo.save_feedback_rule(rule)

                    # Update profile with constraint
                    profile = await memory_repo.load_profile(state.salesperson_id)
                    if not profile:
                        profile = profile_manager.create_profile(state.salesperson_id)
                    profile = profile_manager.add_constraint(profile, rule.rule_id)
                    await memory_repo.save_profile(profile)

                    # Notify about new constraint
                    yield _sse_data({'type': 'constraint_added', 'constraint': rule.model_dump(mode="json")})

            # D.3: Also check for frustration in message
            profile = await memory_repo.load_profile(state.salesperson_id)
            if not profile:
                profile = profile_manager.create_profile(state.salesperson_id)
            if profile_manager.detect_frustration(profile, payload.message):
                await memory_repo.save_profile(profile)

            done_chunk = _sse_data({'type': 'done'})
            async for chunk in process_with_agents(state, payload.message):
                if chunk != done_chunk:
                    if '"type": "assistant_message"' in chunk or '"type": "agent_message"' in chunk or '"type": "content"' in chunk:
                        assistant_emitted = True
                    yield chunk

            if not assistant_emitted:
                yield _sse_data({
                    'type': 'assistant_message',
                    'agent': 'sales_orchestrator',
                    'content': 'Mình cần thêm chút thông tin trước khi tiếp tục.',
                })

            # Day 5: Check if we need to create a checkpoint
            # This runs after agents complete, looking for quote/plan outputs
            # Guard with try-except to prevent reviewer errors from breaking the stream
            try:
                checkpoint = await _maybe_create_checkpoint(state)
            except Exception as e:
                print(f"Warning: Failed to create checkpoint: {e}")
                checkpoint = None

            if checkpoint:
                # Convert checkpoint to dict with datetime serialization
                checkpoint_dict = checkpoint.model_dump()
                for dt_field in ['created_at', 'updated_at', 'decided_at']:
                    if checkpoint_dict.get(dt_field) and hasattr(checkpoint_dict[dt_field], 'isoformat'):
                        checkpoint_dict[dt_field] = checkpoint_dict[dt_field].isoformat()
                yield _sse_data({'type': 'checkpoint_card', 'checkpoint': checkpoint_dict})

            # Save final state to in-memory store
            update_session(state)

            # Day 4: Also persist to database for cross-session resume
            try:
                memory_repo = get_memory_repo()
                await memory_repo.save_session(state)
            except Exception as e:
                print(f"Warning: Failed to persist session: {e}")

            # Send session update
            # Serialize brief with datetime handling
            brief_dict = None
            if state.brief:
                brief_dict = state.brief.model_dump(mode="json")
            yield _sse_data({'type': 'session_updated', 'session_id': state.session_id, 'brief': brief_dict})
            yield done_chunk
        except Exception as exc:
            print(f"Error in chat stream: {exc}")
            yield _sse_data({'type': 'error', 'error': str(exc)})
            yield _sse_data({'type': 'done'})
            return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/sessions/{session_id}")
async def get_session_by_id(session_id: str):
    """Get session by ID. Checks in-memory store first, then database."""
    # First check in-memory
    if session_id in _session_store:
        state = _session_store[session_id]
        return {
            "session_id": state.session_id,
            "salesperson_id": state.salesperson_id,
            "mode": ACTIVE_MODE,
            "brief": state.brief.model_dump() if state.brief else None,
            "summary": state.summary,
            "outputs": {k: v.model_dump() for k, v in state.outputs.items()},
            "visited": state.visited,
            "hop_depth": state.hop_depth,
            "message_count": len(state.messages),
            "created_at": state.created_at.isoformat(),
            "updated_at": state.updated_at.isoformat(),
        }

    # Try database
    try:
        repo = get_memory_repo()
        state = await repo.load_session(session_id)
        if state:
            # Put in memory
            _session_store[session_id] = state
            return {
                "session_id": state.session_id,
                "salesperson_id": state.salesperson_id,
                "mode": ACTIVE_MODE,
                "brief": state.brief.model_dump() if state.brief else None,
                "summary": state.summary,
                "outputs": {k: v.model_dump() for k, v in state.outputs.items()},
                "visited": state.visited,
                "hop_depth": state.hop_depth,
                "message_count": len(state.messages),
                "created_at": state.created_at.isoformat(),
                "updated_at": state.updated_at.isoformat(),
            }
    except Exception as e:
        print(f"Warning: Failed to load session from DB: {e}")

    raise HTTPException(status_code=404, detail="Session not found")


@app.get("/sessions")
async def list_sessions(
    salesperson_id: Optional[str] = None,
    limit: int = 10,
):
    """List recent sessions."""
    sessions = list(_session_store.values())

    if salesperson_id:
        sessions = [s for s in sessions if s.salesperson_id == salesperson_id]

    sessions.sort(key=lambda s: s.updated_at, reverse=True)

    return [
        {
            "session_id": s.session_id,
            "salesperson_id": s.salesperson_id,
            "mode": ACTIVE_MODE,
            "summary": s.summary,
            "visited": s.visited,
            "hop_depth": s.hop_depth,
            "message_count": len(s.messages),
            "updated_at": s.updated_at.isoformat(),
        }
        for s in sessions[:limit]
    ]


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    if session_id in _session_store:
        del _session_store[session_id]
        return {"status": "deleted", "session_id": session_id}

    raise HTTPException(status_code=404, detail="Session not found")


class SwitchModeRequest(BaseModel):
    """Request to switch chat mode."""
    session_id: str
    mode: str  # chat, planning, execute, brainstorm
    participants: Optional[List[str]] = None  # For brainstorm mode


@app.post("/sessions/switch_mode")
async def switch_mode(request: SwitchModeRequest):
    """
    Mode switching is disabled for now.

    Chat is the only active mode. Other modes are marked coming soon so the
    UI can show them without changing the runtime workflow.
    """
    if request.session_id not in _session_store:
        raise HTTPException(status_code=404, detail="Session not found")

    state = _session_store[request.session_id]
    old_mode = state.mode
    state.mode = ACTIVE_MODE

    return {
        "status": "coming_soon",
        "session_id": state.session_id,
        "old_mode": old_mode,
        "new_mode": state.mode,
        "requested_mode": request.mode,
        "message": "Only chat mode is active right now. Planning, execute, and brainstorm are coming soon.",
        "preserved": {
            "brief": state.brief.model_dump() if state.brief else None,
            "message_count": len(state.messages),
            "output_count": len(state.outputs),
        },
    }


# =============================================================================
# Question Answering (Day 3)
# =============================================================================


class AnswerQuestionRequest(BaseModel):
    """Request to answer a validation question."""

    session_id: str
    question_id: str
    answer: str


class SkipQuestionRequest(BaseModel):
    """Request to skip an optional question."""

    session_id: str
    question_id: str


class WorkflowInteractionRequest(BaseModel):
    """Unified workflow request for FE-driven interactions."""

    action: Literal["answer", "skip_question", "answer_free_text", "checkpoint_decision"]
    session_id: Optional[str] = None
    question_id: Optional[str] = None
    answer: Optional[str] = None
    message: Optional[str] = None
    salesperson_id: Optional[str] = None
    checkpoint_id: Optional[str] = None
    decision: Optional[str] = None
    params: Optional[dict] = None
    auto_approve: bool = False


@app.post("/chat/answer")
@limiter.limit("20/minute")
async def answer_question(request: Request, payload: AnswerQuestionRequest):
    """
    C.5 Â§2: Answer a question from the QuestionStack.
    Maps answer to brief field, re-validates, returns updated question list.
    """
    state = await get_session_or_404(payload.session_id)

    # Get sales_orchestrator to handle validation response
    orchestrator = get_sales_orchestrator()

    # Special case: desired_output question routes to state.desired_outputs, not the brief
    if payload.question_id == "desired_output":
        outputs = await orchestrator.extract_desired_outputs(payload.answer)
        if not outputs:
            outputs = ["pptx"]  # default fallback
        state.desired_outputs = outputs
        update_session(state)
        try:
            await get_memory_repo().save_session(state)
        except Exception as exc:
            print(f"Warning: failed to persist session after desired_output answer: {exc}")
        return {
            "status": "ready",
            "message": f"Got it â€” will generate: {', '.join(outputs)}. Send your next message to proceed.",
            "questions": [],
            "validation_status": state.validation_status,
            "brief": state.brief.model_dump() if state.brief else None,
        }

    # Handle the answer
    answers = {payload.question_id: payload.answer}
    validation_output = await orchestrator.handle_validation_response(state, answers)
    update_session(state)
    try:
        await get_memory_repo().save_session(state)
    except Exception as exc:
        print(f"Warning: failed to persist session after answer_question: {exc}")

    # Get updated questions
    question_manager = get_question_manager()
    remaining_questions = question_manager.stack.next_batch()

    # Build response based on validation status
    if validation_output.status == "COMPLETE":
        return {
            "status": "ready",
            "message": "All questions answered. Ready to proceed.",
            "questions": [],
            "validation_status": "READY",
            "brief": state.brief.model_dump() if state.brief else None,
        }
    else:
        return {
            "status": "pending",
            "message": validation_output.summary,
            "questions": [q.model_dump() for q in remaining_questions],
            "validation_status": state.validation_status,
            "brief": state.brief.model_dump() if state.brief else None,
        }


@app.post("/chat/skip_question")
@limiter.limit("20/minute")
async def skip_question(request: Request, payload: SkipQuestionRequest):
    """
    C.5 Â§6: Skip an optional question.
    Records the assumption as implicit approval.
    """
    state = await get_session_or_404(payload.session_id)

    # Get question manager and skip
    question_manager = get_question_manager()
    question_manager.skip_optional(payload.question_id)

    # Re-validate
    orchestrator = get_sales_orchestrator()
    validation_output, should_dispatch = await orchestrator.validate_before_dispatch(
        state
    )
    update_session(state)
    try:
        await get_memory_repo().save_session(state)
    except Exception as exc:
        print(f"Warning: failed to persist session after skip_question: {exc}")

    remaining_questions = question_manager.stack.next_batch()

    if should_dispatch:
        return {
            "status": "ready",
            "message": "Optional question skipped. Ready to proceed.",
            "questions": [],
            "validation_status": "READY",
            "brief": state.brief.model_dump() if state.brief else None,
        }
    else:
        return {
            "status": "pending",
            "message": validation_output.summary,
            "questions": [q.model_dump() for q in remaining_questions],
            "validation_status": state.validation_status,
            "brief": state.brief.model_dump() if state.brief else None,
        }


@app.post("/chat/answer_free_text")
async def answer_free_text(request: ChatRequest):
    """
    C.5 Â§5: Answer multiple questions with free text.
    The backend maps the free text to appropriate brief fields.
    """
    if not request.session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    state = await get_session_or_404(request.session_id)

    # Get sales_orchestrator
    orchestrator = get_sales_orchestrator()

    # Handle free text answer
    answers = {"free_text": request.message}
    validation_output = await orchestrator.handle_validation_response(state, answers)
    update_session(state)
    try:
        await get_memory_repo().save_session(state)
    except Exception as exc:
        print(f"Warning: failed to persist session after answer_free_text: {exc}")

    # Get updated questions
    question_manager = get_question_manager()
    remaining_questions = question_manager.stack.next_batch()

    if validation_output.status == "COMPLETE":
        return {
            "status": "ready",
            "message": "Answers mapped successfully. Ready to proceed.",
            "questions": [],
            "validation_status": "READY",
            "brief": state.brief.model_dump() if state.brief else None,
        }
    else:
        return {
            "status": "pending",
            "message": validation_output.summary,
            "questions": [q.model_dump() for q in remaining_questions],
            "validation_status": state.validation_status,
        }


@app.post("/workflow/interact")
@limiter.limit("30/minute")
async def workflow_interact(request: Request, payload: WorkflowInteractionRequest):
    """
    Unified FE workflow endpoint.
    """
    if payload.action == "answer":
        if not payload.session_id or not payload.question_id or payload.answer is None:
            raise HTTPException(status_code=400, detail="session_id, question_id, and answer are required")

        state = await get_session_or_404(payload.session_id)
        orchestrator = get_sales_orchestrator()

        if payload.question_id == "desired_output":
            outputs = await orchestrator.extract_desired_outputs(payload.answer)
            if not outputs:
                outputs = ["pptx"]
            state.desired_outputs = outputs
            update_session(state)
            await persist_session_best_effort(state, "workflow.answer desired_output")
            return {
                "status": "ready",
                "message": f"Got it - will generate: {', '.join(outputs)}. Send your next message to proceed.",
                "questions": [],
                **serialize_workflow_state(state),
            }

        validation_output = await orchestrator.handle_validation_response(
            state, {payload.question_id: payload.answer}
        )
        update_session(state)
        await persist_session_best_effort(state, "workflow.answer")

        question_manager = get_question_manager()
        remaining_questions = question_manager.stack.next_batch()
        return {
            "status": "ready" if validation_output.status == "COMPLETE" else "pending",
            "message": "All questions answered. Ready to proceed."
            if validation_output.status == "COMPLETE"
            else validation_output.summary,
            "questions": [] if validation_output.status == "COMPLETE" else [q.model_dump() for q in remaining_questions],
            **serialize_workflow_state(state),
        }

    if payload.action == "skip_question":
        if not payload.session_id or not payload.question_id:
            raise HTTPException(status_code=400, detail="session_id and question_id are required")

        state = await get_session_or_404(payload.session_id)
        question_manager = get_question_manager()
        question_manager.skip_optional(payload.question_id)

        orchestrator = get_sales_orchestrator()
        validation_output, should_dispatch = await orchestrator.validate_before_dispatch(state)
        update_session(state)
        await persist_session_best_effort(state, "workflow.skip_question")

        remaining_questions = question_manager.stack.next_batch()
        return {
            "status": "ready" if should_dispatch else "pending",
            "message": "Optional question skipped. Ready to proceed."
            if should_dispatch
            else validation_output.summary,
            "questions": [] if should_dispatch else [q.model_dump() for q in remaining_questions],
            **serialize_workflow_state(state),
        }

    if payload.action == "answer_free_text":
        if not payload.session_id or payload.message is None:
            raise HTTPException(status_code=400, detail="session_id and message are required")

        state = await get_session_or_404(payload.session_id)
        orchestrator = get_sales_orchestrator()
        validation_output = await orchestrator.handle_validation_response(
            state, {"free_text": payload.message}
        )
        update_session(state)
        await persist_session_best_effort(state, "workflow.answer_free_text")

        question_manager = get_question_manager()
        remaining_questions = question_manager.stack.next_batch()
        return {
            "status": "ready" if validation_output.status == "COMPLETE" else "pending",
            "message": "Answers mapped successfully. Ready to proceed."
            if validation_output.status == "COMPLETE"
            else validation_output.summary,
            "questions": [] if validation_output.status == "COMPLETE" else [q.model_dump() for q in remaining_questions],
            **serialize_workflow_state(state),
        }

    if payload.action == "checkpoint_decision":
        if not payload.session_id or not payload.checkpoint_id or not payload.decision:
            raise HTTPException(status_code=400, detail="session_id, checkpoint_id, and decision are required")

        state = await get_session_or_404(payload.session_id)
        checkpoint = state.checkpoint
        if not checkpoint or checkpoint.id != payload.checkpoint_id:
            raise HTTPException(status_code=404, detail=f"Checkpoint not found: {payload.checkpoint_id}")

        cpm = get_checkpoint_manager()
        if payload.auto_approve:
            cpm.set_auto_approve(payload.session_id, checkpoint.action.type, True)

        updated = await cpm.process_decision(checkpoint, payload.decision, payload.params)
        if payload.decision == "edit" and payload.params:
            new_payload = await _recompute_preview(state, payload.params)
            if new_payload:
                updated.preview = new_payload
                updated.action.parameters.update(payload.params)
                if "total_vnd" in new_payload:
                    updated.action.description = f"Generate quotation for {new_payload['total_vnd']:,} VND"

        state.checkpoint = updated
        update_session(state)
        await persist_session_best_effort(state, "workflow.checkpoint_decision")

        clarifying_question = cpm.get_clarifying_question(updated) if payload.decision == "reject" else None
        return {
            "checkpoint": updated.model_dump(),
            "clarifying_question": clarifying_question,
            "auto_approve_enabled": payload.auto_approve,
            **serialize_workflow_state(state),
        }

    raise HTTPException(status_code=400, detail=f"Unsupported workflow action: {payload.action}")


# =============================================================================
# Memory & Learning Endpoints (Day 4)
# =============================================================================


@app.get("/memory/constraints/{salesperson_id}")
async def get_constraints(salesperson_id: str):
    """
    D.2: Get active constraints for a salesperson.
    Used by the Context panel.
    """
    repo = get_memory_repo()
    constraints = await repo.load_feedback_rules(salesperson_id, active_only=True)

    return {
        "salesperson_id": salesperson_id,
        "constraints": [c.model_dump() for c in constraints],
        "count": len(constraints),
    }


@app.post("/memory/constraints/{rule_id}/toggle")
async def toggle_constraint(
    rule_id: str,
    active: bool = True,
    salesperson_id: Optional[str] = None,
):
    """
    D.2: Toggle a constraint's active status.
    Used by the Context panel to revoke constraints.
    """
    repo = get_memory_repo()

    # Load the rule if we have the salesperson_id
    if salesperson_id:
        rules = await repo.load_feedback_rules(salesperson_id, active_only=False)
        for rule in rules:
            if rule.rule_id == rule_id:
                rule.active = active
                await repo.save_feedback_rule(rule)
                return {
                    "rule_id": rule_id,
                    "active": active,
                    "message": f"Constraint {'activated' if active else 'revoked'} successfully",
                }

    return {"error": "Rule not found", "rule_id": rule_id}


@app.get("/memory/profile/{salesperson_id}")
async def get_profile(salesperson_id: str):
    """
    D.3: Get salesperson profile.
    """
    repo = get_memory_repo()
    profile = await repo.load_profile(salesperson_id)

    if not profile:
        # Create new profile
        profile_manager = get_profile_manager()
        profile = profile_manager.create_profile(salesperson_id)
        await repo.save_profile(profile)

    return profile.model_dump()


@app.post("/memory/profile/{salesperson_id}/learn")
async def learn_from_interaction(
    salesperson_id: str,
    question_text: Optional[str] = None,
    answer: Optional[str] = None,
    was_helpful: Optional[bool] = None,
    message: Optional[str] = None,
):
    """
    D.3: Learn from user interactions.
    Updates profile with style, question_frequency, and detects frustration.
    """
    repo = get_memory_repo()
    profile_manager = get_profile_manager()
    feedback_extractor = get_feedback_extractor()

    # Load or create profile
    profile = await repo.load_profile(salesperson_id)
    if not profile:
        profile = profile_manager.create_profile(salesperson_id)

    # Detect feedback in message
    if message:
        # Check for frustration
        profile_manager.detect_frustration(profile, message)

        # Try to extract feedback rule
        if feedback_extractor.is_feedback_message(message):
            rule = feedback_extractor.extract(message, {"salesperson_id": salesperson_id})
            if rule:
                await repo.save_feedback_rule(rule)
                profile = profile_manager.add_constraint(profile, rule.rule_id)
                await repo.save_profile(profile)
                return {
                    "feedback_rule": rule.model_dump(),
                    "profile": profile.model_dump(),
                    "message": "Feedback rule extracted and saved",
                }

    # Update from answer
    if question_text and answer:
        profile = profile_manager.update_from_answer(
            profile, question_text, answer, was_helpful
        )
        await repo.save_profile(profile)

    return {
        "profile": profile.model_dump(),
        "message": "Profile updated",
    }


@app.get("/memory/sessions/{salesperson_id}")
async def get_sessions(salesperson_id: str, limit: int = 10):
    """
    D.1: List recent sessions for a salesperson.
    """
    repo = get_memory_repo()
    sessions = await repo.list_sessions(salesperson_id, limit)
    return {"sessions": sessions, "count": len(sessions)}


@app.get("/memory/session/{session_id}")
async def get_session(session_id: str):
    """
    D.1: Resume a session from checkpointer.
    Tries in-memory first, then database.
    """
    # First try in-memory store
    if session_id in _session_store:
        return _session_store[session_id].model_dump()

    # Then try database
    repo = get_memory_repo()
    state = await repo.load_session(session_id)

    if not state:
        # Try creating the session if it doesn't exist yet
        # This handles edge case where DB has data but memory doesn't
        raise HTTPException(
            status_code=404,
            detail="Session not found. Provide session_id in your request to resume."
        )

    # Also put in memory for future requests
    _session_store[session_id] = state

    return state.model_dump()


# =============================================================================
# Checkpoint Endpoints (Day 5)
# =============================================================================


class CheckpointDecisionRequest(BaseModel):
    """Request to decide on a checkpoint."""

    decision: str = Field(..., description="Decision: approve, edit, or reject")
    params: Optional[dict] = Field(None, description="Parameters for edit decision")
    auto_approve: bool = Field(False, description="Enable session auto-approve")


@app.post("/checkpoint/{checkpoint_id}/decision")
async def checkpoint_decision(
    checkpoint_id: str,
    request: CheckpointDecisionRequest,
    session_id: Optional[str] = None,
):
    """
    Process a checkpoint decision.
    - approve: Execute the action
    - edit: Re-compute preview with new params
    - reject: Do not execute, post clarifying question
    """
    print(f"[DEBUG] checkpoint_decision: session_id={session_id}, checkpoint_id={checkpoint_id}")

    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    state = await get_session_or_404(session_id)
    checkpoint = state.checkpoint
    print(f"[DEBUG] Current checkpoint in state: {checkpoint.id if checkpoint else None}")

    if not checkpoint or checkpoint.id != checkpoint_id:
        raise HTTPException(status_code=404, detail=f"Checkpoint not found: {checkpoint_id} (session has {checkpoint.id if checkpoint else 'none'})")

    if request.auto_approve:
        from checkpoint.manager import get_checkpoint_manager

        cpm = get_checkpoint_manager()
        cpm.set_auto_approve(session_id, checkpoint.action.type, True)

    cpm = get_checkpoint_manager()
    updated = await cpm.process_decision(checkpoint, request.decision, request.params)

    if request.decision == "edit" and request.params:
        new_payload = await _recompute_preview(state, request.params)
        if new_payload:
            updated.preview = new_payload
            updated.action.parameters.update(request.params)
            if "total_vnd" in new_payload:
                updated.action.description = f"Generate quotation for {new_payload['total_vnd']:,} VND"

    state.checkpoint = updated
    update_session(state)
    try:
        await get_memory_repo().save_session(state)
    except Exception as exc:
        print(f"Warning: failed to persist session after checkpoint_decision: {exc}")

    clarifying_question = None
    if request.decision == "reject":
        clarifying_question = cpm.get_clarifying_question(updated)

    return {
        "checkpoint": updated.model_dump(),
        "clarifying_question": clarifying_question,
        "auto_approve_enabled": request.auto_approve,
    }


@app.get("/checkpoint/{checkpoint_id}")
async def get_checkpoint(checkpoint_id: str, session_id: Optional[str] = None):
    """Get checkpoint details."""
    if session_id:
        state = await get_session_or_404(session_id)
        checkpoint = state.checkpoint

        if checkpoint and checkpoint.id == checkpoint_id:
            return checkpoint.model_dump()

    raise HTTPException(status_code=404, detail="Checkpoint not found")


# =============================================================================
# Debug Endpoints
# =============================================================================


@app.get("/debug/config")
async def debug_config():
    """Debug endpoint to check configuration."""
    from llm.greennode import validate_environment

    result = validate_environment()

    registry = get_registry()
    result["agents"] = {
        "count": len(registry.all()),
        "names": registry.all_names(),
        "routing": registry.routing_descriptions(),
    }

    return result


@app.get("/artifact/{artifact_id}")
async def download_artifact(artifact_id: str):
    """
    Download a generated artifact (PPTX, Mermaid diagram, HTML wireframe, etc.).
    """
    from fastapi.responses import FileResponse, Response as FastAPIResponse

    entry = _artifact_store.get(artifact_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Artifact not found")

    if entry.get("storage") == "file":
        path = entry["path"]
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="Artifact file no longer available")
        return FileResponse(
            path=path,
            filename=entry.get("filename", artifact_id),
            media_type=entry.get("media_type", "application/octet-stream"),
        )

    # In-memory text artifact
    content = entry.get("content", "")
    if isinstance(content, str):
        content = content.encode("utf-8")
    return FastAPIResponse(
        content=content,
        media_type=entry.get("media_type", "text/plain"),
        headers={
            "Content-Disposition": f'attachment; filename="{entry.get("filename", artifact_id)}"'
        },
    )


@app.get("/debug/agents")
async def debug_agents():
    """Debug endpoint to list all agents."""
    try:
        registry = get_registry()
        agents = []
        for name in registry.all_names():
            agent = registry.get(name)
            if not agent:
                continue
            agents.append(
                {
                    "name": getattr(agent, "name", name),
                    "role": getattr(agent, "role_description", ""),
                    "enabled": bool(getattr(agent, "enabled", True)),
                }
            )
        return {"agents": agents}
    except Exception as exc:
        print(f"Warning: /debug/agents failed: {exc}")
        return {"agents": []}


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=DEBUG,
    )

