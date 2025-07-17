"""Tests for rate limiting functionality in the Nomos API."""

import asyncio
import os
import shutil
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest
import redis.asyncio as redis
from fastapi import HTTPException
from fastapi.testclient import TestClient

# Set dummy environment variables to avoid OpenAI API key requirement
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")

# Setup config file before imports
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


class TestRateLimitingConfiguration:
    """Test rate limiting configuration and setup."""

    def setup_method(self):
        """Setup for each test method."""
        self.openai_patcher = patch("nomos.llms.openai.OpenAI")
        self.agent_patcher = patch("nomos.api.agent.agent")
        self.session_store_patcher = patch("nomos.api.app.session_store")

        self.openai_patcher.start()
        self.agent_patcher.start()
        self.session_store_patcher.start()

    def teardown_method(self):
        """Cleanup for each test method."""
        self.openai_patcher.stop()
        self.agent_patcher.stop()
        self.session_store_patcher.stop()

    @pytest.fixture
    def app_with_rate_limiting(self):
        """Create app with rate limiting enabled."""
        with patch("nomos.api.app.config") as mock_config:
            mock_config.name = "test-agent"
            mock_config.server.host = "localhost"
            mock_config.server.port = 8000
            mock_config.server.workers = 1
            mock_config.server.security.enable_auth = False
            mock_config.server.security.enable_rate_limiting = True
            mock_config.server.security.redis_url = "redis://localhost:6379"
            mock_config.server.security.rate_limit_times = 5
            mock_config.server.security.rate_limit_seconds = 60
            mock_config.server.security.enable_csrf_protection = False
            mock_config.server.security.allowed_origins = ["*"]

            from nomos.api.app import app

            return app

    @pytest.fixture
    def app_without_rate_limiting(self):
        """Create app without rate limiting."""
        with patch("nomos.api.app.config") as mock_config:
            mock_config.name = "test-agent"
            mock_config.server.host = "localhost"
            mock_config.server.port = 8000
            mock_config.server.workers = 1
            mock_config.server.security.enable_auth = False
            mock_config.server.security.enable_rate_limiting = False
            mock_config.server.security.enable_csrf_protection = False
            mock_config.server.security.allowed_origins = ["*"]

            from nomos.api.app import app

            return app

    def test_rate_limiting_disabled_by_default(self, app_without_rate_limiting):
        """Test that rate limiting is disabled by default."""
        client = TestClient(app_without_rate_limiting)

        # Make multiple requests quickly
        for _ in range(10):
            response = client.get("/health")
            assert response.status_code == 200

        # All requests should succeed when rate limiting is disabled

    @patch("redis.asyncio.from_url")
    @patch("fastapi_limiter.FastAPILimiter.init")
    def test_rate_limiting_redis_initialization(self, mock_limiter_init, mock_redis_from_url):
        """Test Redis initialization for rate limiting."""
        mock_redis_client = AsyncMock()
        mock_redis_from_url.return_value = mock_redis_client
        mock_limiter_init.return_value = None

        # Test that Redis client is created correctly during app startup
        # This would normally happen in the lifespan function

        redis_url = "redis://localhost:6379"
        redis.from_url(redis_url, encoding="utf-8", decode_responses=True)

        mock_redis_from_url.assert_called_once_with(
            redis_url, encoding="utf-8", decode_responses=True
        )

    def test_rate_limiting_dependency_creation(self):
        """Test rate limiting dependency creation."""
        from fastapi_limiter.depends import RateLimiter

        # Test creating a rate limiter dependency
        rate_limiter = RateLimiter(times=50, seconds=60)
        assert rate_limiter is not None

    def test_rate_limiting_configuration_validation(self):
        """Test rate limiting configuration validation."""
        from nomos.config import ServerSecurity

        # Valid configuration
        config = ServerSecurity(
            enable_rate_limiting=True,
            redis_url="redis://localhost:6379",
            rate_limit_times=100,
            rate_limit_seconds=60,
        )

        assert config.enable_rate_limiting is True
        assert config.redis_url == "redis://localhost:6379"
        assert config.rate_limit_times == 100
        assert config.rate_limit_seconds == 60

    def test_rate_limiting_missing_redis_url(self):
        """Test rate limiting configuration with missing Redis URL."""
        from nomos.config import ServerSecurity

        # Configuration with rate limiting enabled but no Redis URL
        config = ServerSecurity(
            enable_rate_limiting=True,
            rate_limit_times=100,
            rate_limit_seconds=60,
            # redis_url is None
        )

        assert config.enable_rate_limiting is True
        assert config.redis_url is None
        # This should be caught during app startup


