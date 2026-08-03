"""
GreenNode LLM Wrapper
=====================
OpenAI-compatible client for GreenNode MAAS (Model-as-a-Service).
Supports per-agent model configuration via environment variables.

Usage:
    from llm.greennode import get_llm_client

    # Get client for specific agent
    client = get_llm_client("sales_orchestrator")

    # Chat completion
    response = client.chat.completions.create(
        model=client.model_path,
        messages=[{"role": "user", "content": "Hello!"}],
        stream=False
    )

    # Streaming
    for chunk in client.chat.completions.create(...stream=True):
        print(chunk.choices[0].delta.content)
"""

import os
import json
import threading
from typing import Optional, Generator, Any
from dataclasses import dataclass

from openai import (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from dotenv import load_dotenv

from llm.usage import get_tracker
from tenacity import (
    RetryError,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

# Load environment variables
load_dotenv()


# =============================================================================
# Configuration
# =============================================================================

# Required environment variables
LLM_BASE_URL = os.getenv(
    "LLM_BASE_URL", "https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1"
)
LLM_API_KEY = os.getenv("LLM_API_KEY", "")

# Per-request HTTP timeout. GreenNode MAAS can be slow under concurrent load — this must stay
# below central_agent's per-skill wall-clock budget (_SKILL_TIMEOUT_S, currently 270s) but high
# enough that a real (non-hung) completion isn't killed mid-generation.
LLM_REQUEST_TIMEOUT_S = float(os.getenv("LLM_REQUEST_TIMEOUT_S", "240.0"))

# Cap on in-flight completions across the whole process.
#
# A full proposal turn fans out — planner, a knowledge selector per skill, four
# specialists in parallel, then assembler and synthesis. Measured against Gemini's
# free tier, six simultaneous requests already draws a 429. Retrying after the fact
# helps, but not colliding in the first place is cheaper and keeps latency honest.
#
# Enforced with a threading semaphore rather than an asyncio one because every call
# site funnels through run_in_executor, so the blocking happens on worker threads.
LLM_MAX_CONCURRENCY = int(os.getenv("LLM_MAX_CONCURRENCY", "3"))
_INFLIGHT = threading.BoundedSemaphore(LLM_MAX_CONCURRENCY)

# Reasoning budget, sent as OpenAI's `reasoning_effort`.
#
# Gemini 3.x thinks by default, and its thinking tokens are drawn from the same
# max_tokens budget as the answer. Measured on gemini-3.6-flash with this project's
# planner prompt: default thinking never returned inside 150s, and gemini-3.5-flash
# came back with finish_reason "length" having spent the whole budget without
# producing an answer. "low" returns in ~11s and finishes cleanly.
#
# Empty string disables the parameter entirely, for providers that reject it —
# GreenNode MAAS among them, and Gemini itself 400s on the value "none".
LLM_REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT", "").strip()

# Retry budget. Tunable because how long it takes a quota window to roll over is a
# property of the plan you are on, not of this code. Measured on Gemini's free tier:
# a full proposal run produced 28 rate-limit errors and seven calls exhausted every
# attempt, which failed four skills and left the deck with only a cover and a closing
# slide. Waiting longer is the only free remedy; the real fix is paid quota.
LLM_RETRY_ATTEMPTS = int(os.getenv("LLM_RETRY_ATTEMPTS", "6"))
LLM_RETRY_MAX_WAIT_S = int(os.getenv("LLM_RETRY_MAX_WAIT_S", "60"))

# Models to try, in order, once the configured one has spent its rate limit.
#
# Retrying is the wrong remedy for half of Gemini's free-tier limits. Requests-per-day
# is the one that bites: measured on this key, gemini-3.6-flash sat at 25/20 RPD while
# gemini-3.5-flash-lite was at 246/500 — so the five skills pointed at 3.6-flash could
# not succeed at any point later that day no matter how long they waited, and the two
# pointed at flash-lite sailed through. Waiting cannot buy back a daily quota; another
# model can.
#
# A weaker model's answer beats no answer, and the swap is logged, so a thin section in
# a proposal can be traced to it. Empty string disables fallback entirely. Deliberately
# excludes gemini-3.1-pro-preview (429s immediately on free tier) and gemini-2.5-flash
# (404s despite being advertised) — see the model table in CLAUDE.md.
LLM_FALLBACK_MODELS: list[str] = [
    m.strip()
    for m in os.getenv(
        "LLM_FALLBACK_MODELS", "gemini-3.5-flash-lite,gemini-3.5-flash"
    ).split(",")
    if m.strip()
]

# Per-agent/skill model mapping (from environment)
MODEL_MAPPING = {
    # Legacy agent names (kept for backward compat)
    "sales_orchestrator": os.getenv("MODEL_SALES_ORCHESTRATOR", "minimax/minimax-m2.5"),
    "requirement_elicitation": os.getenv("MODEL_REQUIREMENT_ELICITATION", "qwen/qwen3-5-27b"),
    "validation": os.getenv("MODEL_VALIDATION", "minimax/minimax-m2.5"),
    # Multi-skills: central agent + skills
    "central_agent": os.getenv("MODEL_CENTRAL_AGENT", os.getenv("MODEL_SALES_ORCHESTRATOR", "minimax/minimax-m2.5")),
    "market_strategy": os.getenv("MODEL_MARKET_STRATEGY", "qwen/qwen3-5-27b"),
    "product_solution": os.getenv("MODEL_PRODUCT_SOLUTION", "qwen/qwen3-5-27b"),
    "compliance": os.getenv("MODEL_COMPLIANCE", "qwen/qwen3-5-27b"),
    "client_simulator": os.getenv("MODEL_CLIENT_SIMULATOR", "qwen/qwen3-5-27b"),
    "design": os.getenv("MODEL_DESIGN", "minimax/minimax-m2.5"),
    # config/agents.yaml declares this skill's env var as MODEL_WIREFRAME_DESIGNER;
    # it was missing here, so the skill silently rode on sales_orchestrator's model
    # and the env var had no effect.
    "wireframe_designer": os.getenv("MODEL_WIREFRAME_DESIGNER", "minimax/minimax-m2.5"),
    # Figma wireframe spec generation. Emits JSON, like deck_extractor — but deliberately not
    # pinned to the same light model: deck extraction is transcription and runs on every
    # proposal turn, whereas this one runs only when a rep presses the button and has to
    # *decide* which journey steps deserve a screen and which archetype each one is. Low
    # volume means the quota argument for flash-lite does not apply here.
    # Falls back to MODEL_WIREFRAME_DESIGNER rather than the bare literal: the literal in
    # every other entry here is a leftover provider name (`minimax/...`) that Gemini answers
    # with a 404, so a skill whose own env var is missing from .env.production dies on its
    # first call instead of degrading. This one is new, so .env.production did not have its
    # var — which is exactly how that was found.
    "figma_wireframe": os.getenv(
        "MODEL_FIGMA_WIREFRAME", os.getenv("MODEL_WIREFRAME_DESIGNER", "gemini-3.6-flash")
    ),
    # CS mode skills (default to minimax; override via env if needed)
    "cs_agent": os.getenv("MODEL_CS_AGENT", "minimax/minimax-m2.5"),
    "predict_agent": os.getenv("MODEL_PREDICT_AGENT", "minimax/minimax-m2.5"),
    # Synthesis skill (default to minimax; override via MODEL_PROPOSAL_ASSEMBLER)
    "proposal_assembler": os.getenv("MODEL_PROPOSAL_ASSEMBLER", "minimax/minimax-m2.5"),
    # Slide extraction for the deck. Separated from "design" so it can be pointed at a
    # lighter model: it runs concurrently with the 16k-token proposal assembler, and on
    # a rate-limited tier those two together were reliably the pair that drew the 429 —
    # which silently degraded the deck to just a cover and a closing slide.
    "deck_extractor": os.getenv(
        "MODEL_DECK_EXTRACTOR", os.getenv("MODEL_DESIGN", "minimax/minimax-m2.5")
    ),
}


_TRANSIENT = (APITimeoutError, APIConnectionError, InternalServerError)


def _is_daily_quota(exc: Exception) -> bool:
    """Is this 429 a requests-per-DAY limit rather than a per-minute one?

    Gemini names the limit it hit in the error body — `GenerateRequestsPerDayPer...`
    versus `...PerMinute...`. The distinction decides the remedy: a per-minute limit
    clears in under a minute, a per-day one does not clear until tomorrow, so retrying
    it spends the caller's whole budget to arrive at the same 429.
    """
    text = str(exc).lower().replace(" ", "").replace("_", "")
    return "perday" in text


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, RateLimitError):
        # Worth waiting for a per-minute limit; a daily one is handed straight to the
        # caller so it can switch models instead.
        return not _is_daily_quota(exc)
    return isinstance(exc, _TRANSIENT)


# =============================================================================
# Client Class
# =============================================================================


# Runtime model overrides, set from the UI — `"*"` applies to every caller, a skill
# name to just that one.
#
# In memory only, and deliberately: a picker is for getting through the next few
# turns when a model has run dry, not for redefining the deployment. MODEL_<NAME> in
# the environment stays the source of truth across a restart.
_OVERRIDES: dict[str, str] = {}
_OVERRIDE_LOCK = threading.Lock()


def set_model_override(agent: str, model: str | None) -> None:
    """Point one caller — or everything, with agent="*" — at a specific model.
    Passing model=None clears that override."""
    with _OVERRIDE_LOCK:
        if model:
            _OVERRIDES[agent] = model
            print(f"[llm] model override: {agent} -> {model}")
        elif agent in _OVERRIDES:
            del _OVERRIDES[agent]
            print(f"[llm] model override cleared for {agent}")


def get_model_overrides() -> dict[str, str]:
    with _OVERRIDE_LOCK:
        return dict(_OVERRIDES)


def resolve_model(agent: str) -> str:
    """The model this caller will actually start with: its own override, then the
    global override, then MODEL_<NAME> from the environment."""
    with _OVERRIDE_LOCK:
        if agent in _OVERRIDES:
            return _OVERRIDES[agent]
        if "*" in _OVERRIDES:
            return _OVERRIDES["*"]
    return MODEL_MAPPING.get(
        agent, MODEL_MAPPING.get("sales_orchestrator", "MiniMax-M2.5")
    )


@dataclass
class GreenNodeClient:
    """
    OpenAI-compatible client for GreenNode MAAS.
    Wraps the OpenAI client with GreenNode-specific configuration.
    """

    agent_name: str
    model_path: str
    _client: OpenAI

    @property
    def chat(self) -> OpenAI.chat:
        """Access to chat completions API."""
        return self._client.chat

    def model_chain(self) -> list[str]:
        """Models this call will try, in order.

        Resolved per call rather than at client construction so an override taken
        from the UI applies to the very next turn — clients are cached and handed out
        by the factory, and a chain fixed at construction would ignore the picker
        until a restart.
        """
        first = resolve_model(self.agent_name)
        return [first] + [m for m in LLM_FALLBACK_MODELS if m != first]

    def create_completion(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str | dict] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs,
    ) -> ChatCompletion | Generator[ChatCompletionChunk, None, None]:
        """
        Create a chat completion with retry logic for transient errors.

        Retry policy:
        - LLM_RETRY_ATTEMPTS attempts, exponential backoff capped at LLM_RETRY_MAX_WAIT_S
        - Retries on: timeout, connection failure, 5xx, per-minute rate limits
        - Does NOT retry a per-day rate limit — falls through to the next model in
          LLM_FALLBACK_MODELS instead, because tomorrow is not a backoff window

        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: Optional list of tool definitions (OpenAI schema)
            tool_choice: Optional tool choice ("auto", "none", or {"type": "function", "function": {...}})
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response
            **kwargs: Additional parameters

        Returns:
            ChatCompletion (non-streaming) or Generator of ChatCompletionChunk (streaming)
        """
        # Try the configured model, then LLM_FALLBACK_MODELS, moving on only when a
        # model has spent its whole retry budget on rate limits. Anything else — a bad
        # request, a 404 model, a malformed reply — raises straight out: another model
        # would fail the same way, and swallowing it would hide the real error.
        chain = self.model_chain()
        tracker = get_tracker()
        last_error: Exception | None = None

        for i, model in enumerate(chain):
            try:
                # Streaming can be retried too, as long as it is only the *opening* of
                # the stream being retried — no chunk has been consumed yet, so nothing
                # is duplicated. Previously this path had no retry at all, which meant a
                # single 429 on the synthesis call ended the turn with no answer at all:
                # the most visible call in the product was also the least protected.
                if stream:
                    opened = self._open_stream_with_retry(
                        messages=messages,
                        tools=tools,
                        tool_choice=tool_choice,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        model=model,
                        **kwargs,
                    )
                    # The handshake is as far as success can be judged here — the
                    # tokens are consumed by the caller, long after this returns.
                    tracker.record_success(model)
                    return opened

                result = self._create_completion_with_retry(
                    messages=messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=False,
                    model=model,
                    **kwargs,
                )
                tracker.record_success(model)
                return result
            except (RetryError, RateLimitError) as e:
                last_error = e
                # RetryError wraps the 429 that ended the retry loop; the loop only
                # ends that way for a per-minute limit, so unwrap to tell the two
                # apart in the panel.
                inner = (
                    e.last_attempt.exception()
                    if isinstance(e, RetryError) and e.last_attempt.failed
                    else e
                )
                tracker.record_rate_limit(
                    model, daily=_is_daily_quota(inner or e), detail=str(inner or e)
                )
                if i + 1 < len(chain):
                    print(
                        f"[llm] {self.agent_name}: {model} out of quota after "
                        f"{LLM_RETRY_ATTEMPTS} attempts — switching to {chain[i + 1]}"
                    )
                else:
                    print(
                        f"[llm] {self.agent_name}: every model in the chain is out of "
                        f"quota ({', '.join(chain)})"
                    )
            except Exception as e:
                tracker.record_error(model, str(e))
                raise

        raise last_error  # type: ignore[misc]  # chain is never empty

    @retry(
        # LLM_RETRY_ATTEMPTS/LLM_RETRY_MAX_WAIT_S, not the hardcoded 5 and 30 this used
        # to carry. Every skill call is non-streaming, so those two env vars — documented
        # as the knob for a rate-limited tier — governed nothing that mattered: raising
        # them changed only the synthesis handshake while the four specialists still gave
        # up after five tries and a 30s ceiling.
        stop=stop_after_attempt(LLM_RETRY_ATTEMPTS),
        # A rate limit needs the quota window to roll over, and giving up early just
        # turns a wait into a failed turn.
        wait=wait_exponential(multiplier=1.5, min=2, max=LLM_RETRY_MAX_WAIT_S),
        # openai raises APITimeoutError/APIConnectionError (not the builtin TimeoutError)
        # on request timeouts and connection failures.
        # RateLimitError was missing despite the docstring claiming it was covered — on a
        # free tier that fires constantly, and an unretried 429 kills the whole turn.
        retry=retry_if_exception(_is_retryable),
        before_sleep=lambda retry_state: print(
            f"[llm] retry {retry_state.attempt_number}/{LLM_RETRY_ATTEMPTS} after "
            f"{type(retry_state.outcome.exception()).__name__}"
        ),
    )
    def _create_completion_with_retry(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str | dict] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs,
    ) -> ChatCompletion:
        """Internal method with retry logic."""
        return self._create_completion_no_retry(
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
            **kwargs,
        )

    @retry(
        stop=stop_after_attempt(LLM_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=2, min=4, max=LLM_RETRY_MAX_WAIT_S),
        retry=retry_if_exception(_is_retryable),
        before_sleep=lambda retry_state: print(
            f"[llm] stream retry {retry_state.attempt_number}/{LLM_RETRY_ATTEMPTS} after "
            f"{type(retry_state.outcome.exception()).__name__}"
        ),
    )
    def _open_stream_with_retry(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str | dict] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> Generator[ChatCompletionChunk, None, None]:
        """Open a stream, retrying only the handshake — safe because no chunk has
        been read yet, so a retry cannot duplicate output."""
        return self._create_completion_no_retry(
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            **kwargs,
        )

    def _create_completion_no_retry(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str | dict] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs,
    ) -> ChatCompletion | Generator[ChatCompletionChunk, None, None]:
        params = {
            "model": self.model_path,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        # Counted here rather than in create_completion so retries count too: five
        # attempts against a rate-limited model are five requests as far as the
        # provider's allowance is concerned, and a panel that showed one would explain
        # nothing about why the allowance ran out.
        get_tracker().record_attempt(str(kwargs.get("model") or self.model_path),
                                     self.agent_name)

        if tools:
            params["tools"] = tools
        if tool_choice:
            params["tool_choice"] = tool_choice
        if max_tokens:
            params["max_tokens"] = max_tokens
        if LLM_REASONING_EFFORT:
            params["reasoning_effort"] = LLM_REASONING_EFFORT

        params.update(kwargs)

        # Every completion in the process passes through here, so this is the one
        # place the concurrency cap can be applied without threading a limiter
        # through the orchestrator, the skills and the knowledge selector.
        #
        # For a stream, the semaphore is released as soon as the generator is handed
        # back rather than when it finishes: holding a slot for the whole token
        # stream would serialise the one call the user is actually watching.
        with _INFLIGHT:
            return self._client.chat.completions.create(**params)

    async def async_create_completion(
        self,
        messages: list[dict[str, Any]],
        **kwargs,
    ) -> ChatCompletion:
        """Non-blocking wrapper: runs the synchronous create_completion in a thread-pool executor."""
        import asyncio
        from functools import partial
        from llm.pool import LLM_POOL
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            LLM_POOL,
            partial(self.create_completion, messages=messages, **kwargs),
        )

    def __call__(
        self, messages: list[dict[str, Any]], **kwargs
    ) -> ChatCompletion | Generator[ChatCompletionChunk, None, None]:
        """Shorthand for create_completion."""
        return self.create_completion(messages, **kwargs)


