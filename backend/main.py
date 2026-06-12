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

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
import uvicorn

from dotenv import load_dotenv
load_dotenv()

# Import schemas
from schemas.state import (
    SalesCaseState,
    Brief,
    Question,
    ValidationReport,
    AgentOutput,
    SalespersonProfile,
)

# Import repositories
from repos.memory_repo import get_memory_repo, MemoryRepo

# Import LLM
from llm.greennode import get_llm_client, GreenNodeClient

# =============================================================================
# Configuration
# =============================================================================

APP_NAME = "Multi-Agent Sales Assistant"
APP_VERSION = "0.1.0"
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
    session_id: Optional[str] = Field(None, description="Session ID (create new if not provided)")
    salesperson_id: str = Field(..., description="Salesperson identifier")
    mode: str = Field("chat", description="Chat mode: chat, planning, execute, brainstorm")
    brief: Optional[Brief] = Field(None, description="Initial brief data")
    context: Optional[dict] = Field(None, description="Additional context")


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    session_id: str
    message: str
    agent: str
    done: bool = False


class StreamEvent(BaseModel):
    """SSE event structure."""
    event: str
    data: dict


# =============================================================================
# State Management
# =============================================================================

# In-memory state store (would use MemoryRepo in production)
_session_store: dict[str, SalesCaseState] = {}


def get_or_create_session(
    session_id: Optional[str],
    salesperson_id: str,
    mode: str = "chat"
) -> SalesCaseState:
    """Get existing session or create new one."""
    if session_id and session_id in _session_store:
        return _session_store[session_id]

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
# LLM Interaction
# =============================================================================

async def call_llm(
    client: GreenNodeClient,
    messages: list[dict],
    system_prompt: Optional[str] = None,
) -> str:
    """
    Call the LLM and get a response.
    In Day 1, this is a simple single-turn call.
    """
    # Build messages with system prompt
    all_messages = []
    if system_prompt:
        all_messages.append({"role": "system", "content": system_prompt})
    all_messages.extend(messages)

    try:
        # For Day 1: simple non-streaming call
        response = client.create_completion(
            messages=all_messages,
            stream=False,
            temperature=0.7,
            max_tokens=2000,
        )

        if response.choices and response.choices[0].message:
            return response.choices[0].message.content or ""

        return "I apologize, but I couldn't generate a response."

    except Exception as e:
        return f"Error calling LLM: {str(e)}"


