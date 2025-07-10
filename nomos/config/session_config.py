from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class SessionStoreType(str, Enum):
    MEMORY = "memory"
    PRODUCTION = "production"


class SessionConfig(BaseModel):
    store_type: SessionStoreType = SessionStoreType.MEMORY
    default_ttl: int = Field(3600, description="Default session TTL")
    cache_ttl: int = Field(3600, description="Cache TTL for production store")
    database_url: Optional[str] = None
    redis_url: Optional[str] = None
    kafka_brokers: Optional[str] = None
    kafka_topic: str = "session_events"
    events_enabled: bool = False

    @classmethod
    def from_env(cls) -> "SessionConfig":
        import os

        return cls(
            store_type=SessionStoreType(os.getenv("SESSION_STORE", "memory")),
            default_ttl=int(os.getenv("SESSION_DEFAULT_TTL", "3600")),
            cache_ttl=int(os.getenv("SESSION_CACHE_TTL", "3600")),
            database_url=os.getenv("DATABASE_URL"),
            redis_url=os.getenv("REDIS_URL"),
            kafka_brokers=os.getenv("KAFKA_BROKERS"),
            kafka_topic=os.getenv("KAFKA_TOPIC", "session_events"),
            events_enabled=os.getenv("SESSION_EVENTS", "false").lower() == "true",
        )
