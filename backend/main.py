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
from typing import Optional, AsyncGenerator

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import uvicorn

from dotenv import load_dotenv

load_dotenv()

# Import schemas
from schemas.state import (
    SalesCaseState,
    Brief,
    FeedbackRule,
)

# Import repositories
from repos.memory_repo import get_memory_repo, SQLiteMemoryRepo

# Import LLM
from llm.greennode import get_llm_client

# Import agent system (Day 2)
from agents.registry import get_registry
from agents.graph import get_simple_runner
from agents.orchestrator import get_orchestrator

# Import validation (Day 3)
from validation.question_stack import get_question_manager

# Import memory (Day 4)
from memory.feedback_extractor import get_feedback_extractor
from memory.profile import get_profile_manager

# =============================================================================
# Configuration
# =============================================================================

APP_NAME = "Multi-Agent Sales Assistant"
APP_VERSION = "0.4.0"  # Day 4 version
DEBUG = os.getenv("DEBUG", "true").lower() == "true"


# =============================================================================
# FastAPI App
# =============================================================================

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="AI-powered sales assistant with multi-agent orchestration",
    debug=DEBUG,
)

# CORS configuration
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
        "chat", description="Chat mode: chat, planning, execute, brainstorm"
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


def get_or_create_session(
    session_id: Optional[str], salesperson_id: str, mode: str = "chat"
) -> SalesCaseState:
    """Get existing session or create new one."""
    # First check in-memory store
    if session_id and session_id in _session_store:
        return _session_store[session_id]

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
    # First check in-memory store
    if session_id and session_id in _session_store:
        return _session_store[session_id]

    # Try loading from database (Day 4: cross-session resume)
    if session_id:
        try:
            memory_repo = get_memory_repo()
            state = await memory_repo.load_session(session_id)
            if state:
                # Found in database, also put in memory
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


# =============================================================================
# Agent-Based Processing (Day 2)
# =============================================================================


async def process_with_agents(
    state: SalesCaseState,
    message: str,
) -> AsyncGenerator[str, None]:
    """
    Process message using the multi-agent system.

    This uses the SimpleAgentRunner from Day 2 which provides
    proper agent dispatch, anti-loop guard, and status streaming.

    NOTE: When ENABLE_CHECKPOINT is true, this will use the full LangGraph
    AgentGraph which supports interrupt-before-tool HITL and durable checkpointer
    for resume. This is needed for Day 4-5 checkpoint functionality.
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

    # Check if we should use the full LangGraph (for checkpoint support)
    use_full_graph = os.getenv("ENABLE_CHECKPOINT", "false").lower() == "true"

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

    if use_full_graph:
        # Use full AgentGraph with LangGraph (for Day 4-5 checkpoint + resume)
        from agents.graph import get_graph

        graph = get_graph()
        config = {"configurable": {"thread_id": state.session_id}}

        stream_events = []
        async for event in graph.run_stream(state, config=config):
            stream_events.append(event)
            yield f"data: {json.dumps(event)}\n\n"

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

        # Stream events to client
        for event in stream_events:
            yield f"data: {json.dumps(event)}\n\n"

        # Only process summaries for non-graph mode (graph mode handles internally)
        # Add agent summary to messages
        summary_parts = []
        for agent_name, output in final_state.outputs.items():
            if hasattr(output, "summary"):
                summary_parts.append(f"{agent_name}: {output.summary}")

        if summary_parts:
            full_summary = "\n\n".join(summary_parts)
            final_state.messages.append(
                {
                    "role": "assistant",
                    "content": full_summary,
                    "agent": "orchestrator",
                    "timestamp": datetime.now().isoformat(),
                }
            )

        # Update summary
        final_state.summary = (
            f"User: {message[:30]}... → Agents: {', '.join(final_state.outputs.keys())}"
        )

        # Return updated state
        state.outputs = final_state.outputs
        state.summary = final_state.summary


# =============================================================================
# Simple LLM Processing (Day 1 fallback)
# =============================================================================

ORCHESTRATOR_SYSTEM_PROMPT = """You are the Orchestrator for a Multi-Agent Sales Assistant.

Your role is to:
1. Understand the user's request and intent
2. Determine what information is needed
3. Respond appropriately based on the mode

