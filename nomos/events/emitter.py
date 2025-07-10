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
        payload = json.dumps(event.model_dump()).encode()
        try:
            await loop.run_in_executor(None, self.producer.send, self.topic, payload)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Kafka emitter error: {exc}")


class DatabaseEventEmitter:
    """Persist events to the database."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def emit(self, event: SessionEvent) -> None:
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
        try:
            await self.session.commit()
        except Exception as exc:  # noqa: BLE001
            await self.session.rollback()
            logger.warning(f"DB emitter error: {exc}")


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
