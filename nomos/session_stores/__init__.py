from __future__ import annotations

from typing import Optional

from redis.asyncio import Redis

from ..api.db import get_session
from ..config.session_config import SessionConfig, SessionStoreType
from .base import SessionStoreBase
from .memory_store import InMemorySessionStore
from .production_store import ProductionSessionStore


class SessionStoreFactory:
    @staticmethod
    async def create_store(config: Optional[SessionConfig] = None) -> SessionStoreBase:
        config = config or SessionConfig.from_env()
        if config.store_type == SessionStoreType.PRODUCTION:
            db = await get_session()
            redis = None
            if config.redis_url:
                redis = Redis.from_url(config.redis_url)
            return ProductionSessionStore(db=db, redis=redis, cache_ttl=config.cache_ttl)
        return InMemorySessionStore(default_ttl=config.default_ttl)


__all__ = [
    "SessionStoreFactory",
    "InMemorySessionStore",
    "ProductionSessionStore",
    "SessionStoreBase",
]
