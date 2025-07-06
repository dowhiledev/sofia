"""Models for the API requests and responses."""

from typing import Optional

from pydantic import BaseModel

from nomos.models.agent import State


class Message(BaseModel):
    """Model for incoming messages."""

    content: str


class SessionResponse(BaseModel):
    """Response model for session creation."""

    session_id: str
    message: dict


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    user_input: Optional[str] = None
    session_data: Optional[State] = None


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""

    response: dict
    tool_output: Optional[str] = None
    session_data: State
