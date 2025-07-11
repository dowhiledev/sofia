"""Database models for session persistence."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import JSON, Column, DateTime, func
from sqlmodel import Field, SQLModel


class Session(SQLModel, table=True):  # type: ignore
    """Database model for persisting sessions."""

    __tablename__ = "sessions"

    session_id: str = Field(primary_key=True)
    session_data: dict = Field(default=dict, sa_column=Column(JSON))
    created_at: Optional[str] = Field(
        sa_column=Column(DateTime(timezone=True), default=func.now(), nullable=False)
    )
    updated_at: Optional[str] = Field(
        sa_column=Column(
            DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
        )
    )
