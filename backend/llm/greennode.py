"""
GreenNode LLM Wrapper
=====================
OpenAI-compatible client for GreenNode MAAS (Model-as-a-Service).
Supports per-agent model configuration via environment variables.

Usage:
    from llm.greennode import get_llm_client

    # Get client for specific agent
    client = get_llm_client("orchestrator")

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
from typing import Optional, Generator, Any
from dataclasses import dataclass

from openai import OpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from dotenv import load_dotenv
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

# Load environment variables
load_dotenv()


# =============================================================================
# Configuration
# =============================================================================

# Required environment variables
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")

# Per-agent model mapping (from environment)
MODEL_MAPPING = {
    "orchestrator": os.getenv("MODEL_ORCHESTRATOR", "MiniMax-M2.5"),
    "tech_solution": os.getenv("MODEL_TECH_SOLUTION", "MiniMax-M2.5"),
    "market_strategy": os.getenv("MODEL_MARKET_STRATEGY", "Qwen3-8B"),
    "account": os.getenv("MODEL_ACCOUNT", "Qwen3-8B"),
    "adtimabox": os.getenv("MODEL_ADTIMABOX", "Qwen3-8B"),
    "design": os.getenv("MODEL_DESIGN", "Gemma-4-2b"),
    "validation": os.getenv("MODEL_VALIDATION", "Gemma-4-2b"),
}


# =============================================================================
# Client Class
# =============================================================================

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
    def chat(self) -> OpenAI.Chat:
        """Access to chat completions API."""
        return self._client.chat

    def create_completion(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str | dict] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs
    ) -> ChatCompletion | Generator[ChatCompletionChunk, None, None]:
        """
        Create a chat completion with retry logic for transient errors.

        Retry policy:
        - 3 attempts with exponential backoff
        - Retries on: timeout, 5xx errors, rate-limit errors

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
        # For streaming, we cannot retry easily as the generator would be consumed
        # NOTE: If you need retry on streaming, consider using a non-streaming call first
        # then convert to streaming, or handle retries at a higher level
        if stream:
            return self._create_completion_no_retry(
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                **kwargs
            )

        # Use retry wrapper for non-streaming calls
        return self._create_completion_with_retry(
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
            **kwargs
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(TimeoutError),
        before_sleep=lambda retry_state: print(f"Retrying... attempt {retry_state.attempt_number}")
    )
    def _create_completion_with_retry(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str | dict] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs
    ) -> ChatCompletion:
        """Internal method with retry logic."""
        return self._create_completion_no_retry(
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
            **kwargs
        )

    def _create_completion_no_retry(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str | dict] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs
    ) -> ChatCompletion | Generator[ChatCompletionChunk, None, None]:
        params = {
            "model": self.model_path,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }

        if tools:
            params["tools"] = tools
        if tool_choice:
            params["tool_choice"] = tool_choice
        if max_tokens:
            params["max_tokens"] = max_tokens

        params.update(kwargs)

        return self._client.chat.completions.create(**params)

    def __call__(
        self,
        messages: list[dict[str, Any]],
        **kwargs
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
                timeout=60.0,  # Default timeout
                max_retries=3,
            )
        return self._client

    def get_client(self, agent_name: str) -> GreenNodeClient:
        """
        Get a configured client for a specific agent.

        Args:
            agent_name: Name of the agent (e.g., 'orchestrator', 'tech_solution')

        Returns:
            GreenNodeClient configured for that agent

        Raises:
            ValueError: If agent_name is not recognized
        """
        if agent_name not in MODEL_MAPPING:
            available = ", ".join(MODEL_MAPPING.keys())
            raise ValueError(
                f"Unknown agent: {agent_name}. "
                f"Available agents: {available}"
            )

        return GreenNodeClient(
            agent_name=agent_name,
            model_path=MODEL_MAPPING[agent_name],
            _client=self.client
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
        raise ValueError(
            "LLM not configured. Please set LLM_API_KEY in .env file."
        )
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
        result.append({
            "type": "function",
            "function": {
                "name": tool.__name__.lower(),
                "description": tool.__doc__ or f"Execute {tool.__name__}",
                "parameters": schema
            }
        })

    return result


def parse_tool_calls(
    response: ChatCompletion,
    tools: list[type]
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
    **kwargs
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
        messages=messages,
        tools=tools,
        stream=True,
        **kwargs
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
    results = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "config": {}
    }

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
    missing_models = [k for k, v in MODEL_MAPPING.items() if not v or v.startswith("your_")]
    if missing_models:
        results["warnings"].append(f"Missing model config for agents: {', '.join(missing_models)}")

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