# =============================================================================
# Client Factory
# =============================================================================


class GreenNodeLLM:
    """
    Factory for creating GreenNode clients for different agents.
    Handles client creation and configuration.
    """

    def __init__(self):
        self._client: Optional[OpenAI] = None
        self._validate_config()

    def _validate_config(self) -> None:
        """Validate that required configuration is present."""
        if not LLM_API_KEY or LLM_API_KEY == "your_greennode_api_key_here":
            raise ValueError(
                "LLM_API_KEY not configured. "
                "Please set LLM_API_KEY in your .env file. "
                "See README.md for setup instructions."
            )

    @property
    def client(self) -> OpenAI:
        """Get or create the underlying OpenAI client."""
        if self._client is None:
            self._client = OpenAI(
                base_url=LLM_BASE_URL,
                api_key=LLM_API_KEY,
                timeout=LLM_REQUEST_TIMEOUT_S,
                max_retries=3,
            )
        return self._client

    def get_client(self, agent_name: str) -> GreenNodeClient:
        """
        Get a configured client for a specific agent.

        Args:
            agent_name: Name of the agent (e.g., 'sales_orchestrator', 'market_strategy')

        Returns:
            GreenNodeClient configured for that agent

        Raises:
            ValueError: If agent_name is not recognized
        """
        # Unknown agents fall back to the sales_orchestrator model rather than crashing.
        # resolve_model also applies any override set from the UI.
        model_path = resolve_model(agent_name)

        return GreenNodeClient(
            agent_name=agent_name,
            model_path=model_path,
            _client=self.client,
        )

    def list_available_models(self) -> list[str]:
        """List all available model paths."""
        return list(MODEL_MAPPING.values())

    def get_model_for_agent(self, agent_name: str) -> str:
        """Get the model path for a specific agent."""
        return MODEL_MAPPING.get(agent_name, "MiniMax-M2.5")


