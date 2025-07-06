"""Nomos Visual Builder Backend.

FastAPI backend server for the Nomos Visual Builder application.
"""

import glob
import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from nomos.api.models import ChatRequest, ChatResponse
from nomos.core import Agent, AgentConfig
from nomos.models.agent import Response

app = FastAPI()

# Environment configuration
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))
DISABLE_AGENT_CACHE = os.getenv("DISABLE_AGENT_CACHE", "false").lower() in (
    "true",
    "1",
    "yes",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

agent: Optional[Agent] = None


def clean_tools_directory() -> None:
    """Remove all .py files from tools directory except __init__.py."""
    tools_dir = "tools"
    if not os.path.exists(tools_dir):
        os.makedirs(tools_dir)

    # Keep __init__.py, remove all other .py files
    for py_file in glob.glob(os.path.join(tools_dir, "*.py")):
        if not py_file.endswith("__init__.py"):
            os.remove(py_file)


@app.post("/upload-tools")
async def upload_tools(files: List[UploadFile] = File(...)) -> Dict[str, Any]:  # type: ignore
    """Upload .py tool files to the tools directory."""
    try:
        # Clean existing tools first
        clean_tools_directory()

        uploaded_files = []
        for file in files:
            if not file.filename or not file.filename.endswith(".py"):
                continue

            file_path = os.path.join("tools", file.filename)
            content = await file.read()

            with open(file_path, "wb") as f:
                f.write(content)

            uploaded_files.append(file.filename)

        return {"status": "success", "uploaded_files": uploaded_files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ServerlessChatRequest(BaseModel):
    """Request model for serverless chat endpoint."""

    agent_config: AgentConfig
    chat_request: ChatRequest
    env_vars: Optional[Dict[str, str]] = None
    verbose: bool = False


@app.post("/chat")
def chat(request: ServerlessChatRequest) -> ChatResponse:
    """Handle serverless chat requests."""
    global agent
    from tools import tool_list

    # Snapshot current environment state
    original_env = dict(os.environ) if DISABLE_AGENT_CACHE and request.env_vars else None

    try:
        # Update environment variables
        if request.env_vars:
            os.environ.update(request.env_vars)

        # Re-instantiate agent if needed
        if (
            agent is None
            or agent.config.model_dump_json() != request.agent_config.model_dump_json()  # type: ignore
        ):
            agent = Agent.from_config(config=request.agent_config, tools=tool_list)

        # Process the chat request
        res: Response = agent.next(
            user_input=request.chat_request.user_input,
            session_data=request.chat_request.session_data,
            return_step=request.verbose,
            return_tool=request.verbose,
        )

        return ChatResponse(
            response=res.decision.model_dump(mode="json"),
            tool_output=res.tool_output,
            session_data=res.state,
        )

    finally:
        if DISABLE_AGENT_CACHE:
            agent = None
            # Restore environment to original state
            if original_env is not None:
                os.environ.clear()
                os.environ.update(original_env)


if __name__ == "__main__":
    import uvicorn

    # Start the FastAPI server
    uvicorn.run("main:app", host="0.0.0.0", port=BACKEND_PORT, log_level="info")
