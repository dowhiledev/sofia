from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nomos.models.agent import Step, StepOverrides
from nomos.models.tool import Tool
from nomos.tools.mcp import MCPServer
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
    @patch("nomos.tools.mcp.Client")
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
        auth_key = "test_auth_key"
        server = MCPServer(name="server", url="https://example.com", auth=auth_key)
        result = await server.list_tools_async()

        # Verify client was created and used correctly
        mock_client_class.assert_called_once_with(server.url_path, auth=auth_key)
        mock_client.list_tools.assert_called_once()

        assert result[0].name == "test_tool"
        assert result[0].description == "A test tool"
        assert result[0].parameters == {
            "param1": {"type": str, "description": "First parameter"},
        }

    @pytest.mark.asyncio
    @patch("nomos.tools.mcp.Client")
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
        mock_result = MagicMock()
        mock_result.content = [call_tool_result]
        mock_client.call_tool.return_value = mock_result

        auth_key = "test_auth_key"
        server = MCPServer(name="server", url="https://example.com", auth=auth_key)
        result = await server.call_tool_async(tool_name, params)

        # Verify client was created and used correctly
        mock_client_class.assert_called_once_with(server.url_path, auth=auth_key)
        mock_client.call_tool.assert_called_once_with(tool_name, params)

        assert result == [call_tool_result.text]


class TestTool:
    @patch("nomos.tools.mcp.MCPServer.get_tools")
    def test_from_mcp_server(self, mock_get_tools):
        """Test Tool.from_mcp_server method."""
        server_name = "test_server"
        server = MCPServer(name=server_name, url="https://example.com/nomos")
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


class TestStepOverrides:
    """Test Step model overrides."""

    def test_empty_step_persona(self):
        """Test Step persona property."""
        step = Step(name="test_step", step_id="id", description="A test step")
        assert step.persona is None

    def test_step_persona(self):
        """Test Step persona property with overrides."""
        overrides = StepOverrides(persona="test_persona")
        step = Step(name="test_step", step_id="id", description="A test step", overrides=overrides)
        assert step.persona == "test_persona"

    def test_step_empty_llm(self):
        """Test Step llm property."""
        step = Step(name="test_step", step_id="id", description="A test step")
        assert step.llm == "global"

    def test_step_llm(self):
        """Test Step llm property with overrides."""
        overrides = StepOverrides(llm="other")
        step = Step(name="test_step", step_id="id", description="A test step", overrides=overrides)
        assert step.llm == "other"
