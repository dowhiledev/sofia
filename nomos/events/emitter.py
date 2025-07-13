from __future__ import annotations

import asyncio
import json
from typing import Any, Iterable

from kafka import KafkaProducer
from loguru import logger
from sqlmodel.ext.asyncio.session import AsyncSession

from .models import SessionEvent, SessionEventModel


class KafkaEventEmitter:
    """Emit session events to a Kafka topic."""

    def __init__(self, producer: KafkaProducer, topic: str) -> None:
        self.producer = producer
        self.topic = topic

    async def emit(self, event: SessionEvent) -> None:
        loop = asyncio.get_running_loop()
        # Use mode="json" to properly serialize datetime and enums
        try:
            payload = json.dumps(event.model_dump(mode="json"), ensure_ascii=False).encode("utf-8")

            # Send to Kafka with proper error handling
            await loop.run_in_executor(None, self.producer.send, self.topic, payload)

            # Log successful emission
            logger.debug(
                f"Emitted event {event.event_type} for session {event.session_id} to Kafka topic {self.topic}"
            )

        except json.JSONDecodeError as exc:
            logger.error(f"JSON serialization error in Kafka emitter: {exc}")
        except Exception as exc:
            logger.warning(f"Kafka emitter error: {exc}")
            # Consider if you want to raise here or just log
            # For now, we'll just log to avoid breaking the main flow


class DatabaseEventEmitter:
    """Persist events to the database."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def emit(self, event: SessionEvent) -> None:
        try:
            model = SessionEventModel(
                session_id=event.session_id,
                event_type=event.event_type,
                data=event.data,
                decision=(
                    event.decision.model_dump(mode="json") if event.decision is not None else None
                ),
                timestamp=event.timestamp,
            )
            self.session.add(model)
            # Don't commit here - let the main transaction handle the commit
            # to avoid SQLAlchemy warnings about nested transactions during session operations
        except Exception as exc:
            logger.warning(f"Database emitter error: {exc}")
            try:
                await self.session.rollback()
            except Exception:
                pass


class CompositeEventEmitter:
    """Emit events to multiple emitters."""

    def __init__(self, *emitters: Any) -> None:
        self.emitters: Iterable[Any] = emitters

    async def emit(self, event: SessionEvent) -> None:
        for emitter in self.emitters:
            try:
                await emitter.emit(event)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"Emitter error: {exc}")
