"""
Nomos Client - A Python client for connecting to Nomos Agent API servers.

This client provides a simple and typed interface to interact with Nomos agents
running on remote servers, supporting both stateful sessions and stateless chat modes.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
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
        data = await self._client._request("POST", "/sessions", params=params)
        return SessionResponse(**data)
    
    async def next(self, session_id: str, query: str) -> Message:
        """
        Send a message to an existing session.
        
        Args:
            session_id: The session ID
            query: The user's message/query
            
        Returns:
            Message with the agent's response
            
        Raises:
            AuthenticationError: If authentication fails
            APIError: If the API request fails
        """
        request = Message(content=query)
        data = await self._client._request(
            "POST",
            f"/sessions/{session_id}/message",
            json_data=request.model_dump(),
        )
        return Message(**data)
    
    async def get_history(self, session_id: str) -> State:
        """
        Get the conversation history for a session.
        
        Args:
            session_id: The session ID
            
        Returns:
            State object containing the session history
            
        Raises:
            AuthenticationError: If authentication fails
            APIError: If the API request fails
        """
        data = await self._client._request("GET", f"/sessions/{session_id}")
        return State(**data)
    
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
        return await self._client._request("DELETE", f"/sessions/{session_id}")


class ChatAPISync:
    """Synchronous Chat API namespace for stateless chat operations."""
    
    def __init__(self, client: "NomosClientSync"):
        self._client = client
    
    def next(self, query: str, session_data: Optional[State] = None) -> ChatResponse:
        """
        Send a chat message with optional session data.
        
        Args:
            query: The user's message/query
            session_data: Optional session state for stateless chat
            
        Returns:
            ChatResponse with agent response and updated session data
        """
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
        data = self._client._request("POST", "/sessions", params=params)
        return SessionResponse(**data)
    
    def next(self, session_id: str, query: str) -> Message:
        """Send a message to an existing session."""
        request = Message(content=query)
        data = self._client._request(
            "POST",
            f"/sessions/{session_id}/message",
            json_data=request.model_dump(),
        )
        return Message(**data)
    
    def get_history(self, session_id: str) -> State:
        """Get the conversation history for a session."""
        data = self._client._request("GET", f"/sessions/{session_id}")
        return State(**data)
    
    def end(self, session_id: str) -> Dict[str, Any]:
        """End a session."""
        return self._client._request("DELETE", f"/sessions/{session_id}")


class NomosClientSync:


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

    auth_type: str = Field(default="none", description="Authentication type: 'jwt', 'api_key', or 'none'")
    token: Optional[str] = Field(default=None, description="JWT token or API key")


class NomosClient:
    """
    A client for interacting with Nomos Agent API servers.

    This client supports multiple authentication methods, session management,
    and both stateful and stateless interaction modes.

    Examples:
        Basic usage with no authentication:
        ```python
        client = NomosClient("http://localhost:8000")
        response = await client.chat("Hello!")
        ```

        With JWT authentication:
        ```python
        auth = AuthConfig(auth_type="jwt", token="your-jwt-token")
        client = NomosClient("http://localhost:8000", auth=auth)
        ```

        Session management:
        ```python
        session = await client.create_session(initiate=True)
        response = await client.send_message(session.session_id, "Hello!")
        history = await client.get_session_history(session.session_id)
        await client.end_session(session.session_id)
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
        headers = {
            "Content-Type": "application/json",
            **self.custom_headers,
        }

        # Add authentication header if configured
        if self.auth.auth_type != "none" and self.auth.token:
            headers["Authorization"] = f"Bearer {self.auth.token}"

        return headers

    def _build_url(self, endpoint: str) -> str:
        """Build full URL for an endpoint."""
        return urljoin(self.base_url + "/", endpoint.lstrip("/"))

    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to the API.

        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            endpoint: API endpoint
            json_data: JSON data for request body
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
                raise AuthenticationError(
                    f"Authentication failed: {response.text}"
                )

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
            Health status information

        Raises:
            NomosClientError: If the health check fails
        """
        return await self._request("GET", "/health")

    # Session Management Methods

    async def create_session(self, initiate: bool = False) -> SessionResponse:
        """
        Create a new session.

        Args:
            initiate: If True, the agent will send an initial message

        Returns:
            SessionResponse with session_id and initial message (if initiated)

        Raises:
            AuthenticationError: If authentication fails
            APIError: If the API request fails
        """
        params = {"initiate": "true"} if initiate else {}
        data = await self._request("POST", "/session", params=params)
        return SessionResponse(**data)

    async def send_message(self, session_id: str, message: str) -> SessionResponse:
        """
        Send a message to an existing session.

        Args:
            session_id: ID of the session
            message: Message content to send

        Returns:
            SessionResponse with the agent's response

        Raises:
            AuthenticationError: If authentication fails
            APIError: If the session is not found or API request fails
        """
        message_obj = Message(content=message)
        data = await self._request(
            "POST",
            f"/session/{session_id}/message",
            json_data=message_obj.model_dump(),
        )
        return SessionResponse(**data)

    async def get_session_history(self, session_id: str) -> State:
        """
        Get the conversation history for a session.

        Args:
            session_id: ID of the session

        Returns:
            SessionHistoryResponse with conversation history

        Raises:
            AuthenticationError: If authentication fails
            APIError: If the session is not found or API request fails
        """
        data = await self._request("GET", f"/session/{session_id}/history")
        return State(**data)

    async def end_session(self, session_id: str) -> Dict[str, str]:
        """
        End and cleanup a session.

        Args:
            session_id: ID of the session to end

        Returns:
            Confirmation message

        Raises:
            AuthenticationError: If authentication fails
            APIError: If the session is not found or API request fails
        """
        return await self._request("DELETE", f"/session/{session_id}")

    # Stateless Chat Methods

    async def chat(
        self,
        user_input: Optional[str] = None,
        session_data: Optional[State] = None,
        verbose: bool = False,
    ) -> ChatResponse:
        """
        Send a chat message using the stateless chat endpoint.

        This method allows for client-side session management where session state
        is maintained by the client and passed with each request.

        Args:
            user_input: User's message (None for session initialization)
            session_data: Current session state (None for new session)
            verbose: If True, include additional debug information

        Returns:
            ChatResponse with agent response and updated session state

        Raises:
            AuthenticationError: If authentication fails
            APIError: If the API request fails
        """
        request = ChatRequest(user_input=user_input, session_data=session_data)
        params = {"verbose": "true"} if verbose else {}

        data = await self._request(
            "POST",
            "/chat",
            json_data=request.model_dump(exclude_none=True),
            params=params,
        )
        return ChatResponse(**data)

    # Convenience Methods

    async def quick_chat(self, message: str) -> str:
        """
        Send a quick chat message and return just the response text.

        This is a convenience method for simple one-off interactions.

        Args:
            message: Message to send

        Returns:
            The agent's response as a string

        Raises:
            AuthenticationError: If authentication fails
            APIError: If the API request fails
        """
        response = await self.chat(user_input=message)
        
        # Extract response text from the response dict
        response_dict = response.response
        if isinstance(response_dict, dict):
            return (
                response_dict.get("response") or
                response_dict.get("content") or
                response_dict.get("message") or
                str(response_dict)
            )
        return str(response_dict)

    async def start_conversation(self) -> ChatResponse:
        """
        Start a new conversation and get the initial agent response.

        Returns:
            ChatResponse with initial agent message and session state
        """
        return await self.chat(user_input="")

    async def continue_conversation(
        self, message: str, session_data: State
    ) -> ChatResponse:
        """
        Continue an existing conversation.

        Args:
            message: User's message
            session_data: Current session state from previous response

        Returns:
            ChatResponse with agent response and updated session state
        """
        return await self.chat(user_input=message, session_data=session_data)


# Synchronous wrapper for compatibility
class NomosClientSync:
    """
    Synchronous wrapper for NomosClient.

    This provides a synchronous interface using httpx's sync client for scenarios
    where async/await cannot be used.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        auth: Optional[AuthConfig] = None,
        timeout: float = 30.0,
        headers: Optional[Dict[str, str]] = None,
    ):
        """Initialize the synchronous Nomos client with the same parameters as NomosClient."""
        self.base_url = base_url.rstrip("/")
        self.auth = auth or AuthConfig()
        self.timeout = timeout
        self.custom_headers = headers or {}

        # Initialize HTTP client
        self._client = httpx.Client(timeout=timeout)

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
        headers = {
            "Content-Type": "application/json",
            **self.custom_headers,
        }

        if self.auth.auth_type != "none" and self.auth.token:
            headers["Authorization"] = f"Bearer {self.auth.token}"

        return headers

    def _build_url(self, endpoint: str) -> str:
        """Build full URL for an endpoint."""
        return urljoin(self.base_url + "/", endpoint.lstrip("/"))

    def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make a synchronous HTTP request."""
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

    def create_session(self, initiate: bool = False) -> SessionResponse:
        """Create a new session."""
        params = {"initiate": "true"} if initiate else {}
        data = self._request("POST", "/session", params=params)
        return SessionResponse(**data)

    def send_message(self, session_id: str, message: str) -> SessionResponse:
        """Send a message to an existing session."""
        message_obj = Message(content=message)
        data = self._request(
            "POST",
            f"/session/{session_id}/message",
            json_data=message_obj.model_dump(),
        )
        return SessionResponse(**data)

    def get_session_history(self, session_id: str) -> State:
        """Get the conversation history for a session."""
        data = self._request("GET", f"/session/{session_id}/history")
        return State(**data)

    def end_session(self, session_id: str) -> Dict[str, str]:
        """End and cleanup a session."""
        return self._request("DELETE", f"/session/{session_id}")

    def chat(
        self,
        user_input: Optional[str] = None,
        session_data: Optional[State] = None,
        verbose: bool = False,
    ) -> ChatResponse:
        """Send a chat message using the stateless chat endpoint."""
        request = ChatRequest(user_input=user_input, session_data=session_data)
        params = {"verbose": "true"} if verbose else {}

        data = self._request(
            "POST",
            "/chat",
            json_data=request.model_dump(exclude_none=True),
            params=params,
        )
        return ChatResponse(**data)

    def quick_chat(self, message: str) -> str:
        """Send a quick chat message and return just the response text."""
        response = self.chat(user_input=message)
        
        response_dict = response.response
        if isinstance(response_dict, dict):
            return (
                response_dict.get("response") or
                response_dict.get("content") or
                response_dict.get("message") or
                str(response_dict)
            )
        return str(response_dict)

    def start_conversation(self) -> ChatResponse:
        """Start a new conversation and get the initial agent response."""
        return self.chat(user_input="")

    def continue_conversation(self, message: str, session_data: State) -> ChatResponse:
        """Continue an existing conversation."""
        return self.chat(user_input=message, session_data=session_data)


__all__ = [
    "NomosClient",
    "NomosClientSync",
    "AuthConfig",
    "Message",
    "SessionResponse",
    "ChatRequest",
    "ChatResponse",
    "SessionHistoryResponse",
    "NomosClientError",
    "AuthenticationError",
    "APIError",
]
