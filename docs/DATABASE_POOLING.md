# Database Connection Pooling Configuration

This document explains the database connection pooling implementation in the Research PDF File Renamer application.

## Overview

The application uses SQLAlchemy's built-in connection pooling to manage database connections efficiently. Connection pooling helps reduce the overhead of creating new database connections for each request and improves overall application performance.

## Configuration

### Development (SQLite)
```python
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 2,         # Number of connections to keep in pool
    'max_overflow': 5,      # Number of connections that can exceed pool_size
    'pool_recycle': 1800,  # Recycle connections after 30 minutes
    'pool_pre_ping': True,  # Test connections for liveness before use
    'pool_timeout': 20,     # Timeout in seconds for getting connection from pool
}
```

### Production (PostgreSQL/MySQL)
```python
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 20,        # More connections for production
    'max_overflow': 30,     # Allow burst capacity
    'pool_recycle': 3600,   # Recycle every hour
    'pool_pre_ping': True,  # Always check connection health
    'pool_timeout': 30,     # Wait up to 30 seconds for connection
    'echo': False,          # Don't log all SQL in production
}
```

### PostgreSQL-Specific Configuration
When using PostgreSQL, the application automatically applies optimized settings:

```python
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 25,
    'max_overflow': 50,
    'pool_recycle': 3600,
    'pool_pre_ping': True,
    'pool_timeout': 30,
    'echo': False,
    'connect_args': {
        'application_name': 'research_pdf_renamer',
        'connect_timeout': 10,
    }
}
```

## Environment Variables

Set the following environment variables to configure database pooling:

```bash
# Database URL (automatically detected for PostgreSQL optimization)
DATABASE_URL=postgresql://user:password@localhost/dbname

# Flask environment (development/production)
FLASK_ENV=production
```

## Monitoring

### Admin Dashboard
Admin users can monitor database health at:
- `/api/admin/db-health` - View connection pool statistics and health status

### Log Monitoring
The application logs connection pool status periodically:
- Every 5 minutes in production
- Warning when pool usage exceeds 75%
- Critical when pool usage exceeds 90%

### Health Check API
The database health endpoint provides:
- Connection pool statistics
- Database response time
- Usage percentage and recommendations
- Pool status (healthy/warning/critical)

## Best Practices

### Choosing Pool Size

1. **Development (SQLite)**: Keep pool_size small (2-5) due to SQLite limitations
2. **Production (PostgreSQL/MySQL)**:
   - Start with pool_size = 20-25
   - Adjust based on concurrent user load
   - Rule of thumb: pool_size = concurrent_requests / 2

### Monitoring Recommendations

1. **Watch for High Usage**:
   - >75% usage: Monitor closely
   - >90% usage: Immediate action needed

2. **Performance Metrics**:
   - Response time should be <100ms
   - Pool wait time should be minimal

3. **Database-Specific Considerations**:
   - PostgreSQL: Can handle larger pools (50+ connections)
   - MySQL: Moderate pools (20-30 connections)
   - SQLite: Small pools (2-5 connections)

## Troubleshooting

### Common Issues

1. **Pool Exhaustion**:
   - Error: "Connection pool exhausted"
   - Solution: Increase pool_size or max_overflow
   - Check for connection leaks in code

2. **Slow Response Times**:
   - Check pool_usage percentage
   - Monitor database server performance
   - Consider query optimization

3. **Connection Timeouts**:
   - Increase pool_timeout value
   - Check database server responsiveness
   - Verify network connectivity

### Performance Tuning

1. **For High Traffic**:
   ```python
   SQLALCHEMY_ENGINE_OPTIONS = {
       'pool_size': 50,
       'max_overflow': 100,
       'pool_recycle': 1800,  # Shorter recycle for high traffic
       'pool_pre_ping': True,
       'pool_timeout': 60,   # Longer timeout
   }
   ```

2. **For Low Traffic**:
   ```python
   SQLALCHEMY_ENGINE_OPTIONS = {
       'pool_size': 5,
       'max_overflow': 10,
       'pool_recycle': 7200,  # Longer recycle
       'pool_pre_ping': True,
       'pool_timeout': 30,
   }
   ```

## Migration Guide

To migrate from the old configuration:

1. The application automatically uses connection pooling
2. No code changes required
3. Set appropriate environment variables
4. Monitor `/api/admin/db-health` for performance metrics

## Additional Resources

- [SQLAlchemy Connection Pooling](https://docs.sqlalchemy.org/en/14/core/pooling.html)
- [PostgreSQL Connection Management](https://www.postgresql.org/docs/current/runtime-config-connection.html)
- [MySQL Connection Handling](https://dev.mysql.com/doc/refman/8.0/en/connection-control.html)