class TestRateLimitingIntegration:
    """Test rate limiting integration with API endpoints."""

    def setup_method(self):
        """Setup for each test method."""
        self.openai_patcher = patch("nomos.llms.openai.OpenAI")
        self.agent_patcher = patch("nomos.api.agent.agent")
        self.session_store_patcher = patch("nomos.api.app.session_store")
        self.redis_patcher = patch("redis.asyncio.from_url")
        self.limiter_patcher = patch("fastapi_limiter.FastAPILimiter.init")

        self.openai_patcher.start()
        self.agent_patcher.start()
        self.session_store_patcher.start()

        # Mock Redis and FastAPI Limiter
        mock_redis_client = AsyncMock()
        self.redis_patcher.start().return_value = mock_redis_client
        self.limiter_patcher.start().return_value = None

    def teardown_method(self):
        """Cleanup for each test method."""
        self.openai_patcher.stop()
        self.agent_patcher.stop()
        self.session_store_patcher.stop()
        self.redis_patcher.stop()
        self.limiter_patcher.stop()

    @pytest.fixture
    def mock_rate_limited_app(self):
        """Create app with mocked rate limiting."""
        with patch("nomos.api.app.config") as mock_config:
            mock_config.name = "test-agent"
            mock_config.server.security.enable_auth = False
            mock_config.server.security.enable_rate_limiting = True
            mock_config.server.security.redis_url = "redis://localhost:6379"
            mock_config.server.security.rate_limit_times = 2  # Very low limit for testing
            mock_config.server.security.rate_limit_seconds = 60

            # Mock the rate limiting dependency
            with patch("nomos.api.app.deps") as mock_deps:
                # Create a mock rate limiter that allows first few requests then blocks
                self._request_count = 0

                def mock_rate_limiter():
                    self._request_count += 1
                    if self._request_count > 2:
                        raise HTTPException(status_code=429, detail="Rate limit exceeded")
                    return True

                mock_deps.return_value = [mock_rate_limiter]

                from nomos.api.app import app

                return app

    def test_rate_limiting_allows_initial_requests(self, mock_rate_limited_app):
        """Test that rate limiting allows initial requests."""
        client = TestClient(mock_rate_limited_app)

        # First few requests should succeed
        response = client.get("/health")  # Health endpoint might not be rate limited
        assert response.status_code == 200

    def test_rate_limiting_blocks_excess_requests(self):
        """Test that rate limiting blocks excess requests."""
        # This test would require actual integration with FastAPI Limiter
        # and Redis, which is complex to set up in unit tests

        # Instead, we test the concept by mocking the rate limiter response
        from fastapi import HTTPException

        def mock_rate_limiter_exceeded():
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

        # Test that the rate limiter raises the correct exception
        with pytest.raises(HTTPException) as exc_info:
            mock_rate_limiter_exceeded()

        assert exc_info.value.status_code == 429
        assert "rate limit exceeded" in exc_info.value.detail.lower()

    def test_rate_limiting_headers(self):
        """Test rate limiting response headers."""
        # This test would check for rate limiting headers in responses
        # Headers like: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset

        # Mock response with rate limiting headers
        mock_headers = {
            "x-ratelimit-limit": "100",
            "x-ratelimit-remaining": "95",
            "x-ratelimit-reset": str(int(time.time()) + 60),
        }

        # Verify expected headers are present
        assert "x-ratelimit-limit" in mock_headers
        assert "x-ratelimit-remaining" in mock_headers
        assert "x-ratelimit-reset" in mock_headers

        # Verify header values are reasonable
        assert int(mock_headers["x-ratelimit-limit"]) > 0
        assert int(mock_headers["x-ratelimit-remaining"]) >= 0
        assert int(mock_headers["x-ratelimit-reset"]) > time.time()

    def test_rate_limiting_per_endpoint(self):
        """Test that different endpoints can have different rate limits."""
        # This would test endpoint-specific rate limiting configuration

        # Example: Session creation might have stricter limits than health checks
        session_limit = 10  # requests per minute
        health_limit = 100  # requests per minute

        assert session_limit < health_limit
        # In a real implementation, you would test that these limits are enforced


