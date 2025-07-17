"""Security middleware and authentication for the Nomos API."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import httpx
import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette_csrf import CSRFMiddleware

from ..config import ServerSecurity

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
        except HTTPException:
            # Re-raise HTTPExceptions without wrapping them
            raise
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


def setup_security_middleware(app: FastAPI, security_config: ServerSecurity):
    """Setup all security middleware on the FastAPI app."""

    # CORS middleware configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=security_config.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-CSRF-Token"],
    )

    # Setup CSRF protection
    if security_config.enable_csrf_protection and security_config.csrf_secret_key:
        csrf_secret = security_config.csrf_secret_key
        app.add_middleware(
            CSRFMiddleware,
            secret_key=csrf_secret,
            cookie_name="csrf_token",
            header_name="X-CSRF-Token",
            cookie_secure=True,
            cookie_samesite="lax",
        )
