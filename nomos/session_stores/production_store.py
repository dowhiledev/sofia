from __future__ import annotations

import pickle
from datetime import datetime, timezone
from typing import Optional

from loguru import logger
from redis.asyncio import Redis
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from nomos.types import Session as AgentSession

from ..api.agent import agent
from ..api.session_store import Session
from ..models.agent import State
from .base import SessionStoreBase
from .memory_store import InMemorySessionStore


class ProductionSessionStore(SessionStoreBase):
    """PostgreSQL + Redis backed session store."""

    def __init__(
        self, db: AsyncSession, redis: Optional[Redis] = None, cache_ttl: int = 3600
    ) -> None:
        super().__init__()
        self.db = db
        self.redis = redis
        self.cache_ttl = cache_ttl
        self.memory_store = InMemorySessionStore()

    async def get(self, session_id: str) -> Optional[AgentSession]:
        if self.redis:
            try:
                cached = await self.redis.get(f"session:{session_id}")
                if cached:
                    return pickle.loads(cached)
            except Exception as e:
                logger.warning(f"Redis error: {e}")
        try:
            stmt = select(Session).where(Session.session_id == session_id)
            result = await self.db.exec(stmt)
            model = result.first()
            if model:
                state = State.model_validate(model.session_data)
                session = agent.get_session_from_state(state)
                if self.redis:
                    try:
                        await self.redis.setex(
                            f"session:{session_id}", self.cache_ttl, pickle.dumps(session)
                        )
                    except Exception as e:
                        logger.warning(f"Redis error: {e}")
                return session
        except Exception as e:
            logger.warning(f"DB error: {e}")
        return await self.memory_store.get(session_id)

    async def set(self, session_id: str, session: AgentSession, ttl: Optional[int] = None) -> bool:
        try:
            stmt = select(Session).where(Session.session_id == session_id)
            result = await self.db.exec(stmt)
            model = result.first()
            if model:
                model.session_data = session.get_state().model_dump(mode="json")
                self.db.add(model)
            else:
                model = Session(
                    session_id=session_id,
                    session_data=session.get_state().model_dump(mode="json"),
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                self.db.add(model)
            await self.db.commit()
        except Exception as e:
            logger.warning(f"DB error: {e}")
            await self.db.rollback()
        if self.redis:
            try:
                await self.redis.setex(
                    f"session:{session_id}", ttl or self.cache_ttl, pickle.dumps(session)
                )
            except Exception as e:
                logger.warning(f"Redis error: {e}")
        await self.memory_store.set(session_id, session, ttl)
        return True

    async def delete(self, session_id: str) -> bool:
        if self.redis:
            try:
                await self.redis.delete(f"session:{session_id}")
            except Exception as e:
                logger.warning(f"Redis error: {e}")
        try:
            stmt = select(Session).where(Session.session_id == session_id)
            result = await self.db.exec(stmt)
            model = result.first()
            if model:
                await self.db.delete(model)
                await self.db.commit()
        except Exception as e:
            logger.warning(f"DB error: {e}")
        await self.memory_store.delete(session_id)
        return True

    async def close(self) -> None:
        await self.db.close()
        if self.redis:
            await self.redis.close()
