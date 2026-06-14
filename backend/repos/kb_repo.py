"""
Knowledge Base Repository (KBRepo)
===================================
Repository interface for the vector knowledge base.
Dual implementation: LanceDB (local fallback) / AgentBase (primary).

This interface enables RAG (Retrieval-Augmented Generation) for agents.
Uses bge-m3 embeddings and bge-reranker-v2-m3 for multilingual retrieval.
"""

import os
import json
import uuid
from typing import Optional, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

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
    Uses bge-m3 embeddings and bge-reranker-v2-m3 for multilingual retrieval.
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
        self._embedding_model = None
        self._reranker = None

    def _ensure_db_dir(self):
        """Ensure the database directory exists."""
        db_dir = (
            self.db_path
            if not self.db_path.endswith(".LanceDB")
            else os.path.dirname(self.db_path)
        )
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

    def _get_embedding_model(self):
        """Lazy load the embedding model."""
        if self._embedding_model is None:
            try:
                from sentence_transformers import SentenceTransformer

                # Use bge-m3 for multilingual embeddings (Vietnamese support)
                self._embedding_model = SentenceTransformer("BAAI/bge-m3")
            except ImportError:
                print("Warning: sentence-transformers not installed. Using fallback.")
                self._embedding_model = None
        return self._embedding_model

    def _get_reranker(self):
        """Lazy load the reranker model."""
        if self._reranker is None:
            try:
                from sentence_transformers import CrossEncoder

                # Use bge-reranker-v2-m3 for reranking
                self._reranker = CrossEncoder("BAAI/bge-reranker-v2-m3")
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

            # Define schema with vector column
            schema = {
                "vector": "float32",  # Will be 1024-dim for bge-m3
                "text": "string",
                "source": "string",
                "doc_id": "string",
                "metadata": "string",  # JSON string
            }

            # Try to open existing table or create new
            try:
                self._table = client.open_table("knowledge")
            except Exception:
                # Table doesn't exist, will be created on first add
                self._table = None

            if self._table is None:
                # Create new table with schema
                self._table = client.create_table(
                    "knowledge", schema=schema, exist_ok=True
                )

        return self._table

    def _embed_text(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for text(s)."""
        model = self._get_embedding_model()
        if model is None:
            # Fallback: return random vectors (for testing without model)
            import random

            dim = 1024  # bge-m3 dimension
            return [[random.random() for _ in range(dim)] for _ in texts]

        # Generate embeddings
        embeddings = model.encode(
            texts, normalize_embeddings=True, batch_size=32, show_progress_bar=False
        )
        return embeddings.tolist()

    async def add_document(
        self, content: str, metadata: Optional[dict[str, Any]] = None
    ) -> str:
        """Add a single document to LanceDB."""
        doc_id = str(uuid.uuid4())
        metadata = metadata or {}

        # Get embedding
        embedding = self._embed_text([content])[0]

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
        embeddings = self._embed_text(texts)

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
        query_embedding = self._embed_text([query])[0]

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
                values={"text": "[DELETED]"},
            )
        except Exception:
            pass

    async def delete_by_source(self, source: str) -> int:
        """Delete all documents from a source."""
        table = self._get_table()
        try:
            # Get count before
            before = table.count_rows()

            # Delete by source (mark as deleted)
            table.update(where=f"source = '{source}'", values={"text": "[DELETED]"})

            # Get count after
            after = table.count_rows()
            return before - after
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
            total = table.count_rows()
            sources = await self.list_sources()
            return {"total_documents": total, "sources": sources, "source_count": len(sources)}
        except Exception:
            return {"total_documents": 0, "sources": [], "source_count": 0}


class AgentBaseKBRepo(KBRepo):
    """
    AgentBase managed vector store implementation.
    NOTE: This is a placeholder until AgentBase KB credentials are available.
    """

    def __init__(self):
        raise NotImplementedError(
            "AgentBase KB implementation requires AgentBase credentials. "
            "Use LanceDBKBRepo() for local development."
        )

    async def add_document(self, content: str, metadata: Optional[dict[str, Any]] = None) -> str:
        raise NotImplementedError()

    async def add_documents(self, documents: list[tuple[str, dict[str, Any]]]) -> list[str]:
        raise NotImplementedError()

    async def search(self, query: str, top_k: int = 5, filters: Optional[dict[str, Any]] = None) -> list[SearchResult]:
        raise NotImplementedError()

    async def delete(self, doc_id: str) -> None:
        raise NotImplementedError()

    async def delete_by_source(self, source: str) -> int:
        raise NotImplementedError()

    async def list_sources(self) -> list[str]:
        raise NotImplementedError()

    async def get_stats(self) -> dict[str, Any]:
        raise NotImplementedError()


def create_kb_repo(use_agentbase: bool = False) -> KBRepo:
    """
    Create a KB repository based on configuration.

    Args:
        use_agentbase: If True, try to use AgentBase KB.
                      Falls back to LanceDB if not available.

    Returns:
        KBRepo implementation
    """
    if use_agentbase:
        try:
            return AgentBaseKBRepo()
        except NotImplementedError:
            pass

    # Default to LanceDB
    return LanceDBKBRepo()


# Default instance
_default_kb_repo: Optional[KBRepo] = None


def get_kb_repo() -> KBRepo:
    """Get the default KB repository."""
    global _default_kb_repo
    if _default_kb_repo is None:
        _default_kb_repo = create_kb_repo(use_agentbase=False)
    return _default_kb_repo


def set_kb_repo(repo: KBRepo) -> None:
    """Set the default KB repository."""
    global _default_kb_repo
    _default_kb_repo = repo