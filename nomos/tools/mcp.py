"""Module defining the MCP related types."""

import asyncio
import enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from pydantic import BaseModel, HttpUrl, SecretStr

from ..utils.misc import join_urls
from ..utils.utils import create_base_model, parse_type

try:
    from fastmcp import Client
except ImportError:
    Client = None  # type: ignore[assignment]


if TYPE_CHECKING:
    from ..models.tool import Tool


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


class MCPServer(BaseModel):
    """Represents a MCP server."""

    name: str
    url: HttpUrl
    path: Optional[str] = None
    transport: Optional[MCPServerTransport] = MCPServerTransport.mcp
    auth: Optional[SecretStr] = None

    @property
    def id(self) -> str:
        """
        Get the unique identifier for the MCP server.

        :return: The unique identifier for the MCP server.
        """
        return self.name

    @property
    def url_path(self) -> str:
        """
        Get the URL path for the MCP server.

        :return: The URL path for the MCP server.
        """
        if not self.path:
            return str(self.url)

        return join_urls(str(self.url), self.path)

    def get_tools(self) -> List["Tool"]:
        """
        Get a list of Tool instances from the MCP server.

        :return: A list of Tool instances.
        """
        return asyncio.run(self.list_tools_async())

    def call_tool(self, tool_name: str, kwargs: Optional[dict] = None) -> List[str]:
        """
        Call a tool on the MCP server.

        :param tool_name: Toll name to call.
        :param kwargs: Optional keyword arguments for the tool.
        :return: The result of the tool's function.
        """
        return asyncio.run(self.call_tool_async(tool_name, kwargs))

    async def list_tools_async(self) -> List["Tool"]:
        """
        Asynchronously get a list of Tool instances from the MCP server.

        :return: A list of Tool instances.
        """
        if not Client:
            raise ImportError("fastmcp is not installed. Please install it to use MCPServer.")

        client = Client(self.url_path, auth=self.auth.get_secret_value() if self.auth else None)
        tool_models = []
        async with client:
            tools = await client.list_tools()
            for t in tools:
                tool_name = t.name
                input_parameters = t.inputSchema.get("properties", {})
                mapped_parameters = {}
                for param_name, param_info in input_parameters.items():
                    param_type = parse_type(param_info["type"])
                    mapped_parameters[param_name] = {
                        "type": param_type,
                        "description": param_info.get("description", ""),
                    }

                data = {
                    "name": tool_name,
                    "description": t.description,
                    "parameters": mapped_parameters,
                }
                params: Dict[str, Any] = {
                    "name": {
                        "type": str,
                    },
                    "description": {
                        "type": str,
                    },
                    "parameters": {
                        "type": dict,
                        "default": {},
                    },
                }
                ModelClass = create_base_model("MCPTool", params)
                tool_models.append(ModelClass(**data))

        return tool_models

    async def call_tool_async(self, tool_name: str, kwargs: Optional[dict] = None) -> List[str]:
        """
        Asynchronously call a tool on the MCP server.

        :param tool_name: Toll name to call.
        :param kwargs: Optional keyword arguments for the tool.
        :return: A list of strings representing the tool's output.
        """
        if not Client:
            raise ImportError("fastmcp is not installed. Please install it to use MCPServer.")

        client = Client(self.url_path, auth=self.auth.get_secret_value() if self.auth else None)
        params = kwargs.copy() if kwargs else {}
        async with client:
            res = await client.call_tool(tool_name, params)
            return [r.text for r in res.content if r.type == "text"]
