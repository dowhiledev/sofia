"""Tests for the security features of the Nomos API."""

import asyncio
import os
import shutil
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import httpx
import jwt
import pytest
import redis.asyncio as redis
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

from nomos.api.security import SecurityManager, generate_jwt_token, setup_security_middleware
from nomos.config import ServerSecurity

# Set dummy environment variables to avoid OpenAI API key requirement
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-for-testing")
os.environ.setdefault("CSRF_SECRET_KEY", "test-csrf-secret-key-for-testing")

# Setup config file before imports - set CONFIG_PATH to point to our test config
test_dir = os.path.dirname(__file__)
config_source = os.path.join(test_dir, "fixtures", "config.agent.yaml")
config_dest = os.path.join(test_dir, "..", "config.agent.yaml")
os.environ["CONFIG_PATH"] = config_source
if os.path.exists(config_source) and not os.path.exists(config_dest):
    shutil.copy2(config_source, config_dest)


def teardown_module():
    """Cleanup module-level fixtures - remove temporary config file."""
    if os.path.exists(config_dest):
        os.remove(config_dest)


class TestSecurityManager:
    """Test SecurityManager class functionality."""

    @pytest.fixture
    def jwt_security_config(self):
        """Security config with JWT authentication enabled."""
        return ServerSecurity(
            enable_auth=True,
            auth_type="jwt",
            jwt_secret_key="test-secret-key",
            allowed_origins=["https://example.com"],
        )

    @pytest.fixture
    def api_key_security_config(self):
        """Security config with API key authentication enabled."""
        return ServerSecurity(
            enable_auth=True,
            auth_type="api_key",
            api_key_url="https://api.example.com/validate",
            allowed_origins=["https://example.com"],
        )

    @pytest.fixture
    def rate_limiting_config(self):
        """Security config with rate limiting enabled."""
        return ServerSecurity(
            enable_rate_limiting=True,
            redis_url="redis://localhost:6379",
            rate_limit_times=5,
            rate_limit_seconds=60,
        )

    @pytest.fixture
    def csrf_config(self):
        """Security config with CSRF protection enabled."""
        return ServerSecurity(
            enable_csrf_protection=True,
            csrf_secret_key="test-csrf-secret",
        )

    def test_security_manager_init(self, jwt_security_config):
        """Test SecurityManager initialization."""
        manager = SecurityManager(jwt_security_config)
        assert manager.config == jwt_security_config
        assert manager._http_client is not None

    @pytest.mark.asyncio
    async def test_security_manager_close(self, jwt_security_config):
        """Test SecurityManager cleanup."""
        manager = SecurityManager(jwt_security_config)
        # Mock the HTTP client close method
        manager._http_client.aclose = AsyncMock()

        await manager.close()
        manager._http_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_jwt_token_valid(self, jwt_security_config):
        """Test JWT token verification with valid token."""
        manager = SecurityManager(jwt_security_config)

        # Create a valid token
        payload = {"user_id": "123", "role": "user"}
        token = generate_jwt_token(payload, jwt_security_config.jwt_secret_key)

        result = await manager.verify_jwt_token(token)
        assert result["user_id"] == "123"
        assert result["role"] == "user"
        assert "exp" in result

    @pytest.mark.asyncio
    async def test_verify_jwt_token_expired(self, jwt_security_config):
        """Test JWT token verification with expired token."""
        manager = SecurityManager(jwt_security_config)

        # Create an expired token
        payload = {"user_id": "123", "exp": int(time.time()) - 3600}  # Expired 1 hour ago
        token = jwt.encode(payload, jwt_security_config.jwt_secret_key, algorithm="HS256")

        with pytest.raises(HTTPException) as exc_info:
            await manager.verify_jwt_token(token)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "expired" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_verify_jwt_token_invalid(self, jwt_security_config):
        """Test JWT token verification with invalid token."""
        manager = SecurityManager(jwt_security_config)

        # Invalid token
        invalid_token = "invalid.token.here"

        with pytest.raises(HTTPException) as exc_info:
            await manager.verify_jwt_token(invalid_token)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "invalid" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_verify_jwt_token_no_secret(self):
        """Test JWT token verification without secret key configured."""
        config = ServerSecurity(enable_auth=True, auth_type="jwt")  # No secret key
        manager = SecurityManager(config)

        with pytest.raises(HTTPException) as exc_info:
            await manager.verify_jwt_token("some.token.here")

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "secret key not configured" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_verify_api_key_valid(self, api_key_security_config):
        """Test API key verification with valid response."""
        manager = SecurityManager(api_key_security_config)

        # Mock the HTTP client response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"user_id": "123", "valid": True}

        manager._http_client.post = AsyncMock(return_value=mock_response)

        result = await manager.verify_api_key("valid-api-key")
        assert result["user_id"] == "123"
        assert result["valid"] is True

        # Verify the HTTP client was called correctly
        manager._http_client.post.assert_called_once_with(
            api_key_security_config.api_key_url,
            json={"api_key": "valid-api-key"},
            timeout=10.0,
        )

    @pytest.mark.asyncio
    async def test_verify_api_key_invalid(self, api_key_security_config):
        """Test API key verification with invalid key."""
        manager = SecurityManager(api_key_security_config)

        # Mock the HTTP client response for invalid key
        mock_response = Mock()
        mock_response.status_code = 401

        manager._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(HTTPException) as exc_info:
            await manager.verify_api_key("invalid-api-key")

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "invalid api key" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_verify_api_key_server_error(self, api_key_security_config):
        """Test API key verification with server error."""
        manager = SecurityManager(api_key_security_config)

        # Mock the HTTP client response for server error
        mock_response = Mock()
        mock_response.status_code = 500

        manager._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(HTTPException) as exc_info:
            await manager.verify_api_key("some-api-key")

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "validation failed" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_verify_api_key_timeout(self, api_key_security_config):
        """Test API key verification with timeout."""
        manager = SecurityManager(api_key_security_config)

        # Mock timeout exception
        manager._http_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        with pytest.raises(HTTPException) as exc_info:
            await manager.verify_api_key("some-api-key")

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "timeout" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_verify_api_key_no_url(self):
        """Test API key verification without URL configured."""
        config = ServerSecurity(enable_auth=True, auth_type="api_key")  # No URL
        manager = SecurityManager(config)

        with pytest.raises(HTTPException) as exc_info:
            await manager.verify_api_key("some-api-key")

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "url not configured" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_authenticate_no_auth(self):
        """Test authentication when authentication is disabled."""
        config = ServerSecurity(enable_auth=False)
        manager = SecurityManager(config)

        result = await manager.authenticate(None)
        assert result == {"authenticated": False}

    @pytest.mark.asyncio
    async def test_authenticate_no_credentials(self, jwt_security_config):
        """Test authentication without credentials when auth is required."""
        manager = SecurityManager(jwt_security_config)

        with pytest.raises(HTTPException) as exc_info:
            await manager.authenticate(None)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "authentication required" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_authenticate_jwt_success(self, jwt_security_config):
        """Test successful JWT authentication."""
        manager = SecurityManager(jwt_security_config)

        # Create valid credentials
        payload = {"user_id": "123", "role": "user"}
        token = generate_jwt_token(payload, jwt_security_config.jwt_secret_key)
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        result = await manager.authenticate(credentials)
        assert result["authenticated"] is True
        assert result["user"]["user_id"] == "123"
        assert result["user"]["role"] == "user"

    @pytest.mark.asyncio
    async def test_authenticate_api_key_success(self, api_key_security_config):
        """Test successful API key authentication."""
        manager = SecurityManager(api_key_security_config)

        # Mock the HTTP client response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"user_id": "123", "valid": True}

        manager._http_client.post = AsyncMock(return_value=mock_response)

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid-key")
        result = await manager.authenticate(credentials)

        assert result["authenticated"] is True
        assert result["user"]["user_id"] == "123"

    @pytest.mark.asyncio
    async def test_authenticate_invalid_auth_type(self):
        """Test authentication with invalid auth type."""
        config = ServerSecurity(enable_auth=True, auth_type="jwt")
        # Manually set invalid auth type after creation to bypass Pydantic validation
        config.auth_type = "invalid_type"

        manager = SecurityManager(config)
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="token")

        with pytest.raises(HTTPException) as exc_info:
            await manager.authenticate(credentials)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "invalid authentication type" in exc_info.value.detail.lower()


