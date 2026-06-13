"""
Knowledge Base Repository (KBRepo)
===================================
Repository interface for the vector knowledge base.
Dual implementation: LanceDB (local fallback) / AgentBase (primary).

This interface enables RAG (Retrieval-Augmented Generation) for agents.
"""

from typing import Optional, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SearchResult:
    """A single search result from the knowledge base."""

    content: str
    source: str
    score: float
    metadata: dict[str, Any]


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
    async def list_sources(self) -> list[str]:
        """List all unique source names in the KB."""
        pass


class LanceDBKBRepo(KBRepo):
    """
    LanceDB implementation of KBRepo.
    Used as fallback when a managed vector store is not available.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize LanceDB knowledge base repository.

        Args:
            db_path: Path to LanceDB database. Defaults to ./data/knowledge_base
        """
        import os
        from dotenv import load_dotenv

        load_dotenv()

        self.db_path = db_path or os.getenv("LANCEDB_PATH", "./data/knowledge_base")
        self._ensure_db_dir()
        self._client = None  # Will be initialized lazily
        self._table = None

    def _ensure_db_dir(self):
        """Ensure the database directory exists."""
        import os

        db_dir = (
            self.db_path
            if not self.db_path.endswith(". LanceDB")
            else os.path.dirname(self.db_path)
        )
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

    async def add_document(
        self, content: str, metadata: Optional[dict[str, Any]] = None
    ) -> str:
        """
        Add a document to LanceDB.
        NOTE: Full implementation requires embedding model (bge-m3).
        This is a stub for Day 1 - will be fully implemented in Day 5.
        """
        import uuid

        doc_id = str(uuid.uuid4())
        # TODO: Implement with LanceDB + embedding
        # For now, return a placeholder ID
        return doc_id

    async def search(
        self, query: str, top_k: int = 5, filters: Optional[dict[str, Any]] = None
    ) -> list[SearchResult]:
        """
        Search LanceDB for relevant documents.
        NOTE: Full implementation requires embedding model (bge-m3).
        This is a stub for Day 1 - will be fully implemented in Day 5.
        """
        # Return empty results for now
        # TODO: Implement with LanceDB + embedding + reranking
        return []

    async def delete(self, doc_id: str) -> None:
        """Delete a document from LanceDB."""
        # TODO: Implement
        pass

    async def list_sources(self) -> list[str]:
        """List all unique source names."""
        # TODO: Implement
        return []


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
