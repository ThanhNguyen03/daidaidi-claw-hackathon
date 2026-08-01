"""
Main FastAPI Application
========================
Entry point for the multi-agent sales assistant backend.
Provides REST API and SSE streaming endpoints.
"""

import asyncio
import hashlib
import os
import json
import uuid
from collections import deque
from datetime import datetime, timezone
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
    AgentOutput,
)

# Import repositories
from repos.memory_repo import get_memory_repo

# Multi-skills: central agent + skill registry
from central_agent.agent import get_central_agent
from skills.registry import get_skill_registry

# Import validation (Day 3)
from validation.question_stack import get_question_manager

# Import memory (Day 4)
from memory.feedback_extractor import get_feedback_extractor
from memory.profile import get_profile_manager

# Import checkpoint (Day 5)
from checkpoint.manager import get_checkpoint_manager

# PII masking — system component, must run before any model sees the message (BRD §3)
from pii.masking import get_masker, forget_session as forget_masked_session


# =============================================================================
# Configuration
# =============================================================================

APP_NAME = "Multi-Agent Sales Assistant"
APP_VERSION = "0.6.0"  # Day 6 version
DEBUG = os.getenv("DEBUG", "true").lower() == "true"
ACTIVE_MODE = "chat"


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
    # Startup: initialize SQLite database (users, sessions, org_rules)
    try:
        from database import init_db
        init_db()
    except Exception as e:
        print(f"Warning: database init failed (non-fatal): {e}")

    # Startup: warm up skill registry
    print("Starting up: loading skill registry...")
    try:
        registry = get_skill_registry()
        print(f"Skills loaded: {registry.all_names()}")
    except Exception as e:
        print(f"Warning: skill registry init failed (non-fatal): {e}")

    # Knowledge reaches prompts through knowledge/loader.py, which reads the files
    # each SKILL.md declares. The vector index is no longer on that path, so it is
    # off by default: it cost an embedding round-trip per document at every boot and
    # failed closed *and silently* — a 401 left the knowledge base empty with nothing
    # but a warning on stdout. Set KB_VECTOR_ENABLED=true to index anyway.
    if os.getenv("KB_VECTOR_ENABLED", "false").lower() == "true":
        print("Starting up: indexing agent knowledge into the KB vector store...")
        try:
            from tools.ingest import ingest_all_agents
            await ingest_all_agents(force=False)
        except Exception as e:
            print(f"Warning: knowledge ingest failed (non-fatal): {e}")
    else:
        print("Knowledge: static lookup via knowledge/loader.py (vector index disabled)")

    # LLM calls now run on their own pool (llm/pool.py), so asyncio's default
    # executor — used by every `asyncio.to_thread` DB/file write — is no
    # longer competing with them for threads. Widen it anyway: the default of
    # min(32, cpu+4) is as few as 6 threads on a 2-vCPU container, and a turn
    # can have several DB writes and file writes in flight at once (session
    # save, deck HTML, PPTX). Must happen before any request touches
    # to_thread, so here, before `yield`, is the only safe place.
    try:
        from concurrent.futures import ThreadPoolExecutor
        io_workers = int(os.getenv("IO_POOL_WORKERS", "16"))
        asyncio.get_running_loop().set_default_executor(
            ThreadPoolExecutor(max_workers=io_workers, thread_name_prefix="io")
        )
    except Exception as e:
        print(f"Warning: could not widen default executor (non-fatal): {e}")

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
# Auth & Admin Endpoints
# =============================================================================


class RegisterRequest(BaseModel):
    username: str
    password: str
    full_name: str


class LoginRequest(BaseModel):
    username: str
    password: str


class UserRoleRequest(BaseModel):
    user_id: int
    role: str


class OrgRuleCreateRequest(BaseModel):
    title: str
    content: str
    scope: str = "all"


class OrgRuleUpdateRequest(BaseModel):
    title: str
    content: str
    scope: str
    is_active: bool


