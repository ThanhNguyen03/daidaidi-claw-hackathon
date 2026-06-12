"""
Memory Repository
=================
Repository interface for agent memory with dual implementations:
- AgentBase Managed Memory (primary)
- SQLite (local fallback)

The interface ensures both can be used interchangeably.
"""

import os
import json
import asyncio
from typing import Optional, Any
from datetime import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict

from dotenv import load_dotenv
load_dotenv()

from schemas.state import (
    SalesCaseState,
    SalespersonProfile,
    FeedbackRule,
    Brief,
    Question,
    ValidationReport,
    ExecutionPlan,
    AgentOutput,
    Checkpoint,
)


# =============================================================================
# Repository Interface
# =============================================================================

class MemoryRepo(ABC):
    """
    Abstract interface for memory persistence.
    Implement this to add new storage backends.
    """

    @abstractmethod
    async def save_session(self, state: SalesCaseState) -> None:
        """Save the current session state."""
        pass

    @abstractmethod
    async def load_session(self, session_id: str) -> Optional[SalesCaseState]:
        """Load a session by ID."""
        pass

    @abstractmethod
    async def save_profile(self, profile: SalespersonProfile) -> None:
        """Save a salesperson profile."""
        pass

    @abstractmethod
    async def load_profile(self, salesperson_id: str) -> Optional[SalespersonProfile]:
        """Load a salesperson profile."""
        pass

    @abstractmethod
    async def save_feedback_rule(self, rule: FeedbackRule) -> None:
        """Save a feedback rule."""
        pass

    @abstractmethod
    async def load_feedback_rules(
        self,
        salesperson_id: str,
        active_only: bool = True
    ) -> list[FeedbackRule]:
        """Load feedback rules for a salesperson."""
        pass

    @abstractmethod
    async def delete_feedback_rule(self, rule_id: str) -> None:
        """Delete a feedback rule."""
        pass

    @abstractmethod
    async def list_sessions(
        self,
        salesperson_id: Optional[str] = None,
        limit: int = 10
    ) -> list[dict[str, Any]]:
        """List recent sessions."""
        pass


# =============================================================================
# SQLite Implementation (Local Fallback)
# =============================================================================

