from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from nomos.types import Session as AgentSession


class SessionStoreBase(ABC):
    """Abstract interface for session stores."""

    def __init__(self) -> None:
        self.event_emitter = None

    def set_event_emitter(self, emitter: Any) -> None:
        """Attach an event emitter to the store."""
        self.event_emitter = emitter

    # CRUD operations
    @abstractmethod
    async def get(self, session_id: str) -> Optional[AgentSession]:
        """Retrieve a session by ID."""

    @abstractmethod
    async def set(self, session_id: str, session: AgentSession, ttl: Optional[int] = None) -> bool:
        """Store a session."""

    @abstractmethod
    async def delete(self, session_id: str) -> bool:
        """Delete a session."""

    # Optional helpers
    async def exists(self, session_id: str) -> bool:
        """Check if a session exists."""
        return await self.get(session_id) is not None

    async def list_sessions(self, limit: int = 100, offset: int = 0) -> List[str]:
        """List available session IDs."""
        return []

    async def cleanup_expired(self) -> int:
        """Clean up expired sessions."""
        return 0

    async def get_metrics(self) -> Dict[str, Any]:
        """Return store metrics."""
        return {}

    async def close(self) -> None:
        """Close any open resources."""
        return None
