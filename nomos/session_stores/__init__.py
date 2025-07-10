from __future__ import annotations

from typing import Optional

from kafka import KafkaProducer
from redis.asyncio import Redis

from ..api.db import get_session
from ..config import SessionConfig, SessionStoreType
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
            kafka_producer = None
            if config.events_enabled and config.kafka_brokers:
                kafka_producer = KafkaProducer(bootstrap_servers=config.kafka_brokers.split(","))
            return ProductionSessionStore(
                db=db,
                redis=redis,
                cache_ttl=config.cache_ttl,
                kafka_producer=kafka_producer,
                kafka_topic=config.kafka_topic,
            )
        return InMemorySessionStore(default_ttl=config.default_ttl)


__all__ = [
    "SessionStoreFactory",
    "InMemorySessionStore",
    "ProductionSessionStore",
    "SessionStoreBase",
]
