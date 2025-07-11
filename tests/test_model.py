from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp.exceptions import ToolError

from nomos.models.mcp import MCPServer
from nomos.models.tool import Tool
from nomos.utils.utils import create_base_model


@pytest.fixture
def call_tool_result():
    params = {
        "type": {
            "type": str,
        },
        "text": {
            "type": str,
        },
    }
    Model = create_base_model("CallToolResult", params)
    return Model(type="text", text="This is a test result.")


class TestMCPServer:
    """Test MCPServer model and functionality."""

    def test_mcp_server_url_path(self):
        """Test MCPServer can be created with required fields."""
        server = MCPServer(
            name="test_server",
            url="https://example.com",
            path="/mcp",
        )
        assert server.url_path == "https://example.com/mcp"

        server2 = MCPServer(
            name="test_server",
            url="https://example.com/mcp",
        )
        assert server2.url_path == "https://example.com/mcp"

    @pytest.mark.asyncio
    @patch("nomos.models.mcp.Client")
    async def test_list_tools_async(self, mock_client_class):
        """Test asynchronous list_tools_async method."""
        # Mock the client and its methods
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client

        # Mock tool data from MCP server
        mock_tool = MagicMock()
        mock_tool.name = "test_tool"
        mock_tool.description = "A test tool"
        mock_tool.inputSchema = {
            "properties": {
                "param1": {"type": "string", "description": "First parameter"},
            }
        }
        mock_client.list_tools.return_value = [mock_tool]
        server = MCPServer(name="server", url="https://example.com")
        result = await server.list_tools_async()

        # Verify client was created and used correctly
        mock_client_class.assert_called_once_with(server.url_path)
        mock_client.list_tools.assert_called_once()

        assert result[0].name == "test_tool"
        assert result[0].description == "A test tool"
        assert result[0].parameters == {
            "param1": {"type": str, "description": "First parameter"},
        }

    @pytest.mark.asyncio
    @patch("nomos.models.mcp.Client")
    async def test_call_tool_async(self, mock_client_class, call_tool_result):
        """Test asynchronous call_tool_async method."""
        # Mock the client and its methods
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client

        # Mock tool data from MCP server
        tool_name = "test_tool"
        params = {
            "param1": {"type": "string", "description": "First parameter"},
        }

        # Mock the call to the tool
        mock_client.call_tool.return_value = [call_tool_result]

        server = MCPServer(name="server", url="https://example.com")
        result = await server.call_tool_async(tool_name, params)

        # Verify client was created and used correctly
        mock_client_class.assert_called_once_with(server.url_path)
        mock_client.call_tool.assert_called_once_with(tool_name, params)

        assert result == [call_tool_result.text]


class TestTool:
    @patch("nomos.models.tool.MCPServer.get_tools")
    def test_from_mcp_server(self, mock_get_tools):
        """Test Tool.from_mcp_server method."""
        server_name = "test_server"
        server = MCPServer(name=server_name, url="https://example.com")
        tool_name = "test_tool"
        tool_description = "A test tool"
        tool_params = {"properties": {}}
        tool_mock = MagicMock(name=tool_name, description=tool_description, parameters=tool_params)
        tool_mock.name = tool_name
        mock_tools = [tool_mock]
        mock_get_tools.return_value = mock_tools
        tools = Tool.from_mcp_server(server)

        assert tools[0].name == f"{server.name}/{tool_name}"
        assert tools[0].description == tool_description
        assert tools[0].parameters == tool_params
