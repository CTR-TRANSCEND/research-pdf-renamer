"""Middleware for database monitoring."""

import logging
from time import time
from flask import g, request
from backend.utils.db_health import log_pool_status, ConnectionPoolMonitor

# Configure logger
logger = logging.getLogger(__name__)

class DatabaseMonitorMiddleware:
    """Middleware to monitor database performance and connection pool usage."""

    def __init__(self, app):
        self.app = app
        self.init_app(app)

    def init_app(self, app):
        """Initialize middleware with Flask app."""
        app.before_request(self.before_request)
        app.after_request(self.after_request)

        # Setup periodic pool logging
        self.last_pool_log = 0
        self.pool_log_interval = 300  # Log every 5 minutes

    def before_request(self):
        """Before request handler."""
        g.start_time = time()
        g.db_monitor = ConnectionPoolMonitor(f"{request.method} {request.endpoint}")

        # Log pool status periodically
        current_time = time()
        if current_time - self.last_pool_log > self.pool_log_interval:
            log_pool_status()
            self.last_pool_log = current_time

        # Start monitoring this request
        g.db_monitor.__enter__()

    def after_request(self, response):
        """After request handler."""
        # End monitoring
        if hasattr(g, 'db_monitor'):
            g.db_monitor.__exit__(None, None, None)

        # Log slow requests
        if hasattr(g, 'start_time'):
            duration = time() - g.start_time
            if duration > 1.0:  # Log requests taking more than 1 second
                logger.warning(
                    f"Slow request: {request.method} {request.url} took {duration:.3f}s"
                )

        return response