"""Nomos Agent API."""

import pathlib
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles

from ..models.agent import Event, StepIdentifier, Summary
from .agent import agent, config
from .db import init_db
from .models import ChatRequest, ChatResponse, Message, SessionResponse
from .security import (
    SecurityManager,
    bearer_scheme,
    create_auth_dependency,
    create_rate_limit_dependency,
    setup_security_middleware,
)
from .sessions import SessionStore, create_session_store

session_store: Optional[SessionStore] = None
security_manager: Optional[SecurityManager] = None

BASE_DIR = pathlib.Path(__file__).parent.absolute()


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
    print(security_manager)

    yield
    # Cleanup
    await session_store.close()
    if security_manager:
        await security_manager.close()


app = FastAPI(title=f"{config.name}-api", lifespan=lifespan)

# Setup security middleware
setup_security_middleware(app, config.server.security)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.server.security.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-CSRF-Token"],
)

# Mount static files directory
app.mount("/static", StaticFiles(directory=str(BASE_DIR)), name="static")


# Create auth dependency
def get_auth_dependency():
    """Get authentication dependency."""
    assert security_manager is not None, "Security manager not initialized"
    return create_auth_dependency(security_manager)


# Create optional auth dependency (for endpoints that can work with or without auth)
def get_optional_auth_dependency():
    """Get optional authentication dependency."""
    assert security_manager is not None, "Security manager not initialized"

    async def optional_auth_dependency(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    ) -> Dict[str, Any]:
        if not config.server.security.enable_auth or not credentials:
            return {"authenticated": False}
        try:
            return await security_manager.authenticate(credentials)
        except HTTPException:
            return {"authenticated": False}

    return optional_auth_dependency


# Create rate limit dependency
def get_rate_limit_dependency():
    """Get rate limiting dependency."""
    return create_rate_limit_dependency(config.server.security)


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


# Configuration endpoint (optional authentication)
@app.get("/config")
async def get_config(
    auth: Dict = Depends(get_optional_auth_dependency()),
    rate_limit: Optional[None] = Depends(get_rate_limit_dependency()),
) -> dict:
    """Get server configuration information."""
    return {
        "security": {
            "auth_enabled": config.server.security.enable_auth,
            "auth_type": config.server.security.auth_type,
            "csrf_enabled": config.server.security.enable_csrf_protection,
            "rate_limiting_enabled": config.server.security.enable_rate_limiting,
        },
        "server": {
            "host": config.server.host,
            "port": config.server.port,
        },
    }


# Generate JWT token endpoint (for testing purposes)
@app.post("/auth/token")
async def generate_token(payload: dict) -> dict:
    """Generate a JWT token for testing purposes."""
    if not config.server.security.enable_auth or config.server.security.auth_type != "jwt":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="JWT authentication not enabled",
        )

    if not config.server.security.jwt_secret_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT secret key not configured",
        )

    from .security import generate_jwt_token

    token = generate_jwt_token(payload, config.server.security.jwt_secret_key)
    return {"access_token": token, "token_type": "bearer"}


@app.post("/session", response_model=SessionResponse)
async def create_session(
    initiate: Optional[bool] = False,
    auth: Dict = Depends(get_auth_dependency()),
    rate_limit: Optional[None] = Depends(get_rate_limit_dependency()),
) -> SessionResponse:
    """Create a new session."""
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


