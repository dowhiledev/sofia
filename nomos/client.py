"""
Nomos Client - A Python client for connecting to Nomos Agent API servers.

This client provides a simple and typed interface to interact with Nomos agents
running on remote servers, supporting both stateful sessions and stateless chat modes.
"""

import json
from datetime import datetime
from typing import Any, Dict, Literal, Optional
from urllib.parse import urljoin

import httpx
from pydantic import BaseModel, Field

from .api.models import ChatRequest, ChatResponse, Message, SessionResponse
from .models.agent import State


def json_serializer(obj: Any) -> Any:
    """Custom JSON serializer for datetime objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


class NomosClientError(Exception):
    """Base exception for Nomos client errors."""

    pass


class AuthenticationError(NomosClientError):
    """Authentication related errors."""

    pass


class APIError(NomosClientError):
    """API response errors."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class AuthConfig(BaseModel):
    """Authentication configuration."""

    auth_type: Literal["none", "jwt", "api_key"] = Field(
        default="none", description="Authentication type: 'jwt', 'api_key', or 'none'"
    )
    token: Optional[str] = Field(default=None, description="JWT token or API key")


class ChatAPI:
    """Chat API namespace for stateless chat operations."""

    def __init__(self, client: "NomosClient"):
        self._client = client

    async def next(self, query: str, session_data: Optional[State] = None) -> ChatResponse:
        """
        Send a chat message with optional session data.

        Args:
            query: The user's message/query
            session_data: Optional session state for stateless chat

        Returns:
            ChatResponse with agent response and updated session data

        Raises:
            AuthenticationError: If authentication fails
            APIError: If the API request fails
        """
        request = ChatRequest(user_input=query, session_data=session_data)
        data = await self._client._request(
            "POST",
            "/chat",
            json_data=request.model_dump(exclude_none=True),
        )
        return ChatResponse(**data)


class SessionAPI:
    """Session API namespace for stateful session operations."""

    def __init__(self, client: "NomosClient"):
        self._client = client

    async def init(self, initiate: bool = False) -> SessionResponse:
        """
        Create a new session.

        Args:
            initiate: Whether to initiate the session with a greeting

        Returns:
            SessionResponse with session ID and optional initial message

        Raises:
            AuthenticationError: If authentication fails
            APIError: If the API request fails
        """
        params = {"initiate": "true"} if initiate else {}
        data = await self._client._request("POST", "/session", params=params)
        return SessionResponse(**data)

    async def next(self, session_id: str, query: str) -> SessionResponse:
        """
        Send a message to an existing session.

        Args:
            session_id: The session ID
            query: The user's message/query

        Returns:
            SessionResponse with the agent's response

        Raises:
            AuthenticationError: If authentication fails
            APIError: If the API request fails
        """
        request = Message(content=query)
        data = await self._client._request(
            "POST",
            f"/session/{session_id}/message",
            json_data=request.model_dump(),
        )
        return SessionResponse(**data)

    async def get_history(self, session_id: str) -> Dict[str, Any]:
        """
        Get the conversation history for a session.

        Args:
            session_id: The session ID

        Returns:
            Dictionary containing session_id and history

        Raises:
            AuthenticationError: If authentication fails
            APIError: If the API request fails
        """
        data = await self._client._request("GET", f"/session/{session_id}/history")
        return data

    async def end(self, session_id: str) -> Dict[str, Any]:
        """
        End a session.

        Args:
            session_id: The session ID to end

        Returns:
            Response dictionary with confirmation message

        Raises:
            AuthenticationError: If authentication fails
            APIError: If the API request fails
        """
        return await self._client._request("DELETE", f"/session/{session_id}")


class NomosClient:
    """
    Asynchronous client for connecting to Nomos Agent API servers.

    This client provides a typed interface for interacting with Nomos agents,
    supporting authentication, session management, and stateless chat.

    Examples:
        Basic usage:
        ```python
        async with NomosClient("http://localhost:8000") as client:
            response = await client.chat.next("Hello!")
        ```

        With authentication:
        ```python
        auth = AuthConfig(auth_type="jwt", token="your-jwt-token")
        async with NomosClient("http://localhost:8000", auth=auth) as client:
            response = await client.chat.next("Hello!")
        ```

        Session management:
        ```python
        session = await client.session.init(initiate=True)
        response = await client.session.next(session.session_id, "Hello!")
        history = await client.session.get_history(session.session_id)
        await client.session.end(session.session_id)
        ```
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        auth: Optional[AuthConfig] = None,
        timeout: float = 30.0,
        headers: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize the Nomos client.

        Args:
            base_url: Base URL of the Nomos API server
            auth: Authentication configuration
            timeout: Request timeout in seconds
            headers: Additional headers to include in requests
        """
        self.base_url = base_url.rstrip("/")
        self.auth = auth or AuthConfig()
        self.timeout = timeout
        self.custom_headers = headers or {}

        # Initialize HTTP client
        self._client = httpx.AsyncClient(timeout=timeout)

        # Initialize API namespaces
        self.chat = ChatAPI(self)
        self.session = SessionAPI(self)

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for requests including authentication."""
        headers = {"Content-Type": "application/json", **self.custom_headers}

        if self.auth.auth_type == "jwt" and self.auth.token:
            headers["Authorization"] = f"Bearer {self.auth.token}"
        elif self.auth.auth_type == "api_key" and self.auth.token:
            headers["X-API-Key"] = self.auth.token

        return headers

    def _build_url(self, endpoint: str) -> str:
        """Build full URL for an endpoint."""
        return urljoin(self.base_url, endpoint.lstrip("/"))

    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to the API.

        Args:
            method: HTTP method
            endpoint: API endpoint
            json_data: JSON data to send
            params: Query parameters

        Returns:
            Response data as dictionary

        Raises:
            AuthenticationError: For authentication failures
            APIError: For API errors
            NomosClientError: For other client errors
        """
        url = self._build_url(endpoint)
        headers = self._get_headers()

        try:
            # Custom JSON serialization to handle datetime objects
            if json_data is not None:
                json_content = json.dumps(json_data, default=json_serializer)
                headers["Content-Type"] = "application/json"
                response = await self._client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    content=json_content,
                    params=params,
                )
            else:
                response = await self._client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                )

            # Handle authentication errors
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed: {response.text}")

            # Handle other HTTP errors
            if not response.is_success:
                try:
                    error_data = response.json()
                    error_message = error_data.get("detail", f"HTTP {response.status_code}")
                except (json.JSONDecodeError, ValueError):
                    error_message = f"HTTP {response.status_code}: {response.text}"

                raise APIError(error_message, response.status_code)

            return response.json()

        except httpx.RequestError as e:
            raise NomosClientError(f"Request failed: {e}")

    async def health_check(self) -> Dict[str, Any]:
        """
        Check the health status of the API server.

        Returns:
            Health status dictionary

        Raises:
            NomosClientError: If the health check fails
        """
        return await self._request("GET", "/health")


