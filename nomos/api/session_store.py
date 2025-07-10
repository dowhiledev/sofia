"""Compatibility layer for session stores used by the API."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Column, DateTime, func
from sqlmodel import Field, SQLModel

from nomos.types import Session as AgentSession

from ..config.session_config import SessionConfig
from ..session_stores import SessionStoreBase, SessionStoreFactory


class Session(SQLModel, table=True):  # type: ignore
    """Database model for persisting sessions."""

    __tablename__ = "sessions"

    session_id: str = Field(primary_key=True)
    session_data: dict = Field(default=dict)
    created_at: Optional[str] = Field(
        sa_column=Column(DateTime(timezone=True), default=func.now(), nullable=False)
    )
    updated_at: Optional[str] = Field(
        sa_column=Column(
            DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
        )
    )


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


async def create_session_store() -> SessionStore:
    """Create a session store based on environment configuration."""
    store = await SessionStoreFactory.create_store(SessionConfig.from_env())
    return SessionStore(store)


__all__ = ["create_session_store", "SessionStore", "Session"]
