"""
Knowledge Base Repository (KBRepo)
===================================
Repository interface for the vector knowledge base. LanceDB-backed.

This interface enables RAG (Retrieval-Augmented Generation) for agents.
Uses configurable embeddings with GreenNode-hosted `baai/bge-m3` as the
default production provider, plus an optional local reranker fallback.
"""

import os
import json
import uuid
from typing import Optional, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from dotenv import load_dotenv

from repos.embeddings import (
    EmbeddingProvider,
    create_embedding_provider,
)

load_dotenv()


@dataclass
class SearchResult:
    """A single search result from the knowledge base."""

    content: str
    source: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class KBRepo(ABC):
    """
    Abstract interface for knowledge base operations.
    Implement this to add new vector store backends.
    """

    @abstractmethod
    async def add_document(
        self, content: str, metadata: Optional[dict[str, Any]] = None
    ) -> str:
        """Add a document to the knowledge base. Returns document ID."""
        pass

    @abstractmethod
    async def add_documents(
        self, documents: list[tuple[str, dict[str, Any]]]
    ) -> list[str]:
        """Add multiple documents at once. Returns list of document IDs."""
        pass

    @abstractmethod
    async def search(
        self, query: str, top_k: int = 5, filters: Optional[dict[str, Any]] = None
    ) -> list[SearchResult]:
        """Search the knowledge base for relevant documents."""
        pass

    @abstractmethod
    async def delete(self, doc_id: str) -> None:
        """Delete a document by ID."""
        pass

    @abstractmethod
    async def delete_by_source(self, source: str) -> int:
        """Delete all documents from a source. Returns count of deleted docs."""
        pass

    @abstractmethod
    async def list_sources(self) -> list[str]:
        """List all unique source names in the KB."""
        pass

    @abstractmethod
    async def get_stats(self) -> dict[str, Any]:
        """Get KB statistics (doc count, etc.)."""
        pass


