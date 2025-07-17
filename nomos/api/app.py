"""Nomos Agent API."""

import pathlib
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import redis.asyncio as redis
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

from ..models.agent import Event, StepIdentifier, Summary
from .agent import agent, config
from .db import init_db
from .models import ChatRequest, ChatResponse, Message, SessionResponse
from .security import (
    SecurityManager,
    setup_security_middleware,
)
from .sessions import SessionStore, create_session_store

session_store: Optional[SessionStore] = None
security_manager: Optional[SecurityManager] = None

BASE_DIR = pathlib.Path(__file__).parent.absolute()

deps = (
    [
        Depends(
            RateLimiter(
                times=config.server.security.rate_limit_times or 50,
                seconds=config.server.security.rate_limit_seconds or 60,
            )
        )
    ]
    if config.server.security.enable_rate_limiting
    else []
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for FastAPI app."""
    global session_store, security_manager
    # Initialize database
    await init_db()
    session_store = await create_session_store(config.server.session)
    assert session_store is not None, "Session store initialization failed"

    # Initialize security manager
    security_manager = SecurityManager(config.server.security)
    # Setup FastAPI Limiter if rate limiting is enabled
    redis_client: Optional[redis.Redis] = None
    if config.server.security.enable_rate_limiting:
        redis_url = config.server.security.redis_url
        assert redis_url, "Redis URL must be provided for rate limiting"
        redis_client = redis.from_url(redis_url, encoding="utf-8", decode_responses=True)
        await FastAPILimiter.init(redis_client)

    yield

    # Cleanup
    await session_store.close()
    if security_manager:
        await security_manager.close()
    if redis_client:
        await FastAPILimiter.close()


app = FastAPI(title=f"{config.name}-api", lifespan=lifespan)
setup_security_middleware(app, config.server.security)
app.mount("/static", StaticFiles(directory=str(BASE_DIR)), name="static")


async def authenticate_request(request: Request) -> Dict[str, Any]:
    """Authenticate a request manually."""
    if not config.server.security.enable_auth or security_manager is None:
        return {"authenticated": False}

    authorization = request.headers.get("authorization")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.replace("Bearer ", "", 1).strip()
    try:
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        return await security_manager.authenticate(credentials)
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


# Serve chat UI at root
@app.get("/", response_class=HTMLResponse)
async def get_chat_ui() -> HTMLResponse:
    """Serve the chat UI HTML file."""
    chat_ui_path = BASE_DIR / "static" / "index.html"
    if not chat_ui_path.exists():
        raise HTTPException(status_code=404, detail="Chat UI file not found")

    with open(chat_ui_path, "r") as f:
        return HTMLResponse(content=f.read())


# Health check endpoint (no authentication required)
@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": time.time()}


# Generate JWT token endpoint (for testing purposes only - should be disabled in production)
if (
    config.server.security.enable_token_endpoint
    and config.server.security.enable_auth
    and config.server.security.auth_type == "jwt"
):

    @app.post("/auth/token")
    async def generate_token(payload: dict, request: Request) -> dict:
        """Generate a JWT token for testing purposes ONLY.

        WARNING: This endpoint should be disabled in production environments.
        It's only intended for development and testing.
        """
        from .security import generate_jwt_token

        assert config.server.security.jwt_secret_key is not None
        token = generate_jwt_token(payload, config.server.security.jwt_secret_key)
        return {"access_token": token, "token_type": "bearer"}


@app.post("/session", response_model=SessionResponse, dependencies=deps)
async def create_session(
    request: Request,
    initiate: Optional[bool] = False,
) -> SessionResponse:
    """Create a new session."""
    # Handle authentication
    await authenticate_request(request)

    assert session_store is not None, "Session store not initialized"
    session = agent.create_session()
    session_id = session.session_id  # Use the session's internal ID
    await session_store.set(session_id, session)
    # Get initial message from agent
    if initiate:
        res = session.next(None)
        await session_store.set(session_id, session)
    return SessionResponse(
        session_id=session_id,
        message=(
            res.decision.model_dump(mode="json")
            if initiate
            else {"status": "Session created successfully"}
        ),
    )


@app.post("/session/{id}/message", response_model=SessionResponse, dependencies=deps)
async def send_message(
    id: str,
    message: Message,
    request: Request,
) -> SessionResponse:
    """Send a message to an existing session."""
    # Handle authentication
    await authenticate_request(request)

    assert session_store is not None, "Session store not initialized"
    session = await session_store.get(id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    res = session.next(message.content)
    await session_store.set(id, session)
    return SessionResponse(session_id=id, message=res.decision.model_dump(mode="json"))


@app.delete("/session/{id}", dependencies=deps)
async def end_session(
    id: str,
    request: Request,
) -> dict:
    """End and cleanup a session."""
    # Handle authentication
    await authenticate_request(request)

    assert session_store is not None, "Session store not initialized"
    session = await session_store.get(id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Clean up session
    await session_store.delete(id)
    return {"message": "Session ended successfully"}


@app.get("/session/{id}/history", response_model=dict, dependencies=deps)
async def get_session_history(
    id: str,
    request: Request,
) -> dict:
    """Get the history of a session."""
    # Handle authentication
    await authenticate_request(request)

    assert session_store is not None, "Session store not initialized"
    session = await session_store.get(id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Assuming session.history() returns a list of messages
    history: List[Union[Event, StepIdentifier, Summary]] = session.memory.get_history()
    history_json = [
        msg.model_dump(mode="json")
        for msg in history
        if isinstance(msg, Event) and msg.type not in ["error", "fallback"]
    ]
    return {"session_id": id, "history": history_json}


@app.post("/chat", response_model=ChatResponse, dependencies=deps)
async def chat(
    request_obj: ChatRequest,
    request: Request,
    verbose: bool = False,
) -> ChatResponse:
    """Chat endpoint to get the next response from the agent based on the session data."""
    # Handle authentication
    await authenticate_request(request)

    res = agent.next(**request_obj.model_dump(), verbose=verbose)
    return ChatResponse(
        response=res.decision.model_dump(mode="json"),
        tool_output=res.tool_output,
        session_data=res.state,
    )


if __name__ == "__main__":
    import sys

    import uvicorn

    reload = "--reload" in sys.argv
    uvicorn.run(
        "nomos.api.app:app",
        host=config.server.host,
        port=config.server.port,
        workers=config.server.workers,
        reload=reload,
    )