def _get_current_user(authorization: Optional[str] = None) -> Optional[dict]:
    """Extract user from Authorization: Bearer <token> header."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:]
    try:
        from database import verify_token
        return verify_token(token)
    except Exception:
        return None


@app.post("/api/auth/register")
@app.post("/auth/register")  # Nginx strips /api/ prefix
async def auth_register(req: RegisterRequest):
    from database import register_user
    try:
        # pbkdf2 at 100_000 rounds is deliberately slow; off the loop so a
        # registration does not stall every other rep's open SSE stream.
        user = await asyncio.to_thread(register_user, req.username, req.password, req.full_name)
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/auth/login")
@app.post("/auth/login")  # Nginx strips /api/ prefix
async def auth_login(req: LoginRequest):
    from database import login_user
    try:
        # Same reason as register: pbkdf2 verification is ~60-100ms of pure
        # CPU, and it runs while other reps' streams are open.
        user = await asyncio.to_thread(login_user, req.username, req.password)
        return user
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@app.get("/api/auth/me")
@app.get("/auth/me")  # Nginx strips /api/ prefix
async def auth_me(authorization: Optional[str] = Header(None)):
    payload = _get_current_user(authorization)
    if not payload:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    from database import get_user_by_id
    user = get_user_by_id(payload["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy user")
    return user


@app.get("/api/user/sessions")
@app.get("/user/sessions")  # Nginx strips /api/ prefix
async def get_user_sessions(authorization: Optional[str] = Header(None)):
    payload = _get_current_user(authorization)
    user_id = payload["user_id"] if payload else None
    from database import db_list_user_sessions
    # Off the event loop. The sidebar polls this while a turn is streaming, and
    # sqlite3 is blocking — a read here stalls every in-flight SSE stream for its
    # duration, which is exactly when the rep is watching for progress.
    sessions = await asyncio.to_thread(db_list_user_sessions, user_id)
    return {"sessions": sessions}


@app.get("/api/user/sessions/{session_id}")
@app.get("/user/sessions/{session_id}")  # Nginx strips /api/ prefix
async def get_session_detail(session_id: str, authorization: Optional[str] = Header(None)):
    payload = _get_current_user(authorization)
    from database import db_load_session
    session = await asyncio.to_thread(db_load_session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy session")
    if session["user_id"] and payload and session["user_id"] != payload["user_id"]:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")

    # The deck/PPTX links only ever came down as a one-off SSE event on the turn
    # that built them (main.py's chat_stream, "proposal_assets") — nothing wrote
    # them into the transcript this endpoint reads (app.db). So opening a past
    # conversation from the sidebar, without sending a new message, showed no way
    # to re-download a deck that was very much still sitting in ARTIFACTS_DIR. The
    # artifact ids live in the wireframe_designer payload, which is only in the
    # *other* database (sales_assistant.db, via memory_repo) — so fetch that too.
    try:
        state = await get_memory_repo().load_session(session_id)
        wf = (state.outputs or {}).get("wireframe_designer") if state else None
        wp = wf.payload if wf is not None and isinstance(wf.payload, dict) else None
        if wp:
            assets: dict = {}
            if _artifact_available(wp.get("deck_artifact_id")):
                assets["deck_url"] = f"/artifact/{wp['deck_artifact_id']}"
            if _artifact_available(wp.get("pptx_artifact_id")):
                assets["pptx_url"] = f"/artifact/{wp['pptx_artifact_id']}"
            if assets:
                session["proposal_assets"] = assets
    except Exception as e:
        print(f"[main] proposal_assets lookup failed for {session_id} (non-fatal): {e}")

    return session


async def _purge_session_everywhere(session_id: str) -> None:
    """Drop every trace of one conversation.

    A conversation is spread across five places, and leaving any of them behind
    means the delete does not free what the rep expected: the transcript row in
    app.db, the full serialised state in sales_assistant.db (much the larger of
    the two — it carries every skill output), the in-memory session, the PII
    alias table, and the deck/PPTX files on disk.
    """
    from database import db_delete_session

    # Artifact ids live on the wireframe payload, so read them before the state goes.
    state = _session_store.get(session_id)
    if state is None:
        try:
            state = await get_memory_repo().load_session(session_id)
        except Exception:
            state = None

    artifact_ids: list[str] = []
    figma_codes: list[str] = []
    if state is not None:
        wf = (state.outputs or {}).get("wireframe_designer")
        payload = getattr(wf, "payload", None) if wf is not None else None
        if isinstance(payload, dict):
            artifact_ids = [
                payload[k]
                for k in ("deck_artifact_id", "pptx_artifact_id")
                if payload.get(k)
            ]
        # A parked wireframe spec carries the client's brand, prices and journey, so it is
        # part of the conversation and goes with it.
        fw = (state.outputs or {}).get("figma_wireframe")
        fw_payload = getattr(fw, "payload", None) if fw is not None else None
        if isinstance(fw_payload, dict) and fw_payload.get("job_code"):
            figma_codes = [fw_payload["job_code"]]

    await asyncio.to_thread(db_delete_session, session_id)

    try:
        await get_memory_repo().delete_session(session_id)
    except Exception as e:
        print(f"[main] memory repo delete failed for {session_id}: {e}")

    _session_store.pop(session_id, None)
    _cs_session_store.pop(session_id, None)
    _deleted_sessions.append(session_id)
    # The alias table is the only place raw PII still exists in this process
    # (BRD §13); it must go with the conversation it belongs to.
    forget_masked_session(session_id)

    for artifact_id in artifact_ids:
        _artifact_store.pop(artifact_id, None)
        for ext in (".pptx", ".html"):
            path = os.path.join(ARTIFACTS_DIR, artifact_id + ext)
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError as e:
                print(f"[main] could not remove artifact {path}: {e}")

    if figma_codes:
        from figma.jobs import purge_jobs
        await asyncio.to_thread(purge_jobs, figma_codes)


async def _reclaim_space() -> None:
    """Compact both databases. Called once per delete request, never per session."""
    from database import db_vacuum

    await asyncio.to_thread(db_vacuum)
    try:
        await get_memory_repo().vacuum()
    except Exception as e:
        print(f"[main] state DB vacuum skipped: {e}")


def _assert_may_delete(session_id: str, payload: Optional[dict]) -> None:
    """404 when the conversation is gone, 403 when it is somebody else's."""
    from database import db_get_session_owner

    try:
        owner_id = db_get_session_owner(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Không tìm thấy cuộc trò chuyện")
    if owner_id is not None and (not payload or owner_id != payload["user_id"]):
        raise HTTPException(status_code=403, detail="Không có quyền xoá cuộc trò chuyện này")


@app.delete("/api/user/sessions/{session_id}")
@app.delete("/user/sessions/{session_id}")  # Nginx strips /api/ prefix
async def delete_user_session(
    session_id: str, authorization: Optional[str] = Header(None)
):
    """Delete one conversation from the history list."""
    payload = _get_current_user(authorization)
    await asyncio.to_thread(_assert_may_delete, session_id, payload)

    await _purge_session_everywhere(session_id)
    await _reclaim_space()

    print(f"[history] deleted session {session_id}")
    return {"status": "deleted", "session_id": session_id}


@app.delete("/api/user/sessions")
@app.delete("/user/sessions")  # Nginx strips /api/ prefix
async def delete_all_user_sessions(authorization: Optional[str] = Header(None)):
    """Clear the whole history for the caller.

    Scoped to the caller on purpose: a guest clears only the unowned rows, never
    a logged-in rep's history.
    """
    from database import db_delete_user_sessions

    payload = _get_current_user(authorization)
    user_id = payload["user_id"] if payload else None

    # Read and remove the app.db rows first — that list is what tells us which
    # sessions the caller was entitled to clear.
    session_ids = await asyncio.to_thread(db_delete_user_sessions, user_id)
    for session_id in session_ids:
        await _purge_session_everywhere(session_id)
    await _reclaim_space()

    print(f"[history] cleared {len(session_ids)} session(s) for user_id={user_id}")
    return {"status": "deleted", "count": len(session_ids)}



# --- Admin-only endpoints ---

def _require_admin(authorization: Optional[str]) -> dict:
    payload = _get_current_user(authorization)
    if not payload:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    from database import get_user_by_id
    user = get_user_by_id(payload["user_id"])
    if not user or user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Chỉ Admin mới có quyền thực hiện thao tác này")
    return user


@app.get("/api/admin/users")
@app.get("/admin/users")  # Nginx strips /api/ prefix
async def admin_list_users(authorization: Optional[str] = Header(None)):
    _require_admin(authorization)
    from database import list_all_users
    return {"users": list_all_users()}


@app.put("/api/admin/users/role")
@app.put("/admin/users/role")  # Nginx strips /api/ prefix
async def admin_set_role(req: UserRoleRequest, authorization: Optional[str] = Header(None)):
    _require_admin(authorization)
    from database import update_user_role
    try:
        update_user_role(req.user_id, req.role)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/admin/rules")
@app.get("/admin/rules")  # Nginx strips /api/ prefix
async def admin_list_rules(authorization: Optional[str] = Header(None)):
    _require_admin(authorization)
    from database import list_org_rules
    return {"rules": list_org_rules()}


@app.post("/api/admin/rules")
@app.post("/admin/rules")  # Nginx strips /api/ prefix
async def admin_create_rule(req: OrgRuleCreateRequest, authorization: Optional[str] = Header(None)):
    user = _require_admin(authorization)
    from database import create_org_rule
    rule = create_org_rule(req.title, req.content, req.scope, user["id"])
    return rule


@app.put("/api/admin/rules/{rule_id}")
@app.put("/admin/rules/{rule_id}")  # Nginx strips /api/ prefix
async def admin_update_rule(rule_id: int, req: OrgRuleUpdateRequest, authorization: Optional[str] = Header(None)):
    _require_admin(authorization)
    from database import update_org_rule
    update_org_rule(rule_id, req.title, req.content, req.scope, req.is_active)
    return {"ok": True}


@app.patch("/api/admin/rules/{rule_id}/toggle")
@app.patch("/admin/rules/{rule_id}/toggle")  # Nginx strips /api/ prefix
async def admin_toggle_rule(rule_id: int, authorization: Optional[str] = Header(None)):
    _require_admin(authorization)
    from database import list_org_rules, toggle_org_rule
    rules = list_org_rules()
    rule = next((r for r in rules if r["id"] == rule_id), None)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule không tồn tại")
    toggle_org_rule(rule_id, not rule["is_active"])
    return {"ok": True, "is_active": not rule["is_active"]}


@app.delete("/api/admin/rules/{rule_id}")
@app.delete("/admin/rules/{rule_id}")  # Nginx strips /api/ prefix
async def admin_delete_rule(rule_id: int, authorization: Optional[str] = Header(None)):
    _require_admin(authorization)
    from database import delete_org_rule
    delete_org_rule(rule_id)
    return {"ok": True}


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
    resume: bool = Field(
        False,
        description=(
            "This turn is the UI nudging a paused pipeline back to life after a "
            "checkpoint approval or a question card, not something the rep typed. "
            "Inferring it from the text does not work: the nudge reads as small talk "
            "and got answered with a greeting."
        ),
    )


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

# CS mode has its own isolated session store (mode="cs", prefix "cs_sess_")
_cs_session_store: dict[str, SalesCaseState] = {}

# Sessions deleted while a turn was still in flight.
#
# Both session writes are upserts, and the one at the end of a turn runs after the
# rep could have deleted the conversation — which is exactly what they do to a turn
# that looks stuck. Without this the row came straight back, so the delete appeared
# to fail. Bounded because an entry only has to outlive one in-flight turn.
_deleted_sessions: deque[str] = deque(maxlen=256)


def _is_deleted(session_id: str) -> bool:
    return session_id in _deleted_sessions


def _clear_deletion(session_id: str) -> None:
    """Retract a tombstone because a new turn started on that session.

    A second tab can still be holding a conversation someone deleted here. If it
    sends a message, the rep is plainly using it again — persisting is right, and
    the alternative is a session that silently stops saving forever.
    """
    try:
        _deleted_sessions.remove(session_id)
    except ValueError:
        pass


def _get_or_create_cs_session(
    session_id: Optional[str], salesperson_id: str
) -> SalesCaseState:
    """Get existing CS session or create a new one."""
    if session_id and session_id in _cs_session_store:
        return _cs_session_store[session_id]
    new_id = session_id or f"cs_sess_{uuid.uuid4().hex[:12]}"
    state = SalesCaseState(
        session_id=new_id,
        salesperson_id=salesperson_id,
        mode="cs",
        validation_status="PENDING",
    )
    _cs_session_store[new_id] = state
    return state


def _brief_to_dict(brief) -> dict | None:
    """Serialize brief to dict, filtering out None values. Returns None if no fields set."""
    if not brief:
        return None
    raw = brief.model_dump(mode="json")
    filtered = {k: v for k, v in raw.items() if v is not None}
    return filtered if filtered else None


def _merge_brief_into_state(state: SalesCaseState, incoming: "Brief") -> None:
    """Merge non-None fields from incoming brief into state.brief.

    Never clears fields that the agent already extracted from conversation.
    FE-provided values take priority for fields they explicitly set.
    """
    from schemas.state import Brief as BriefModel
    if not state.brief:
        state.brief = BriefModel()
    for field in BriefModel.model_fields:
        value = getattr(incoming, field, None)
        if value is not None:
            setattr(state.brief, field, value)

# =============================================================================
# Artifact Store
# =============================================================================

_artifact_store: dict[str, dict] = {}
ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "data", "artifacts")


