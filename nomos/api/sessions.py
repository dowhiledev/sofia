"""Compatibility layer for session stores used by the API."""

from __future__ import annotations

from typing import Optional

from nomos.types import Session as AgentSession

from ..config import SessionConfig
from ..models.session import Session
from ..sessions import SessionStoreBase, SessionStoreFactory


class SessionStore(SessionStoreBase):
    """Thin wrapper around the new session store implementations."""

    def __init__(self, store: SessionStoreBase) -> None:
        super().__init__()
        self._store = store

    async def get(self, session_id: str) -> Optional[AgentSession]:
        return await self._store.get(session_id)

    async def set(self, session_id: str, session: AgentSession, ttl: Optional[int] = None) -> bool:
        return await self._store.set(session_id, session, ttl)

    async def delete(self, session_id: str) -> bool:
        return await self._store.delete(session_id)

    async def close(self) -> None:
        await self._store.close()


async def create_session_store(config: Optional[SessionConfig] = None) -> SessionStore:
    """Create a session store based on configuration or environment variables."""
    store = await SessionStoreFactory.create_store(config or SessionConfig.from_env())
    return SessionStore(store)


__all__ = ["create_session_store", "SessionStore", "Session"]
