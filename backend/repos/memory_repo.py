"""
Memory Repository
=================
Repository interface for agent memory. SQLite-backed (data/sales_assistant.db) —
this project deploys to its own VPS via docker-compose, not AgentBase Runtime.
"""

import asyncio
import os
import json
from typing import Optional, Any
from datetime import datetime
from abc import ABC, abstractmethod

from dotenv import load_dotenv

load_dotenv()

from schemas.state import (
    SalesCaseState,
    SalespersonProfile,
    FeedbackRule,
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
        self, salesperson_id: str, active_only: bool = True
    ) -> list[FeedbackRule]:
        """Load feedback rules for a salesperson."""
        pass

    @abstractmethod
    async def delete_feedback_rule(self, rule_id: str) -> None:
        """Delete a feedback rule."""
        pass

    @abstractmethod
    async def list_sessions(
        self, salesperson_id: Optional[str] = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        """List recent sessions."""
        pass

    @abstractmethod
    async def delete_session(self, session_id: str) -> None:
        """Delete a session and its persisted state."""
        pass

    async def vacuum(self) -> None:
        """Reclaim space freed by deletes. No-op unless the backend needs it.

        Separate from delete_session because clearing a whole history calls that
        once per conversation, and compacting the file after each one would do the
        same work thirty times over.
        """
        return None


# =============================================================================
# SQLite Implementation (Local Fallback)
# =============================================================================


class SQLiteMemoryRepo(MemoryRepo):
    """SQLite implementation of MemoryRepo."""

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize SQLite memory repository.

        Args:
            db_path: Path to SQLite database file. Defaults to ./data/sales_assistant.db
        """
        self.db_path = db_path or os.getenv(
            "SQLITE_DB_PATH", "./data/sales_assistant.db"
        )
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

        _, profile_json, created_at, updated_at = row
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
        # Update timestamps
        state.updated_at = datetime.now()

        # Convert to JSON
        state_json = state.model_dump_json()

        # In a thread: this is the largest write of the turn — the whole state,
        # every skill output included — and it runs at the end of a streaming
        # response, where blocking the event loop delays the `done` event for
        # every session on the box, not just this one.
        await asyncio.to_thread(
            self._write_session_row,
            state.session_id,
            state.salesperson_id,
            state_json,
            state.created_at.isoformat(),
            state.updated_at.isoformat(),
        )

    def _write_session_row(
        self,
        session_id: str,
        salesperson_id: str,
        state_json: str,
        created_at: str,
        updated_at: str,
    ) -> None:
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO sessions
            (session_id, salesperson_id, state_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """,
            (session_id, salesperson_id, state_json, created_at, updated_at),
        )

        conn.commit()
        conn.close()

    async def load_session(self, session_id: str) -> Optional[SalesCaseState]:
        """Load session from SQLite."""
        import sqlite3

        def _work() -> Optional[tuple]:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT session_id, salesperson_id, state_json, created_at, updated_at
                FROM sessions
                WHERE session_id = ?
            """,
                (session_id,),
            )
            row = cursor.fetchone()
            conn.close()
            return row

        row = await asyncio.to_thread(_work)
        return self._row_to_state(row)

    async def save_profile(self, profile: SalespersonProfile) -> None:
        """Save profile to SQLite."""
        import sqlite3

        profile.updated_at = datetime.now()
        profile_json = profile.model_dump_json()

        def _work() -> None:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """
                INSERT OR REPLACE INTO profiles
                (salesperson_id, profile_json, created_at, updated_at)
                VALUES (?, ?, ?, ?)
            """,
                (
                    profile.salesperson_id,
                    profile_json,
                    profile.created_at.isoformat(),
                    profile.updated_at.isoformat(),
                ),
            )
            conn.commit()
            conn.close()

        await asyncio.to_thread(_work)

    async def load_profile(self, salesperson_id: str) -> Optional[SalespersonProfile]:
        """Load profile from SQLite."""
        import sqlite3

        def _work() -> Optional[tuple]:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT salesperson_id, profile_json, created_at, updated_at
                FROM profiles
                WHERE salesperson_id = ?
            """,
                (salesperson_id,),
            )
            row = cursor.fetchone()
            conn.close()
            return row

        row = await asyncio.to_thread(_work)
        return self._row_to_profile(row)

    async def save_feedback_rule(self, rule: FeedbackRule) -> None:
        """Save feedback rule to SQLite."""
        import sqlite3

        rule_json = rule.model_dump_json()

        def _work() -> None:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """
                INSERT OR REPLACE INTO feedback_rules
                (rule_id, salesperson_id, rule_json, created_at, active)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    rule.rule_id,
                    rule.salesperson_id,
                    rule_json,
                    rule.created_at.isoformat(),
                    1 if rule.active else 0,
                ),
            )
            conn.commit()
            conn.close()

        await asyncio.to_thread(_work)

    async def load_feedback_rules(
        self, salesperson_id: str, active_only: bool = True
    ) -> list[FeedbackRule]:
        """Load feedback rules from SQLite. Called on every turn (main.py's
        feedback-constraint check), so this is the highest-traffic method in
        the class — off the loop, and each row parsed only once."""
        import sqlite3

        def _work() -> list[tuple]:
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
            return rows

        rows = await asyncio.to_thread(_work)
        # Each row was parsed (json.loads + pydantic construct) twice here —
        # once to filter, once to build the list.
        return [r for row in rows if (r := self._row_to_rule(row))]

    async def delete_feedback_rule(self, rule_id: str) -> None:
        """Delete feedback rule from SQLite."""
        import sqlite3

        def _work() -> None:
            conn = sqlite3.connect(self.db_path)
            conn.execute("DELETE FROM feedback_rules WHERE rule_id = ?", (rule_id,))
            conn.commit()
            conn.close()

        await asyncio.to_thread(_work)

    async def delete_session(self, session_id: str) -> None:
        """Delete a session's state row from SQLite.

        This is the row that carries the whole serialised SalesCaseState — skill
        outputs included — so it is much larger than the transcript row in
        app.db and is the one worth reclaiming.
        """
        import sqlite3

        def _delete() -> None:
            conn = sqlite3.connect(self.db_path)
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            conn.commit()
            conn.close()

        await asyncio.to_thread(_delete)

    async def vacuum(self) -> None:
        """Compact sales_assistant.db. A DELETE alone does not shrink the file."""
        import sqlite3

        def _vacuum() -> None:
            conn = sqlite3.connect(self.db_path, isolation_level=None)
            try:
                conn.execute("VACUUM")
            except Exception as e:
                print(f"[memory_repo] VACUUM skipped: {e}")
            finally:
                conn.close()

        await asyncio.to_thread(_vacuum)

    async def list_sessions(
        self, salesperson_id: Optional[str] = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        """List recent sessions from SQLite."""
        import sqlite3

        def _work() -> list[tuple]:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            if salesperson_id:
                cursor.execute(
                    """
                    SELECT session_id, salesperson_id, state_json, created_at, updated_at
                    FROM sessions
                    WHERE salesperson_id = ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                """,
                    (salesperson_id, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT session_id, salesperson_id, state_json, created_at, updated_at
                    FROM sessions
                    ORDER BY updated_at DESC
                    LIMIT ?
                """,
                    (limit,),
                )
            rows = cursor.fetchall()
            conn.close()
            return rows

        rows = await asyncio.to_thread(_work)

        result = []
        for row in rows:
            session_id, salesperson_id, state_json, created_at, updated_at = row
            state = json.loads(state_json)
            result.append(
                {
                    "session_id": session_id,
                    "salesperson_id": salesperson_id,
                    "mode": state.get("mode", "chat"),
                    "summary": state.get("summary", ""),
                    "created_at": created_at,
                    "updated_at": updated_at,
                }
            )

        return result


# =============================================================================
# Repository Factory
# =============================================================================


def create_memory_repo() -> MemoryRepo:
    """Create the memory repository. SQLite only — this project runs on its own
    VPS (see CLAUDE.md's Deployment section), not AgentBase Runtime."""
    return SQLiteMemoryRepo()


# =============================================================================
# Checkpoint Saver for LangGraph
# =============================================================================


class SQLiteCheckpointSaver:
    """
    LangGraph CheckpointSaver implementation using SQLite.
    This enables LangGraph's state persistence and resumability.
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

# Default repo instance
_default_repo: Optional[MemoryRepo] = None


def get_memory_repo() -> MemoryRepo:
    """Get the default memory repository."""
    global _default_repo
    if _default_repo is None:
        _default_repo = create_memory_repo()
    return _default_repo


def set_memory_repo(repo: MemoryRepo) -> None:
    """Set the default memory repository."""
    global _default_repo
    _default_repo = repo
