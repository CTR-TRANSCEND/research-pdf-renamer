"""
Tests for Redis-backed rate limiting (SPEC-FEAT-001).

Verifies:
- REQ-1: Redis storage backend when RATE_LIMIT_STORAGE_URL is redis://
- REQ-2: Fallback to memory:// when env var is not set
- REQ-4: Graceful degradation when Redis connection fails (log warning, use memory://)
- REQ-5: redis package is importable
- REQ-6: Existing rate limit values unchanged
"""

import logging
import os
import pytest
from unittest.mock import patch, MagicMock


class TestRedisPackageAvailable:
    """REQ-5: redis package must be importable."""

    def test_redis_package_importable(self):
        """redis package must be installed and importable."""
        import redis  # noqa: F401 -- must not raise ImportError


class TestRateLimitStorageDefault:
    """REQ-2: Default storage falls back to memory://."""

    def test_default_storage_is_memory(self, app):
        """When RATE_LIMIT_STORAGE_URL is not set, limiter uses memory://."""
        limiter = app.limiter
        assert limiter._storage_uri == "memory://"

    def test_default_storage_is_not_dead(self, app):
        """Memory storage backend is alive by default."""
        limiter = app.limiter
        assert limiter._storage_dead is False


class TestRateLimitStorageWithRedisUrl:
    """REQ-1: Limiter uses Redis when RATE_LIMIT_STORAGE_URL is redis:// and Redis is reachable."""

    def test_redis_url_is_used_as_storage_uri_when_ping_succeeds(self):
        """When RATE_LIMIT_STORAGE_URL=redis://... and Redis is reachable, limiter uses that URI."""
        redis_url = "redis://localhost:6379"
        with patch.dict(os.environ, {"RATE_LIMIT_STORAGE_URL": redis_url}):
            # Mock redis.Redis.from_url to simulate a reachable Redis server
            mock_conn = MagicMock()
            mock_conn.ping.return_value = True  # Redis is reachable
            with patch("redis.Redis.from_url", return_value=mock_conn):
                from backend.app import create_app

                test_app = create_app("testing")
                limiter = test_app.limiter
                assert limiter._storage_uri == redis_url

    def test_memory_url_explicit_still_works(self):
        """When RATE_LIMIT_STORAGE_URL=memory://, limiter uses memory:// (no ping check)."""
        with patch.dict(os.environ, {"RATE_LIMIT_STORAGE_URL": "memory://"}):
            from backend.app import create_app

            test_app = create_app("testing")
            limiter = test_app.limiter
            assert limiter._storage_uri == "memory://"


class TestRateLimitGracefulFallback:
    """REQ-4: Graceful fallback when Redis is unreachable."""

    def test_fallback_to_memory_when_redis_unavailable(self, caplog):
        """When Redis URL is set but ping fails, fallback to memory:// with a warning log."""
        redis_url = "redis://127.0.0.1:19999"  # non-existent port
        with patch.dict(os.environ, {"RATE_LIMIT_STORAGE_URL": redis_url}):
            mock_conn = MagicMock()
            mock_conn.ping.side_effect = Exception("Connection refused")

            with patch("redis.Redis.from_url", return_value=mock_conn):
                with caplog.at_level(logging.WARNING, logger="backend.app"):
                    from backend.app import create_app

                    test_app = create_app("testing")

                limiter = test_app.limiter
                # Must fall back gracefully to memory://
                assert limiter is not None
                assert limiter._storage_uri == "memory://"
                # Warning must be logged
                warning_logged = any(
                    "redis" in record.message.lower()
                    or "fallback" in record.message.lower()
                    or "rate limit" in record.message.lower()
                    for record in caplog.records
                    if record.levelno >= logging.WARNING
                )
                assert warning_logged, (
                    "Expected a warning log about Redis fallback, got: "
                    + str([(r.levelname, r.message) for r in caplog.records])
                )

    def test_app_starts_without_redis_running(self):
        """Application must start even if Redis URL is set but Redis is not running."""
        redis_url = "redis://127.0.0.1:19999"
        mock_conn = MagicMock()
        mock_conn.ping.side_effect = Exception("Connection refused")

        with patch.dict(os.environ, {"RATE_LIMIT_STORAGE_URL": redis_url}):
            with patch("redis.Redis.from_url", return_value=mock_conn):
                # Must not raise any exception
                from backend.app import create_app

                test_app = create_app("testing")
                assert test_app is not None


class TestExistingRateLimitsUnchanged:
    """REQ-6: Existing rate limit values and decorators are preserved."""

    def test_global_default_limits_unchanged(self, app):
        """Default global rate limits remain 200/day and 50/hour."""
        limiter = app.limiter
        default_limits = [str(lim.limit) for lim in limiter.limit_manager.default_limits]
        assert any("200" in lim and "day" in lim for lim in default_limits), (
            f"Expected '200 per day' in default limits, got: {default_limits}"
        )
        assert any("50" in lim and "hour" in lim for lim in default_limits), (
            f"Expected '50 per hour' in default limits, got: {default_limits}"
        )

    def test_rate_limit_strategy_is_fixed_window(self, app):
        """Rate limiting strategy remains fixed-window."""
        limiter = app.limiter
        assert limiter._strategy == "fixed-window"