# =============================================================================
# Singleton Instance
# =============================================================================

# Global singleton instance
_llm_instance: Optional[GreenNodeLLM] = None


def get_llm(force_recreate: bool = False) -> GreenNodeLLM:
    """
    Get the global GreenNode LLM instance.

    Args:
        force_recreate: If True, recreate the instance (useful for testing)

    Returns:
        GreenNodeLLM instance
    """
    global _llm_instance

    if _llm_instance is None or force_recreate:
        try:
            _llm_instance = GreenNodeLLM()
        except ValueError as e:
            # Return a dummy instance for development without API key
            # This allows imports to work even without configuration
            print(f"Warning: {e}")
            print("Running in development mode without LLM configuration.")
            _llm_instance = None

    return _llm_instance


def get_llm_client(agent_name: str) -> GreenNodeClient:
    """
    Convenience function to get a client for a specific agent.

    Args:
        agent_name: Name of the agent

    Returns:
        GreenNodeClient for the agent

    Raises:
        ValueError: If LLM is not configured
    """
    llm = get_llm()
    if llm is None:
        raise ValueError("LLM not configured. Please set LLM_API_KEY in .env file.")
    return llm.get_client(agent_name)


# =============================================================================
# Tool Calling Utilities
# =============================================================================


def format_tools(tools: list[type]) -> list[dict[str, Any]]:
    """
    Format Pydantic models as OpenAI function tools.

    Args:
        tools: List of Pydantic model classes

    Returns:
        List of tool definitions in OpenAI schema format
    """
    from pydantic import BaseModel

    result = []
    for tool in tools:
        if not issubclass(tool, BaseModel):
            raise ValueError(f"Tool must be a Pydantic model, got {tool}")

        schema = tool.model_json_schema()
        result.append(
            {
                "type": "function",
                "function": {
                    "name": tool.__name__.lower(),
                    "description": tool.__doc__ or f"Execute {tool.__name__}",
                    "parameters": schema,
                },
            }
        )

    return result


