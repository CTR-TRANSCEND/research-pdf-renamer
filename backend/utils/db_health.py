"""Database health monitoring utilities."""

import time
from flask import current_app
from backend.database import db
from sqlalchemy import text


def get_connection_pool_stats():
    """Get statistics about the database connection pool."""
    try:
        engine = db.engine
        pool = engine.pool

        # Get pool information
        pool_info = {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "status": "healthy",
            "timestamp": time.time(),
        }

        # Calculate usage percentage
        total_connections = pool_info["checked_out"]
        max_connections = pool.size() + pool.max_overflow
        if max_connections > 0:
            pool_info["usage_percentage"] = round(
                (total_connections / max_connections) * 100, 2
            )
        else:
            pool_info["usage_percentage"] = 0

        # Determine pool health
        if pool_info["usage_percentage"] > 90:
            pool_info["status"] = "critical"
        elif pool_info["usage_percentage"] > 75:
            pool_info["status"] = "warning"

        return pool_info

    except Exception as e:
        return {"status": "error", "error": str(e), "timestamp": time.time()}


def check_database_health():
    """Check if database is responding and connection pool is healthy."""
    try:
        # Simple database ping
        start_time = time.time()
        result = db.session.execute(text("SELECT 1"))
        response_time = time.time() - start_time

        # Get pool stats
        pool_stats = get_connection_pool_stats()

        health = {
            "database_responsive": True,
            "response_time_ms": round(response_time * 1000, 2),
            "pool_stats": pool_stats,
            "timestamp": time.time(),
        }

        # Determine overall health
        if health["response_time_ms"] > 5000:  # More than 5 seconds
            health["status"] = "critical"
        elif health["response_time_ms"] > 1000:  # More than 1 second
            health["status"] = "warning"
        elif pool_stats.get("status") in ["critical", "warning"]:
            health["status"] = pool_stats["status"]
        else:
            health["status"] = "healthy"

        return health

    except Exception as e:
        return {
            "database_responsive": False,
            "status": "error",
            "error": str(e),
            "timestamp": time.time(),
        }


def log_pool_status():
    """Log the current status of the connection pool for monitoring."""
    try:
        pool_stats = get_connection_pool_stats()

        if pool_stats["status"] == "healthy":
            current_app.logger.info(
                f"DB Pool: {pool_stats['checked_out']}/{pool_stats['pool_size']} connections in use"
            )
        elif pool_stats["status"] == "warning":
            current_app.logger.warning(
                f"DB Pool warning: {pool_stats['usage_percentage']}% usage"
            )
        elif pool_stats["status"] == "critical":
            current_app.logger.error(
                f"DB Pool critical: {pool_stats['usage_percentage']}% usage"
            )

    except Exception as e:
        current_app.logger.error(f"Error checking DB pool status: {e}")


class ConnectionPoolMonitor:
    """Context manager to monitor database connection usage during operations."""

    def __init__(self, operation_name="operation"):
        self.operation_name = operation_name
        self.start_time = None
        self.start_connections = None

    def __enter__(self):
        self.start_time = time.time()
        pool = db.engine.pool
        # StaticPool (used for in-memory SQLite) doesn't have checkedout()
        if hasattr(pool, "checkedout"):
            self.start_connections = pool.checkedout()
        else:
            self.start_connections = 0
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = time.time()
        pool = db.engine.pool
        # StaticPool (used for in-memory SQLite) doesn't have checkedout()
        if hasattr(pool, "checkedout"):
            end_connections = pool.checkedout()
        else:
            end_connections = 0

        duration = end_time - self.start_time
        connections_used = end_connections - self.start_connections

        if connections_used > 0:
            current_app.logger.info(
                f"DB Operation '{self.operation_name}': "
                f"{duration:.3f}s, +{connections_used} connections"
            )

        if exc_type is not None:
            current_app.logger.error(
                f"DB Operation '{self.operation_name}' failed after {duration:.3f}s"
            )
