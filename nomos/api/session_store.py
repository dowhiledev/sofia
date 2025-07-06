"""Session store for managing session data in PostgreSQL and Redis."""

import os
import pickle
from datetime import datetime, timezone
from typing import Dict, Optional

from loguru import logger
from redis.asyncio import Redis
from sqlalchemy import Column, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from nomos.types import Session as AgentSession

from ..models.agent import State
from .agent import agent


class Session(SQLModel, table=True):  # type: ignore
    """
    SQLAlchemy model for storing session data in PostgreSQL.

    This model is used to persist session data in a relational database.
    """

    __tablename__ = "sessions"

    session_id: str = Field(primary_key=True)
    session_data: dict = Field(default=dict, sa_type=JSONB)
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), default=func.now(), nullable=False)
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            default=func.now(),
            onupdate=func.now(),
            nullable=False,
        )
    )


class InMemoryStore:
    """
    In-memory store for session data.

    This is a simple dictionary-based store that does not persist data.
    It is used as a fallback when Redis or database connections are not available.
    """

    def __init__(self) -> None:
        """
        Initialize an in-memory store for session data.

        This is a simple dictionary-based store that does not persist data.
        """
        self._store: Dict[str, tuple[AgentSession, datetime]] = {}

    async def get(self, key: str) -> Optional[AgentSession]:
        """Get session from in-memory store."""
        if key in self._store:
            return self._store[key][0]
        return None

    async def set(self, key: str, value: AgentSession, ttl: Optional[int] = None) -> None:
        """Set session in in-memory store."""
        self._store[key] = (value, datetime.now(timezone.utc))

    async def delete(self, key: str) -> None:
        """Delete session from in-memory store."""
        self._store.pop(key, None)


class SessionStore:
    """
    Session store for managing session data.

    This class provides methods to get, set, and delete session data
    from a PostgreSQL database and/or Redis cache.
    It uses an in-memory store as a fallback when Redis or database connections are not available.
    """

    def __init__(
        self,
        db: Optional[AsyncSession] = None,
        redis: Optional[Redis] = None,
        cache_ttl: int = 3600,
    ) -> None:
        """
        Initialize the session store with optional database and Redis connections.

        :param db: Optional SQLAlchemy AsyncSession for database operations.
        :param redis: Optional Redis client for caching.
        :param cache_ttl: Time-to-live for cache entries in seconds.
        """
        self.db = db
        self.redis = redis
        self.cache_ttl = cache_ttl
        self.memory_store = InMemoryStore()

        # Log storage configuration
        logger.info(
            f"Session store initialized with: "
            f"DB={'PostgreSQL' if db else 'Memory'}, "
            f"Cache={'Redis' if redis else 'Memory'}"
        )

    async def _get_from_cache(self, session_id: str) -> Optional[AgentSession]:
        """Get session from cache (Redis or memory)."""
        if self.redis:
            try:
                cached = await self.redis.get(f"session:{session_id}")
                if cached:
                    return pickle.loads(cached)
            except Exception as e:
                logger.warning(f"Redis error: {e}. Falling back to memory cache.")

        return await self.memory_store.get(session_id)

    async def _set_to_cache(self, session_id: str, session: AgentSession) -> None:
        """Set session in cache (Redis or memory)."""
        if self.redis:
            try:
                await self.redis.setex(
                    f"session:{session_id}", self.cache_ttl, pickle.dumps(session)
                )
                return
            except Exception as e:
                logger.warning(f"Redis error: {e}. Falling back to memory cache.")

        await self.memory_store.set(session_id, session)

    async def _delete_from_cache(self, session_id: str) -> None:
        """Delete session from cache (Redis or memory)."""
        if self.redis:
            try:
                await self.redis.delete(f"session:{session_id}")
                return
            except Exception as e:
                logger.warning(f"Redis error: {e}. Falling back to memory cache.")

        await self.memory_store.delete(session_id)

    async def _update_db(self, session_id: str, session: AgentSession) -> None:
        """Update existing session in database or create new one."""
        if not self.db:
            return

        try:
            # Check if session exists
            stmt = select(Session).where(Session.session_id == session_id)
            result = await self.db.exec(stmt)
            existing_session = result.first()

            session_data = session.get_state().model_dump(mode="json")

            if existing_session:
                # Update existing session
                existing_session.session_data = session_data
                self.db.add(existing_session)
            else:
                # Create new session
                session_model = Session(session_id=session_id, session_data=session_data)
                self.db.add(session_model)

            await self.db.commit()

        except Exception as e:
            logger.warning(f"Database error: {e}. Using memory store only.")
            # Rollback the transaction on error
            await self.db.rollback()

    async def get(self, session_id: str) -> Optional[AgentSession]:
        """Get session from cache or database."""
        # Try cache first
        session = await self._get_from_cache(session_id)
        if session:
            return session

        # Try database if available
        if self.db:
            try:
                stmt = select(Session).where(Session.session_id == session_id)
                result = await self.db.exec(stmt)
                session_model = result.first()

                if session_model:
                    session_data = State.model_validate(session_model.session_data)
                    session = agent.get_session_from_state(session_data)
                    assert session is not None, "Session should not be None"
                    await self._set_to_cache(session_id, session)
                    return session
            except Exception as e:
                logger.warning(f"Database error: {e}. Falling back to memory store.")

        return None

    async def set(self, session_id: str, session: AgentSession) -> None:
        """Set or update session in both database and cache."""
        # Update database if available
        if self.db:
            await self._update_db(session_id, session)

        # Update cache
        await self._set_to_cache(session_id, session)

    async def delete(self, session_id: str) -> None:
        """Delete session from both database and cache."""
        # Delete from database if available
        if self.db:
            try:
                stmt = select(Session).where(Session.session_id == session_id)
                result = await self.db.exec(stmt)
                session_model = result.first()

                if session_model:
                    await self.db.delete(session_model)
                    await self.db.commit()
            except Exception as e:
                logger.warning(f"Database error: {e}")

        # Delete from cache
        await self._delete_from_cache(session_id)

    async def close(self) -> None:
        """Close database and Redis connections."""
        if self.db:
            await self.db.close()
        if self.redis:
            await self.redis.close()


# Initialize session store based on environment
async def create_session_store() -> SessionStore:
    """
    Create a session store based on the environment.

    This function initializes the session store with a database connection,
    a Redis connection, or an in-memory store based on the availability of
    the respective services.

    :return: An instance of SessionStore.
    """
    db_session = None
    redis_client = None

    # Try to initialize database connection
    if os.getenv("DATABASE_URL"):
        try:
            from .db import get_session

            db_session = await get_session()
        except Exception as e:
            logger.warning(f"Failed to initialize database: {e}")

    # Try to initialize Redis connection
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        try:
            redis_client = Redis.from_url(redis_url)
        except Exception as e:
            logger.warning(f"Failed to initialize Redis: {e}")

    return SessionStore(db=db_session, redis=redis_client)


__all__ = ["create_session_store", "SessionStore", "Session"]
