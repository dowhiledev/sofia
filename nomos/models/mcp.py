"""Module defining the MCP related types."""

import enum
from typing import Optional

from pydantic import BaseModel


class MCPTool(BaseModel):
    """Represents a tool in MCP.

    Attributes:
        name (str): Name of the tool.
        description (str): Description of the tool.
        parameters (Optional[dict]): Parameters required by the tool.
    """

    name: str
    description: str
    parameters: Optional[dict] = None


class MCPServerTransport(str, enum.Enum):
    """
    Enum representing different types of MCP servers.

    Attributes:
        mcp: Represents a Model Configuration Protocol (MCP) server.
    """

    mcp = "mcp"
