from __future__ import annotations

from typing import Optional

from kafka import KafkaProducer
from redis.asyncio import Redis

from ..api.db import get_session
from ..config import SessionConfig, SessionStoreType
from .base import SessionStoreBase
from .default import InMemorySessionStore
from .prod import ProdSessionStore


class SessionStoreFactory:
    @staticmethod
    async def create_store(config: Optional[SessionConfig] = None) -> SessionStoreBase:
        config = config or SessionConfig.from_env()
        if config.store_type == SessionStoreType.PRODUCTION:
            db = await get_session()
            redis = Redis.from_url(config.redis_url) if config.redis_url else None
            kafka_producer = (
                KafkaProducer(bootstrap_servers=config.kafka_brokers.split(","))
                if config.events_enabled and config.kafka_brokers
                else None
            )
            return ProdSessionStore(
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
    "ProdSessionStore",
    "SessionStoreBase",
]