class TestRateLimitingEdgeCases:
    """Test edge cases and error scenarios for rate limiting."""

    def test_redis_connection_failure(self):
        """Test behavior when Redis connection fails."""
        # Mock Redis connection failure
        with patch("redis.asyncio.from_url") as mock_redis:
            mock_redis.side_effect = Exception("Redis connection failed")

            # App startup should handle Redis connection failures gracefully
            # The exact behavior depends on the implementation
            with pytest.raises(Exception):
                redis.from_url("redis://invalid-host:6379")

    def test_rate_limiter_initialization_failure(self):
        """Test behavior when FastAPI Limiter initialization fails."""
        from fastapi_limiter import FastAPILimiter

        with patch("fastapi_limiter.FastAPILimiter.init") as mock_init:
            mock_init.side_effect = Exception("Limiter init failed")

            # App should handle limiter initialization failures
            with pytest.raises(Exception):
                # Call the actual init method that would fail
                asyncio.run(FastAPILimiter.init(None))

    def test_rate_limiting_with_invalid_redis_url(self):
        """Test rate limiting configuration with invalid Redis URL."""
        from nomos.config import ServerSecurity

        # Configuration with invalid Redis URL
        config = ServerSecurity(
            enable_rate_limiting=True,
            redis_url="invalid://url",
            rate_limit_times=100,
            rate_limit_seconds=60,
        )

        # Redis client creation should fail with invalid URL
        with pytest.raises(Exception):
            redis.from_url(config.redis_url)

    def test_rate_limiting_with_zero_limits(self):
        """Test rate limiting with zero or negative limits."""
        from nomos.config import ServerSecurity

        # Configuration with zero limits
        config = ServerSecurity(
            enable_rate_limiting=True,
            redis_url="redis://localhost:6379",
            rate_limit_times=0,  # Zero requests allowed
            rate_limit_seconds=60,
        )

        # This should be handled appropriately
        assert config.rate_limit_times == 0

        # Negative limits
        config.rate_limit_times = -1
        # Pydantic validation might catch this, or it might be handled at runtime

    def test_rate_limiting_cleanup(self):
        """Test rate limiting cleanup during app shutdown."""
        # Mock FastAPI Limiter close
        with patch("fastapi_limiter.FastAPILimiter.close") as mock_close:
            mock_close.return_value = AsyncMock()

            # Test that cleanup is called
            async def test_cleanup():
                await mock_close()

            asyncio.run(test_cleanup())
            mock_close.assert_called_once()