def _artifact_available(artifact_id: Optional[str]) -> bool:
    """Can we still serve this artifact?

    The registry is in memory and dies with the container, but the files do not —
    `/artifact/{id}` rehydrates an entry from ARTIFACTS_DIR. Checking only the
    registry meant that after a restart the deck and PPTX buttons vanished from a
    session whose files were sitting on disk the whole time.
    """
    if not artifact_id:
        return False
    if artifact_id in _artifact_store:
        return True
    return any(
        os.path.exists(os.path.join(ARTIFACTS_DIR, artifact_id + ext))
        for ext in (".pptx", ".html")
    )


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


# Sentinel yielded by _with_heartbeat when the wrapped stream has gone quiet.
_HEARTBEAT = object()
SSE_HEARTBEAT_S = float(os.getenv("SSE_HEARTBEAT_S", "10"))


async def _with_heartbeat(source: AsyncGenerator[str, None], interval: float = SSE_HEARTBEAT_S):
    """Yield from `source`, emitting a sentinel whenever it is silent for `interval`.

    A turn can spend minutes inside one skill — retrying against a rate limit, or
    just waiting on a slow completion — and during that time the SSE stream sends
    nothing at all. An idle HTTP/2 stream gets reset somewhere in the middle
    (nginx logged "upstream prematurely closed connection"), and the browser
    surfaces that to the rep as a bare "network error" on a request that was in
    fact still working.

    An SSE comment line is invisible to EventSource consumers and to our own
    parser, which only reads `data:` lines — it exists purely to keep bytes moving.
    """
    queue: asyncio.Queue = asyncio.Queue()
    _DONE = object()

    async def pump():
        try:
            async for item in source:
                await queue.put(item)
        except Exception as exc:  # surface it on the consuming side
            await queue.put(exc)
        finally:
            await queue.put(_DONE)

    task = asyncio.create_task(pump())
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=interval)
            except asyncio.TimeoutError:
                yield _HEARTBEAT
                continue
            if item is _DONE:
                return
            if isinstance(item, Exception):
                raise item
            yield item
    finally:
        if not task.done():
            task.cancel()


# =============================================================================
# Agent-Based Processing (Day 2)
# =============================================================================


