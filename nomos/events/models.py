from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel
from sqlalchemy import JSON, Column, DateTime
from sqlmodel import Field, SQLModel


class SessionEvent(BaseModel):
    """Runtime event emitted during a session."""

    session_id: str
    event_type: str
    data: Dict[str, Any] = {}
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SessionEventModel(SQLModel, table=True):  # type: ignore
    """Database table for session events."""

    __tablename__ = "session_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str
    event_type: str
    data: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