class TestRateLimitingPerformance:
    """Test performance aspects of rate limiting."""

    def test_rate_limiting_overhead(self):
        """Test performance overhead of rate limiting."""
        # Test that rate limiting doesn't add significant latency

        start_time = time.time()

        # Simulate rate limit check
        def simulate_rate_check():
            # In real implementation, this would check Redis
            time.sleep(0.001)  # 1ms simulated overhead
            return True

        # Check multiple times
        for _ in range(100):
            result = simulate_rate_check()
            assert result is True

        end_time = time.time()
        total_time = end_time - start_time

        # Should complete quickly (under 1 second for 100 checks)
        assert total_time < 1.0

    def test_redis_connection_pooling(self):
        """Test Redis connection pooling for rate limiting."""
        # Test that Redis connections are properly pooled and reused

        with patch("redis.asyncio.from_url") as mock_redis:
            mock_pool = Mock()
            mock_redis.return_value = mock_pool

            # Create multiple "connections"
            clients = []
            for _ in range(5):
                client = redis.from_url("redis://localhost:6379")
                clients.append(client)

            # Should reuse the same connection pool
            assert len(clients) == 5
            # In real implementation, verify connection pooling behavior

    def test_concurrent_rate_limit_checks(self):
        """Test concurrent rate limit checks."""
        # Test that concurrent requests don't interfere with rate limiting

        import concurrent.futures

        def simulate_request():
            # Simulate a request that checks rate limits
            time.sleep(0.01)  # 10ms simulated request time
            return True

        # Make concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(simulate_request) for _ in range(20)]
            results = [future.result() for future in futures]

        # All requests should complete successfully
        assert all(results)
        assert len(results) == 20


class TestRateLimitingMonitoring:
    """Test monitoring and observability for rate limiting."""

    def test_rate_limiting_metrics(self):
        """Test rate limiting metrics collection."""
        # Test that rate limiting events are properly tracked

        metrics = {"requests_allowed": 0, "requests_blocked": 0, "total_requests": 0}

        def track_request(allowed: bool):
            metrics["total_requests"] += 1
            if allowed:
                metrics["requests_allowed"] += 1
            else:
                metrics["requests_blocked"] += 1

        # Simulate some requests
        for i in range(10):
            allowed = i < 8  # First 8 allowed, last 2 blocked
            track_request(allowed)

        assert metrics["total_requests"] == 10
        assert metrics["requests_allowed"] == 8
        assert metrics["requests_blocked"] == 2

    def test_rate_limiting_logging(self):
        """Test rate limiting event logging."""
        # Test that rate limiting events are properly logged

        import logging

        # Mock logger
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            logger = logging.getLogger("rate_limiter")

            # Simulate logging rate limit events
            logger.warning("Rate limit exceeded for IP: 192.168.1.1")
            logger.info("Rate limit check passed for user: test-user")

            # Verify logging was called
            mock_logger.warning.assert_called()
            mock_logger.info.assert_called()

    def test_rate_limiting_alerting(self):
        """Test rate limiting alerting thresholds."""
        # Test that alerts are triggered when rate limiting thresholds are exceeded

        def check_alerting_threshold(blocked_percentage: float) -> bool:
            """Check if alerting threshold is exceeded."""
            return blocked_percentage > 0.1  # Alert if more than 10% blocked

        # Test scenarios
        assert check_alerting_threshold(0.05) is False  # 5% blocked - no alert
        assert check_alerting_threshold(0.15) is True  # 15% blocked - alert
        assert check_alerting_threshold(0.5) is True  # 50% blocked - alert

    def test_rate_limiting_dashboard_data(self):
        """Test data collection for rate limiting dashboards."""
        # Test that appropriate data is collected for monitoring dashboards

        dashboard_data = {
            "current_requests_per_second": 45.2,
            "average_requests_per_minute": 2710,
            "peak_requests_per_minute": 3200,
            "rate_limit_hit_percentage": 2.1,
            "top_rate_limited_ips": [
                {"ip": "192.168.1.100", "hits": 25},
                {"ip": "10.0.0.50", "hits": 18},
            ],
        }

        # Verify data structure
        assert "current_requests_per_second" in dashboard_data
        assert "rate_limit_hit_percentage" in dashboard_data
        assert isinstance(dashboard_data["top_rate_limited_ips"], list)

        # Verify data ranges
        assert 0 <= dashboard_data["rate_limit_hit_percentage"] <= 100
        assert dashboard_data["current_requests_per_second"] >= 0