async def _recompute_preview(state: SalesCaseState, params: dict) -> Optional[dict]:
    """
    Re-compute the preview/quote with updated parameters.

    This is called when user edits checkpoint params.
    For now, we simply update the total based on params.
    In a full implementation, this would re-run the Account agent.
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


async def process_with_central_agent(
    state: SalesCaseState,
    message: str,
    resume: bool = False,
) -> AsyncGenerator[str, None]:
    """
    Process message using the central agent + skills system.

    The central agent classifies intent, elicits requirements when needed,
    dispatches to the relevant skills in parallel groups, and synthesizes
    a final response. No inter-agent communication -- skills are isolated executors.
    """
    # Record user message
    state.messages.append({
        "role": "user",
        "content": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    # Load active feedback constraints
    try:
        memory_repo = get_memory_repo()
        constraints = await memory_repo.load_feedback_rules(state.salesperson_id, active_only=True)
        state.constraints = constraints
    except Exception as e:
        print(f"Warning: Failed to load constraints: {e}")
        state.constraints = []

    central_agent = get_central_agent()

    has_content = False
    async for event in central_agent.run(state, message, resume=resume):
        etype = event.get("type", "")
        if etype not in ("done",):
            # A checkpoint IS the turn's output — Chốt 1 and Chốt 2 deliberately hand
            # the rep a card and nothing else. Leaving them off this list meant a
            # perfectly successful confirmation stop was followed by "Mình đang gặp sự
            # cố kỹ thuật", which is both wrong and alarming.
            if etype in (
                "content", "agent_message", "assistant_message",
                "question_card", "checkpoint", "checkpoint_card", "proposal_assets",
            ):
                has_content = True
            yield _sse_data(event)

    if not has_content:
        # Something went wrong in the agent (exception / silent failure).
        # If we have prior context, say something useful; otherwise ask for brief.
        has_prior_context = any(m.get("role") == "assistant" for m in state.messages)
        fallback_msg = (
            "Mình đang gặp sự cố kỹ thuật. Bạn có thể thử gửi lại câu hỏi không?"
            if has_prior_context
            else "Để mình tư vấn tốt hơn, bạn có thể chia sẻ brief không? "
                 "(ngành hàng, mục tiêu, đối tượng mục tiêu)"
        )
        # Save to state.messages so the NEXT turn knows there was an error and
        # doesn't mis-interpret meta follow-ups like "lỗi gì vậy" as sales questions.
        state.messages.append({
            "role": "assistant",
            "content": fallback_msg,
            "agent": "central_agent",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        yield _sse_data({
            "type": "assistant_message",
            "agent": "central_agent",
            "content": fallback_msg,
        })

    state.summary = f"User: {message[:40]}... -> Skills: {', '.join(state.outputs.keys()) or 'none'}"
    yield _sse_data({"type": "done"})



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
    from llm.client import validate_environment

    llm_status = validate_environment()

    # Check skill registry
    skill_reg = get_skill_registry()
    skills = skill_reg.all_names()

    return {
        "status": "healthy",
        "llm_configured": llm_status["valid"],
        "skills_loaded": len(skills),
        "skill_names": skills,
    }


class ModelSelectionRequest(BaseModel):
    """Point a skill — or everything — at a specific model."""

    model: Optional[str] = Field(
        None, description="Model id to use. Null or empty clears the override."
    )
    agent: str = Field(
        "*",
        description=(
            "Skill name to override, or '*' for all of them. A per-skill override "
            "wins over the global one."
        ),
    )


@app.get("/models")
async def list_models():
    """What model each skill is on, what it will fall back to, and how much of each
    model's allowance this app has spent.

    The usage numbers are counted locally — Google exposes no API for remaining quota
    — so the response carries the caveat with it rather than leaving the UI to invent
    a confidence it does not have.
    """
    from llm.client import (
        LLM_FALLBACK_MODELS,
        MODEL_MAPPING,
        get_model_overrides,
        resolve_model,
    )
    from llm.usage import get_tracker

    tracker = get_tracker()
    overrides = get_model_overrides()
    skill_names = get_skill_registry().all_names() + ["central_agent", "deck_extractor"]

    skills = []
    for name in skill_names:
        active = resolve_model(name)
        skills.append({
            "skill": name,
            # What it starts on, what the environment says, and what actually served
            # the last call — three different things the moment a fallback fires.
            "model": active,
            "configured": MODEL_MAPPING.get(name),
            "overridden": name in overrides or "*" in overrides,
            "last_used": tracker.last_model_for(name),
            "chain": [active] + [m for m in LLM_FALLBACK_MODELS if m != active],
        })

    return {
        "skills": skills,
        "overrides": overrides,
        "fallback_chain": LLM_FALLBACK_MODELS,
        **tracker.snapshot(),
    }


@app.post("/models/select")
async def select_model(request: ModelSelectionRequest):
    """Switch models without a redeploy, for when one has run out of quota mid-demo."""
    from llm.client import get_model_overrides, resolve_model, set_model_override

    set_model_override(request.agent, request.model)
    return {
        "agent": request.agent,
        "model": resolve_model(request.agent),
        "overrides": get_model_overrides(),
    }


@app.post("/chat")
async def chat(request: ChatRequest):
    """Chat endpoint - non-streaming."""
    # Get or create session
    state = await get_or_create_session_async(
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
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )

    try:
        central_agent = get_central_agent()
        all_events = []
        async for event in central_agent.run(state, request.message):
            all_events.append(event)
        # Collect first content/agent_message as response
        response_text = ""
        for ev in all_events:
            if ev.get("type") in ("content", "agent_message", "assistant_message"):
                response_text += ev.get("content", "")
        response_text = response_text or "No response generated."
    except Exception as e:
        response_text = f"Error: {str(e)}"

    return ChatResponse(
        session_id=state.session_id,
        message=response_text,
        agent="central_agent",
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
    state = await get_or_create_session_async(
        session_id=payload.session_id,
        salesperson_id=payload.salesperson_id,
        mode=payload.mode,
    )

    # Merge FE brief into state brief — never replace entirely.
    # FE may send partial or outdated brief; BE accumulates fields across turns.
    if payload.brief:
        _merge_brief_into_state(state, payload.brief)

    # Always sync the mode on the session -- user may have switched modes
    # between requests while keeping the same session (brief/history carries over).
    state.mode = ACTIVE_MODE

    # Reset per-request agent state so agents re-run on every new message.
    # Without this, state.plan and state.visited accumulate across turns and
    # _get_next_task returns None on the 2nd+ message (all agents "visited").
    state.plan = None
    state.visited = []
    state.hop_depth = 0

    # ---- PII masking: system component, runs before anything reads the message ----
    # BRD §3/§4[A]. Everything downstream — intent classification, the planner, every
    # skill, and the persisted transcript — sees aliases. Real values are restored
    # only on the way back out to the rep. There is no code path that skips this.
    masker = get_masker(state.session_id)
    mask_result = masker.mask(payload.message)
    print(mask_result.log_line())          # counts and kinds only, never values (§14)
    safe_message = mask_result.text

    async def event_generator():
        try:
            # A new turn on this session outranks any earlier delete of it.
            _clear_deletion(state.session_id)

            # Save session to DB immediately on start so History list updates instantly
            try:
                from database import db_save_session
                auth_header = request.headers.get("authorization")
                user_payload = _get_current_user(auth_header)
                uid = user_payload["user_id"] if user_payload else None
                first_msg = state.messages[0]["content"] if state.messages else payload.message[:50]
                # Guard against state.brief being None on the very first message
                _brief = state.brief
                title = (
                    (getattr(_brief, "brand_name", None) or getattr(_brief, "industry", None) or first_msg[:50])
                    if _brief else first_msg[:50]
                )
                brief_data = _brief_to_dict(_brief) if _brief else {}
                # In a thread: this writes the whole transcript, and it sits between
                # the rep pressing send and the first byte of the stream.
                await asyncio.to_thread(
                    db_save_session,
                    session_id=state.session_id,
                    user_id=uid,
                    title=title,
                    brief_data=brief_data,
                    messages_data=state.messages,
                    constraints_data=[c.to_dict() if hasattr(c, "to_dict") else c for c in state.constraints],
                )
            except Exception as _e:
                print(f"[main] Immediate session save warning: {_e}")

            # Send session info + current brief so FE can immediately sync state
            initial_brief = _brief_to_dict(state.brief)
            yield _sse_data({'type': 'session', 'session_id': state.session_id, 'brief': initial_brief})

            # Echo the rep's own words back to their screen, not the aliased form.
            yield _sse_data({'type': 'user_message', 'content': payload.message})
            assistant_emitted = False

            feedback_extractor = get_feedback_extractor()
            memory_repo = get_memory_repo()
            profile_manager = get_profile_manager()

            # Check if message contains feedback (non-critical, swallow errors)
            try:
                if feedback_extractor.is_feedback_message(safe_message):
                    rule = feedback_extractor.extract(
                        safe_message,
                        {"salesperson_id": state.salesperson_id}
                    )
                    if rule:
                        await memory_repo.save_feedback_rule(rule)
                        profile = await memory_repo.load_profile(state.salesperson_id)
                        if not profile:
                            profile = profile_manager.create_profile(state.salesperson_id)
                        profile = profile_manager.add_constraint(profile, rule.rule_id)
                        await memory_repo.save_profile(profile)
                        yield _sse_data({'type': 'constraint_added', 'constraint': rule.model_dump(mode="json")})
            except Exception as _mem_e:
                print(f"Warning: feedback/constraint update failed (non-fatal): {_mem_e}")

            # Check for frustration in message (non-critical, swallow errors)
            try:
                profile = await memory_repo.load_profile(state.salesperson_id)
                if not profile:
                    profile = profile_manager.create_profile(state.salesperson_id)
                if profile_manager.detect_frustration(profile, safe_message):
                    await memory_repo.save_profile(profile)
            except Exception as _mem_e:
                print(f"Warning: profile frustration check failed (non-fatal): {_mem_e}")

            done_chunk = _sse_data({'type': 'done'})
            async for chunk in _with_heartbeat(
                process_with_central_agent(state, safe_message, resume=payload.resume)
            ):
                if chunk is _HEARTBEAT:
                    yield ": keepalive\n\n"
                    continue
                if chunk != done_chunk:
                    # Same list as has_content above, for the same reason: a turn whose
                    # entire output is a card has not failed.
                    if any(
                        f'"type": "{t}"' in chunk
                        for t in (
                            "assistant_message", "agent_message", "content",
                            "question_card", "checkpoint", "checkpoint_card",
                            "proposal_assets",
                        )
                    ):
                        assistant_emitted = True
                    # Restore real values on the way out. Only worth the string scan
                    # when this session actually has aliases.
                    yield masker.unmask(chunk) if masker.has_aliases() else chunk

            if not assistant_emitted:
                yield _sse_data({
                    'type': 'assistant_message',
                    'agent': 'central_agent',
                    'content': 'Mình cần thêm chút thông tin trước khi tiếp tục.',
                })

            # Checkpoint/approval flow disabled — diagrams are generated inline by skills

            # Emit proposal assets (HTML deck + PPTX) if wireframe_designer ran
            wireframe_out = state.outputs.get("wireframe_designer")
            if wireframe_out and getattr(wireframe_out, "status", "") == "COMPLETE":
                wp = wireframe_out.payload if isinstance(wireframe_out.payload, dict) else {}
                assets: dict = {}

                # Re-emit artifacts produced on an earlier turn. Without this, the
                # buttons only ever appeared on the turn that built the deck — and
                # since the PPTX bytes are dropped from state right after being stored
                # (they break JSON persistence), a later "tải file" produced a deck
                # link and no PPTX at all. Remembering the ids costs nothing.
                if _artifact_available(wp.get("deck_artifact_id")):
                    assets["deck_url"] = f"/artifact/{wp['deck_artifact_id']}"
                if _artifact_available(wp.get("pptx_artifact_id")):
                    assets["pptx_url"] = f"/artifact/{wp['pptx_artifact_id']}"

                html_content = "" if assets.get("deck_url") else wp.get("html_content", "")
                if html_content:
                    deck_id = f"deck_{uuid.uuid4().hex[:10]}"
                    # To disk, like the PPTX beside it. Held in memory the deck was
                    # lost on every restart, and the copy left behind in the payload
                    # was re-serialised into the state row on every subsequent turn —
                    # a few hundred KB of HTML rewritten per message, for a string
                    # nothing reads again.
                    try:
                        os.makedirs(ARTIFACTS_DIR, exist_ok=True)
                        deck_path = os.path.join(ARTIFACTS_DIR, f"{deck_id}.html")
                        with open(deck_path, "w", encoding="utf-8") as _f:
                            _f.write(html_content)
                        _artifact_store[deck_id] = {
                            "storage": "file",
                            "path": deck_path,
                            "filename": "proposal_deck.html",
                            "media_type": "text/html",
                            "type": "deck",
                            "title": "Proposal Deck (HTML)",
                        }
                        # Only safe to drop once the file is actually on disk.
                        wp.pop("html_content", None)
                    except Exception as _e:
                        print(f"[main] deck disk save failed, using in-memory: {_e}")
                        _artifact_store[deck_id] = {
                            "storage": "memory",
                            "content": html_content.encode("utf-8"),
                            "filename": "proposal_deck.html",
                            "media_type": "text/html",
                            "type": "deck",
                            "title": "Proposal Deck (HTML)",
                        }
                    wp["deck_artifact_id"] = deck_id
                    assets["deck_url"] = f"/artifact/{deck_id}"

                pptx_bytes = None if assets.get("pptx_url") else wp.get("pptx_bytes")
                if pptx_bytes:
                    pptx_id = f"pptx_{uuid.uuid4().hex[:10]}"
                    client_name = (state.brief.industry if state.brief and state.brief.industry else "Client")
                    pptx_data = pptx_bytes if isinstance(pptx_bytes, bytes) else bytes(pptx_bytes)
                    try:
                        os.makedirs(ARTIFACTS_DIR, exist_ok=True)
                        pptx_path = os.path.join(ARTIFACTS_DIR, f"{pptx_id}.pptx")
                        with open(pptx_path, "wb") as _f:
                            _f.write(pptx_data)
                        _artifact_store[pptx_id] = {
                            "storage": "file",
                            "path": pptx_path,
                            "filename": f"proposal_{client_name}.pptx",
                            "media_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                            "type": "pptx",
                            "title": f"Proposal Deck — {client_name}",
                        }
                    except Exception as _e:
                        print(f"[main] PPTX disk save failed, using in-memory: {_e}")
                        _artifact_store[pptx_id] = {
                            "storage": "memory",
                            "content": pptx_data,
                            "filename": f"proposal_{client_name}.pptx",
                            "media_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                            "type": "pptx",
                            "title": f"Proposal Deck — {client_name}",
                        }
                    wp["pptx_artifact_id"] = pptx_id
                    assets["pptx_url"] = f"/artifact/{pptx_id}"

                if assets:
                    yield _sse_data({"type": "proposal_assets", **assets})

                # The raw PPTX has been copied into the artifact store; drop it from
                # session state. It is binary, and SalesCaseState is serialised to JSON
                # on every save — leaving it there failed persistence outright with
                # "invalid utf-8 sequence", so any session that produced a deck silently
                # stopped being saved from that point on.
                wp.pop("pptx_bytes", None)

            # Save final state to in-memory store — unless the rep deleted this
            # conversation while the turn was running, in which case every write
            # below would put it back.
            if _is_deleted(state.session_id):
                print(f"[history] {state.session_id} deleted mid-turn — skipping final save")
                yield done_chunk
                return

            update_session(state)

            # Day 4: Also persist to database for cross-session resume & history UI
            try:
                memory_repo = get_memory_repo()
                await memory_repo.save_session(state)

                from database import db_save_session
                auth_header = request.headers.get("authorization")
                user_payload = _get_current_user(auth_header)
                uid = user_payload["user_id"] if user_payload else None
                first_msg = state.messages[0]["content"] if state.messages else "Hội thoại mới"
                # Guard against state.brief being None
                _brief2 = state.brief
                title2 = (
                    (getattr(_brief2, "brand_name", None) or getattr(_brief2, "industry", None) or first_msg[:50])
                    if _brief2 else first_msg[:50]
                )
                brief_data2 = _brief_to_dict(_brief2) if _brief2 else {}
                # Same reason, and it matters more here: this write is the last thing
                # between the final token and the `done` event, so blocking on it
                # leaves the rep watching a spinner over a finished answer.
                await asyncio.to_thread(
                    db_save_session,
                    session_id=state.session_id,
                    user_id=uid,
                    title=title2,
                    brief_data=brief_data2,
                    messages_data=state.messages,
                    constraints_data=[c.to_dict() if hasattr(c, "to_dict") else c for c in state.constraints],
                )
            except Exception as e:
                print(f"Warning: Failed to persist session to DB: {e}")

            # Send session update with latest brief (only non-None fields)
            yield _sse_data({'type': 'session_updated', 'session_id': state.session_id, 'brief': _brief_to_dict(state.brief)})
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


class CsChatRequest(BaseModel):
    """Request payload for CS mode chat."""

    message: str
    session_id: Optional[str] = None
    salesperson_id: str = Field(..., description="Salesperson identifier")


@app.post("/cs/chat/stream")
@limiter.limit("10/minute")
async def cs_chat_stream(request: Request, payload: CsChatRequest):
    """
    CS mode chat endpoint — streaming via SSE.
    Uses cs_agent and predict_agent skills only. Completely isolated from sale mode.
    """
    from cs_agent.agent import get_cs_agent

    state = _get_or_create_cs_session(
        session_id=payload.session_id,
        salesperson_id=payload.salesperson_id,
    )

    cs_agent = get_cs_agent()

    async def cs_event_generator():
        try:
            yield _sse_data({"type": "session", "session_id": state.session_id})
            yield _sse_data({"type": "user_message", "content": payload.message})

            content_emitted = False
            async for event_payload in cs_agent.run(state, payload.message):
                if event_payload.get("type") == "content" and event_payload.get("content"):
                    content_emitted = True
                yield _sse_data(event_payload)

            if not content_emitted:
                yield _sse_data({
                    "type": "assistant_message",
                    "agent": "cs_agent",
                    "content": "Xin lỗi, mình chưa tìm được câu trả lời. Bạn thử mô tả rõ hơn nhé.",
                })

            _cs_session_store[state.session_id] = state
            yield _sse_data({"type": "session_updated", "session_id": state.session_id})
            yield _sse_data({"type": "done"})
        except Exception as exc:
            print(f"Error in CS chat stream: {exc}")
            yield _sse_data({"type": "error", "error": str(exc)})
            yield _sse_data({"type": "done"})

    return StreamingResponse(
        cs_event_generator(),
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
        # The alias table dies with the session — it is the only place raw PII
        # still exists in this process (BRD §13).
        forget_masked_session(session_id)
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
    # Several answers at once, keyed by question id. The card shows every blocking
    # field together, so the rep fills them in together — submitting one at a time
    # meant the first pick immediately advanced the pipeline and the rest of the
    # card was discarded. `question_id`/`answer` still work for single answers.
    answers: Optional[dict[str, str]] = None
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
    C.5 §2: Answer a question from the QuestionStack.
    Maps answer to brief field, re-validates, returns updated question list.
    """
    state = await get_session_or_404(payload.session_id)

    # Get central_agent to handle validation response
    orchestrator = get_central_agent()

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
            "message": f"Got it -- will generate: {', '.join(outputs)}. Send your next message to proceed.",
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
    # Read from the session, not the process-global stack: questions are raised
    # per session by the gate and never registered with that manager, so it was
    # always empty and the card lost its remaining questions after one answer.
    remaining_questions = [q for q in state.question_stack if not q.answered]

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
    C.5 §6: Skip an optional question.
    Records the assumption as implicit approval.
    """
    state = await get_session_or_404(payload.session_id)

    # Get question manager and skip
    question_manager = get_question_manager()
    question_manager.skip_optional(payload.question_id)

    # Re-validate
    orchestrator = get_central_agent()
    validation_output, should_dispatch = await orchestrator.validate_before_dispatch(
        state
    )
    update_session(state)
    try:
        await get_memory_repo().save_session(state)
    except Exception as exc:
        print(f"Warning: failed to persist session after skip_question: {exc}")

    # Read from the session, not the process-global stack: questions are raised
    # per session by the gate and never registered with that manager, so it was
    # always empty and the card lost its remaining questions after one answer.
    remaining_questions = [q for q in state.question_stack if not q.answered]

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
    C.5 §5: Answer multiple questions with free text.
    The backend maps the free text to appropriate brief fields.
    """
    if not request.session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    state = await get_session_or_404(request.session_id)

    # Get central_agent
    orchestrator = get_central_agent()

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
    # Read from the session, not the process-global stack: questions are raised
    # per session by the gate and never registered with that manager, so it was
    # always empty and the card lost its remaining questions after one answer.
    remaining_questions = [q for q in state.question_stack if not q.answered]

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
        if not payload.session_id:
            raise HTTPException(status_code=400, detail="session_id is required")
        if not payload.answers and (not payload.question_id or payload.answer is None):
            raise HTTPException(
                status_code=400,
                detail="either answers, or question_id and answer, are required",
            )

        state = await get_session_or_404(payload.session_id)
        orchestrator = get_central_agent()

        # Batch: the whole card submitted in one go.
        if payload.answers:
            validation_output = await orchestrator.handle_validation_response(
                state, dict(payload.answers)
            )
            update_session(state)
            await persist_session_best_effort(state, "workflow.answer batch")
            remaining_questions = [q for q in state.question_stack if not q.answered]
            answered = len(payload.answers)
            print(f"[questions] {answered} answered in one submit, "
                  f"{len(remaining_questions)} left")
            return {
                "status": "ready" if not remaining_questions else "pending",
                "message": f"Đã ghi nhận {answered} câu trả lời.",
                "questions": [q.model_dump(mode="json") for q in remaining_questions],
                **serialize_workflow_state(state),
            }

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
        # Read from the session, not the process-global stack.
        remaining_questions = [q for q in state.question_stack if not q.answered]
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

        orchestrator = get_central_agent()
        validation_output, should_dispatch = await orchestrator.validate_before_dispatch(state)
        update_session(state)
        await persist_session_best_effort(state, "workflow.skip_question")

        # Read from the session, not the process-global stack.
        remaining_questions = [q for q in state.question_stack if not q.answered]
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
        orchestrator = get_central_agent()
        validation_output = await orchestrator.handle_validation_response(
            state, {"free_text": payload.message}
        )
        update_session(state)
        await persist_session_best_effort(state, "workflow.answer_free_text")

        question_manager = get_question_manager()
        # Read from the session, not the process-global stack.
        remaining_questions = [q for q in state.question_stack if not q.answered]
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
            if checkpoint.action.type == "confirm_brief":
                # Correcting the brief IS the point of Chốt 1 — the rep is fixing what
                # we misread. Overwrite rather than merge: _apply_field only fills
                # blanks, and here the existing value is precisely what is wrong.
                from central_agent.agent import _parse_vnd

                if state.brief is None:
                    state.brief = Brief()
                corrected: list[str] = []
                for field, raw in payload.params.items():
                    if field not in Brief.model_fields:
                        continue
                    text = str(raw).strip()
                    if not text:
                        continue
                    if field == "budget_vnd":
                        parsed = _parse_vnd(text)
                        if parsed is None:
                            continue
                        setattr(state.brief, field, parsed)
                    elif field in ("specific_requirements", "constraints"):
                        setattr(state.brief, field, [p.strip() for p in text.split(",") if p.strip()])
                    else:
                        setattr(state.brief, field, text)
                    corrected.append(field)
                print(f"[checkpoint] confirm_brief edited: {corrected or 'nothing changed'}")
            else:
                new_payload = await _recompute_preview(state, payload.params)
                if new_payload:
                    updated.preview = new_payload
                    updated.action.parameters.update(payload.params)
                    if "total_vnd" in new_payload:
                        updated.action.description = f"Generate quotation for {new_payload['total_vnd']:,} VND"

        # BRD §11.2-§11.4 — what a decision invalidates.
        # Approving clears the stop for the rest of the session. Editing or rejecting
        # rewinds only as far as it has to: a correction at Chốt 1 means extraction was
        # wrong, so the solution built on it is void too; a change of direction at Chốt 2
        # leaves the strategy and compliance work standing.
        stage = updated.action.type
        if stage in ("confirm_brief", "confirm_solution"):
            if payload.decision == "approve":
                if stage not in state.confirmed_stages:
                    state.confirmed_stages.append(stage)
                print(f"[checkpoint] {stage} approved — cleared for this session")
            else:
                state.confirmed_stages = [
                    s for s in state.confirmed_stages if s != stage
                ]
                if stage == "confirm_brief":
                    # Everything downstream rested on the brief we got wrong.
                    state.confirmed_stages = []
                    state.outputs.pop("proposal_assembler", None)
                    state.outputs.pop("wireframe_designer", None)
                print(f"[checkpoint] {stage} {payload.decision} — rerunning from that step")

        state.checkpoint = updated
        update_session(state)
        await persist_session_best_effort(state, "workflow.checkpoint_decision")

        clarifying_question = cpm.get_clarifying_question(updated) if payload.decision == "reject" else None
        return {
            "checkpoint": updated.model_dump(),
            "clarifying_question": clarifying_question,
            "auto_approve_enabled": payload.auto_approve,
            "confirmed_stages": state.confirmed_stages,
            # Tells the FE to resume the pipeline rather than just close the card.
            # An edit resumes too: confirmed_stages was cleared above, so the next
            # turn re-raises the same stop with the corrected brief and the rep sees
            # their fix reflected before anything is built on it (BRD §11.2).
            "resume": stage in ("confirm_brief", "confirm_solution")
            and payload.decision in ("approve", "edit"),
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

    # No local re-import of get_checkpoint_manager here: a function-scoped import makes
    # the name local for the whole function, so the module-level import at the top became
    # invisible and the call below raised UnboundLocalError on every request — this route
    # returned 500 unconditionally.
    cpm = get_checkpoint_manager()
    if request.auto_approve:
        cpm.set_auto_approve(session_id, checkpoint.action.type, True)

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
    from llm.client import validate_environment

    result = validate_environment()

    skill_reg = get_skill_registry()
    result["skills"] = {
        "count": len(skill_reg.all()),
        "names": skill_reg.all_names(),
        "descriptions": skill_reg.descriptions(),
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
        # Fallback: check filesystem directly — handles server restarts where in-memory
        # _artifact_store was wiped but the file was already written to ARTIFACTS_DIR.
        for _ext, _mt, _fn_suffix in [
            (".pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pptx"),
            (".html", "text/html", ".html"),
        ]:
            _candidate = os.path.join(ARTIFACTS_DIR, artifact_id + _ext)
            if os.path.exists(_candidate):
                entry = {
                    "storage": "file",
                    "path": _candidate,
                    "filename": artifact_id + _fn_suffix,
                    "media_type": _mt,
                }
                _artifact_store[artifact_id] = entry  # re-cache for subsequent requests
                break
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


# =============================================================================
# Figma wireframe — on-demand, pull-based
# =============================================================================
#
# Figma has no REST API for creating nodes, and OAuth grants no Plugin-API access, so a
# server cannot draw into a rep's file however many scopes they grant. Drawing only happens
# inside a running Figma session. Hence: the rep presses the button, this endpoint builds a
# spec and parks it under a short code, and the AdtimaBox Figma plugin pulls that code from
# inside their own file. Do not replace this with a "connect Figma via OAuth and draw
# automatically" flow — the capability does not exist to build it on.


class FigmaWireframeRequest(BaseModel):
    session_id: str


def _unmask_spec(masker, value: Any) -> Any:
    """Restore real values through the spec tree before it leaves for the plugin.

    The proposal in state is masked (pii/masking.py runs before anything reads a message), so
    the spec the skill wrote off it carries aliases. Drawing "[CONTACT-1]" into a wireframe a
    rep shows a client is worse than not drawing at all. Walked per-string rather than by
    unmasking the serialised JSON: a restored value containing a quote or a backslash would
    break the document if substituted into JSON text.
    """
    if isinstance(value, str):
        return masker.unmask(value)
    if isinstance(value, list):
        return [_unmask_spec(masker, v) for v in value]
    if isinstance(value, dict):
        return {k: _unmask_spec(masker, v) for k, v in value.items()}
    return value


@app.post("/api/figma/wireframe")
@app.post("/figma/wireframe")  # Nginx strips /api/ prefix
async def create_figma_wireframe(
    body: FigmaWireframeRequest, authorization: Optional[str] = Header(None)
):
    """Build a wireframe spec from this session's proposal and park it under a job code."""
    payload = _get_current_user(authorization)
    session_id = body.session_id

    from database import db_get_session_owner

    try:
        owner_id = await asyncio.to_thread(db_get_session_owner, session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Không tìm thấy hội thoại")
    if owner_id is not None and (not payload or owner_id != payload["user_id"]):
        raise HTTPException(status_code=403, detail="Không có quyền truy cập hội thoại này")

    state = _session_store.get(session_id)
    if state is None:
        try:
            state = await get_memory_repo().load_session(session_id)
        except Exception as e:
            print(f"[figma] state load failed for {session_id}: {e}")
            state = None
    if state is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hội thoại")

    from figma.jobs import create_job, load_job

    assembler = (state.outputs or {}).get("proposal_assembler")
    proposal = getattr(assembler, "content", "") if assembler is not None else ""
    if not proposal:
        raise HTTPException(
            status_code=409,
            detail="Chưa có proposal trong hội thoại này — tạo proposal trước khi vẽ wireframe.",
        )

    # Re-pressing the button must not spend another LLM call — but only while both the proposal
    # and the generator are unchanged. A later turn can rebuild proposal_assembler
    # (`desired_outputs` is sticky), and reusing the code across that would hand the rep a
    # wireframe of the proposal they just replaced. SPEC_VERSION covers the other half: a
    # skill upgrade has to invalidate parked specs too, or every existing session keeps
    # serving the spec its old vocabulary produced. Fingerprint, not a boolean.
    from skills.figma_wireframe.skill import SPEC_VERSION

    proposal_fp = hashlib.sha256(
        f"v{SPEC_VERSION}:{proposal}".encode("utf-8")
    ).hexdigest()[:16]
    existing = (state.outputs or {}).get("figma_wireframe")
    existing_payload = getattr(existing, "payload", None) if existing is not None else None
    if isinstance(existing_payload, dict) and existing_payload.get("proposal_fp") == proposal_fp:
        code = existing_payload.get("job_code")
        if code and await asyncio.to_thread(load_job, code):
            return {
                "job_code": code,
                "screen_count": existing_payload.get("screen_count", 0),
                "reused": True,
            }

    skill = get_skill_registry().get("figma_wireframe")
    if skill is None:
        raise HTTPException(status_code=503, detail="Skill figma_wireframe chưa được nạp")

    from skills.base import SkillContext

    context = SkillContext(
        task=(
            "Build the low-fidelity Figma wireframe spec for the user-facing screens and "
            "messaging templates described in this proposal."
        ),
        brief=state.brief,
        messages=[],
        previous_outputs={"proposal_assembler": {"content": proposal}},
        constraints=list(state.constraints or []),
        session_id=session_id,
    )

    out = await skill.execute(context)
    if out.status == "FAILED":
        # The skill's summary already says which failure this was (no proposal detail, no
        # drawable screens, model truncated) in Vietnamese — pass it through rather than
        # flattening every cause into one message.
        raise HTTPException(status_code=422, detail=out.summary)

    spec = out.payload.get("spec") or {}
    masker = get_masker(session_id)
    if masker.has_aliases():
        spec = _unmask_spec(masker, spec)

    code = await asyncio.to_thread(create_job, spec)

    # The superseded spec is now unreachable — nothing holds its code — so it would otherwise
    # sit on disk until its TTL, carrying the client's brand and prices.
    if isinstance(existing_payload, dict) and existing_payload.get("job_code"):
        from figma.jobs import purge_jobs
        await asyncio.to_thread(purge_jobs, [existing_payload["job_code"]])

    state.outputs["figma_wireframe"] = AgentOutput(
        agent="figma_wireframe",
        status=out.status,
        # The spec itself is deliberately not kept here: it is on disk under the job code,
        # and SalesCaseState is re-serialised into sqlite on every later turn — the same
        # shape of waste the deck's html_content used to cause.
        payload={
            "job_code": code,
            "screen_count": out.payload.get("screen_count", 0),
            "proposal_fp": proposal_fp,
        },
        summary=out.summary,
        content=out.content,
    )
    update_session(state)
    try:
        await get_memory_repo().save_session(state)
    except Exception as e:
        print(f"[figma] state save failed for {session_id} (non-fatal): {e}")

    return {
        "job_code": code,
        "screen_count": out.payload.get("screen_count", 0),
        "reused": False,
    }


@app.get("/api/figma/job/{code}")
@app.get("/figma/job/{code}")  # Nginx strips /api/ prefix
async def get_figma_job(code: str):
    """Serve a parked spec to the Figma plugin.

    Unauthenticated by necessity — the request comes from a plugin sandbox inside Figma,
    which carries none of this app's auth. The code is the credential: 40 bits from `secrets`,
    valid for 24 hours, and it names nothing about the session it came from.
    """
    from figma.jobs import load_job

    job = await asyncio.to_thread(load_job, code.upper())
    if not job:
        raise HTTPException(status_code=404, detail="Mã không hợp lệ hoặc đã hết hạn")
    return job


@app.get("/debug/agents")
async def debug_agents():
    """Debug endpoint to list all skills."""
    try:
        skill_reg = get_skill_registry()
        skills = []
        for name in skill_reg.all_names():
            skill = skill_reg.get(name)
            if not skill:
                continue
            skills.append({
                "name": skill.name,
                "description": skill.description,
            })
        return {"skills": skills}
    except Exception as exc:
        print(f"Warning: /debug/agents failed: {exc}")
        return {"skills": []}


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