Current modes:
- chat: Answer questions, provide information
- planning: Create sales plans
- execute: Generate proposals, quotes, designs
- brainstorm: Facilitate group discussion

You should be helpful, professional, and concise.
Respond in the user's language (Vietnamese if they write in Vietnamese).
"""


async def process_simple(
    state: SalesCaseState,
    message: str,
) -> AsyncGenerator[str, None]:
    """
    Process message with simple LLM call (Day 1 fallback).
    """
    # Get orchestrator client
    try:
        client = get_llm_client("orchestrator")
    except ValueError as e:
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        return

    # Build conversation history
    messages = [
        {"role": msg["role"], "content": msg["content"]} for msg in state.messages[-10:]
    ]
    messages.append({"role": "user", "content": message})

    # Add brief context if available
    if state.brief:
        context_parts = []
        if state.brief.industry:
            context_parts.append(f"Industry: {state.brief.industry}")
        if state.brief.budget_vnd:
            context_parts.append(f"Budget: {state.brief.budget_vnd:,} VND")
        if context_parts:
            messages[-1]["content"] += f"\n\nContext: {', '.join(context_parts)}"

    # Stream response
    try:
        stream = client.create_completion(
            messages=messages,
            stream=True,
            temperature=0.7,
            max_tokens=2000,
        )

        accumulated = ""
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                accumulated += content
                yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"

        # Add to messages
        state.messages.append(
            {
                "role": "assistant",
                "content": accumulated,
                "agent": "orchestrator",
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


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

    # For Day 2, we'll use simple response (non-streaming)
    # The full agent dispatch would be implemented later
    client = get_llm_client("orchestrator")
    messages = [{"role": "user", "content": request.message}]

    try:
        response = client.create_completion(
            messages=messages,
            stream=False,
            temperature=0.7,
            max_tokens=2000,
        )
        response_text = (
            response.choices[0].message.content if response.choices else "No response"
        )
    except Exception as e:
        response_text = f"Error: {str(e)}"

    return ChatResponse(
        session_id=state.session_id,
        message=response_text,
        agent="orchestrator",
        done=True,
    )


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Chat endpoint - streaming via SSE.
    Uses the multi-agent system (Day 2).
    """
    # Get or create session
    state = get_or_create_session(
        session_id=request.session_id,
        salesperson_id=request.salesperson_id,
        mode=request.mode,
    )

    if request.brief:
        state.brief = request.brief

    # Determine processing mode based on request
    # Use agent system for planning/execute modes, simple for chat
    use_agents = request.mode in ["planning", "execute"]

    async def event_generator():
        # Send session info first
        yield f"data: {json.dumps({'type': 'session', 'session_id': state.session_id})}\n\n"

        # Send user message event
        yield f"data: {json.dumps({'type': 'user_message', 'content': request.message})}\n\n"

        # C.5 §3: Validation gate - check before any agent dispatch
        orchestrator = get_orchestrator()
        validation_output, should_dispatch = (
            await orchestrator.validate_before_dispatch(state)
        )

        if not should_dispatch:
            # Validation failed - send question card
            if validation_output.questions:
                yield f"data: {json.dumps({'type': 'question_card', 'questions': [q.model_dump() for q in validation_output.questions]})}\n\n"
            elif validation_output.status == "FAILED":
                # BLOCKED - send error
                yield f"data: {json.dumps({'type': 'error', 'error': validation_output.summary})}\n\n"

            # Save state to in-memory store
            update_session(state)

            # Day 4: Also persist to database for cross-session resume
            try:
                memory_repo = get_memory_repo()
                await memory_repo.save_session(state)
            except Exception as e:
                print(f"Warning: Failed to persist session: {e}")

            brief_data = state.brief.model_dump() if state.brief else None
            yield f"data: {json.dumps({'type': 'session_updated', 'session_id': state.session_id, 'validation_status': state.validation_status, 'brief': brief_data})}\n\n"
            return

        # Validation passed - proceed with agent dispatch
        # D.2: Check for feedback in the message and extract rules
        feedback_extractor = get_feedback_extractor()
        memory_repo = get_memory_repo()
        profile_manager = get_profile_manager()

        # Check if message contains feedback
        if feedback_extractor.is_feedback_message(request.message):
            rule = feedback_extractor.extract(
                request.message,
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
                yield f"data: {json.dumps({'type': 'constraint_added', 'constraint': rule.model_dump()})}\n\n"

        # D.3: Also check for frustration in message
        profile = await memory_repo.load_profile(state.salesperson_id)
        if not profile:
            profile = profile_manager.create_profile(state.salesperson_id)
        if profile_manager.detect_frustration(profile, request.message):
            await memory_repo.save_profile(profile)

        # Process based on mode
        if use_agents:
            # Use multi-agent system
            async for chunk in process_with_agents(state, request.message):
                yield chunk
        else:
            # Use simple LLM call
            async for chunk in process_simple(state, request.message):
                yield chunk

        # Save final state to in-memory store
        update_session(state)

        # Day 4: Also persist to database for cross-session resume
        try:
            memory_repo = get_memory_repo()
            await memory_repo.save_session(state)
        except Exception as e:
            print(f"Warning: Failed to persist session: {e}")

        # Send session update
        yield f"data: {json.dumps({'type': 'session_updated', 'session_id': state.session_id, 'brief': state.brief.model_dump() if state.brief else None})}\n\n"

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
async def get_session(session_id: str):
    """Get session by ID. Checks in-memory store first, then database."""
    # First check in-memory
    if session_id in _session_store:
        state = _session_store[session_id]
        return {
            "session_id": state.session_id,
            "salesperson_id": state.salesperson_id,
            "mode": state.mode,
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
                "mode": state.mode,
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
            "mode": s.mode,
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


@app.post("/chat/answer")
async def answer_question(request: AnswerQuestionRequest):
    """
    C.5 §2: Answer a question from the QuestionStack.
    Maps answer to brief field, re-validates, returns updated question list.
    """
    if request.session_id not in _session_store:
        raise HTTPException(status_code=404, detail="Session not found")

    state = _session_store[request.session_id]

    # Get orchestrator to handle validation response
    orchestrator = get_orchestrator()

    # Handle the answer
    answers = {request.question_id: request.answer}
    validation_output = await orchestrator.handle_validation_response(state, answers)

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
        }
    else:
        return {
            "status": "pending",
            "message": validation_output.summary,
            "questions": [q.model_dump() for q in remaining_questions],
            "validation_status": state.validation_status,
        }


@app.post("/chat/skip_question")
async def skip_question(request: SkipQuestionRequest):
    """
    C.5 §6: Skip an optional question.
    Records the assumption as implicit approval.
    """
    if request.session_id not in _session_store:
        raise HTTPException(status_code=404, detail="Session not found")

    state = _session_store[request.session_id]

    # Get question manager and skip
    question_manager = get_question_manager()
    question_manager.skip_optional(request.question_id)

    # Re-validate
    orchestrator = get_orchestrator()
    validation_output, should_dispatch = await orchestrator.validate_before_dispatch(
        state
    )

    remaining_questions = question_manager.stack.next_batch()

    if should_dispatch:
        return {
            "status": "ready",
            "message": "Optional question skipped. Ready to proceed.",
            "questions": [],
            "validation_status": "READY",
        }
    else:
        return {
            "status": "pending",
            "message": validation_output.summary,
            "questions": [q.model_dump() for q in remaining_questions],
            "validation_status": state.validation_status,
        }


@app.post("/chat/answer_free_text")
async def answer_free_text(request: ChatRequest):
    """
    C.5 §5: Answer multiple questions with free text.
    The backend maps the free text to appropriate brief fields.
    """
    if request.session_id not in _session_store:
        raise HTTPException(status_code=404, detail="Session not found")

    state = _session_store[request.session_id]

    # Get orchestrator
    orchestrator = get_orchestrator()

    # Handle free text answer
    answers = {"free_text": request.message}
    validation_output = await orchestrator.handle_validation_response(state, answers)

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


@app.get("/debug/agents")
async def debug_agents():
    """Debug endpoint to list all agents."""
    registry = get_registry()
    return {
        "agents": [
            {
                "name": agent.name,
                "role": agent.role_description,
                "model": agent.model_path,
                "enabled": agent.enabled,
            }
            for agent in registry.all()
        ]
    }


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
