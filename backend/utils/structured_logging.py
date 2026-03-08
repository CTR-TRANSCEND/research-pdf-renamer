"""
Structured JSON logging utilities for SPEC-OPS-001.

Provides:
- JSONLogFormatter: logging.Formatter subclass that emits JSON records
- generate_request_id(): UUID4 generator for per-request correlation
- setup_structured_logging(): configure app logger with JSON formatter
"""

import json
import logging
import uuid
from datetime import datetime, timezone


class JSONLogFormatter(logging.Formatter):
    """Log formatter that outputs JSON records for structured log ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as a JSON string.

        Args:
            record: The log record to format.

        Returns:
            JSON string with timestamp, level, message, and any extra fields.
        """
        log_entry = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }

        # Include request_id if present on the record
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id

        # Include extra fields that were passed to the logger call
        for key, value in record.__dict__.items():
            if key not in (
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "taskName",
            ):
                if not key.startswith("_"):
                    log_entry[key] = value

        return json.dumps(log_entry, default=str)


def generate_request_id() -> str:
    """Generate a UUID4 string for per-request correlation.

    Returns:
        A UUID4 formatted as a lowercase hyphenated string.
    """
    return str(uuid.uuid4())


def setup_structured_logging(app) -> None:
    """Configure the Flask app logger to use JSON formatting.

    This replaces the default StreamHandler formatter with JSONLogFormatter.
    Call this during app factory setup for production structured logging.

    Args:
        app: The Flask application instance.
    """
    formatter = JSONLogFormatter()
    for handler in app.logger.handlers:
        handler.setFormatter(formatter)

    # If no handlers are configured yet, add a StreamHandler
    if not app.logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        app.logger.addHandler(handler)