class ChatAPISync:
    """Synchronous Chat API namespace for stateless chat operations."""

    def __init__(self, client: "NomosClientSync"):
        self._client = client

    def next(self, query: str, session_data: Optional[State] = None) -> ChatResponse:
        """Send a chat message with optional session data."""
        request = ChatRequest(user_input=query, session_data=session_data)
        data = self._client._request(
            "POST",
            "/chat",
            json_data=request.model_dump(exclude_none=True),
        )
        return ChatResponse(**data)


class SessionAPISync:
    """Synchronous Session API namespace for stateful session operations."""

    def __init__(self, client: "NomosClientSync"):
        self._client = client

    def init(self, initiate: bool = False) -> SessionResponse:
        """Create a new session."""
        params = {"initiate": "true"} if initiate else {}
        data = self._client._request("POST", "/session", params=params)
        return SessionResponse(**data)

    def next(self, session_id: str, query: str) -> SessionResponse:
        """Send a message to an existing session."""
        request = Message(content=query)
        data = self._client._request(
            "POST",
            f"/session/{session_id}/message",
            json_data=request.model_dump(),
        )
        return SessionResponse(**data)

    def get_history(self, session_id: str) -> Dict[str, Any]:
        """Get the conversation history for a session."""
        data = self._client._request("GET", f"/session/{session_id}/history")
        return data

    def end(self, session_id: str) -> Dict[str, Any]:
        """End a session."""
        return self._client._request("DELETE", f"/session/{session_id}")


class NomosClientSync:
    """
    Synchronous client for connecting to Nomos Agent API servers.

    This is the synchronous version of NomosClient for use in non-async contexts.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        auth: Optional[AuthConfig] = None,
        timeout: float = 30.0,
        headers: Optional[Dict[str, str]] = None,
    ):
        """Initialize the synchronous Nomos client."""
        self.base_url = base_url.rstrip("/")
        self.auth = auth or AuthConfig()
        self.timeout = timeout
        self.custom_headers = headers or {}

        # Initialize HTTP client
        self._client = httpx.Client(timeout=timeout)

        # Initialize API namespaces
        self.chat = ChatAPISync(self)
        self.session = SessionAPISync(self)

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for requests including authentication."""
        headers = {"Content-Type": "application/json", **self.custom_headers}

        if self.auth.auth_type == "jwt" and self.auth.token:
            headers["Authorization"] = f"Bearer {self.auth.token}"
        elif self.auth.auth_type == "api_key" and self.auth.token:
            headers["X-API-Key"] = self.auth.token

        return headers

    def _build_url(self, endpoint: str) -> str:
        """Build full URL for an endpoint."""
        return urljoin(self.base_url, endpoint.lstrip("/"))

    def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make an HTTP request to the API."""
        url = self._build_url(endpoint)
        headers = self._get_headers()

        try:
            # Custom JSON serialization to handle datetime objects
            if json_data is not None:
                json_content = json.dumps(json_data, default=json_serializer)
                headers["Content-Type"] = "application/json"
                response = self._client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    content=json_content,
                    params=params,
                )
            else:
                response = self._client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                )

            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed: {response.text}")

            if not response.is_success:
                try:
                    error_data = response.json()
                    error_message = error_data.get("detail", f"HTTP {response.status_code}")
                except (json.JSONDecodeError, ValueError):
                    error_message = f"HTTP {response.status_code}: {response.text}"

                raise APIError(error_message, response.status_code)

            return response.json()

        except httpx.RequestError as e:
            raise NomosClientError(f"Request failed: {e}")

    def health_check(self) -> Dict[str, Any]:
        """Check the health status of the API server."""
        return self._request("GET", "/health")
