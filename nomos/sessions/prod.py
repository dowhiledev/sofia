from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from kafka import KafkaProducer
from loguru import logger
from redis.asyncio import Redis
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from nomos.types import Session as AgentSession

from ..api.agent import agent
from ..events import (
    CompositeEventEmitter,
    DatabaseEventEmitter,
    KafkaEventEmitter,
)
from ..models.agent import State
from ..models.session import Session
from .base import SessionStoreBase
from .default import InMemorySessionStore


class ProdSessionStore(SessionStoreBase):
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
        # Try Redis first with JSON serialization
        if self.redis:
            try:
                cached = await self.redis.get(f"session:{session_id}")
                if cached:
                    # Handle both string and bytes from Redis
                    cached_str = cached.decode("utf-8") if isinstance(cached, bytes) else cached
                    state_dict = json.loads(cached_str)
                    state = State.model_validate(state_dict)
                    session = agent.get_session_from_state(state)
                    if self.event_emitter:
                        session.set_event_emitter(self.event_emitter)
                    logger.debug(f"Session {session_id} retrieved from Redis cache")
                    return session
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Redis retrieval error for session {session_id}: {e}")
                # Remove corrupted cache entry
                try:
                    await self.redis.delete(f"session:{session_id}")
                except Exception:
                    pass

        # Fallback to database
        try:
            stmt = select(Session).where(Session.session_id == session_id)
            result = await self.db.exec(stmt)
            model = result.first()
            if model:
                state = State.model_validate(model.session_data)
                session = agent.get_session_from_state(state)
                # Cache in Redis as JSON with proper error handling
                if self.redis:
                    try:
                        state_json = json.dumps(state.model_dump(mode="json"), ensure_ascii=False)
                        await self.redis.setex(f"session:{session_id}", self.cache_ttl, state_json)
                        logger.debug(f"Session {session_id} cached in Redis from database")
                    except Exception as e:
                        logger.warning(f"Redis caching error for session {session_id}: {e}")
                if self.event_emitter:
                    session.set_event_emitter(self.event_emitter)
                logger.debug(f"Session {session_id} retrieved from database")
                return session
        except Exception as e:
            logger.warning(f"Database retrieval error for session {session_id}: {e}")

        # Final fallback to memory store
        memory_session = await self.memory_store.get(session_id)
        if memory_session and self.event_emitter:
            memory_session.set_event_emitter(self.event_emitter)
        if memory_session:
            logger.debug(f"Session {session_id} retrieved from memory store")
        return memory_session

    async def set(self, session_id: str, session: AgentSession, ttl: Optional[int] = None) -> bool:
        if self.event_emitter:
            session.set_event_emitter(self.event_emitter)

        # Get session state and serialize it properly
        state = session.get_state()
        state_dict = state.model_dump(mode="json")

        # Store in database with proper transaction handling
        try:
            stmt = select(Session).where(Session.session_id == session_id)
            result = await self.db.exec(stmt)
            model = result.first()
            if model:
                model.session_data = state_dict
                model.updated_at = datetime.now(timezone.utc)
                self.db.add(model)
                logger.debug(f"Updated existing session {session_id} in database")
            else:
                model = Session(
                    session_id=session_id,
                    session_data=state_dict,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                self.db.add(model)
                logger.debug(f"Created new session {session_id} in database")

            # Commit the database transaction
            await self.db.commit()

        except Exception as e:
            logger.warning(f"Database error for session {session_id}: {e}")
            await self.db.rollback()

        # Cache in Redis as JSON with better error handling
        if self.redis:
            try:
                state_json = json.dumps(state_dict, ensure_ascii=False)
                await self.redis.setex(f"session:{session_id}", ttl or self.cache_ttl, state_json)
                logger.debug(f"Session {session_id} cached in Redis")
            except Exception as e:
                logger.warning(f"Redis caching error for session {session_id}: {e}")

        # Always update memory store as fallback
        await self.memory_store.set(session_id, session, ttl)
        return True

    async def delete(self, session_id: str) -> bool:
        # Delete from Redis
        if self.redis:
            try:
                result = await self.redis.delete(f"session:{session_id}")
                logger.debug(f"Deleted session {session_id} from Redis: {result}")
            except Exception as e:
                logger.warning(f"Redis deletion error for session {session_id}: {e}")

        # Delete from database
        try:
            stmt = select(Session).where(Session.session_id == session_id)
            result = await self.db.exec(stmt)
            model = result.first()
            if model:
                await self.db.delete(model)
                await self.db.commit()
                logger.debug(f"Deleted session {session_id} from database")
            else:
                logger.debug(f"Session {session_id} not found in database")
        except Exception as e:
            logger.warning(f"Database deletion error for session {session_id}: {e}")
            await self.db.rollback()

        # Always delete from memory store
        await self.memory_store.delete(session_id)
        return True

    async def close(self) -> None:
        """Close all connections and clean up resources."""
        # Close database connection
        try:
            await self.db.close()
            logger.debug("Database connection closed")
        except Exception as e:
            logger.warning(f"Error closing database connection: {e}")

        # Close Redis connection
        if self.redis:
            try:
                await self.redis.close()
                logger.debug("Redis connection closed")
            except Exception as e:
                logger.warning(f"Error closing Redis connection: {e}")

        # Close Kafka producer if it exists
        if hasattr(self, "event_emitter") and self.event_emitter:
            try:
                # Check if this is a CompositeEventEmitter
                if hasattr(self.event_emitter, "emitters"):
                    for emitter in self.event_emitter.emitters:
                        if hasattr(emitter, "producer"):
                            emitter.producer.close()
                            logger.debug("Kafka producer closed")
                elif hasattr(self.event_emitter, "producer"):
                    self.event_emitter.producer.close()
                    logger.debug("Kafka producer closed")
            except Exception as e:
                logger.warning(f"Error closing Kafka producer: {e}")

        # Close memory store
        try:
            await self.memory_store.close()
        except Exception as e:
            logger.warning(f"Error closing memory store: {e}")
