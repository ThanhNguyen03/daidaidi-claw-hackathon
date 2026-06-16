"""
Knowledge Base Repository (KBRepo)
===================================
Repository interface for the vector knowledge base.
Dual implementation: LanceDB (local fallback) / AgentBase (primary).

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
            return {"total_documents": total, "sources": sources, "source_count": len(sources)}
        except Exception:
            return {"total_documents": 0, "sources": [], "source_count": 0}


# =============================================================================
# AgentBase Memory — persistent KV layer
# =============================================================================

class _AgentBaseMemoryClient:
    """
    Thin HTTP wrapper around the AgentBase Memory Records API.

    Used for KB source hash tracking (persistent across container restarts):
      Namespace "kb-hashes": records in format "{source_key}={md5_hash}"

    The Memory Records API stores text facts, not raw binary data.  Vector
    embeddings are NOT stored here — LanceDB is rebuilt via re-embedding at
    each container start using the configured embedding provider.

    IAM: standard OAuth2 client-credentials (HTTP Basic Auth + form body).
    Token script: bash .claude/skills/agentbase/scripts/get_token.sh
    """

    IAM_URL = "https://iam.api.vngcloud.vn/accounts-api/v2/auth/token"
    MEMORIES_URL = "https://agentbase.api.vngcloud.vn/memory/memories"
    HASH_NAMESPACE = "kb-hashes"

    def __init__(self, memory_id: str):
        self.memory_id = memory_id
        self._token: Optional[str] = None
        self._token_expiry: float = 0.0
        self._hash_cache: dict[str, str] = {}
        self._cache_loaded: bool = False

    async def _get_token(self) -> str:
        """
        Exchange GREENNODE_CLIENT_ID + GREENNODE_CLIENT_SECRET for a bearer token.
        Uses HTTP Basic Auth + form-encoded body (standard OAuth2 client-credentials).
        Raises ValueError immediately if credentials missing so callers can degrade.
        """
        import time
        import httpx

        if self._token and time.time() < self._token_expiry - 60:
            return self._token

        client_id = os.getenv("GREENNODE_CLIENT_ID", "").strip()
        client_secret = os.getenv("GREENNODE_CLIENT_SECRET", "").strip()

        if not client_id or not client_secret:
            raise ValueError(
                "AgentBase Memory requires GREENNODE_CLIENT_ID and "
                "GREENNODE_CLIENT_SECRET. Set them in .env (local dev) or "
                "they are auto-injected on AgentBase Runtime."
            )

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                self.IAM_URL,
                auth=(client_id, client_secret),          # HTTP Basic Auth
                data={"grant_type": "client_credentials"}, # form-encoded body
            )
            if not resp.is_success:
                raise RuntimeError(
                    f"IAM token exchange failed {resp.status_code}: {resp.text[:200]}"
                )
            data = resp.json()
            # Standard OAuth2: {"access_token": "...", "expires_in": 3600}
            # VNG Cloud nested: {"data": {"token": "...", "expiresIn": 3600}}
            if "access_token" in data:
                self._token = data["access_token"]
                self._token_expiry = time.time() + data.get("expires_in", 3600)
            elif "data" in data and "token" in data.get("data", {}):
                self._token = data["data"]["token"]
                self._token_expiry = time.time() + data["data"].get("expiresIn", 3600)
            else:
                raise RuntimeError(f"Unexpected IAM token response: keys={list(data.keys())}")

        return self._token

    async def _list_hash_records(self, token: str) -> list[dict]:
        """List all records in the kb-hashes namespace (up to 1000)."""
        import httpx
        url = f"{self.MEMORIES_URL}/{self.memory_id}/memory-records"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                params={"namespace": self.HASH_NAMESPACE, "limit": 1000},
            )
            resp.raise_for_status()
            data = resp.json()
            # Handle both dict with listData and direct list responses
            if isinstance(data, list):
                return data
            return data.get("listData", [])

    async def _ensure_cache(self) -> None:
        """Lazy-load all hash records into the in-memory cache (once per session)."""
        if self._cache_loaded:
            return
        token = await self._get_token()
        records = await self._list_hash_records(token)
        for record in records:
            # API returns text in the "memory" field (not "content")
            text = self._record_text(record)
            if "=" in text:
                k, _, v = text.partition("=")
                self._hash_cache[k] = v
        self._cache_loaded = True

    # ------------------------------------------------------------------
    # High-level KB helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _record_text(record: dict) -> str:
        """Extract the text content from a memory record.
        AgentBase Memory API returns the text in the 'memory' field."""
        return record.get("memory", "") or record.get("content", "")

    async def get_source_hash(self, source_key: str) -> Optional[str]:
        """Return the MD5 hash stored for this source, or None if not cached."""
        await self._ensure_cache()
        return self._hash_cache.get(source_key)

    async def store_source_hash(self, source_key: str, file_hash: str) -> None:
        """Persist (or update) the hash for a source file in AgentBase Memory."""
        import httpx
        token = await self._get_token()
        records = await self._list_hash_records(token)
        base = f"{self.MEMORIES_URL}/{self.memory_id}/memory-records"

        async with httpx.AsyncClient(timeout=15) as client:
            # Delete any existing record for this source_key
            for record in records:
                if self._record_text(record).startswith(f"{source_key}="):
                    record_id = record.get("id", "")
                    if record_id:
                        await client.delete(
                            f"{base}/{record_id}",
                            headers={"Authorization": f"Bearer {token}"},
                        )
            # Insert the new hash record
            resp = await client.post(
                f"{base}:insert-directly",
                headers={"Authorization": f"Bearer {token}"},
                params={"namespace": self.HASH_NAMESPACE},
                json={"memoryRecords": [f"{source_key}={file_hash}"]},
            )
            resp.raise_for_status()

        self._hash_cache[source_key] = file_hash

    async def remove_source_hash(self, source_key: str) -> None:
        """Remove the hash record for a source file from AgentBase Memory."""
        import httpx
        token = await self._get_token()
        records = await self._list_hash_records(token)
        base = f"{self.MEMORIES_URL}/{self.memory_id}/memory-records"

        async with httpx.AsyncClient(timeout=15) as client:
            for record in records:
                if self._record_text(record).startswith(f"{source_key}="):
                    record_id = record.get("id", "")
                    if record_id:
                        await client.delete(
                            f"{base}/{record_id}",
                            headers={"Authorization": f"Bearer {token}"},
                        )

        self._hash_cache.pop(source_key, None)


# =============================================================================
# HybridKBRepo — AgentBase Memory (persistence) + LanceDB (fast search)
# =============================================================================

class HybridKBRepo(KBRepo):
    """
    Two-tier KB:

    • AgentBase Memory  — persistent hash tracking across container restarts.
      Stores source_key → md5_hash records in the Memory Records API so we
      know which files have changed and avoid unnecessary hash writes.

    • LanceDB (in-process) — vector index rebuilt at every container start by
      re-embedding all source files with the configured embedding provider.
      This is the fast local vector index used for retrieval.

    Fallback (AGENTBASE_MEMORY_ID not set):
      Plain LanceDB with local ingest_state.json hash tracking.
    """

    def __init__(self):
        memory_id = os.getenv("AGENTBASE_MEMORY_ID", "").strip()
        client_id = os.getenv("GREENNODE_CLIENT_ID", "").strip()

        if memory_id and client_id:
            self._ab: Optional[_AgentBaseMemoryClient] = _AgentBaseMemoryClient(memory_id)
            self._lancedb = LanceDBKBRepo(db_path="./data/kb_runtime_cache")
            self._using_agentbase = True
            self._ab_healthy = True   # optimistic; degrades on first failure
            print("[KB] HybridKBRepo: AgentBase Memory primary + LanceDB cache")
        elif memory_id and not client_id:
            self._ab = None
            self._lancedb = LanceDBKBRepo(db_path="./data/kb_runtime_cache")
            self._using_agentbase = False
            self._ab_healthy = False
            print(
                "[KB] HybridKBRepo: AGENTBASE_MEMORY_ID is set but "
                "GREENNODE_CLIENT_ID is missing — using LanceDB only. "
                "Set GREENNODE_CLIENT_ID + GREENNODE_CLIENT_SECRET to enable AgentBase Memory."
            )
        else:
            self._ab = None
            self._lancedb = LanceDBKBRepo()  # file-based path for local dev
            self._using_agentbase = False
            self._ab_healthy = False
            print("[KB] HybridKBRepo: LanceDB-only (set AGENTBASE_MEMORY_ID to enable AgentBase Memory)")

    # ------------------------------------------------------------------
    # Hybrid-specific helpers (used by ingest.py)
    # ------------------------------------------------------------------

    @property
    def using_agentbase(self) -> bool:
        """True only when AgentBase Memory is configured AND still reachable."""
        return self._using_agentbase and self._ab_healthy

    def _degrade(self, reason: str) -> None:
        """
        Mark AgentBase Memory as unhealthy for this session.
        Logged once; all subsequent AgentBase calls are skipped silently.
        """
        if self._ab_healthy:
            self._ab_healthy = False
            print(
                f"[KB] AgentBase Memory unavailable ({reason[:200]}). "
                "Falling back to LanceDB for this session. "
                "Check GREENNODE_CLIENT_ID / GREENNODE_CLIENT_SECRET."
            )

    async def get_cached_hash(self, source_key: str) -> Optional[str]:
        """
        Return the MD5 hash stored in AgentBase Memory for this source, or None.
        Falls back to returning None (triggering a fresh embed) if AgentBase is down.
        """
        if not self.using_agentbase or not self._ab:
            return None
        try:
            return await self._ab.get_source_hash(source_key)
        except Exception as e:
            self._degrade(str(e))
            return None


    # ------------------------------------------------------------------
    # KBRepo interface
    # ------------------------------------------------------------------

    async def add_document(
        self, content: str, metadata: Optional[dict[str, Any]] = None
    ) -> str:
        return await self._lancedb.add_document(content, metadata)

    async def add_documents(
        self,
        documents: list[tuple[str, dict[str, Any]]],
        source_key: Optional[str] = None,
        file_hash: Optional[str] = None,
        update_memory: bool = True,
    ) -> list[str]:
        """
        Embed + index documents into LanceDB.
        If source_key + file_hash + update_memory are set and AgentBase Memory is
        configured, the hash is also persisted to Memory for next-restart detection.
        """
        if not documents:
            return []

        texts = [d[0] for d in documents]
        metadata_list = [d[1] for d in documents]
        embeddings = await self._lancedb._embed_text(texts)

        doc_ids: list[str] = []
        records = []

        for i, (text, meta) in enumerate(zip(texts, metadata_list)):
            did = str(uuid.uuid4())
            doc_ids.append(did)
            vec = embeddings[i]
            records.append({
                "vector": vec,
                "text": text,
                "source": meta.get("source", source_key or "unknown"),
                "doc_id": did,
                "metadata": json.dumps(meta),
            })

        table = self._lancedb._get_table()
        table.add(records)

        # Persist hash to AgentBase Memory for change detection on next restart.
        if update_memory and self.using_agentbase and self._ab and source_key and file_hash:
            try:
                await self._ab.store_source_hash(source_key, file_hash)
            except Exception as e:
                self._degrade(f"write failed for {source_key}: {e}")

        return doc_ids

    async def search(
        self, query: str, top_k: int = 5, filters: Optional[dict[str, Any]] = None
    ) -> list[SearchResult]:
        return await self._lancedb.search(query, top_k, filters)

    async def delete(self, doc_id: str) -> None:
        await self._lancedb.delete(doc_id)

    async def delete_by_source(self, source: str) -> int:
        if self.using_agentbase and self._ab:
            try:
                await self._ab.remove_source_hash(source)
            except Exception as e:
                self._degrade(f"delete failed for {source}: {e}")
        return await self._lancedb.delete_by_source(source)

    async def list_sources(self) -> list[str]:
        return await self._lancedb.list_sources()

    async def get_stats(self) -> dict[str, Any]:
        stats = await self._lancedb.get_stats()
        stats["backend"] = "agentbase+lancedb" if self._using_agentbase else "lancedb"
        return stats


# =============================================================================
# Factory
# =============================================================================

def create_kb_repo() -> KBRepo:
    """Always returns HybridKBRepo. It self-selects AgentBase vs LanceDB-only."""
    return HybridKBRepo()


# Default instance
_default_kb_repo: Optional[KBRepo] = None


def get_kb_repo() -> KBRepo:
    """Get the default KB repository (HybridKBRepo singleton)."""
    global _default_kb_repo
    if _default_kb_repo is None:
        _default_kb_repo = create_kb_repo()
    return _default_kb_repo


def set_kb_repo(repo: KBRepo) -> None:
    """Set the default KB repository (for testing)."""
    global _default_kb_repo
    _default_kb_repo = repo