class TestJWTTokenGeneration:
    """Test JWT token generation functionality."""

    def test_generate_jwt_token_default_expiry(self):
        """Test JWT token generation with default expiry."""
        payload = {"user_id": "123", "role": "user"}
        secret_key = "test-secret"

        token = generate_jwt_token(payload, secret_key)

        # Decode and verify
        decoded = jwt.decode(token, secret_key, algorithms=["HS256"])
        assert decoded["user_id"] == "123"
        assert decoded["role"] == "user"
        assert "exp" in decoded

        # Check expiry is roughly 24 hours from now
        exp_time = datetime.fromtimestamp(decoded["exp"], timezone.utc)
        now = datetime.now(timezone.utc)
        assert (exp_time - now).total_seconds() > 23 * 3600  # More than 23 hours

    def test_generate_jwt_token_custom_expiry(self):
        """Test JWT token generation with custom expiry."""
        payload = {"user_id": "123", "role": "user"}
        secret_key = "test-secret"
        expires_delta = timedelta(hours=1)

        token = generate_jwt_token(payload, secret_key, expires_delta)

        # Decode and verify
        decoded = jwt.decode(token, secret_key, algorithms=["HS256"])
        assert decoded["user_id"] == "123"
        assert decoded["role"] == "user"

        # Check expiry is roughly 1 hour from now
        exp_time = datetime.fromtimestamp(decoded["exp"], timezone.utc)
        now = datetime.now(timezone.utc)
        time_diff = (exp_time - now).total_seconds()
        assert 3500 < time_diff < 3700  # Between 58-62 minutes


