"""Tests for API tools and wrapper functionality."""

from unittest.mock import Mock, patch

import pytest
import requests

from nomos.models.tool import Tool, ToolWrapper
from nomos.tools.api import APITool, APIWrapper
from nomos.tools.models import ArgDef, ToolDef


class TestAPITool:
    """Test APITool class functionality."""

    def test_api_tool_initialization(self):
        """Test APITool initialization with basic parameters."""
        tool = APITool(name="test_api", url="https://api.example.com/users", method="GET")
        assert tool.name == "test_api"
        assert tool.url == "https://api.example.com/users"
        assert tool.method == "GET"
        assert tool.headers is None

    def test_api_tool_initialization_with_headers(self):
        """Test APITool initialization with headers."""
        headers = {"Authorization": "Bearer token123"}
        tool = APITool(
            name="test_api", url="https://api.example.com/users", method="POST", headers=headers
        )
        assert tool.headers == headers

    @patch("requests.request")
    def test_api_tool_run_get_request(self, mock_request):
        """Test running an API tool with GET method."""
        mock_response = Mock()
        mock_response.text = '{"users": []}'
        mock_request.return_value = mock_response

        tool = APITool(name="get_users", url="https://api.example.com/users", method="GET")

        result = tool.run()

        mock_request.assert_called_once_with(
            method="GET", url="https://api.example.com/users", json=None, headers={}, params={}
        )
        assert result == '{"users": []}'

    @patch("requests.request")
    def test_api_tool_run_post_request_with_body(self, mock_request):
        """Test running an API tool with POST method and JSON body."""
        mock_response = Mock()
        mock_response.text = '{"id": 123, "name": "John"}'
        mock_request.return_value = mock_response

        tool = APITool(name="create_user", url="https://api.example.com/users", method="POST")

        body_data = {"name": "John", "email": "john@example.com"}
        result = tool.run(body=body_data)

        mock_request.assert_called_once_with(
            method="POST",
            url="https://api.example.com/users",
            json=body_data,
            headers={"Content-Type": "application/json"},
            params={},
        )
        assert result == '{"id": 123, "name": "John"}'

    @patch("requests.request")
    def test_api_tool_run_with_url_parameters(self, mock_request):
        """Test running an API tool with URL parameters."""
        mock_response = Mock()
        mock_response.text = '{"id": 123, "name": "John"}'
        mock_request.return_value = mock_response

        tool = APITool(name="get_user", url="https://api.example.com/users/{user_id}", method="GET")

        result = tool.run(user_id=123)

        mock_request.assert_called_once_with(
            method="GET", url="https://api.example.com/users/123", json=None, headers={}, params={}
        )
        assert result == '{"id": 123, "name": "John"}'

    @patch("requests.request")
    def test_api_tool_run_with_query_parameters(self, mock_request):
        """Test running an API tool with query parameters."""
        mock_response = Mock()
        mock_response.text = '{"users": [], "total": 0}'
        mock_request.return_value = mock_response

        tool = APITool(name="search_users", url="https://api.example.com/users", method="GET")

        result = tool.run(page=1, limit=10, search="john")

        mock_request.assert_called_once_with(
            method="GET",
            url="https://api.example.com/users",
            json=None,
            headers={},
            params={"page": 1, "limit": 10, "search": "john"},
        )
        assert result == '{"users": [], "total": 0}'

    @patch("requests.request")
    def test_api_tool_run_with_mixed_parameters(self, mock_request):
        """Test running an API tool with both URL and query parameters."""
        mock_response = Mock()
        mock_response.text = '{"posts": []}'
        mock_request.return_value = mock_response

        tool = APITool(
            name="get_user_posts", url="https://api.example.com/users/{user_id}/posts", method="GET"
        )

        result = tool.run(user_id=123, page=2, limit=5)

        mock_request.assert_called_once_with(
            method="GET",
            url="https://api.example.com/users/123/posts",
            json=None,
            headers={},
            params={"page": 2, "limit": 5},
        )
        assert result == '{"posts": []}'

    def test_api_tool_run_missing_url_parameter(self):
        """Test that missing URL parameters raise ValueError."""
        tool = APITool(name="get_user", url="https://api.example.com/users/{user_id}", method="GET")

        with pytest.raises(ValueError, match="Missing required parameter: user_id"):
            tool.run()

    @patch("requests.request")
    def test_api_tool_run_with_custom_headers(self, mock_request):
        """Test running an API tool with custom headers."""
        mock_response = Mock()
        mock_response.text = '{"data": "success"}'
        mock_request.return_value = mock_response

        headers = {"Authorization": "Bearer token123", "X-Custom": "value"}
        tool = APITool(
            name="protected_api",
            url="https://api.example.com/protected",
            method="GET",
            headers=headers,
        )

        result = tool.run()

        mock_request.assert_called_once_with(
            method="GET",
            url="https://api.example.com/protected",
            json=None,
            headers=headers,
            params={},
        )
        assert result == '{"data": "success"}'

    @patch("requests.request")
    def test_api_tool_run_http_error(self, mock_request):
        """Test that HTTP errors are properly raised."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        mock_request.return_value = mock_response

        tool = APITool(name="failing_api", url="https://api.example.com/nonexistent", method="GET")

        with pytest.raises(requests.HTTPError):
            tool.run()


class TestAPIWrapper:
    """Test APIWrapper class functionality."""

    def test_api_wrapper_initialization(self):
        """Test APIWrapper initialization with basic parameters."""
        wrapper = APIWrapper(identifier="GET/https://api.example.com/users", name="users_api")
        assert wrapper.identifier == "GET/https://api.example.com/users"
        assert wrapper.name == "users_api"
        assert wrapper.map is None
        assert wrapper.tool_defs is None

    def test_api_wrapper_initialization_with_map(self):
        """Test APIWrapper initialization with endpoint mapping."""
        endpoint_map = {
            "get_users": "GET/users",
            "create_user": "POST/users",
            "get_user": "GET/users/{id}",
        }
        wrapper = APIWrapper(
            identifier="https://api.example.com", name="users_api", map=endpoint_map
        )
        assert wrapper.map == endpoint_map

    def test_api_wrapper_initialization_with_tool_defs(self):
        """Test APIWrapper initialization with tool definitions."""
        tool_defs = {
            "get_users": ToolDef(
                desc="Get all users",
                args=[
                    ArgDef(key="page", type="int", desc="Page number"),
                    ArgDef(key="limit", type="int", desc="Items per page"),
                ],
            )
        }
        wrapper = APIWrapper(
            identifier="GET/https://api.example.com/users", name="users_api", tool_defs=tool_defs
        )
        assert wrapper.tool_defs == tool_defs

    def test_split_url_with_method(self):
        """Test splitting URL with HTTP method."""
        method, url = APIWrapper.split_url("GET/https://api.example.com/users")
        assert method == "GET"
        assert url == "https://api.example.com/users"

    def test_split_url_without_method(self):
        """Test splitting URL without HTTP method."""
        method, url = APIWrapper.split_url("https://api.example.com/users")
        assert method is None
        assert url == "https://api.example.com/users"

    def test_split_url_with_leading_slash(self):
        """Test splitting URL with leading slash."""
        method, url = APIWrapper.split_url("/GET/https://api.example.com/users")
        assert method == "GET"
        assert url == "https://api.example.com/users"

    def test_split_url_lowercase_method(self):
        """Test splitting URL with lowercase method."""
        method, url = APIWrapper.split_url("post/https://api.example.com/users")
        assert method == "POST"
        assert url == "https://api.example.com/users"

    def test_tools_property_single_endpoint(self):
        """Test tools property with single endpoint identifier."""
        wrapper = APIWrapper(identifier="GET/https://api.example.com/users", name="get_users")
        tools = wrapper.tools
        assert len(tools) == 1
        assert tools[0].name == "get_users"
        assert tools[0].url == "https://api.example.com/users"
        assert tools[0].method == "GET"

    def test_tools_property_with_map(self):
        """Test tools property with endpoint mapping."""
        endpoint_map = {
            "get_users": "GET/users",
            "create_user": "POST/users",
            "get_user": "GET/users/{id}",
        }
        wrapper = APIWrapper(
            identifier="https://api.example.com", name="users_api", map=endpoint_map
        )
        tools = wrapper.tools
        assert len(tools) == 3

        # Check get_users tool
        get_users_tool = next(tool for tool in tools if tool.name == "get_users")
        assert get_users_tool.url == "https://api.example.com/users"
        assert get_users_tool.method == "GET"

        # Check create_user tool
        create_user_tool = next(tool for tool in tools if tool.name == "create_user")
        assert create_user_tool.url == "https://api.example.com/users"
        assert create_user_tool.method == "POST"

        # Check get_user tool
        get_user_tool = next(tool for tool in tools if tool.name == "get_user")
        assert get_user_tool.url == "https://api.example.com/users/{id}"
        assert get_user_tool.method == "GET"

    def test_tools_property_invalid_method_in_identifier(self):
        """Test tools property with invalid method in identifier."""
        wrapper = APIWrapper(identifier="INVALID/https://api.example.com/users", name="invalid_api")
        # Since INVALID is not a valid method, split_url returns None, url
        # which causes the assertion to fail for missing map instead
        with pytest.raises(AssertionError, match="API map must be defined"):
            _ = wrapper.tools

    def test_tools_property_invalid_method_in_map(self):
        """Test tools property with invalid method in endpoint map."""
        endpoint_map = {"invalid_endpoint": "INVALID/users"}
        wrapper = APIWrapper(
            identifier="https://api.example.com", name="users_api", map=endpoint_map
        )
        # Since INVALID is not a valid method, split_url returns None, url
        # which causes the assertion to fail for None method
        with pytest.raises(AssertionError, match="Invalid method 'None' in endpoint"):
            _ = wrapper.tools

    def test_tools_property_no_method_without_map(self):
        """Test tools property with no method and no map raises assertion."""
        wrapper = APIWrapper(identifier="https://api.example.com", name="users_api")
        with pytest.raises(AssertionError, match="API map must be defined"):
            _ = wrapper.tools

    def test_tools_property_no_method_in_map_endpoint(self):
        """Test tools property with no method in map endpoint."""
        endpoint_map = {"no_method": "users"}
        wrapper = APIWrapper(
            identifier="https://api.example.com", name="users_api", map=endpoint_map
        )
        # URL without slash causes split error
        with pytest.raises(ValueError, match="not enough values to unpack"):
            _ = wrapper.tools


class TestAPIToolIntegration:
    """Test integration of API tools with Tool class."""

    def test_tool_from_api_tool_basic(self):
        """Test creating Tool from APITool."""
        api_tool = APITool(name="test_api", url="https://api.example.com/users", method="GET")
        tool = Tool.from_api_tool(api_tool)

        assert tool.name == "test_api"
        assert tool.description == ""
        assert tool.function == api_tool.run
        assert tool.parameters == {}

    def test_tool_from_api_tool_with_tool_defs(self):
        """Test creating Tool from APITool with tool definitions."""
        api_tool = APITool(name="get_users", url="https://api.example.com/users", method="GET")
        tool_defs = {
            "get_users": ToolDef(
                desc="Get all users from the API",
                args=[
                    ArgDef(key="page", type="int", desc="Page number", default=1),
                    ArgDef(key="limit", type="int", desc="Items per page", default=10),
                ],
            )
        }
        tool = Tool.from_api_tool(api_tool, tool_defs=tool_defs)

        assert tool.name == "get_users"
        assert tool.description == "Get all users from the API"
        assert tool.function == api_tool.run
        assert "page" in tool.parameters
        assert "limit" in tool.parameters
        assert tool.parameters["page"]["default"] == 1
        assert tool.parameters["limit"]["default"] == 10

    @patch("requests.request")
    def test_tool_from_api_tool_run_method(self, mock_request):
        """Test running a Tool created from APITool."""
        mock_response = Mock()
        mock_response.text = '{"users": []}'
        mock_request.return_value = mock_response

        api_tool = APITool(name="get_users", url="https://api.example.com/users", method="GET")
        tool = Tool.from_api_tool(api_tool)

        result = tool.run()
        assert result == '{"users": []}'
        mock_request.assert_called_once()


class TestToolWrapperAPIIntegration:
    """Test ToolWrapper integration with API tools."""

    def test_tool_wrapper_api_single_endpoint(self):
        """Test ToolWrapper with single API endpoint."""
        wrapper = ToolWrapper(
            tool_type="api", name="get_users", tool_identifier="GET/https://api.example.com/users"
        )
        tools = wrapper.get_tool()

        assert isinstance(tools, list)
        assert len(tools) == 1
        assert isinstance(tools[0], Tool)
        assert tools[0].name == "get_users"

    def test_tool_wrapper_api_with_map(self):
        """Test ToolWrapper with API endpoint mapping."""
        endpoint_map = {"get_users": "GET/users", "create_user": "POST/users"}
        wrapper = ToolWrapper(
            tool_type="api",
            name="users_api",
            tool_identifier="https://api.example.com",
            map=endpoint_map,
        )
        tools = wrapper.get_tool()

        assert isinstance(tools, list)
        assert len(tools) == 2
        tool_names = [tool.name for tool in tools]
        assert "get_users" in tool_names
        assert "create_user" in tool_names

    def test_tool_wrapper_api_with_tool_defs(self):
        """Test ToolWrapper with API tools and tool definitions."""
        endpoint_map = {"get_users": "GET/users"}
        tool_defs = {
            "get_users": ToolDef(
                desc="Get all users", args=[ArgDef(key="page", type="int", desc="Page number")]
            )
        }
        wrapper = ToolWrapper(
            tool_type="api",
            name="users_api",
            tool_identifier="https://api.example.com",
            map=endpoint_map,
        )
        tools = wrapper.get_tool(tool_defs=tool_defs)

        assert isinstance(tools, list)
        assert len(tools) == 1
        assert tools[0].name == "get_users"
        assert tools[0].description == "Get all users"
        assert "page" in tools[0].parameters

    def test_tool_wrapper_api_id_property(self):
        """Test ToolWrapper id property for API tools."""
        wrapper = ToolWrapper(
            tool_type="api", name="test_api", tool_identifier="GET/https://api.example.com/users"
        )
        # ToolWrapper.id simply returns the name for most tool types
        expected_id = "test_api"
        assert wrapper.id == expected_id


class TestAPIToolsWithAgent:
    """Test API tools integration with Agent (if needed)."""

    @pytest.fixture
    def api_tool_wrapper(self):
        """Fixture providing an API tool wrapper."""
        return ToolWrapper(
            tool_type="api", name="test_api", tool_identifier="GET/https://api.example.com/users"
        )

    @pytest.fixture
    def api_tool_wrapper_with_map(self):
        """Fixture providing an API tool wrapper with endpoint mapping."""
        endpoint_map = {"get_users": "GET/users", "create_user": "POST/users"}
        return ToolWrapper(
            tool_type="api",
            name="users_api",
            tool_identifier="https://api.example.com",
            map=endpoint_map,
        )

    @pytest.fixture
    def api_tool_defs(self):
        """Fixture providing tool definitions for API tools."""
        return {
            "get_users": ToolDef(
                desc="Get all users from the API",
                args=[
                    ArgDef(key="page", type="int", desc="Page number", default=1),
                    ArgDef(key="limit", type="int", desc="Items per page", default=10),
                ],
            ),
            "create_user": ToolDef(
                desc="Create a new user",
                args=[
                    ArgDef(key="name", type="str", desc="User name"),
                    ArgDef(key="email", type="str", desc="User email"),
                ],
            ),
        }

    def test_api_tool_wrapper_get_tool_single(self, api_tool_wrapper, api_tool_defs):
        """Test getting tools from API wrapper with single endpoint."""
        tools = api_tool_wrapper.get_tool(tool_defs=api_tool_defs)

        assert isinstance(tools, list)
        assert len(tools) == 1
        assert isinstance(tools[0], Tool)
        assert tools[0].name == "test_api"

    def test_api_tool_wrapper_get_tool_multiple(self, api_tool_wrapper_with_map, api_tool_defs):
        """Test getting tools from API wrapper with multiple endpoints."""
        tools = api_tool_wrapper_with_map.get_tool(tool_defs=api_tool_defs)

        assert isinstance(tools, list)
        assert len(tools) == 2
        tool_names = [tool.name for tool in tools]
        assert "get_users" in tool_names
        assert "create_user" in tool_names

        # Check that tool definitions are properly applied
        get_users_tool = next(tool for tool in tools if tool.name == "get_users")
        assert get_users_tool.description == "Get all users from the API"
        assert "page" in get_users_tool.parameters
        assert "limit" in get_users_tool.parameters

    @patch("requests.request")
    def test_api_tool_execution_in_context(self, mock_request, api_tool_wrapper):
        """Test executing API tool in a realistic context."""
        mock_response = Mock()
        mock_response.text = '{"users": [{"id": 1, "name": "John"}]}'
        mock_request.return_value = mock_response

        tools = api_tool_wrapper.get_tool()
        tool = tools[0]

        result = tool.run()
        assert result == '{"users": [{"id": 1, "name": "John"}]}'
        mock_request.assert_called_once_with(
            method="GET", url="https://api.example.com/users", json=None, headers={}, params={}
        )


class TestAPIToolsEdgeCases:
    """Test edge cases and error conditions for API tools."""

    def test_split_url_edge_cases(self):
        """Test edge cases in split_url method."""
        # Empty string - will cause ValueError
        try:
            method, url = APIWrapper.split_url("")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

        # Only method - will cause ValueError
        try:
            method, url = APIWrapper.split_url("GET")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

        # Method with slash but no URL
        method, url = APIWrapper.split_url("GET/")
        assert method == "GET"
        assert url == ""

        # Multiple slashes
        method, url = APIWrapper.split_url("POST/api/v1/users")
        assert method == "POST"
        assert url == "api/v1/users"

    @patch("requests.request")
    def test_api_tool_with_multiple_url_parameters(self, mock_request):
        """Test API tool with multiple URL parameters."""
        mock_response = Mock()
        mock_response.text = '{"comment": {"id": 1, "text": "Hello"}}'
        mock_request.return_value = mock_response

        tool = APITool(
            name="get_comment",
            url="https://api.example.com/posts/{post_id}/comments/{comment_id}",
            method="GET",
        )

        result = tool.run(post_id=123, comment_id=456, include_replies=True)

        mock_request.assert_called_once_with(
            method="GET",
            url="https://api.example.com/posts/123/comments/456",
            json=None,
            headers={},
            params={"include_replies": True},
        )
        assert result == '{"comment": {"id": 1, "text": "Hello"}}'

    @patch("requests.request")
    def test_api_tool_with_mixed_body_and_params(self, mock_request):
        """Test API tool with both body and query parameters."""
        mock_response = Mock()
        mock_response.text = '{"success": true}'
        mock_request.return_value = mock_response

        tool = APITool(
            name="update_user", url="https://api.example.com/users/{user_id}", method="PUT"
        )

        body_data = {"name": "Updated Name"}
        result = tool.run(user_id=123, body=body_data, notify=True)

        mock_request.assert_called_once_with(
            method="PUT",
            url="https://api.example.com/users/123",
            json=body_data,
            headers={"Content-Type": "application/json"},
            params={"notify": True},
        )
        assert result == '{"success": true}'

    def test_api_wrapper_with_complex_mapping(self):
        """Test API wrapper with complex endpoint mapping."""
        endpoint_map = {
            "list_users": "GET/users",
            "get_user": "GET/users/{id}",
            "create_user": "POST/users",
            "update_user": "PUT/users/{id}",
            "delete_user": "DELETE/users/{id}",
            "get_user_posts": "GET/users/{user_id}/posts",
            "create_post": "POST/users/{user_id}/posts",
        }

        wrapper = APIWrapper(
            identifier="https://api.example.com", name="users_api", map=endpoint_map
        )

        tools = wrapper.tools
        assert len(tools) == 7

        # Check specific tools
        tool_names = [tool.name for tool in tools]
        expected_names = [
            "list_users",
            "get_user",
            "create_user",
            "update_user",
            "delete_user",
            "get_user_posts",
            "create_post",
        ]
        assert set(tool_names) == set(expected_names)

        # Check methods
        methods = [tool.method for tool in tools]
        assert "GET" in methods
        assert "POST" in methods
        assert "PUT" in methods
        assert "DELETE" in methods

    def test_api_wrapper_with_tool_definitions_comprehensive(self):
        """Test API wrapper with comprehensive tool definitions."""
        endpoint_map = {"search_users": "GET/users/search", "create_user": "POST/users"}

        tool_defs = {
            "search_users": ToolDef(
                desc="Search for users with filters",
                args=[
                    ArgDef(key="query", type="str", desc="Search query"),
                    ArgDef(key="page", type="int", desc="Page number", default=1),
                    ArgDef(key="per_page", type="int", desc="Items per page", default=10),
                    ArgDef(key="sort", type="str", desc="Sort field", default="created_at"),
                ],
            ),
            "create_user": ToolDef(
                desc="Create a new user account",
                args=[
                    ArgDef(key="name", type="str", desc="Full name"),
                    ArgDef(key="email", type="str", desc="Email address"),
                    ArgDef(key="role", type="str", desc="User role", default="user"),
                ],
            ),
        }

        wrapper = APIWrapper(
            identifier="https://api.example.com",
            name="users_api",
            map=endpoint_map,
            tool_defs=tool_defs,
        )

        tools = wrapper.tools
        assert len(tools) == 2

        # Verify tool definitions are preserved
        assert wrapper.tool_defs == tool_defs


class TestAPIToolsIntegrationWithAgent:
    """Integration tests for API tools with Agent workflow."""

    @pytest.fixture
    def api_tool_config(self):
        """Configuration for API tools integration test."""
        from nomos.config import AgentConfig, ToolsConfig
        from nomos.models.agent import Route, Step

        steps = [
            Step(
                step_id="start",
                description="Start step with API tools",
                routes=[Route(target="end", condition="Task completed")],
                available_tools=["get_users", "create_user"],
            ),
            Step(step_id="end", description="End step", routes=[], available_tools=[]),
        ]

        tool_defs = {
            "get_users": ToolDef(
                desc="Get all users from API",
                args=[
                    ArgDef(key="page", type="int", desc="Page number", default=1),
                    ArgDef(key="limit", type="int", desc="Items per page", default=10),
                ],
            ),
            "create_user": ToolDef(
                desc="Create a new user",
                args=[
                    ArgDef(key="name", type="str", desc="User name"),
                    ArgDef(key="email", type="str", desc="User email"),
                ],
            ),
        }

        return AgentConfig(
            name="api_test_agent",
            persona="API testing agent",
            steps=steps,
            start_step_id="start",
            tools=ToolsConfig(tool_defs=tool_defs),
        )

    @pytest.fixture
    def api_tool_wrappers(self):
        """API tool wrappers for integration test."""
        endpoint_map = {"get_users": "GET/users", "create_user": "POST/users"}

        return [
            ToolWrapper(
                tool_type="api",
                name="users_api",
                tool_identifier="https://api.example.com",
                map=endpoint_map,
            )
        ]

    def test_api_agent_creation(self, mock_llm, api_tool_config, api_tool_wrappers):
        """Test creating an agent with API tools."""
        from nomos.core import Agent

        agent = Agent.from_config(config=api_tool_config, llm=mock_llm, tools=api_tool_wrappers)

        assert agent.name == "api_test_agent"
        assert len(agent.tools) == 2  # get_users and create_user

        # Check that tools are properly converted
        tool_names = list(agent.tools.keys())
        assert "get_users" in tool_names
        assert "create_user" in tool_names

        # Check that tools are Tool instances
        from nomos.models.tool import Tool

        assert isinstance(agent.tools["get_users"], Tool)
        assert isinstance(agent.tools["create_user"], Tool)

    @patch("requests.request")
    def test_api_agent_tool_execution(
        self, mock_request, mock_llm, api_tool_config, api_tool_wrappers
    ):
        """Test executing API tools through an agent session."""
        from nomos.core import Agent
        from nomos.models.agent import Action

        # Setup mock response
        mock_response = Mock()
        mock_response.text = '{"users": [{"id": 1, "name": "John"}]}'
        mock_request.return_value = mock_response

        agent = Agent.from_config(config=api_tool_config, llm=mock_llm, tools=api_tool_wrappers)

        session = agent.create_session()

        # Create a decision model and mock response
        decision_model = agent.llm._create_decision_model(
            current_step=session.current_step, current_step_tools=tuple(session.tools.values())
        )

        tool_response = decision_model(
            reasoning=["Need to get users"],
            action=Action.TOOL_CALL.value,
            tool_call={"tool_name": "get_users", "tool_kwargs": {"page": 1, "limit": 5}},
        )

        session.llm.set_response(tool_response)

        # Execute tool through session
        result = session.next("Get the users", return_tool=True)

        # Verify tool was called correctly
        assert result.decision.action == Action.TOOL_CALL
        assert result.decision.tool_call.tool_name == "get_users"
        assert result.tool_output == '{"users": [{"id": 1, "name": "John"}]}'

        # Verify HTTP request was made correctly
        mock_request.assert_called_once_with(
            method="GET",
            url="https://api.example.com/users",
            json=None,
            headers={},
            params={"page": 1, "limit": 5},
        )

    def test_api_tools_in_workflow(self, mock_llm, api_tool_config, api_tool_wrappers):
        """Test API tools in a complete workflow."""
        from nomos.core import Agent

        agent = Agent.from_config(config=api_tool_config, llm=mock_llm, tools=api_tool_wrappers)

        session = agent.create_session()

        # Verify initial state
        assert session.current_step.step_id == "start"
        assert len(session.tools) == 2

        # Verify available tools in current step
        available_tools = session.current_step.available_tools
        assert "get_users" in available_tools
        assert "create_user" in available_tools

        # Verify tool accessibility
        assert "get_users" in session.tools
        assert "create_user" in session.tools

        # Verify tool properties
        get_users_tool = session.tools["get_users"]
        assert get_users_tool.name == "get_users"
        assert get_users_tool.description == "Get all users from API"
        assert "page" in get_users_tool.parameters
        assert "limit" in get_users_tool.parameters
