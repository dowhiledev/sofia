"""
Tests for the Nomos client library.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
import httpx

from nomos.client import (
    AuthConfig,
    NomosClient,
    NomosClientSync,
    APIError,
    AuthenticationError,
    NomosClientError,
    SessionResponse,
    ChatResponse,
)
from nomos.models.agent import State


class TestAuthConfig:
    """Test AuthConfig model."""
    
    def test_default_auth_config(self):
        """Test default auth config."""
        auth = AuthConfig()
        assert auth.auth_type == "none"
        assert auth.token is None
    
    def test_jwt_auth_config(self):
        """Test JWT auth config."""
        auth = AuthConfig(auth_type="jwt", token="test-token")
        assert auth.auth_type == "jwt"
        assert auth.token == "test-token"
    
    def test_api_key_auth_config(self):
        """Test API key auth config."""
        auth = AuthConfig(auth_type="api_key", token="test-key")
        assert auth.auth_type == "api_key"
        assert auth.token == "test-key"


class TestNomosClient:
    """Test NomosClient functionality."""
    
    @pytest.fixture
    def mock_response(self):
        """Create a mock HTTP response."""
        response = MagicMock()
        response.is_success = True
        response.status_code = 200
        response.json.return_value = {"status": "ok"}
        return response
    
    @pytest.fixture
    def client(self):
        """Create a client instance for testing."""
        return NomosClient("http://test-server:8000")
    
    def test_client_initialization(self):
        """Test client initialization."""
        client = NomosClient(
            "http://localhost:8000",
            auth=AuthConfig(auth_type="jwt", token="test"),
            timeout=60.0,
            headers={"X-Test": "value"}
        )
        
        assert client.base_url == "http://localhost:8000"
        assert client.auth.auth_type == "jwt"
        assert client.auth.token == "test"
        assert client.timeout == 60.0
        assert client.custom_headers == {"X-Test": "value"}
    
    def test_headers_no_auth(self, client):
        """Test headers without authentication."""
        headers = client._get_headers()
        expected = {"Content-Type": "application/json"}
        assert headers == expected
    
    def test_headers_with_jwt_auth(self):
        """Test headers with JWT authentication."""
        auth = AuthConfig(auth_type="jwt", token="test-jwt-token")
        client = NomosClient("http://test", auth=auth)
        
        headers = client._get_headers()
        expected = {
            "Content-Type": "application/json",
            "Authorization": "Bearer test-jwt-token"
        }
        assert headers == expected
    
    def test_headers_with_api_key_auth(self):
        """Test headers with API key authentication."""
        auth = AuthConfig(auth_type="api_key", token="test-api-key")
        client = NomosClient("http://test", auth=auth)
        
        headers = client._get_headers()
        expected = {
            "Content-Type": "application/json",
            "Authorization": "Bearer test-api-key"
        }
        assert headers == expected
    
    def test_headers_with_custom_headers(self):
        """Test headers with custom headers."""
        custom_headers = {"X-Client": "test", "X-Version": "1.0"}
        client = NomosClient("http://test", headers=custom_headers)
        
        headers = client._get_headers()
        expected = {
            "Content-Type": "application/json",
            "X-Client": "test",
            "X-Version": "1.0"
        }
        assert headers == expected
    
    def test_build_url(self, client):
        """Test URL building."""
        assert client._build_url("/health") == "http://test-server:8000/health"
        assert client._build_url("health") == "http://test-server:8000/health"
        assert client._build_url("/session/123") == "http://test-server:8000/session/123"
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, client, mock_response):
        """Test successful health check."""
        client._client = AsyncMock()
        client._client.request = AsyncMock(return_value=mock_response)
        
        result = await client.health_check()
        assert result == {"status": "ok"}
        
        client._client.request.assert_called_once_with(
            method="GET",
            url="http://test-server:8000/health",
            headers={"Content-Type": "application/json"},
            json=None,
            params=None,
        )
    
    @pytest.mark.asyncio
    async def test_request_authentication_error(self, client):
        """Test authentication error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        
        client._client = AsyncMock()
        client._client.request = AsyncMock(return_value=mock_response)
        
        with pytest.raises(AuthenticationError, match="Authentication failed"):
            await client.health_check()
    
    @pytest.mark.asyncio
    async def test_request_api_error(self, client):
        """Test API error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.is_success = False
        mock_response.json.return_value = {"detail": "Not found"}
        
        client._client = AsyncMock()
        client._client.request = AsyncMock(return_value=mock_response)
        
        with pytest.raises(APIError, match="Not found") as exc_info:
            await client.health_check()
        
        assert exc_info.value.status_code == 404
    
    @pytest.mark.asyncio
    async def test_request_network_error(self, client):
        """Test network error handling."""
        client._client = AsyncMock()
        client._client.request = AsyncMock(side_effect=httpx.RequestError("Connection failed"))
        
        with pytest.raises(NomosClientError, match="Request failed"):
            await client.health_check()
    
    @pytest.mark.asyncio
    async def test_create_session(self, client, mock_response):
        """Test session creation."""
        mock_response.json.return_value = {
            "session_id": "test-session-123",
            "message": {"status": "created"}
        }
        
        client._client = AsyncMock()
        client._client.request = AsyncMock(return_value=mock_response)
        
        result = await client.create_session(initiate=True)
        
        assert isinstance(result, SessionResponse)
        assert result.session_id == "test-session-123"
        assert result.message == {"status": "created"}
        
        client._client.request.assert_called_once_with(
            method="POST",
            url="http://test-server:8000/session",
            headers={"Content-Type": "application/json"},
            json=None,
            params={"initiate": "true"},
        )
    
    @pytest.mark.asyncio
    async def test_send_message(self, client, mock_response):
        """Test sending a message."""
        mock_response.json.return_value = {
            "session_id": "test-session-123",
            "message": {"response": "Hello back!"}
        }
        
        client._client = AsyncMock()
        client._client.request = AsyncMock(return_value=mock_response)
        
        result = await client.send_message("test-session-123", "Hello!")
        
        assert isinstance(result, SessionResponse)
        assert result.session_id == "test-session-123"
        assert result.message == {"response": "Hello back!"}
        
        client._client.request.assert_called_once_with(
            method="POST",
            url="http://test-server:8000/session/test-session-123/message",
            headers={"Content-Type": "application/json"},
            json={"content": "Hello!"},
            params=None,
        )
    
    @pytest.mark.asyncio
    async def test_chat(self, client, mock_response):
        """Test chat endpoint."""
        mock_state = State(
            session_id="test-123",
            current_step_id="start",
            history=[],
        )
        
        mock_response.json.return_value = {
            "response": {"action": "respond", "response": "Hello!"},
            "tool_output": None,
            "session_data": mock_state.model_dump()
        }
        
        client._client = AsyncMock()
        client._client.request = AsyncMock(return_value=mock_response)
        
        result = await client.chat(user_input="Hi there!", verbose=True)
        
        assert isinstance(result, ChatResponse)
        assert result.response == {"action": "respond", "response": "Hello!"}
        assert result.tool_output is None
        assert isinstance(result.session_data, State)
        
        client._client.request.assert_called_once_with(
            method="POST",
            url="http://test-server:8000/chat",
            headers={"Content-Type": "application/json"},
            json={"user_input": "Hi there!"},
            params={"verbose": "true"},
        )
    
    @pytest.mark.asyncio
    async def test_quick_chat(self, client, mock_response):
        """Test quick chat convenience method."""
        mock_state = State(
            session_id="test-123",
            current_step_id="start",
            history=[],
        )
        
        mock_response.json.return_value = {
            "response": {"response": "Quick response!"},
            "tool_output": None,
            "session_data": mock_state.model_dump()
        }
        
        client._client = AsyncMock()
        client._client.request = AsyncMock(return_value=mock_response)
        
        result = await client.quick_chat("Hello!")
        
        assert result == "Quick response!"


class TestNomosClientSync:
    """Test synchronous client functionality."""
    
    def test_sync_client_initialization(self):
        """Test sync client initialization."""
        client = NomosClientSync(
            "http://localhost:8000",
            auth=AuthConfig(auth_type="jwt", token="test"),
            timeout=60.0
        )
        
        assert client.base_url == "http://localhost:8000"
        assert client.auth.auth_type == "jwt"
        assert client.timeout == 60.0
    
    def test_sync_health_check(self):
        """Test sync health check."""
        client = NomosClientSync("http://test")
        
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "healthy"}
        
        client._client = MagicMock()
        client._client.request = MagicMock(return_value=mock_response)
        
        result = client.health_check()
        assert result == {"status": "healthy"}
    
    def test_sync_context_manager(self):
        """Test sync client as context manager."""
        with NomosClientSync("http://test") as client:
            assert client.base_url == "http://test"
            assert hasattr(client, '_client')


if __name__ == "__main__":
    pytest.main([__file__])
