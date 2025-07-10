from __future__ import annotations

import pickle
from datetime import datetime, timezone
from typing import Optional

from kafka import KafkaProducer
from loguru import logger
from redis.asyncio import Redis
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from nomos.types import Session as AgentSession

from ..api.agent import agent
from ..core import Session
from ..events import (
    CompositeEventEmitter,
    DatabaseEventEmitter,
    KafkaEventEmitter,
)
from ..models.agent import State
from .base import SessionStoreBase
from .memory_store import InMemorySessionStore


class ProductionSessionStore(SessionStoreBase):
    """PostgreSQL + Redis backed session store."""

    def __init__(
        self,
        db: AsyncSession,
        redis: Optional[Redis] = None,
        cache_ttl: int = 3600,
        kafka_producer: Optional[KafkaProducer] = None,
        kafka_topic: str = "session_events",
    ) -> None:
        super().__init__()
        self.db = db
        self.redis = redis
        self.cache_ttl = cache_ttl
        self.memory_store = InMemorySessionStore()

        if kafka_producer:
            emitter = CompositeEventEmitter(
                KafkaEventEmitter(kafka_producer, kafka_topic),
                DatabaseEventEmitter(db),
            )
            self.set_event_emitter(emitter)

    async def get(self, session_id: str) -> Optional[AgentSession]:
        if self.redis:
            try:
                cached = await self.redis.get(f"session:{session_id}")
                if cached:
                    session = pickle.loads(cached)
                    if self.event_emitter:
                        session.set_event_emitter(self.event_emitter)
                    return session
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
                if self.event_emitter:
                    session.set_event_emitter(self.event_emitter)
                return session
        except Exception as e:
            logger.warning(f"DB error: {e}")
        session = await self.memory_store.get(session_id)
        if session and self.event_emitter:
            session.set_event_emitter(self.event_emitter)
        return session

    async def set(self, session_id: str, session: AgentSession, ttl: Optional[int] = None) -> bool:
        if self.event_emitter:
            session.set_event_emitter(self.event_emitter)
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
