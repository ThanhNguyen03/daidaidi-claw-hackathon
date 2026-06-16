"""
Embedding provider helpers for the knowledge base.

This keeps the RAG layer decoupled from where embeddings are produced:
- GreenNode-hosted OpenAI-compatible embeddings for production
- Local sentence-transformers fallback for offline/dev usage
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Optional

import numpy as np
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

DEFAULT_EMBEDDING_MODEL = os.getenv("KB_EMBEDDING_MODEL", "baai/bge-m3").strip()
DEFAULT_EMBEDDING_PROVIDER = os.getenv("KB_EMBEDDING_PROVIDER", "").strip().lower()
DEFAULT_EMBEDDING_DIMENSION = int(os.getenv("KB_EMBEDDING_DIMENSION", "1024"))


def _normalize_vector(vector: list[float]) -> list[float]:
    """Normalize a vector to unit length for cosine-style retrieval."""
    arr = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(arr))
    if not norm:
        return arr.tolist()
    return (arr / norm).tolist()


class EmbeddingProvider(ABC):
    """Abstract embedding provider used by the KB repository."""

    dimension: int = DEFAULT_EMBEDDING_DIMENSION

    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts."""
        raise NotImplementedError


class LocalSentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """Local fallback that loads sentence-transformers on demand."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = (model_name or os.getenv("KB_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)).strip()
        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                print(
                    "Warning: sentence-transformers not installed. "
                    "Falling back to random vectors."
                )
                self._model = None
                return None

            cache_dir = os.getenv("SENTENCE_TRANSFORMERS_HOME") or os.getenv("HF_HOME")
            try:
                self._model = SentenceTransformer(
                    self.model_name,
                    cache_folder=cache_dir,
                )
            except Exception as exc:
                print(
                    f"Warning: failed to load local embedding model {self.model_name}: {exc}. "
                    "Falling back to random vectors."
                )
                self._model = None

        return self._model

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        model = self._get_model()
        if model is None:
            import random

            return [[random.random() for _ in range(self.dimension)] for _ in texts]

        embeddings = model.encode(
            texts,
            normalize_embeddings=True,
            batch_size=32,
            show_progress_bar=False,
        )
        return embeddings.tolist()


class GreenNodeEmbeddingProvider(EmbeddingProvider):
    """
    GreenNode-hosted embedding provider using the OpenAI-compatible embeddings API.

    This avoids downloading model weights from Hugging Face at runtime.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.model_name = (model_name or os.getenv("KB_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)).strip()
        self.base_url = (
            (base_url or os.getenv("KB_EMBEDDING_BASE_URL") or os.getenv("LLM_BASE_URL") or "").strip()
        )
        self.api_key = (
            (api_key or os.getenv("KB_EMBEDDING_API_KEY") or os.getenv("LLM_API_KEY") or "").strip()
        )
        self._client: Optional[AsyncOpenAI] = None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            if not self.base_url or not self.api_key:
                raise ValueError(
                    "GreenNode embeddings require KB_EMBEDDING_BASE_URL/LLM_BASE_URL "
                    "and KB_EMBEDDING_API_KEY/LLM_API_KEY."
                )
            self._client = AsyncOpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=60.0,
                max_retries=3,
            )
        return self._client

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        client = self._get_client()
        response = await client.embeddings.create(
            model=self.model_name,
            input=texts,
        )
        # Preserve provider output order and normalize for cosine retrieval.
        return [_normalize_vector(item.embedding) for item in response.data]


def create_embedding_provider() -> EmbeddingProvider:
    """
    Create the configured embedding provider.

    Defaults to GreenNode when LLM credentials are present, otherwise falls back
    to the local sentence-transformers implementation.
    """
    provider = os.getenv("KB_EMBEDDING_PROVIDER", DEFAULT_EMBEDDING_PROVIDER).strip().lower()
    green_provider = GreenNodeEmbeddingProvider()

    if provider == "greennode" or (
        provider == "" and green_provider.base_url and green_provider.api_key
    ):
        if green_provider.base_url and green_provider.api_key:
            return green_provider
        print(
            "Warning: GreenNode embedding provider requested but credentials are missing. "
            "Falling back to local embeddings."
        )

    if provider == "local" or provider == "":
        return LocalSentenceTransformerEmbeddingProvider()

    print(
        f"Warning: unknown KB_EMBEDDING_PROVIDER='{provider}'. "
        "Falling back to local embeddings."
    )
    return LocalSentenceTransformerEmbeddingProvider()