class TestSecurityMiddleware:
    """Test security middleware setup functionality."""

    def test_setup_security_middleware_cors(self):
        """Test CORS middleware setup."""
        from fastapi import FastAPI

        app = FastAPI()
        config = ServerSecurity(allowed_origins=["https://example.com", "https://test.com"])

        setup_security_middleware(app, config)

        # Check that CORS middleware was added
        cors_middleware = None
        for middleware in app.user_middleware:
            if "CORSMiddleware" in str(middleware.cls):
                cors_middleware = middleware
                break

        assert cors_middleware is not None

    def test_setup_security_middleware_csrf(self):
        """Test CSRF middleware setup."""
        from fastapi import FastAPI

        app = FastAPI()
        config = ServerSecurity(enable_csrf_protection=True, csrf_secret_key="test-csrf-secret")

        setup_security_middleware(app, config)

        # Check that CSRF middleware was added
        csrf_middleware = None
        for middleware in app.user_middleware:
            if "CSRFMiddleware" in str(middleware.cls):
                csrf_middleware = middleware
                break

        assert csrf_middleware is not None

    def test_setup_security_middleware_no_csrf_without_secret(self):
        """Test CSRF middleware is not added without secret key."""
        from fastapi import FastAPI

        app = FastAPI()
        config = ServerSecurity(
            enable_csrf_protection=True
            # No csrf_secret_key
        )

        setup_security_middleware(app, config)

        # Check that CSRF middleware was NOT added
        csrf_middleware = None
        for middleware in app.user_middleware:
            if "CSRFMiddleware" in str(middleware.cls):
                csrf_middleware = middleware
                break

        assert csrf_middleware is None


