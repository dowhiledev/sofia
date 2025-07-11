from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel
from sqlalchemy import JSON, Column, DateTime
from sqlmodel import Field, SQLModel

from ..models.agent import Decision


class SessionEvent(BaseModel):
    """Runtime event emitted during a session."""

    session_id: str
    event_type: str
    data: Dict[str, Any] = {}
    decision: Optional[Decision] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SessionEventModel(SQLModel, table=True):  # type: ignore
    """Database table for session events."""

    __tablename__ = "session_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str
    event_type: str
    data: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    decision: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON, nullable=True))
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
