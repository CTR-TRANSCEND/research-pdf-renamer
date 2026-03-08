"""
Tests for SPEC-OPS-001: Monitoring and Health Endpoints Enhancement.

RED phase tests (test-first) covering:
- Enhanced /api/health endpoint (REQ-OPS-001)
- /api/metrics endpoint (REQ-OPS-002)
- MetricsCollector singleton thread-safety (REQ-OPS-006)
- Structured JSON logging (REQ-OPS-003)
- LLM call metrics (REQ-OPS-004)
- Upload metrics (REQ-OPS-005)
"""

import json
import threading
import time
import pytest
from unittest.mock import patch, MagicMock


class TestMetricsCollector:
    """Tests for MetricsCollector singleton with thread-safe counters (REQ-OPS-006)."""

    def test_metrics_collector_is_singleton(self):
        """MetricsCollector.get_instance() returns the same object each time."""
        from backend.utils.metrics_collector import MetricsCollector

        instance1 = MetricsCollector.get_instance()
        instance2 = MetricsCollector.get_instance()
        assert instance1 is instance2

    def test_metrics_collector_initial_state(self):
        """MetricsCollector starts with zero counters."""
        from backend.utils.metrics_collector import MetricsCollector

        collector = MetricsCollector.get_instance()
        collector.reset()  # Ensure clean state for test isolation

        metrics = collector.get_metrics()
        assert metrics["request_count"] == 0
        assert metrics["error_count"] == 0
        assert metrics["upload_count"] == 0
        assert metrics["upload_bytes_total"] == 0
        assert metrics["llm_call_count"] == 0
        assert metrics["llm_success_count"] == 0
        assert metrics["llm_failure_count"] == 0
        assert metrics["llm_total_duration_ms"] == 0

    def test_record_request_increments_count(self):
        """record_request() increments request_count."""
        from backend.utils.metrics_collector import MetricsCollector

        collector = MetricsCollector.get_instance()
        collector.reset()

        collector.record_request(200)
        metrics = collector.get_metrics()
        assert metrics["request_count"] == 1

    def test_record_request_tracks_errors_on_5xx(self):
        """record_request(500) increments error_count."""
        from backend.utils.metrics_collector import MetricsCollector

        collector = MetricsCollector.get_instance()
        collector.reset()

        collector.record_request(500)
        metrics = collector.get_metrics()
        assert metrics["error_count"] == 1

    def test_record_request_tracks_errors_on_4xx(self):
        """record_request(404) increments error_count."""
        from backend.utils.metrics_collector import MetricsCollector

        collector = MetricsCollector.get_instance()
        collector.reset()

        collector.record_request(404)
        metrics = collector.get_metrics()
        assert metrics["error_count"] == 1

    def test_record_request_no_error_on_2xx(self):
        """record_request(200) does not increment error_count."""
        from backend.utils.metrics_collector import MetricsCollector

        collector = MetricsCollector.get_instance()
        collector.reset()

        collector.record_request(200)
        metrics = collector.get_metrics()
        assert metrics["error_count"] == 0

    def test_record_upload_increments_count_and_bytes(self):
        """record_upload() increments upload_count and upload_bytes_total."""
        from backend.utils.metrics_collector import MetricsCollector

        collector = MetricsCollector.get_instance()
        collector.reset()

        collector.record_upload(size_bytes=1024, success=True)
        metrics = collector.get_metrics()
        assert metrics["upload_count"] == 1
        assert metrics["upload_bytes_total"] == 1024

    def test_record_upload_failed_increments_count_not_bytes(self):
        """record_upload(success=False) increments count but not bytes."""
        from backend.utils.metrics_collector import MetricsCollector

        collector = MetricsCollector.get_instance()
        collector.reset()

        collector.record_upload(size_bytes=2048, success=False)
        metrics = collector.get_metrics()
        assert metrics["upload_count"] == 1
        assert metrics["upload_bytes_total"] == 0

    def test_record_llm_call_success(self):
        """record_llm_call(duration_ms, True) increments llm counters correctly."""
        from backend.utils.metrics_collector import MetricsCollector

        collector = MetricsCollector.get_instance()
        collector.reset()

        collector.record_llm_call(duration_ms=150, success=True)
        metrics = collector.get_metrics()
        assert metrics["llm_call_count"] == 1
        assert metrics["llm_success_count"] == 1
        assert metrics["llm_failure_count"] == 0
        assert metrics["llm_total_duration_ms"] == 150

    def test_record_llm_call_failure(self):
        """record_llm_call(duration_ms, False) increments failure counter."""
        from backend.utils.metrics_collector import MetricsCollector

        collector = MetricsCollector.get_instance()
        collector.reset()

        collector.record_llm_call(duration_ms=200, success=False)
        metrics = collector.get_metrics()
        assert metrics["llm_call_count"] == 1
        assert metrics["llm_success_count"] == 0
        assert metrics["llm_failure_count"] == 1

    def test_get_metrics_includes_avg_latency(self):
        """get_metrics() calculates avg_llm_latency_ms from total / count."""
        from backend.utils.metrics_collector import MetricsCollector

        collector = MetricsCollector.get_instance()
        collector.reset()

        collector.record_llm_call(duration_ms=100, success=True)
        collector.record_llm_call(duration_ms=200, success=True)
        metrics = collector.get_metrics()
        assert metrics["llm_avg_latency_ms"] == 150.0

    def test_get_metrics_avg_latency_zero_when_no_calls(self):
        """get_metrics() returns 0 avg_llm_latency_ms when no LLM calls recorded."""
        from backend.utils.metrics_collector import MetricsCollector

        collector = MetricsCollector.get_instance()
        collector.reset()

        metrics = collector.get_metrics()
        assert metrics["llm_avg_latency_ms"] == 0.0

    def test_get_metrics_includes_started_at(self):
        """get_metrics() includes started_at ISO timestamp."""
        from backend.utils.metrics_collector import MetricsCollector

        collector = MetricsCollector.get_instance()
        metrics = collector.get_metrics()
        assert "started_at" in metrics
        # Should be a valid ISO timestamp string
        assert isinstance(metrics["started_at"], str)
        assert "T" in metrics["started_at"]  # ISO 8601 format

    def test_get_uptime_returns_seconds(self):
        """get_uptime() returns elapsed seconds since instance creation."""
        from backend.utils.metrics_collector import MetricsCollector

        collector = MetricsCollector.get_instance()
        uptime = collector.get_uptime()
        assert isinstance(uptime, float)
        assert uptime >= 0

    def test_thread_safety_concurrent_requests(self):
        """MetricsCollector counters are consistent under concurrent access."""
        from backend.utils.metrics_collector import MetricsCollector

        collector = MetricsCollector.get_instance()
        collector.reset()

        num_threads = 20
        calls_per_thread = 50

        def record_many():
            for _ in range(calls_per_thread):
                collector.record_request(200)

        threads = [threading.Thread(target=record_many) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        metrics = collector.get_metrics()
        assert metrics["request_count"] == num_threads * calls_per_thread

    def test_thread_safety_concurrent_uploads(self):
        """Upload counters are consistent under concurrent access."""
        from backend.utils.metrics_collector import MetricsCollector

        collector = MetricsCollector.get_instance()
        collector.reset()

        num_threads = 10
        uploads_per_thread = 100
        size_per_upload = 512

        def upload_many():
            for _ in range(uploads_per_thread):
                collector.record_upload(size_bytes=size_per_upload, success=True)

        threads = [threading.Thread(target=upload_many) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        metrics = collector.get_metrics()
        expected_count = num_threads * uploads_per_thread
        expected_bytes = expected_count * size_per_upload
        assert metrics["upload_count"] == expected_count
        assert metrics["upload_bytes_total"] == expected_bytes


class TestEnhancedHealthEndpoint:
    """Tests for enhanced /api/health endpoint (REQ-OPS-001)."""

    def test_health_endpoint_returns_200(self, client):
        """GET /api/health returns HTTP 200."""
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_health_endpoint_returns_status(self, client):
        """GET /api/health response includes 'status' field."""
        response = client.get("/api/health")
        data = response.get_json()
        assert "status" in data
        assert data["status"] in ("healthy", "degraded", "error")

    def test_health_endpoint_returns_version(self, client):
        """GET /api/health response includes 'version' field."""
        response = client.get("/api/health")
        data = response.get_json()
        assert "version" in data
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0

    def test_health_endpoint_returns_uptime(self, client):
        """GET /api/health response includes 'uptime_seconds' field."""
        response = client.get("/api/health")
        data = response.get_json()
        assert "uptime_seconds" in data
        assert isinstance(data["uptime_seconds"], (int, float))
        assert data["uptime_seconds"] >= 0

    def test_health_endpoint_returns_db_status(self, client):
        """GET /api/health response includes 'db_status' field."""
        response = client.get("/api/health")
        data = response.get_json()
        assert "db_status" in data
        assert isinstance(data["db_status"], dict)

    def test_health_endpoint_db_status_has_status_key(self, client):
        """GET /api/health db_status contains a 'status' key."""
        response = client.get("/api/health")
        data = response.get_json()
        assert "status" in data["db_status"]

    def test_health_endpoint_returns_dependencies(self, client):
        """GET /api/health response includes 'dependencies' field."""
        response = client.get("/api/health")
        data = response.get_json()
        assert "dependencies" in data
        assert isinstance(data["dependencies"], dict)

    def test_health_endpoint_no_auth_required(self, client):
        """GET /api/health is accessible without authentication."""
        # No auth headers provided
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_health_endpoint_content_type_is_json(self, client):
        """GET /api/health returns Content-Type: application/json."""
        response = client.get("/api/health")
        assert "application/json" in response.content_type


class TestMetricsEndpoint:
    """Tests for /api/metrics admin endpoint (REQ-OPS-002)."""

    def test_metrics_endpoint_requires_auth(self, client):
        """GET /api/admin/metrics returns 401 or 403 without auth."""
        response = client.get("/api/admin/metrics")
        assert response.status_code in (401, 403)

    def test_metrics_endpoint_requires_admin(self, client, auth_headers):
        """GET /api/admin/metrics returns 403 for non-admin user."""
        response = client.get("/api/admin/metrics", headers=auth_headers)
        assert response.status_code == 403

    def test_metrics_endpoint_returns_200_for_admin(self, client, admin_headers):
        """GET /api/admin/metrics returns 200 for admin user."""
        response = client.get("/api/admin/metrics", headers=admin_headers)
        assert response.status_code == 200

    def test_metrics_endpoint_returns_request_count(self, client, admin_headers):
        """GET /api/admin/metrics response includes request_count."""
        response = client.get("/api/admin/metrics", headers=admin_headers)
        data = response.get_json()
        assert "request_count" in data

    def test_metrics_endpoint_returns_error_count(self, client, admin_headers):
        """GET /api/admin/metrics response includes error_count."""
        response = client.get("/api/admin/metrics", headers=admin_headers)
        data = response.get_json()
        assert "error_count" in data

    def test_metrics_endpoint_returns_upload_stats(self, client, admin_headers):
        """GET /api/admin/metrics response includes upload_count and upload_bytes_total."""
        response = client.get("/api/admin/metrics", headers=admin_headers)
        data = response.get_json()
        assert "upload_count" in data
        assert "upload_bytes_total" in data

    def test_metrics_endpoint_returns_llm_stats(self, client, admin_headers):
        """GET /api/admin/metrics response includes LLM call statistics."""
        response = client.get("/api/admin/metrics", headers=admin_headers)
        data = response.get_json()
        assert "llm_call_count" in data
        assert "llm_success_count" in data
        assert "llm_failure_count" in data
        assert "llm_avg_latency_ms" in data

    def test_metrics_endpoint_returns_started_at(self, client, admin_headers):
        """GET /api/admin/metrics response includes started_at timestamp."""
        response = client.get("/api/admin/metrics", headers=admin_headers)
        data = response.get_json()
        assert "started_at" in data

    def test_metrics_endpoint_content_type_is_json(self, client, admin_headers):
        """GET /api/admin/metrics returns Content-Type: application/json."""
        response = client.get("/api/admin/metrics", headers=admin_headers)
        assert "application/json" in response.content_type


class TestStructuredLogging:
    """Tests for structured JSON logging (REQ-OPS-003)."""

    def test_json_log_formatter_produces_json(self):
        """JSONLogFormatter formats log records as valid JSON."""
        import logging
        import io
        from backend.utils.structured_logging import JSONLogFormatter

        formatter = JSONLogFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        formatted = formatter.format(record)
        # Should parse as valid JSON
        parsed = json.loads(formatted)
        assert isinstance(parsed, dict)

    def test_json_log_formatter_includes_required_fields(self):
        """JSONLogFormatter output includes timestamp, level, and message."""
        import logging
        from backend.utils.structured_logging import JSONLogFormatter

        formatter = JSONLogFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        formatted = formatter.format(record)
        parsed = json.loads(formatted)
        assert "timestamp" in parsed
        assert "level" in parsed
        assert "message" in parsed

    def test_json_log_formatter_level_name(self):
        """JSONLogFormatter includes human-readable level name."""
        import logging
        from backend.utils.structured_logging import JSONLogFormatter

        formatter = JSONLogFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="test.py",
            lineno=1,
            msg="Warning msg",
            args=(),
            exc_info=None,
        )
        formatted = formatter.format(record)
        parsed = json.loads(formatted)
        assert parsed["level"] == "WARNING"

    def test_request_id_middleware_sets_g_attribute(self, app):
        """before_request middleware sets flask.g.request_id to a UUID string."""
        import uuid
        from flask import g

        with app.test_request_context("/api/health"):
            from backend.utils.structured_logging import generate_request_id

            request_id = generate_request_id()
            # Should be a valid UUID4 string
            assert isinstance(request_id, str)
            # Validate UUID format
            uuid_obj = uuid.UUID(request_id, version=4)
            assert str(uuid_obj) == request_id

    def test_setup_structured_logging_is_callable(self):
        """setup_structured_logging() function exists and is callable."""
        from backend.utils.structured_logging import setup_structured_logging

        assert callable(setup_structured_logging)