class LanceDBKBRepo(KBRepo):
    """
    LanceDB implementation of KBRepo.
    Uses the configured embedding provider and an optional local reranker.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize LanceDB knowledge base repository.

        Args:
            db_path: Path to LanceDB database. Defaults to ./data/knowledge_base
        """
        self.db_path = db_path or os.getenv("LANCEDB_PATH", "./data/knowledge_base")
        self._ensure_db_dir()
        self._client = None
        self._table = None
        self._embedding_provider: EmbeddingProvider = create_embedding_provider()
        self._reranker = None
        self._enable_reranker = os.getenv("KB_ENABLE_RERANKER", "false").lower() == "true"

    def _ensure_db_dir(self):
        """Ensure the database directory exists."""
        db_dir = (
            self.db_path
            if not self.db_path.endswith(".LanceDB")
            else os.path.dirname(self.db_path)
        )
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

    async def _embed_text(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for text(s) through the configured provider."""
        return await self._embedding_provider.embed_texts(texts)

    def _get_reranker(self):
        """Lazy load the reranker model."""
        if not self._enable_reranker:
            return None
        if self._reranker is None:
            try:
                from sentence_transformers import CrossEncoder

                cache_dir = os.getenv("SENTENCE_TRANSFORMERS_HOME") or os.getenv("HF_HOME")
                reranker_model = os.getenv(
                    "KB_RERANKER_MODEL", "baai/bge-reranker-v2-m3"
                )
                self._reranker = CrossEncoder(
                    reranker_model,
                    cache_folder=cache_dir,
                )
            except ImportError:
                print("Warning: sentence-transformers not installed. Using fallback.")
                self._reranker = None
        return self._reranker

    def _get_client(self):
        """Lazy initialize LanceDB client."""
        if self._client is None:
            try:
                import lancedb

                self._client = lancedb.connect(self.db_path)
            except ImportError:
                raise ImportError(
                    "LanceDB not installed. Install with: pip install lancedb"
                )
        return self._client

    def _get_table(self):
        """Get or create the LanceDB table."""
        if self._table is None:
            client = self._get_client()

            # Try to open existing table first
            try:
                self._table = client.open_table("knowledge")
            except Exception:
                self._table = None

            if self._table is None:
                import pyarrow as pa
                schema = pa.schema([
                    pa.field("vector", pa.list_(pa.float32(), 1024)),
                    pa.field("text", pa.string()),
                    pa.field("source", pa.string()),
                    pa.field("doc_id", pa.string()),
                    pa.field("metadata", pa.string()),
                ])
                self._table = client.create_table(
                    "knowledge", schema=schema, exist_ok=True
                )

        return self._table

    async def add_document(
        self, content: str, metadata: Optional[dict[str, Any]] = None
    ) -> str:
        """Add a single document to LanceDB."""
        doc_id = str(uuid.uuid4())
        metadata = metadata or {}

        # Get embedding
        embedding = (await self._embed_text([content]))[0]

        # Get table and add
        table = self._get_table()
        table.add(
            [
                {
                    "vector": embedding,
                    "text": content,
                    "source": metadata.get("source", "unknown"),
                    "doc_id": doc_id,
                    "metadata": json.dumps(metadata),
                }
            ]
        )

        return doc_id

    async def add_documents(
        self, documents: list[tuple[str, dict[str, Any]]]
    ) -> list[str]:
        """Add multiple documents at once."""
        if not documents:
            return []

        # Extract texts and metadata
        texts = [doc[0] for doc in documents]
        metadata_list = [doc[1] for doc in documents]

        # Generate embeddings in batch
        embeddings = await self._embed_text(texts)

        # Build records
        doc_ids = []
        records = []
        for i, (text, metadata) in enumerate(zip(texts, metadata_list)):
            doc_id = str(uuid.uuid4())
            doc_ids.append(doc_id)
            records.append(
                {
                    "vector": embeddings[i],
                    "text": text,
                    "source": metadata.get("source", "unknown"),
                    "doc_id": doc_id,
                    "metadata": json.dumps(metadata),
                }
            )

        # Add to table
        table = self._get_table()
        table.add(records)

        return doc_ids

    async def search(
        self, query: str, top_k: int = 5, filters: Optional[dict[str, Any]] = None
    ) -> list[SearchResult]:
        """
        Search LanceDB for relevant documents.
        Uses embedding similarity + optional reranking.
        """
        # Generate query embedding
        query_embedding = (await self._embed_text([query]))[0]

        # Get table
        table = self._get_table()

        # Build search query
        # Increase top_k to get more results for reranking
        search_k = top_k * 3 if self._get_reranker() else top_k

        try:
            results = (
                table.search(query_embedding, vector_column_name="vector")
                .limit(search_k)
                .to_list()
            )
        except Exception:
            # Fallback if search fails
            return []

        if not results:
            return []

        # Apply filters if provided
        if filters:
            results = self._apply_filters(results, filters)

        # Apply reranking if available
        if self._get_reranker() and results:
            results = await self._rerank_results(query, results, top_k)
        else:
            # Just take top_k after filtering
            results = results[:top_k]

        # Convert to SearchResult objects
        search_results = []
        for r in results:
            # Parse metadata
            metadata = {}
            if r.get("metadata"):
                try:
                    metadata = json.loads(r["metadata"])  # Use JSON for safety
                except Exception:
                    pass

            search_results.append(
                SearchResult(
                    content=r.get("text", ""),
                    source=r.get("source", "unknown"),
                    score=r.get("_distance", 1.0),  # LanceDB uses distance, not score (lower = better)
            # Convert distance to relevance score (1 - distance, capped at 0-1)
            # Actually for display we keep raw distance but label it correctly
                    metadata=metadata,
                )
            )

        return search_results

    def _apply_filters(
        self, results: list[dict], filters: dict[str, Any]
    ) -> list[dict]:
        """Apply metadata filters to search results."""
        filtered = []
        for r in results:
            metadata_str = r.get("metadata", "{}")
            try:
                metadata = json.loads(metadata_str)
            except Exception:
                metadata = {}

            # Check if all filter conditions are met
            match = True
            for key, value in filters.items():
                if metadata.get(key) != value:
                    match = False
                    break

            if match:
                filtered.append(r)

        return filtered

    async def _rerank_results(
        self, query: str, results: list[dict], top_k: int
    ) -> list[dict]:
        """Rerank results using bge-reranker-v2-m3."""
        reranker = self._get_reranker()
        if not reranker:
            return results[:top_k]

        # Build query-document pairs
        pairs = [(query, r.get("text", "")) for r in results]

        # Get reranking scores
        try:
            scores = reranker.predict(pairs)
        except Exception:
            return results[:top_k]

        # Add scores to results and sort
        for i, r in enumerate(results):
            r["_rerank_score"] = scores[i] if i < len(scores) else 0.0

        # Sort by rerank score (higher is better)
        results.sort(key=lambda x: x.get("_rerank_score", 0), reverse=True)

        return results[:top_k]

    async def delete(self, doc_id: str) -> None:
        """Delete a document by ID."""
        table = self._get_table()
        # LanceDB doesn't support direct delete by doc_id easily
        # We'll mark it as deleted via metadata
        try:
            table.update(
                where=f"doc_id = '{doc_id}'",
                values={"text": "[DELETED]", "source": "[DELETED]"},
            )
        except Exception:
            pass

    async def delete_by_source(self, source: str) -> int:
        """Delete all documents from a source."""
        table = self._get_table()
        try:
            df = table.to_pandas()
            before = int((df["source"] == source).sum())

            # Delete by source (mark as deleted)
            table.update(
                where=f"source = '{source}'",
                values={"text": "[DELETED]", "source": "[DELETED]"},
            )

            return before
        except Exception:
            return 0

    async def list_sources(self) -> list[str]:
        """List all unique source names."""
        table = self._get_table()
        try:
            df = table.to_pandas()
            sources = df["source"].unique().tolist()
            # Filter out deleted
            return [s for s in sources if s != "[DELETED]"]
        except Exception:
            return []

    async def get_stats(self) -> dict[str, Any]:
        """Get KB statistics."""
        table = self._get_table()
        try:
            df = table.to_pandas()
            total = int((df["source"] != "[DELETED]").sum())
            sources = await self.list_sources()
            return {"total_documents": total, "sources": sources, "source_count": len(sources), "backend": "lancedb"}
        except Exception:
            return {"total_documents": 0, "sources": [], "source_count": 0, "backend": "lancedb"}


# =============================================================================
# Factory
# =============================================================================

def create_kb_repo() -> KBRepo:
    """Create the KB repository. LanceDB only — this project runs on its own
    VPS (see CLAUDE.md's Deployment section), not AgentBase Runtime. Source-file
    change detection uses tools/ingest.py's local ingest_state.json."""
    return LanceDBKBRepo()


# Default instance
_default_kb_repo: Optional[KBRepo] = None


def get_kb_repo() -> KBRepo:
    """Get the default KB repository (LanceDBKBRepo singleton)."""
    global _default_kb_repo
    if _default_kb_repo is None:
        _default_kb_repo = create_kb_repo()
    return _default_kb_repo


def set_kb_repo(repo: KBRepo) -> None:
    """Set the default KB repository (for testing)."""
    global _default_kb_repo
    _default_kb_repo = repo