def parse_tool_calls(
    response: ChatCompletion, tools: list[type]
) -> list[tuple[type, dict]]:
    """
    Parse tool calls from a response.

    Args:
        response: ChatCompletion response
        tools: List of expected tool Pydantic models

    Returns:
        List of (tool_class, arguments) tuples
    """
    from pydantic import BaseModel

    if not response.choices:
        return []

    message = response.choices[0].message
    if not message.tool_calls:
        return []

    # Build tool lookup
    tool_lookup: dict[str, type] = {}
    for tool in tools:
        if issubclass(tool, BaseModel):
            tool_lookup[tool.__name__.lower()] = tool

    results = []
    for tc in message.tool_calls:
        tool_name = tc.function.name.lower()
        if tool_name in tool_lookup:
            args = json.loads(tc.function.arguments)
            results.append((tool_lookup[tool_name], args))

    return results


# =============================================================================
# Streaming Utilities
# =============================================================================


def stream_response(
    client: GreenNodeClient,
    messages: list[dict[str, Any]],
    tools: Optional[list[dict[str, Any]]] = None,
    **kwargs,
) -> Generator[str, None, None]:
    """
    Stream a response and yield content chunks.

    Args:
        client: GreenNodeClient to use
        messages: Chat messages
        tools: Optional tool definitions
        **kwargs: Additional parameters

    Yields:
        Content chunks as they arrive
    """
    stream = client.create_completion(
        messages=messages, tools=tools, stream=True, **kwargs
    )

    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