async def stream_llm_response(
    client: GreenNodeClient,
    messages: list[dict],
    system_prompt: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Stream LLM response as SSE.
    Yields properly formatted SSE data.
    """
    # Build messages with system prompt
    all_messages = []
    if system_prompt:
        all_messages.append({"role": "system", "content": system_prompt})
    all_messages.extend(messages)

    try:
        # Stream the response
        stream = client.create_completion(
            messages=all_messages,
            stream=True,
            temperature=0.7,
            max_tokens=2000,
        )

        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                # SSE format: "data: <json>\n\n"
                yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"

        # End of stream
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"


# =============================================================================
# Simple Orchestrator Logic (Day 1 - Basic)
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


async def process_message(state: SalesCaseState, message: str) -> str:
    """
    Process a user message through the orchestrator.
    Day 1: Simple LLM call without full agent dispatch.
    """
    # Get orchestrator client
    try:
        client = get_llm_client("orchestrator")
    except ValueError as e:
        return f"LLM not configured: {str(e)}. Please check your .env file."

    # Build conversation history
    messages = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in state.messages[-10:]  # Last 10 messages
    ]
    messages.append({"role": "user", "content": message})

    # Add brief context if available
    context_info = ""
    if state.brief:
        brief = state.brief
        context_parts = []
        if brief.industry:
            context_parts.append(f"Industry: {brief.industry}")
        if brief.budget_vnd:
            context_parts.append(f"Budget: {brief.budget_vnd:,} VND")
        if brief.goal:
            context_parts.append(f"Goal: {brief.goal}")
        if context_parts:
            context_info = "\n\nContext: " + ", ".join(context_parts)

    # Enhance the last user message with context
    if context_info and messages:
        messages[-1]["content"] += context_info

    # Call LLM
    response = await call_llm(
        client=client,
        messages=messages,
        system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
    )

    # Update session state
    state.messages.extend([
        {"role": "user", "content": message, "timestamp": datetime.now().isoformat()},
        {"role": "assistant", "content": response, "agent": "orchestrator", "timestamp": datetime.now().isoformat()},
    ])

    # Update summary
    if state.summary:
        state.summary += f" | User: {message[:50]}..."
    else:
        state.summary = f"User: {message[:50]}..."

    return response


async def process_message_streaming(
    state: SalesCaseState,
    message: str,
) -> AsyncGenerator[str, None]:
    """
    Process a user message with streaming response.
    Day 1: Streaming LLM call.
    """
    # Get orchestrator client
    try:
        client = get_llm_client("orchestrator")
    except ValueError as e:
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        return

    # Build conversation history
    messages = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in state.messages[-10:]
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
    accumulated_content = ""

    async for chunk in stream_llm_response(
        client=client,
        messages=messages,
        system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
    ):
        yield chunk
        # Track accumulated content
        if "content" in chunk:
            try:
                data = json.loads(chunk.replace("data: ", ""))
                if data.get("type") == "content":
                    accumulated_content += data.get("content", "")
            except:
                pass

    # Update session state after streaming completes
    if accumulated_content:
        state.messages.extend([
            {"role": "user", "content": message, "timestamp": datetime.now().isoformat()},
            {"role": "assistant", "content": accumulated_content, "agent": "orchestrator", "timestamp": datetime.now().isoformat()},
        ])

        if state.summary:
            state.summary += f" | User: {message[:30]}... → Orchestrator"
        else:
            state.summary = f"User: {message[:30]}... → Orchestrator"


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

    return {
        "status": "healthy",
        "llm_configured": llm_status["valid"],
        "session_count": len(_session_store),
    }


@app.post("/chat")
async def chat(request: ChatRequest):
    """
    Chat endpoint - non-streaming.
    For Day 1, this provides a simple end-to-end LLM call.
    """
    # Get or create session
    state = get_or_create_session(
        session_id=request.session_id,
        salesperson_id=request.salesperson_id,
        mode=request.mode,
    )

    # Update brief if provided
    if request.brief:
        state.brief = request.brief

    # Process message
    response_text = await process_message(state, request.message)

    # Save session
    update_session(state)

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
    This is the primary endpoint for the frontend.
    """
    # Get or create session
    state = get_or_create_session(
        session_id=request.session_id,
        salesperson_id=request.salesperson_id,
        mode=request.mode,
    )

    # Update brief if provided
    if request.brief:
        state.brief = request.brief

    # Save initial state
    update_session(state)

    async def event_generator():
        # Send session info first
        yield f"data: {json.dumps({'type': 'session', 'session_id': state.session_id})}\n\n"

        # Send user message event
        yield f"data: {json.dumps({'type': 'user_message', 'content': request.message})}\n\n"

        # Process and stream response
        async for chunk in process_message_streaming(state, request.message):
            yield chunk

        # Save final state
        update_session(state)

        # Send session update
        yield f"data: {json.dumps({'type': 'session_updated', 'session_id': state.session_id})}\n\n"

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
    """Get session by ID."""
    if session_id not in _session_store:
        raise HTTPException(status_code=404, detail="Session not found")

    state = _session_store[session_id]
    return {
        "session_id": state.session_id,
        "salesperson_id": state.salesperson_id,
        "mode": state.mode,
        "brief": state.brief.model_dump() if state.brief else None,
        "summary": state.summary,
        "message_count": len(state.messages),
        "created_at": state.created_at.isoformat(),
        "updated_at": state.updated_at.isoformat(),
    }


@app.get("/sessions")
async def list_sessions(
    salesperson_id: Optional[str] = None,
    limit: int = 10,
):
    """List recent sessions."""
    sessions = list(_session_store.values())

    if salesperson_id:
        sessions = [s for s in sessions if s.salesperson_id == salesperson_id]

    # Sort by updated_at descending
    sessions.sort(key=lambda s: s.updated_at, reverse=True)

    return [
        {
            "session_id": s.session_id,
            "salesperson_id": s.salesperson_id,
            "mode": s.mode,
            "summary": s.summary,
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
# Debug Endpoints
# =============================================================================

@app.get("/debug/config")
async def debug_config():
    """Debug endpoint to check configuration."""
    from llm.greennode import validate_environment
    result = validate_environment()
    return result


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