"""Security middleware and authentication for the Nomos API."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import httpx
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette_csrf import CSRFMiddleware as StarletteCSRFMiddleware

from ..config import ServerSecurity

# Global limiter instance
limiter = Limiter(key_func=get_remote_address)

# Security schemes
bearer_scheme = HTTPBearer(auto_error=False)


class SecurityManager:
    """Manages security configurations and authentication."""

    def __init__(self, security_config: ServerSecurity):
        self.config = security_config
        self._http_client = httpx.AsyncClient()

    async def close(self):
        """Close the HTTP client."""
        await self._http_client.aclose()

    async def verify_jwt_token(self, token: str) -> Dict[str, Any]:
        """Verify JWT token and return decoded payload."""
        if not self.config.jwt_secret_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="JWT secret key not configured",
            )

        try:
            payload = jwt.decode(
                token,
                self.config.jwt_secret_key,
                algorithms=["HS256"],
                options={"verify_exp": True},
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )

    async def verify_api_key(self, api_key: str) -> Dict[str, Any]:
        """Verify API key using the configured validation URL."""
        if not self.config.api_key_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="API key validation URL not configured",
            )

        try:
            response = await self._http_client.post(
                self.config.api_key_url,
                json={"api_key": api_key},
                timeout=10.0,
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid API key",
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="API key validation failed",
                )
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="API key validation timeout",
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"API key validation error: {str(e)}",
            )

    async def authenticate(
        self, credentials: Optional[HTTPAuthorizationCredentials]
    ) -> Dict[str, Any]:
        """Authenticate user based on the configured authentication method."""
        if not self.config.enable_auth:
            return {"authenticated": False}

        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = credentials.credentials

        if self.config.auth_type == "jwt":
            payload = await self.verify_jwt_token(token)
            return {"authenticated": True, "user": payload}
        elif self.config.auth_type == "api_key":
            payload = await self.verify_api_key(token)
            return {"authenticated": True, "user": payload}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid authentication type configured",
            )


class CSRFMiddleware(BaseHTTPMiddleware):
    """Custom CSRF middleware wrapper."""

    def __init__(self, app, csrf_middleware):
        super().__init__(app)
        self.csrf_middleware = csrf_middleware

    async def dispatch(self, request: Request, call_next):
        # Skip CSRF for GET requests and health checks
        if request.method in ["GET", "HEAD", "OPTIONS"] or request.url.path in [
            "/health",
            "/docs",
            "/openapi.json",
        ]:
            response = await call_next(request)
            return response

        # Use the starlette-csrf middleware
        return await self.csrf_middleware(request, call_next)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware."""

    def __init__(self, app, security_config: ServerSecurity):
        super().__init__(app)
        self.config = security_config

    async def dispatch(self, request: Request, call_next):
        if not self.config.enable_rate_limiting or not self.config.rate_limit:
            response = await call_next(request)
            return response

        try:
            # Apply rate limiting using slowapi
            @limiter.limit(self.config.rate_limit)
            async def rate_limited_call(request: Request):
                return await call_next(request)

            response = await rate_limited_call(request)
            return response
        except RateLimitExceeded:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
            )


def create_auth_dependency(security_manager: SecurityManager):
    """Create authentication dependency function."""

    async def auth_dependency(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    ) -> Dict[str, Any]:
        return await security_manager.authenticate(credentials)

    return auth_dependency


def generate_jwt_token(
    payload: Dict[str, Any], secret_key: str, expires_delta: Optional[timedelta] = None
) -> str:
    """Generate a JWT token with the given payload."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=24)

    payload.update({"exp": expire})
    return jwt.encode(payload, secret_key, algorithm="HS256")


def setup_security_middleware(app, security_config: ServerSecurity):
    """Setup all security middleware on the FastAPI app."""

    # Setup rate limiting
    if security_config.enable_rate_limiting:
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        app.add_middleware(RateLimitMiddleware, security_config=security_config)

    # Setup CSRF protection
    if security_config.enable_csrf_protection:
        # Use provided secret key or generate a random one
        import secrets

        csrf_secret = security_config.csrf_secret_key or secrets.token_hex(32)

        app.add_middleware(
            StarletteCSRFMiddleware,
            secret_key=csrf_secret,
            cookie_name="csrf_token",
            header_name="X-CSRF-Token",
            cookie_secure=False,  # Set to True in production with HTTPS
            cookie_samesite="lax",
        )
