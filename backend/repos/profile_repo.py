"""
Profile Repository (ProfileRepo)
=================================
Repository interface for salesperson profiles.
Dual implementation: SQLite (local fallback) / AgentBase (primary).

This enables personalization and learning from user feedback.
"""

from typing import Optional
from abc import ABC, abstractmethod

from schemas.state import SalespersonProfile


class ProfileRepo(ABC):
    """
    Abstract interface for profile operations.
    Implement this to add new profile storage backends.
    """

    @abstractmethod
    async def save(self, profile: SalespersonProfile) -> None:
        """Save a salesperson profile."""
        pass

    @abstractmethod
    async def get(self, salesperson_id: str) -> Optional[SalespersonProfile]:
        """Load a salesperson profile by ID."""
        pass

    @abstractmethod
    async def delete(self, salesperson_id: str) -> None:
        """Delete a profile."""
        pass

    @abstractmethod
    async def list_all(self) -> list[SalespersonProfile]:
        """List all profiles."""
        pass


class SQLiteProfileRepo(ProfileRepo):
    """
    SQLite implementation of ProfileRepo.
    Uses the same database as SQLiteMemoryRepo for consistency.
    """

    def __init__(self, db_path: Optional[str] = None):
        """Initialize with database path."""
        import os
        from dotenv import load_dotenv
        load_dotenv()

        self.db_path = db_path or os.getenv("SQLITE_DB_PATH", "./data/sales_assistant.db")
        self._ensure_db_dir()

    def _ensure_db_dir(self):
        """Ensure the database directory exists."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

    async def save(self, profile: SalespersonProfile) -> None:
        """Save profile to SQLite (delegates to MemoryRepo)."""
        from repos.memory_repo import get_memory_repo
        repo = get_memory_repo()
        await repo.save_profile(profile)

    async def get(self, salesperson_id: str) -> Optional[SalespersonProfile]:
        """Load profile from SQLite (delegates to MemoryRepo)."""
        from repos.memory_repo import get_memory_repo
        repo = get_memory_repo()
        return await repo.load_profile(salesperson_id)

    async def delete(self, salesperson_id: str) -> None:
        """Delete profile from SQLite."""
        # For now, just mark as deleted by setting a flag or removing
        # Full implementation would delete from the profiles table
        pass

    async def list_all(self) -> list[SalespersonProfile]:
        """List all profiles."""
        # Query all profiles from sessions that have profiles
        # For now, return empty list
        return []


class AgentBaseProfileRepo(ProfileRepo):
    """
    AgentBase managed profile storage.
    NOTE: This is a placeholder until AgentBase credentials are available.
    """

    def __init__(self):
        raise NotImplementedError(
            "AgentBase Profile implementation requires AgentBase credentials. "
            "Use SQLiteProfileRepo() for local development."
        )


def create_profile_repo(use_agentbase: bool = False) -> ProfileRepo:
    """
    Create a profile repository based on configuration.

    Args:
        use_agentbase: If True, try to use AgentBase Profile.
                      Falls back to SQLite if not available.

    Returns:
        ProfileRepo implementation
    """
    if use_agentbase:
        try:
            return AgentBaseProfileRepo()
        except NotImplementedError:
            pass

    # Default to SQLite
    return SQLiteProfileRepo()


# Default instance
_default_profile_repo: Optional[ProfileRepo] = None


def get_profile_repo() -> ProfileRepo:
    """Get the default profile repository."""
    global _default_profile_repo
    if _default_profile_repo is None:
        _default_profile_repo = create_profile_repo(use_agentbase=False)
    return _default_profile_repo


def set_profile_repo(repo: ProfileRepo) -> None:
    """Set the default profile repository."""
    global _default_profile_repo
    _default_profile_repo = repo