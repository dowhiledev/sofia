from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from nomos.types import Session as AgentSession

from .base import SessionStoreBase


class InMemorySessionStore(SessionStoreBase):
    """Simple dictionary based session store with optional TTL."""

    def __init__(self, default_ttl: int = 3600) -> None:
        super().__init__()
        self.default_ttl = default_ttl
        self._store: Dict[str, Tuple[AgentSession, datetime, Optional[int]]] = {}
        self._lock = asyncio.Lock()

    async def get(self, session_id: str) -> Optional[AgentSession]:
        async with self._lock:
            item = self._store.get(session_id)
            if not item:
                return None
            session, created, ttl = item
            if ttl is not None:
                expires = created.timestamp() + ttl
                if datetime.now(timezone.utc).timestamp() > expires:
                    await self.delete(session_id)
                    return None
            if self.event_emitter:
                session.set_event_emitter(self.event_emitter)
            return session

    async def set(self, session_id: str, session: AgentSession, ttl: Optional[int] = None) -> bool:
        if self.event_emitter:
            session.set_event_emitter(self.event_emitter)
        async with self._lock:
            self._store[session_id] = (
                session,
                datetime.now(timezone.utc),
                ttl or self.default_ttl,
            )
            return True

    async def delete(self, session_id: str) -> bool:
        async with self._lock:
            existed = session_id in self._store
            self._store.pop(session_id, None)
            return existed

    async def list_sessions(self, limit: int = 100, offset: int = 0):
        async with self._lock:
            return list(self._store.keys())[offset : offset + limit]