# =============================================================================
# Validation
# =============================================================================


def validate_environment() -> dict[str, Any]:
    """
    Validate the environment configuration.

    Returns:
        Dict with validation results
    """
    results = {"valid": True, "errors": [], "warnings": [], "config": {}}

    # Check base URL
    if not LLM_BASE_URL:
        results["valid"] = False
        results["errors"].append("LLM_BASE_URL not set")
    else:
        results["config"]["LLM_BASE_URL"] = LLM_BASE_URL

    # Check API key
    if not LLM_API_KEY:
        results["valid"] = False
        results["errors"].append("LLM_API_KEY not set")
    elif LLM_API_KEY == "your_greennode_api_key_here":
        results["warnings"].append("LLM_API_KEY is still the placeholder value")
    else:
        results["config"]["LLM_API_KEY"] = "***configured***"

    # Check model mappings
    missing_models = [
        k for k, v in MODEL_MAPPING.items() if not v or v.startswith("your_")
    ]
    if missing_models:
        results["warnings"].append(
            f"Missing model config for agents: {', '.join(missing_models)}"
        )

    results["config"]["MODEL_MAPPING"] = MODEL_MAPPING

    return results


if __name__ == "__main__":
    # Quick validation when run directly
    import sys

    try:
        result = validate_environment()
        print(json.dumps(result, indent=2))

        if not result["valid"]:
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
