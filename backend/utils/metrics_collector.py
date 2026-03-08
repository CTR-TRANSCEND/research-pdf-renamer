"""
In-memory metrics collector for operational monitoring (SPEC-OPS-001).

Provides a thread-safe singleton MetricsCollector that tracks:
- Request counts and error rates
- File upload counts and sizes
- LLM API call durations and success/failure rates
"""

import threading
from datetime import datetime, timezone


class MetricsCollector:
    """Thread-safe singleton for collecting operational metrics."""

    # @MX:ANCHOR: Singleton access point for operational metrics collection
    # @MX:REASON: Called from health endpoint, metrics endpoint, app middleware,
    #             upload routes, and LLM service - fan_in >= 5

    _instance = None
    _instance_lock = threading.Lock()

    def __init__(self):
        self._lock = threading.Lock()
        self._start_time = datetime.now(timezone.utc)
        self._reset_counters()

    def _reset_counters(self):
        """Initialize all counters to zero."""
        self._request_count = 0
        self._error_count = 0
        self._upload_count = 0
        self._upload_bytes_total = 0
        self._llm_call_count = 0
        self._llm_success_count = 0
        self._llm_failure_count = 0
        self._llm_total_duration_ms = 0.0

    @classmethod
    def get_instance(cls) -> "MetricsCollector":
        """Return the singleton MetricsCollector instance."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def reset(self) -> None:
        """Reset all counters to zero (used for test isolation)."""
        with self._lock:
            self._reset_counters()

    def record_request(self, status_code: int) -> None:
        """Record a completed HTTP request.

        Args:
            status_code: HTTP response status code.
        """
        with self._lock:
            self._request_count += 1
            if status_code >= 400:
                self._error_count += 1

    def record_upload(self, size_bytes: int, success: bool) -> None:
        """Record a file upload attempt.

        Args:
            size_bytes: Size of the uploaded file in bytes.
            success: Whether the upload succeeded.
        """
        with self._lock:
            self._upload_count += 1
            if success:
                self._upload_bytes_total += size_bytes

    def record_llm_call(self, duration_ms: float, success: bool) -> None:
        """Record an LLM API call.

        Args:
            duration_ms: Duration of the call in milliseconds.
            success: Whether the call succeeded.
        """
        with self._lock:
            self._llm_call_count += 1
            self._llm_total_duration_ms += duration_ms
            if success:
                self._llm_success_count += 1
            else:
                self._llm_failure_count += 1

    def get_uptime(self) -> float:
        """Return elapsed seconds since this collector was created."""
        now = datetime.now(timezone.utc)
        delta = now - self._start_time
        return delta.total_seconds()

    def get_metrics(self) -> dict:
        """Return a snapshot of all collected metrics.

        Returns:
            dict with request, upload, and LLM statistics.
        """
        with self._lock:
            call_count = self._llm_call_count
            total_ms = self._llm_total_duration_ms
            avg_latency = (total_ms / call_count) if call_count > 0 else 0.0

            return {
                "request_count": self._request_count,
                "error_count": self._error_count,
                "upload_count": self._upload_count,
                "upload_bytes_total": self._upload_bytes_total,
                "llm_call_count": self._llm_call_count,
                "llm_success_count": self._llm_success_count,
                "llm_failure_count": self._llm_failure_count,
                "llm_total_duration_ms": self._llm_total_duration_ms,
                "llm_avg_latency_ms": round(avg_latency, 2),
                "started_at": self._start_time.isoformat(),
            }
