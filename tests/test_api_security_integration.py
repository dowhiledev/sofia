"""Integration tests for API security features."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from nomos.api.security import SecurityManager, setup_security_middleware
from nomos.config import ServerSecurity


class TestSecurityIntegration:
    """Test security integration with configuration and components."""

    def test_security_manager_jwt_authentication(self):
        """Test JWT authentication flow with SecurityManager."""
        config = ServerSecurity(enable_auth=True, auth_type="jwt", jwt_secret_key="test-secret-key")

        security_manager = SecurityManager(config)

        # Test valid JWT token
        payload = {"user_id": "test-user", "role": "admin"}
        token = jwt.encode(payload, "test-secret-key", algorithm="HS256")
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        # Use asyncio to run the async method
        import asyncio

        result = asyncio.run(security_manager.authenticate(credentials))

        assert result["authenticated"] is True
        assert result["user"]["user_id"] == "test-user"
        assert result["user"]["role"] == "admin"

    def test_security_manager_api_key_authentication(self):
        """Test API key authentication flow with SecurityManager."""
        config = ServerSecurity(
            enable_auth=True,
            auth_type="api_key",
            api_key_url="http://test-auth-service.com/validate",
        )

        with patch("httpx.AsyncClient.post") as mock_post:
            # Mock successful API key validation
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"valid": True, "user": {"api_key": "test-key"}}
            mock_post.return_value = mock_response

            security_manager = SecurityManager(config)
            credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="test-key")

            import asyncio

            result = asyncio.run(security_manager.authenticate(credentials))

            assert result["authenticated"] is True
            assert result["user"]["user"]["api_key"] == "test-key"

    def test_security_middleware_setup(self):
        """Test that security middleware is properly set up."""
        app = FastAPI()
        config = ServerSecurity(
            enable_auth=True,
            enable_csrf_protection=True,
            csrf_secret_key="test-csrf-secret",
            allowed_origins=["http://localhost:3000"],
        )

        setup_security_middleware(app, config)

        # Check that middleware was added
        middleware_types = [middleware.cls.__name__ for middleware in app.user_middleware]
        assert "CORSMiddleware" in middleware_types

    def test_authenticate_request_function(self):
        """Test the authenticate_request function behavior."""
        from nomos.api.app import authenticate_request

        # Create a mock request without authorization header
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None

        with (
            patch("nomos.api.app.config") as mock_config,
            patch("nomos.api.app.security_manager") as mock_security_mgr,
        ):
            mock_config.server.security.enable_auth = True
            # Make security_manager not None (it shouldn't be called for missing auth header)
            mock_security_mgr.authenticate = AsyncMock()

            with pytest.raises(HTTPException) as exc_info:
                import asyncio

                asyncio.run(authenticate_request(mock_request))

            assert exc_info.value.status_code == 401
            assert "Authentication required" in str(exc_info.value.detail)

    def test_security_disabled_authentication(self):
        """Test that authentication is bypassed when disabled."""
        from nomos.api.app import authenticate_request

        mock_request = MagicMock()

        with patch("nomos.api.app.config") as mock_config:
            mock_config.server.security.enable_auth = False

            import asyncio

            result = asyncio.run(authenticate_request(mock_request))

            assert result["authenticated"] is False

    def test_jwt_token_validation_edge_cases(self):
        """Test JWT token validation with various edge cases."""
        config = ServerSecurity(enable_auth=True, auth_type="jwt", jwt_secret_key="test-secret-key")

        security_manager = SecurityManager(config)

        test_cases = [
            # Expired token
            {
                "payload": {"user_id": "test", "exp": int(time.time()) - 3600},
                "secret": "test-secret-key",
                "should_fail": True,
            },
            # Wrong secret
            {"payload": {"user_id": "test"}, "secret": "wrong-secret", "should_fail": True},
            # Valid token
            {
                "payload": {"user_id": "test", "exp": int(time.time()) + 3600},
                "secret": "test-secret-key",
                "should_fail": False,
            },
        ]

        import asyncio

        for test_case in test_cases:
            token = jwt.encode(test_case["payload"], test_case["secret"], algorithm="HS256")
            credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

            if test_case["should_fail"]:
                with pytest.raises(HTTPException):
                    asyncio.run(security_manager.authenticate(credentials))
            else:
                result = asyncio.run(security_manager.authenticate(credentials))
                assert result["authenticated"] is True

    def test_api_key_validation_errors(self):
        """Test API key validation error handling."""
        config = ServerSecurity(
            enable_auth=True,
            auth_type="api_key",
            api_key_url="http://test-auth-service.com/validate",
        )

        with patch("httpx.AsyncClient.post") as mock_post:
            # Mock API key validation failure
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.json.return_value = {"valid": False, "error": "Invalid API key"}
            mock_post.return_value = mock_response

            security_manager = SecurityManager(config)
            credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid-key")

            import asyncio

            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(security_manager.authenticate(credentials))

            assert exc_info.value.status_code == 401

    def test_cors_configuration(self):
        """Test CORS configuration setup."""
        app = FastAPI()
        config = ServerSecurity(
            allowed_origins=["http://localhost:3000", "https://myapp.com"], enable_auth=False
        )

        setup_security_middleware(app, config)

        # The CORS middleware should be set up
        # This is a basic test that middleware was added
        assert len(app.user_middleware) > 0

    def test_security_configuration_validation(self):
        """Test that security configuration validation works."""
        # Valid JWT config
        jwt_config = ServerSecurity(enable_auth=True, auth_type="jwt", jwt_secret_key="test-secret")
        security_manager = SecurityManager(jwt_config)
        assert security_manager.config.jwt_secret_key == "test-secret"

        # Valid API key config
        api_key_config = ServerSecurity(
            enable_auth=True, auth_type="api_key", api_key_url="http://test.com/validate"
        )
        security_manager = SecurityManager(api_key_config)
        assert security_manager.config.api_key_url == "http://test.com/validate"

    def test_bearer_token_extraction(self):
        """Test Bearer token extraction from authorization header."""
        from nomos.api.app import authenticate_request

        # Test valid Bearer token format
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "Bearer test-token"

        with patch("nomos.api.app.config") as mock_config:
            with patch("nomos.api.app.security_manager") as mock_security_mgr:
                mock_config.server.security.enable_auth = True
                mock_security_mgr.authenticate = AsyncMock(
                    return_value={"authenticated": True, "user": {"id": "test"}}
                )

                import asyncio

                result = asyncio.run(authenticate_request(mock_request))

                assert result["authenticated"] is True
                # Verify that authenticate was called with correct credentials
                mock_security_mgr.authenticate.assert_called_once()

                # Get the credentials that were passed
                call_args = mock_security_mgr.authenticate.call_args[0][0]
                assert call_args.credentials == "test-token"

    def test_invalid_authorization_header_formats(self):
        """Test various invalid authorization header formats."""
        from nomos.api.app import authenticate_request

        # Test headers that should fail before reaching security_manager
        invalid_headers_no_bearer = [
            "Invalid format",
            "Basic dGVzdDp0ZXN0",  # Basic auth instead of Bearer
            "Bearer",  # Missing space
            "",  # Empty header
            None,  # No header
        ]

        # Test headers that start with "Bearer " but have invalid tokens
        invalid_bearer_tokens = [
            "Bearer ",  # Empty token
            "Bearer invalid-token-format",  # Invalid token that will reach security_manager
        ]

        with (
            patch("nomos.api.app.config") as mock_config,
            patch("nomos.api.app.security_manager") as mock_security_mgr,
        ):
            mock_config.server.security.enable_auth = True
            # For invalid tokens that reach the security_manager, make it reject them
            mock_security_mgr.authenticate = AsyncMock(side_effect=HTTPException(status_code=401))

            import asyncio

            # Test headers that fail before reaching security_manager
            for header in invalid_headers_no_bearer:
                mock_request = MagicMock()
                mock_request.headers.get.return_value = header

                with pytest.raises(HTTPException) as exc_info:
                    asyncio.run(authenticate_request(mock_request))

                assert exc_info.value.status_code == 401

            # Test Bearer tokens that reach security_manager but are invalid
            for header in invalid_bearer_tokens:
                mock_request = MagicMock()
                mock_request.headers.get.return_value = header

                with pytest.raises(HTTPException) as exc_info:
                    asyncio.run(authenticate_request(mock_request))

                assert exc_info.value.status_code == 401

    def test_security_manager_close_method(self):
        """Test SecurityManager close method."""
        config = ServerSecurity(enable_auth=True, auth_type="jwt")
        security_manager = SecurityManager(config)

        # Close should not raise an exception
        import asyncio

        asyncio.run(security_manager.close())

        # Closing twice should also be safe
        asyncio.run(security_manager.close())

    def test_security_manager_with_httpx_client_cleanup(self):
        """Test SecurityManager properly manages httpx client lifecycle."""
        config = ServerSecurity(
            enable_auth=True, auth_type="api_key", api_key_url="http://test.com/validate"
        )

        security_manager = SecurityManager(config)

        # The httpx client should be created for API key auth
        assert hasattr(security_manager, "_http_client")

        import asyncio

        asyncio.run(security_manager.close())

        # After closing, client should be cleaned up
        # Note: This test verifies the close method runs without errors
