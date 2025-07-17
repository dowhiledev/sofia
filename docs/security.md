# Security Configuration Guide

This document describes the security features implemented in the Nomos API and how to configure them.

## Security Features

### Authentication

The API supports two authentication methods:

1. **JWT (JSON Web Tokens)**
2. **API Key Validation**

#### JWT Authentication

To enable JWT authentication, set the following configuration:

```yaml
server:
  security:
    enable_auth: true
    auth_type: jwt
    jwt_secret_key: "your-secret-key-here"
```

#### API Key Authentication

To enable API key authentication, set the following configuration:

```yaml
server:
  security:
    enable_auth: true
    auth_type: api_key
    api_key_url: "https://your-api-key-validation-endpoint.com/validate"
```

The API key validation endpoint should:
- Accept POST requests with `{"api_key": "key-value"}` in the body
- Return 200 status with user information for valid keys
- Return 401 status for invalid keys

### Rate Limiting

Enable rate limiting to prevent abuse:

```yaml
server:
  security:
    enable_rate_limiting: true
    rate_limit: "100/minute"  # Format: "number/time_unit"
```

Supported time units: `second`, `minute`, `hour`, `day`

### CSRF Protection

Enable CSRF protection for web applications:

```yaml
server:
  security:
    enable_csrf_protection: true
    csrf_secret_key: "your-csrf-secret-key"  # Optional, auto-generated if not provided
```

### CORS Configuration

Configure allowed origins for cross-origin requests:

```yaml
server:
  security:
    allowed_origins:
      - "https://your-frontend-domain.com"
      - "https://another-allowed-domain.com"
    # Or use ["*"] for all origins (not recommended in production)
```

## Complete Example Configuration

```yaml
name: "secure-agent"
steps:
  - id: "start"
    type: "llm"
    prompt: "Hello! How can I help you today?"
start_step_id: "start"

server:
  port: 8000
  host: "0.0.0.0"
  security:
    # Authentication
    enable_auth: true
    auth_type: jwt
    jwt_secret_key: "$JWT_SECRET_KEY"

    # Rate limiting
    enable_rate_limiting: true
    rate_limit: "100/minute"

    # CSRF protection
    enable_csrf_protection: true
    csrf_secret_key: "$CSRF_SECRET_KEY"

    # CORS
    allowed_origins:
      - "https://your-frontend.com"
      - "http://localhost:3000"  # For development
```

## Usage

### Authentication Headers

When authentication is enabled, include the token in the Authorization header:

```bash
curl -H "Authorization: Bearer <your-token>" https://your-api.com/session
```

### CSRF Protection

When CSRF protection is enabled, include the CSRF token in the `X-CSRF-Token` header:

```bash
curl -H "X-CSRF-Token: <csrf-token>" -X POST https://your-api.com/session
```

### Rate Limiting

Rate limiting is applied per IP address. When the limit is exceeded, the API returns a 429 status code.

## Testing

Use the `/auth/token` endpoint to generate test JWT tokens:

```bash
curl -X POST https://your-api.com/auth/token \
  -H "Content-Type: application/json" \
  -d '{"user_id": "123", "username": "testuser"}'
```

## Security Best Practices

1. **Use environment variables** for sensitive configuration like secret keys
2. **Enable HTTPS** in production
3. **Use strong secret keys** (at least 32 characters)
4. **Limit CORS origins** to only trusted domains
5. **Monitor rate limiting** and adjust limits based on usage patterns
6. **Regularly rotate** JWT secret keys
7. **Use secure cookie settings** for CSRF tokens in production

## Dependencies

The security features require the following dependencies (included in the `serve` optional dependency):

- `pyjwt>=2.10.1` - JWT token handling
- `slowapi>=0.1.9` - Rate limiting
- `starlette-csrf>=3.0.0` - CSRF protection
- `httpx` - HTTP client for API key validation

Install with:
```bash
pip install nomos[serve]
```