class TestAPISecurityIntegration:
    """Test security integration with API endpoints."""

    def setup_method(self):
        """Setup for each test method."""
        # Mock the OpenAI import and agent to avoid config file dependency
        self.openai_patcher = patch("nomos.llms.openai.OpenAI")
        self.agent_patcher = patch("nomos.api.agent.agent")
        self.openai_patcher.start()
        self.agent_patcher.start()

    def teardown_method(self):
        """Cleanup for each test method."""
        self.openai_patcher.stop()
        self.agent_patcher.stop()

    def test_authenticate_request_function_no_auth(self):
        """Test authenticate_request function when auth is disabled."""
        from fastapi import Request

        from nomos.api.app import authenticate_request

        with (
            patch("nomos.api.app.config") as mock_config,
            patch("nomos.api.app.security_manager") as mock_security_manager,
        ):
            mock_config.server.security.enable_auth = False
            mock_security_manager = None  # noqa

            # Create a mock request
            mock_request = MagicMock(spec=Request)

            # Test that no authentication is required
            async def test_no_auth():
                result = await authenticate_request(mock_request)
                assert result == {"authenticated": False}

            import asyncio

            asyncio.run(test_no_auth())

    def test_authenticate_request_function_missing_credentials(self):
        """Test authenticate_request function with missing credentials."""
        from fastapi import HTTPException, Request

        from nomos.api.app import authenticate_request

        with (
            patch("nomos.api.app.config") as mock_config,
            patch("nomos.api.app.security_manager") as mock_security_manager,
        ):
            mock_config.server.security.enable_auth = True
            mock_security_manager = MagicMock()  # noqa

            # Create a mock request without authorization header
            mock_request = MagicMock(spec=Request)
            mock_request.headers.get.return_value = None

            # Test that authentication fails without credentials
            async def test_missing_auth():
                with pytest.raises(HTTPException) as exc_info:
                    await authenticate_request(mock_request)
                assert exc_info.value.status_code == 401

            import asyncio

            asyncio.run(test_missing_auth())

    def test_authenticate_request_function_with_valid_token(self):
        """Test authenticate_request function with valid token."""
        from fastapi import Request

        from nomos.api.app import authenticate_request

        with (
            patch("nomos.api.app.config") as mock_config,
            patch("nomos.api.app.security_manager") as mock_security_manager,
        ):
            mock_config.server.security.enable_auth = True
            mock_security_manager.authenticate = AsyncMock(
                return_value={"authenticated": True, "user": {"user_id": "123"}}
            )

            # Create a mock request with authorization header
            mock_request = MagicMock(spec=Request)
            mock_request.headers.get.return_value = "Bearer valid-token"

            # Test successful authentication
            async def test_valid_auth():
                result = await authenticate_request(mock_request)
                assert result["authenticated"] is True
                assert result["user"]["user_id"] == "123"

            import asyncio

            asyncio.run(test_valid_auth())

    def test_health_endpoint_no_auth_required(self):
        """Test that health endpoint doesn't require authentication."""
        # Import the existing app (which should have no auth enabled by default)
        from nomos.api.app import app

        client = TestClient(app)

        response = client.get("/health")
        assert response.status_code == 200
        assert "status" in response.json()

    def test_security_middleware_setup_function(self):
        """Test security middleware setup function directly."""
        from fastapi import FastAPI

        from nomos.api.security import setup_security_middleware
        from nomos.config import ServerSecurity

        app = FastAPI()
        config = ServerSecurity(
            allowed_origins=["https://example.com"],
            enable_csrf_protection=True,
            csrf_secret_key="test-csrf-secret-32-characters",
        )

        setup_security_middleware(app, config)

        # Check that middleware was added
        assert len(app.user_middleware) > 0

        # Check for CORS middleware
        cors_middleware_found = False
        csrf_middleware_found = False

        for middleware in app.user_middleware:
            if "CORSMiddleware" in str(middleware.cls):
                cors_middleware_found = True
            if "CSRFMiddleware" in str(middleware.cls):
                csrf_middleware_found = True

        assert cors_middleware_found, "CORS middleware should be added"
        assert csrf_middleware_found, "CSRF middleware should be added"

    def test_jwt_token_generation_function(self):
        """Test JWT token generation function directly."""
        import jwt

        from nomos.api.security import generate_jwt_token

        payload = {"user_id": "123", "role": "test"}
        secret_key = "test-secret-key"

        token = generate_jwt_token(payload, secret_key)

        # Verify the generated token is valid
        decoded = jwt.decode(token, secret_key, algorithms=["HS256"])
        assert decoded["user_id"] == "123"
        assert decoded["role"] == "test"
        assert "exp" in decoded