class SQLiteMemoryRepo(MemoryRepo):
    """
    SQLite implementation of MemoryRepo.
    Used as fallback when AgentBase Memory is not available.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize SQLite memory repository.

        Args:
            db_path: Path to SQLite database file. Defaults to ./data/sales_assistant.db
        """
        self.db_path = db_path or os.getenv("SQLITE_DB_PATH", "./data/sales_assistant.db")
        self._ensure_db_dir()
        self._init_db()

    def _ensure_db_dir(self) -> None:
        """Ensure the database directory exists."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

    def _init_db(self) -> None:
        """Initialize database tables."""
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                salesperson_id TEXT NOT NULL,
                state_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Profiles table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                salesperson_id TEXT PRIMARY KEY,
                profile_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Feedback rules table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback_rules (
                rule_id TEXT PRIMARY KEY,
                salesperson_id TEXT NOT NULL,
                rule_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                active INTEGER DEFAULT 1
            )
        """)

        # Indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_salesperson
            ON sessions(salesperson_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_feedback_rules_salesperson
            ON feedback_rules(salesperson_id)
        """)

        conn.commit()
        conn.close()

    def _row_to_state(self, row: tuple) -> Optional[SalesCaseState]:
        """Convert database row to SalesCaseState."""
        if not row:
            return None

        _, _, state_json, created_at, updated_at = row
        data = json.loads(state_json)
        return SalesCaseState(**data)

    def _row_to_profile(self, row: tuple) -> Optional[SalespersonProfile]:
        """Convert database row to SalespersonProfile."""
        if not row:
            return None

        _, _, profile_json, created_at, updated_at = row
        data = json.loads(profile_json)
        return SalespersonProfile(**data)

    def _row_to_rule(self, row: tuple) -> Optional[FeedbackRule]:
        """Convert database row to FeedbackRule."""
        if not row:
            return None

        _, _, rule_json, created_at, active = row
        data = json.loads(rule_json)
        return FeedbackRule(**data)

    async def save_session(self, state: SalesCaseState) -> None:
        """Save session state to SQLite."""
        import sqlite3

        # Update timestamps
        state.updated_at = datetime.now()

        # Convert to JSON
        state_json = state.model_dump_json()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO sessions
            (session_id, salesperson_id, state_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            state.session_id,
            state.salesperson_id,
            state_json,
            state.created_at.isoformat(),
            state.updated_at.isoformat()
        ))

        conn.commit()
        conn.close()

    async def load_session(self, session_id: str) -> Optional[SalesCaseState]:
        """Load session from SQLite."""
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT session_id, salesperson_id, state_json, created_at, updated_at
            FROM sessions
            WHERE session_id = ?
        """, (session_id,))

        row = cursor.fetchone()
        conn.close()

        return self._row_to_state(row)

    async def save_profile(self, profile: SalespersonProfile) -> None:
        """Save profile to SQLite."""
        import sqlite3

        profile.updated_at = datetime.now()
        profile_json = profile.model_dump_json()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO profiles
            (salesperson_id, profile_json, created_at, updated_at)
            VALUES (?, ?, ?, ?)
        """, (
            profile.salesperson_id,
            profile_json,
            profile.created_at.isoformat(),
            profile.updated_at.isoformat()
        ))

        conn.commit()
        conn.close()

    async def load_profile(self, salesperson_id: str) -> Optional[SalespersonProfile]:
        """Load profile from SQLite."""
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT salesperson_id, profile_json, created_at, updated_at
            FROM profiles
            WHERE salesperson_id = ?
        """, (salesperson_id,))

        row = cursor.fetchone()
        conn.close()

        return self._row_to_profile(row)

    async def save_feedback_rule(self, rule: FeedbackRule) -> None:
        """Save feedback rule to SQLite."""
        import sqlite3

        rule_json = rule.model_dump_json()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO feedback_rules
            (rule_id, salesperson_id, rule_json, created_at, active)
            VALUES (?, ?, ?, ?, ?)
        """, (
            rule.rule_id,
            rule.salesperson_id,
            rule_json,
            rule.created_at.isoformat(),
            1 if rule.active else 0
        ))

        conn.commit()
        conn.close()

    async def load_feedback_rules(
        self,
        salesperson_id: str,
        active_only: bool = True
    ) -> list[FeedbackRule]:
        """Load feedback rules from SQLite."""
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = """
            SELECT rule_id, salesperson_id, rule_json, created_at, active
            FROM feedback_rules
            WHERE salesperson_id = ?
        """

        if active_only:
            query += " AND active = 1"

        cursor.execute(query, (salesperson_id,))
        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_rule(row) for row in rows if self._row_to_rule(row)]

    async def delete_feedback_rule(self, rule_id: str) -> None:
        """Delete feedback rule from SQLite."""
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM feedback_rules WHERE rule_id = ?
        """, (rule_id,))

        conn.commit()
        conn.close()

    async def list_sessions(
        self,
        salesperson_id: Optional[str] = None,
        limit: int = 10
    ) -> list[dict[str, Any]]:
        """List recent sessions from SQLite."""
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if salesperson_id:
            cursor.execute("""
                SELECT session_id, salesperson_id, state_json, created_at, updated_at
                FROM sessions
                WHERE salesperson_id = ?
                ORDER BY updated_at DESC
                LIMIT ?
            """, (salesperson_id, limit))
        else:
            cursor.execute("""
                SELECT session_id, salesperson_id, state_json, created_at, updated_at
                FROM sessions
                ORDER BY updated_at DESC
                LIMIT ?
            """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        result = []
        for row in rows:
            session_id, salesperson_id, state_json, created_at, updated_at = row
            state = json.loads(state_json)
            result.append({
                "session_id": session_id,
                "salesperson_id": salesperson_id,
                "mode": state.get("mode", "chat"),
                "summary": state.get("summary", ""),
                "created_at": created_at,
                "updated_at": updated_at
            })

        return result


# =============================================================================
# AgentBase Memory Implementation (Primary)
# =============================================================================

class AgentBaseMemoryRepo(MemoryRepo):
    """
    AgentBase Managed Memory implementation.
    Uses the AgentBase Memory API when available.

    NOTE: This is a placeholder implementation.
    The actual AgentBase Memory integration requires the AgentBase SDK.
    See: https://docs.greennode.ai/memory
    """

    def __init__(
        self,
        memory_url: Optional[str] = None,
        memory_api_key: Optional[str] = None
    ):
        """
        Initialize AgentBase memory repository.

        Args:
            memory_url: AgentBase Memory service URL
            memory_api_key: AgentBase API key
        """
        self.memory_url = memory_url or os.getenv("AGENTBASE_MEMORY_URL")
        self.memory_api_key = memory_api_key or os.getenv("AGENTBASE_MEMORY_API_KEY")

        if not self.memory_url or not self.memory_api_key:
            raise ValueError(
                "AgentBase Memory requires AGENTBASE_MEMORY_URL and AGENTBASE_MEMORY_API_KEY. "
                "Use SQLite fallback instead: SQLiteMemoryRepo()"
            )

        self._client = None  # Would be AgentBase Memory client

    def _ensure_client(self):
        """Ensure the AgentBase client is initialized."""
        # Placeholder - would initialize actual AgentBase Memory client
        # For now, this will fall back to SQLite
        raise NotImplementedError(
            "AgentBase Memory implementation requires AgentBase SDK. "
            "Please use SQLiteMemoryRepo() for now."
        )

    async def save_session(self, state: SalesCaseState) -> None:
        """Save session to AgentBase Memory."""
        self._ensure_client()

    async def load_session(self, session_id: str) -> Optional[SalesCaseState]:
        """Load session from AgentBase Memory."""
        self._ensure_client()

    async def save_profile(self, profile: SalespersonProfile) -> None:
        """Save profile to AgentBase Memory."""
        self._ensure_client()

    async def load_profile(self, salesperson_id: str) -> Optional[SalespersonProfile]:
        """Load profile from AgentBase Memory."""
        self._ensure_client()

    async def save_feedback_rule(self, rule: FeedbackRule) -> None:
        """Save feedback rule to AgentBase Memory."""
        self._ensure_client()

    async def load_feedback_rules(
        self,
        salesperson_id: str,
        active_only: bool = True
    ) -> list[FeedbackRule]:
        """Load feedback rules from AgentBase Memory."""
        self._ensure_client()

    async def delete_feedback_rule(self, rule_id: str) -> None:
        """Delete feedback rule from AgentBase Memory."""
        self._ensure_client()

    async def list_sessions(
        self,
        salesperson_id: Optional[str] = None,
        limit: int = 10
    ) -> list[dict[str, Any]]:
        """List recent sessions from AgentBase Memory."""
        self._ensure_client()


# =============================================================================
# Repository Factory
# =============================================================================

def create_memory_repo(use_agentbase: bool = False) -> MemoryRepo:
    """
    Create a memory repository based on configuration.

    Args:
        use_agentbase: If True, try to use AgentBase Memory.
                      Falls back to SQLite if not available.

    Returns:
        MemoryRepo implementation
    """
    if use_agentbase:
        try:
            return AgentBaseMemoryRepo()
        except ValueError:
            # AgentBase not configured, fall back to SQLite
            pass

    # Default to SQLite
    return SQLiteMemoryRepo()


# =============================================================================
# Checkpoint Saver for LangGraph
# =============================================================================

class SQLiteCheckpointSaver:
    """
    LangGraph CheckpointSaver implementation using SQLite.
    This enables LangGraph's state persistence and resumability.

    NOTE: The AgentBase version would use the AgentBase Memory bridge.
    """

    def __init__(self, repo: Optional[MemoryRepo] = None):
        """Initialize with a MemoryRepo."""
        self.repo = repo or SQLiteMemoryRepo()

    async def get(self, thread_id: str) -> Optional[dict[str, Any]]:
        """Get checkpoint for a thread."""
        state = await self.repo.load_session(thread_id)
        if state:
            return state.model_dump()
        return None

    async def put(self, thread_id: str, checkpoint: dict[str, Any]) -> None:
        """Save checkpoint for a thread."""
        state = SalesCaseState(**checkpoint)
        await self.repo.save_session(state)

    async def list(self, prefix: str = "") -> list[str]:
        """List thread IDs."""
        sessions = await self.repo.list_sessions(limit=100)
        return [s["session_id"] for s in sessions]


# =============================================================================
# Global Instances
# =============================================================================

# Default repo (SQLite fallback)
_default_repo: Optional[MemoryRepo] = None


def get_memory_repo() -> MemoryRepo:
    """Get the default memory repository."""
    global _default_repo
    if _default_repo is None:
        _default_repo = create_memory_repo(use_agentbase=False)
    return _default_repo


def set_memory_repo(repo: MemoryRepo) -> None:
    """Set the default memory repository."""
    global _default_repo
    _default_repo = repo