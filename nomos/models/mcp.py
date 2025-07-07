"""Module defining the MCP related types."""

import asyncio
import enum
from typing import Dict, List, Optional

from pydantic import BaseModel, HttpUrl

from ..utils.misc import join_urls
from ..utils.utils import parse_type


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

    @property
    def id(self) -> str:
        """
        Get the unique identifier for the MCP server.

        :return: The unique identifier for the MCP server.
        """
        return f"@mcp/{self.name}"

    @property
    def url_path(self) -> str:
        """
        Get the URL path for the MCP server.

        :return: The URL path for the MCP server.
        """
        if not self.path:
            return str(self.url)

        return join_urls(str(self.url), self.path)

    def get_tools(self) -> List[Dict]:
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

    async def list_tools_async(self) -> List[Dict]:
        """
        Asynchronously get a list of Tool instances from the MCP server.

        :return: A list of Tool instances.
        """
        try:
            from fastmcp import Client

            client = Client(self.url_path)
        except ImportError:
            raise ImportError(
                "fastmcp is not installed. Please install it using `pip install fastmcp`."
            )

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
                tool_models.append(data)

        return tool_models

    async def call_tool_async(self, tool_name: str, kwargs: Optional[dict] = None) -> List[str]:
        """
        Asynchronously call a tool on the MCP server.

        :param tool_name: Toll name to call.
        :param kwargs: Optional keyword arguments for the tool.
        :return: A list of strings representing the tool's output.
        """
        try:
            from fastmcp import Client
        except ImportError:
            raise ImportError(
                "fastmcp is not installed. Please install it using `pip install fastmcp`."
            )

        client = Client(self.url_path)
        params = kwargs.copy() if kwargs else {}
        async with client:
            res = await client.call_tool(tool_name, params)
            return [r.text for r in res if r.type == "text"]