class TestRateLimitingIntegration:
    """Test rate limiting functionality integration."""

    @pytest.mark.asyncio
    async def test_rate_limiting_redis_connection(self):
        """Test rate limiting Redis connection setup."""
        # This test would require an actual Redis instance
        # In a real test environment, you might use a Redis test container

        # Mock redis connection for testing
        with patch("redis.asyncio.from_url") as mock_redis:
            mock_redis_client = AsyncMock()
            mock_redis.return_value = mock_redis_client

            # Test Redis URL configuration
            config = ServerSecurity(
                enable_rate_limiting=True,
                redis_url="redis://localhost:6379",
                rate_limit_times=10,
                rate_limit_seconds=60,
            )

            # This would be called during app startup
            redis.from_url(config.redis_url, encoding="utf-8", decode_responses=True)

            # Verify Redis client was created with correct parameters
            mock_redis.assert_called_once_with(
                config.redis_url, encoding="utf-8", decode_responses=True
            )

    def test_rate_limiting_dependency_creation(self):
        """Test rate limiting dependency creation."""
        from fastapi_limiter.depends import RateLimiter

        # Test that rate limiter dependency is created with correct parameters
        rate_limiter = RateLimiter(times=50, seconds=60)

        # Verify the rate limiter was created
        assert rate_limiter is not None
        # Note: Testing the actual rate limiting behavior would require
        # integration with FastAPI Limiter and Redis


class TestSecurityConfiguration:
    """Test various security configuration scenarios."""

    def test_minimal_security_config(self):
        """Test minimal security configuration."""
        config = ServerSecurity()

        assert config.enable_auth is False
        assert config.enable_rate_limiting is False
        assert config.enable_csrf_protection is False
        assert config.allowed_origins == ["*"]

    def test_full_security_config(self):
        """Test full security configuration."""
        config = ServerSecurity(
            enable_auth=True,
            auth_type="jwt",
            jwt_secret_key="secret",
            enable_rate_limiting=True,
            redis_url="redis://localhost:6379",
            rate_limit_times=100,
            rate_limit_seconds=60,
            enable_csrf_protection=True,
            csrf_secret_key="csrf-secret",
            allowed_origins=["https://example.com"],
            enable_token_endpoint=True,
        )

        assert config.enable_auth is True
        assert config.auth_type == "jwt"
        assert config.jwt_secret_key == "secret"
        assert config.enable_rate_limiting is True
        assert config.redis_url == "redis://localhost:6379"
        assert config.rate_limit_times == 100
        assert config.rate_limit_seconds == 60
        assert config.enable_csrf_protection is True
        assert config.csrf_secret_key == "csrf-secret"
        assert config.allowed_origins == ["https://example.com"]
        assert config.enable_token_endpoint is True

    def test_api_key_security_config(self):
        """Test API key security configuration."""
        config = ServerSecurity(
            enable_auth=True, auth_type="api_key", api_key_url="https://api.example.com/validate"
        )

        assert config.enable_auth is True
        assert config.auth_type == "api_key"
        assert config.api_key_url == "https://api.example.com/validate"