@app.post("/session/{id}/message", response_model=SessionResponse)
async def send_message(
    id: str,
    message: Message,
    auth: Dict = Depends(get_auth_dependency()),
    rate_limit: Optional[None] = Depends(get_rate_limit_dependency()),
) -> SessionResponse:
    """Send a message to an existing session."""
    assert session_store is not None, "Session store not initialized"
    session = await session_store.get(id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    res = session.next(message.content)
    await session_store.set(id, session)
    return SessionResponse(session_id=id, message=res.decision.model_dump(mode="json"))


@app.delete("/session/{id}")
async def end_session(
    id: str,
    auth: Dict = Depends(get_auth_dependency()),
    rate_limit: Optional[None] = Depends(get_rate_limit_dependency()),
) -> dict:
    """End and cleanup a session."""
    assert session_store is not None, "Session store not initialized"
    session = await session_store.get(id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Clean up session
    await session_store.delete(id)
    return {"message": "Session ended successfully"}


@app.get("/session/{id}/history")
async def get_session_history(
    id: str,
    auth: Dict = Depends(get_auth_dependency()),
    rate_limit: Optional[None] = Depends(get_rate_limit_dependency()),
) -> dict:
    """Get the history of a session."""
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


@app.post("/chat")
async def chat(
    request: ChatRequest,
    verbose: bool = False,
    auth: Dict = Depends(get_auth_dependency()),
    rate_limit: Optional[None] = Depends(get_rate_limit_dependency()),
) -> ChatResponse:
    """Chat endpoint to get the next response from the agent based on the session data."""
    res = agent.next(**request.model_dump(), verbose=verbose)
    return ChatResponse(
        response=res.decision.model_dump(mode="json"),
        tool_output=res.tool_output,
        session_data=res.state,
    )


# async def _handle_websocket(
#     websocket: WebSocket,
#     session_id: Optional[str],
#     initiate: bool,
#     verbose: bool,
# ) -> None:
#     """Handle real-time chat via WebSocket."""
#     assert session_store is not None, "Session store not initialized"
#     await websocket.accept()

#     created = session_id is None
#     if created:
#         sid = str(uuid.uuid4())
#         session = agent.create_session()
#         await session_store.set(sid, session)
#     else:
#         assert session_id is not None
#         sid = session_id
#         session_opt = await session_store.get(sid)
#         if session_opt is None:
#             await websocket.send_json({"error": "Session not found"})
#             await websocket.close()
#             return
#         session = session_opt

#     if initiate:
#         res = session.next(None)
#         await session_store.set(sid, session)
#         await websocket.send_json(
#             {"session_id": sid, "message": res.decision.model_dump(mode="json")}
#         )
#     elif created:
#         await websocket.send_json({"session_id": sid})

#     with suppress(WebSocketDisconnect):
#         while True:
#             data = await websocket.receive_json()
#             if data.get("close"):
#                 await websocket.close()
#                 break

#             user_message = data.get("message")
#             if user_message is None:
#                 await websocket.send_json({"error": "Invalid message"})
#                 continue

#             res = session.next(user_message)
#             await session_store.set(sid, session)
#             await websocket.send_json(
#                 {"session_id": sid, "message": res.decision.model_dump(mode="json")}
#             )


# @app.websocket("/ws")
# async def websocket_create(
#     websocket: WebSocket,
#     initiate: Optional[bool] = False,
#     verbose: Optional[bool] = False,
# ) -> None:
#     """Create a new session and handle WebSocket communication."""
#     await _handle_websocket(websocket, None, bool(initiate), bool(verbose))


# @app.websocket("/ws/{session_id}")
# async def websocket_endpoint(
#     websocket: WebSocket,
#     session_id: str,
#     initiate: Optional[bool] = False,
#     verbose: Optional[bool] = False,
# ) -> None:
#     """Continue an existing session over WebSocket."""
#     await _handle_websocket(websocket, session_id, bool(initiate), bool(verbose))


# @app.get("/config", response_class=JSONResponse)
# async def get_agent_config() -> JSONResponse:
#     """Get the agent configuration as JSON with enhanced metadata."""
#     config_path = pathlib.Path(os.getenv("CONFIG_PATH", str(BASE_DIR / "config.agent.yaml")))
#     if not config_path.exists():
#         raise HTTPException(status_code=404, detail="Agent configuration file not found")

#     try:
#         # Parse the YAML configuration
#         config = parse_yaml_config(str(config_path))

#         # Generate enhanced JSON representation
#         config_json = generate_config_json(config)
#         config_json["metadata"]["generated_at"] = datetime.datetime.now().isoformat()
#         config_json["metadata"]["config_file_path"] = str(config_path)

#         return JSONResponse(content=config_json)
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error processing configuration: {str(e)}")


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