class TestSecurityErrorHandling:
    """Test security error handling scenarios."""

    @pytest.fixture
    def api_key_security_config(self):
        """Security config with API key authentication enabled."""
        return ServerSecurity(
            enable_auth=True,
            auth_type="api_key",
            api_key_url="https://api.example.com/validate",
            allowed_origins=["https://example.com"],
        )

    @pytest.mark.asyncio
    async def test_http_client_connection_error(self, api_key_security_config):
        """Test handling of HTTP client connection errors."""
        manager = SecurityManager(api_key_security_config)

        # Mock connection error
        manager._http_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))

        with pytest.raises(HTTPException) as exc_info:
            await manager.verify_api_key("some-api-key")

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "validation error" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_unexpected_api_validation_error(self, api_key_security_config):
        """Test handling of unexpected API validation errors."""
        manager = SecurityManager(api_key_security_config)

        # Mock unexpected exception
        manager._http_client.post = AsyncMock(side_effect=Exception("Unexpected error"))

        with pytest.raises(HTTPException) as exc_info:
            await manager.verify_api_key("some-api-key")

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "unexpected error" in exc_info.value.detail.lower()

    def test_jwt_token_with_wrong_secret(self):
        """Test JWT token verification with wrong secret key."""
        config = ServerSecurity(enable_auth=True, auth_type="jwt", jwt_secret_key="correct-secret")
        manager = SecurityManager(config)

        # Create token with different secret
        payload = {"user_id": "123"}
        token = generate_jwt_token(payload, "wrong-secret")

        asyncio.run(self._test_jwt_wrong_secret(manager, token))

    async def _test_jwt_wrong_secret(self, manager, token):
        """Helper method for async JWT wrong secret test."""
        with pytest.raises(HTTPException) as exc_info:
            await manager.verify_jwt_token(token)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "invalid token" in exc_info.value.detail.lower()


class TestSecurityBestPractices:
    """Test security best practices and edge cases."""

    def test_token_expiry_validation(self):
        """Test that tokens have reasonable expiry times."""
        payload = {"user_id": "123"}
        secret_key = "test-secret"

        # Test default expiry (24 hours)
        token = generate_jwt_token(payload, secret_key)
        decoded = jwt.decode(token, secret_key, algorithms=["HS256"])

        exp_time = datetime.fromtimestamp(decoded["exp"], timezone.utc)
        now = datetime.now(timezone.utc)
        time_diff = (exp_time - now).total_seconds()

        # Should be close to 24 hours (86400 seconds)
        assert 86300 < time_diff < 86500

    def test_csrf_token_configuration(self):
        """Test CSRF token configuration options."""
        config = ServerSecurity(
            enable_csrf_protection=True, csrf_secret_key="test-csrf-secret-key-minimum-32-chars"
        )

        assert config.enable_csrf_protection is True
        assert len(config.csrf_secret_key) >= 32  # Should be at least 32 characters

    def test_cors_origin_validation(self):
        """Test CORS origin configuration."""
        # Production-like configuration
        config = ServerSecurity(allowed_origins=["https://example.com", "https://app.example.com"])

        assert "*" not in config.allowed_origins  # Should not allow all origins in production
        assert all(origin.startswith("https://") for origin in config.allowed_origins)

    def test_development_vs_production_config(self):
        """Test differences between development and production configurations."""
        # Development config
        dev_config = ServerSecurity(
            enable_auth=False, allowed_origins=["*"], enable_token_endpoint=True
        )

        # Production config
        prod_config = ServerSecurity(
            enable_auth=True,
            auth_type="jwt",
            jwt_secret_key="production-secret-key",
            allowed_origins=["https://production.example.com"],
            enable_csrf_protection=True,
            csrf_secret_key="production-csrf-secret-key",
            enable_rate_limiting=True,
            enable_token_endpoint=False,  # Should be disabled in production
        )

        # Development should be more permissive
        assert dev_config.enable_auth is False
        assert "*" in dev_config.allowed_origins
        assert dev_config.enable_token_endpoint is True

        # Production should be more restrictive
        assert prod_config.enable_auth is True
        assert "*" not in prod_config.allowed_origins
        assert prod_config.enable_csrf_protection is True
        assert prod_config.enable_rate_limiting is True
        assert prod_config.enable_token_endpoint is False
