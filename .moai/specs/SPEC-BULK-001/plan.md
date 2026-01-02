# Implementation Plan: SPEC-BULK-001

## TAG BLOCK

```
SPEC-ID: SPEC-BULK-001
TITLE: Bulk PDF Processing with Progress Tracking
STATUS: Planned
PHASE: Implementation
ASSIGNED: TBD
CREATED: 2025-12-31
```

## Milestones by Priority

### Primary Goal (MVP - Minimum Viable Product)

**Milestone 1: Database Schema and Job Persistence**
- Create processing_jobs table with indexes
- Create job_files table for per-file tracking
- Add database migration script
- Implement JobManager service with CRUD operations
- Unit tests for job creation, updates, and queries

**Milestone 2: Backend Job Processing Pipeline**
- Refactor upload.py to create jobs before processing
- Modify PDF processing to update job progress at each stage
- Implement status updates: validating, extracting, analyzing, renaming
- Add error handling with per-file error tracking
- Integration tests for job lifecycle

**Milestone 3: Real-Time Progress Broadcasting**
- Implement ProgressService for pub/sub messaging
- Add WebSocket support (flask-socketio or similar)
- Create /ws/job/{job_id} endpoint with authentication
- Implement progress broadcast on status changes
- Add heartbeat mechanism for connection monitoring

**Milestone 4: Frontend Progress Visualization**
- Implement ProgressWebSocket client class
- Update processing modal to show real-time progress
- Add per-file status indicators in progress list
- Implement automatic reconnection with backoff
- Add SSE fallback for WebSocket-unavailable environments

**Milestone 5: End-to-End Integration**
- Connect upload flow to job creation
- Test full batch processing with progress updates
- Verify job status persistence across reconnections
- Add cleanup job for old records
- Performance testing with 30 concurrent files

### Secondary Goal (Enhanced User Experience)

**Milestone 6: Enhanced Progress Features**
- Estimated time remaining calculation
- Processing speed metrics display
- Retry failed files functionality
- Individual file removal from queue
- Per-file processing time visualization

**Milestone 7: Notifications and Monitoring**
- Timeout warning notifications (5 minutes)
- Email notifications for long-running jobs (optional)
- Admin dashboard for monitoring active jobs
- Job statistics and analytics

**Milestone 8: Performance Optimization**
- Database query optimization with proper indexes
- WebSocket connection pooling
- Async file processing with concurrent execution
- Caching for frequently accessed job data

### Final Goal (Production Readiness)

**Milestone 9: Production Deployment**
- Load testing with 100 concurrent users
- Stress testing with maximum batch sizes (30 files)
- Security audit of WebSocket authentication
- Documentation for deployment and operations
- Monitoring and alerting setup

**Milestone 10: Advanced Features (Optional)**
- Pause/resume job functionality
- Job priority queue for registered users
- Batch operation history and search
- Export job reports as CSV

## Technical Approach

### Architecture Pattern: Event-Driven Processing with Pub/Sub

**Rationale**: Event-driven architecture enables real-time progress updates without blocking the main request thread. Pub/Sub pattern allows multiple subscribers (multiple browser tabs) to receive updates simultaneously.

**Components**:
1. Job Manager: Orchestrates processing pipeline and tracks state
2. Progress Service: Manages pub/sub messaging for progress updates
3. WebSocket Handler: Maintains persistent client connections
4. Background Workers: Execute file processing asynchronously

### Technology Stack

**Backend**:
- WebSocket: flask-socketio>=5.3.0 (latest stable)
- Task Queue: Redis + RQ (Redis Queue) or Celery for background jobs
- Database: Existing SQLAlchemy + SQLite/PostgreSQL

**Frontend**:
- WebSocket Client: socket.io-client>=4.6.0 (matches flask-socketio)
- Fallback: EventSource for SSE if WebSocket unavailable

**Technical Constraints**:
- WebSocket library must be compatible with Flask 2.3.3
- Redis/RQ requires additional infrastructure (consider in-memory queue for simplicity)
- Database migrations must be backward compatible

### Database Design

**processing_jobs Table**:
```sql
CREATE TABLE processing_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    total_files INTEGER NOT NULL CHECK (total_files > 0),
    completed_files INTEGER DEFAULT 0 CHECK (completed_files >= 0),
    failed_files INTEGER DEFAULT 0 CHECK (failed_files >= 0),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    download_url TEXT,
    error_summary TEXT,
    processing_started_at TIMESTAMP,
    processing_completed_at TIMESTAMP
);

CREATE INDEX idx_jobs_user_created ON processing_jobs(user_id, created_at DESC);
CREATE INDEX idx_jobs_status_updated ON processing_jobs(status, updated_at);
CREATE INDEX idx_jobs_cleanup ON processing_jobs(status, updated_at) WHERE status IN ('finished', 'failed');
```

**job_files Table**:
```sql
CREATE TABLE job_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES processing_jobs(id) ON DELETE CASCADE,
    original_filename VARCHAR(255) NOT NULL,
    new_filename VARCHAR(255),
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    error_message TEXT,
    error_category VARCHAR(50),
    processing_time_seconds INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_job_files_job_status ON job_files(job_id, status);
CREATE INDEX idx_job_files_status ON job_files(status);
```

### Integration with Existing Code

**Current Flow** (Synchronous):
```
Client Upload -> upload.py -> Process All Files -> Return Response
```

**New Flow** (Asynchronous with Progress):
```
Client Upload -> upload.py (create job) -> Return job_id
                      |
                      v
              Background Processing
                      |
                      +-> Validate -> Update Progress
                      +-> Extract -> Update Progress
                      +-> Analyze -> Update Progress
                      +-> Rename -> Update Progress

Progress Updates -> WebSocket/SSE -> Client UI
```

**Refactoring Strategy**:
1. Keep existing upload.py endpoint for backward compatibility
2. Add new /api/upload/batch endpoint for job-based processing
3. Extract file processing logic into reusable function called by both endpoints
4. Add job progress calls at each processing stage

## Implementation Tasks by Priority

### Priority High (MVP - Core Functionality)

**Task 1.1: Database Setup**
- File: migrations/add_processing_jobs.py
- Create processing_jobs table
- Create job_files table
- Add indexes for performance
- Test migration up/down

**Task 1.2: JobManager Service**
- File: backend/services/job_manager.py
- Implement create_job(user_id, file_count)
- Implement update_job_progress(job_id, file_index, status, message)
- Implement get_job_status(job_id)
- Implement complete_job(job_id, success_count, failed_count)
- Implement fail_job(job_id, error_message)
- Add unit tests

**Task 1.3: ProgressService**
- File: backend/services/progress_service.py
- Implement in-memory pub/sub (dict of job_id -> set of connections)
- subscribe(job_id, connection)
- unsubscribe(job_id, connection)
- broadcast(job_id, progress_data)
- Add unit tests

**Task 1.4: WebSocket Endpoint**
- File: backend/routes/websocket.py
- Install flask-socketio
- Create /ws/job/<job_id> endpoint
- Authenticate JWT on connection
- Validate job ownership
- Subscribe to progress updates
- Handle heartbeat and disconnect

**Task 1.5: Refactor Upload Route**
- File: backend/routes/upload.py
- Create job before processing starts
- Call job_manager.update_progress at each stage
- Return job_id immediately instead of waiting
- Keep existing /api/upload for backward compatibility
- Add /api/upload/batch for new flow

**Task 1.6: Frontend WebSocket Client**
- File: frontend/static/js/main.js
- Add ProgressWebSocket class
- Implement connect(), disconnect(), onMessage()
- Add reconnection logic with exponential backoff
- Update processing modal to handle real-time updates
- Add per-file progress visualization

**Task 1.7: End-to-End Integration**
- File: tests/test_bulk_processing.py
- Test full batch upload with progress
- Verify job status updates
- Test reconnection scenarios
- Test error handling and recovery

### Priority Medium (Enhanced Features)

**Task 2.1: Estimated Time Calculation**
- Track average processing time per file
- Calculate estimated remaining time
- Display in UI

**Task 2.2: Retry Failed Files**
- Add retry button in UI
- Implement retry logic in backend
- Exclude previously failed files from new job

**Task 2.3: Admin Job Monitoring**
- File: backend/routes/admin.py
- Add /api/admin/jobs endpoint
- Show active, completed, failed jobs
- Add job cancellation capability

**Task 2.4: Email Notifications (Optional)**
- File: backend/services/notification_service.py
- Send email when long-running job completes
- Configurable threshold (e.g., jobs > 5 minutes)

### Priority Low (Optimization and Polish)

**Task 3.1: Performance Optimization**
- Add Redis for pub/sub (scale beyond single server)
- Implement connection pooling for WebSocket
- Optimize database queries with EXPLAIN ANALYZE

**Task 3.2: Advanced UI Features**
- Pause/resume job functionality
- Individual file removal from queue
- Job history and search

**Task 3.3: Production Hardening**
- Load testing with Locust or similar
- Security audit of WebSocket auth
- Add rate limiting for connections
- Documentation and deployment guides

## Technical Constraints and Dependencies

### Library Version Requirements

**WebSocket Library**:
- flask-socketio>=5.3.0,<6.0.0
- python-socketio>=5.9.0,<6.0.0
- simple-websocket>=1.0.0
- Compatible with Flask 2.3.3

**Database Migrations**:
- Alembic>=1.12.0 (if not already in use)
- Or manual migration scripts (current approach)

**Frontend**:
- socket.io-client>=4.6.0,<5.0.0
- EventSource polyfill for SSE fallback

### Integration Risks

**Risk 1: WebSocket Infrastructure**
- Issue: WebSocket support may require additional production server configuration
- Mitigation: SSE fallback for unsupported environments
- Fallback: Polling-based progress updates (last resort)

**Risk 2: Background Task Execution**
- Issue: Flask development server doesn't support background tasks well
- Mitigation: Use RQ (Redis Queue) or Celery for production
- Development: Process sequentially or use threads for testing

**Risk 3: Database Lock Contention**
- Issue: Frequent job status updates may cause lock contention
- Mitigation: Use proper indexes, batch updates when possible
- Monitoring: Track database query performance

**Risk 4: Connection Scaling**
- Issue: 50 concurrent WebSocket connections per server may need tuning
- Mitigation: Connection pooling, load balancing for WebSocket
- Alternative: SSE which scales better on stateless servers

### Security Considerations

**WebSocket Authentication**:
- Validate JWT token on connection handshake
- Verify job ownership before subscribing to updates
- Rate limit connection attempts (10 per user per minute)

**Data Privacy**:
- Never broadcast file content or extracted text in progress messages
- Only broadcast status, filenames, and progress percentages
- Sanitize error messages to prevent information leakage

**Job Isolation**:
- Users can only access their own jobs
- Implement job ownership check in WebSocket handler
- Use UUIDs that are difficult to guess

### Performance Targets

**Progress Updates**:
- Broadcast within 500ms of status change
- Client receives update within 2 seconds
- Support 50 concurrent progress connections

**Database Queries**:
- Job status lookup: <100ms
- Job creation: <200ms
- Progress update: <50ms

**Memory Usage**:
- In-memory pub/sub: <10MB per 100 active jobs
- WebSocket connections: <1MB per connection

## Deployment Strategy

### Phase 1: Development
- Use Flask development server with WebSocket support
- In-memory job storage (SQLite database)
- Test with 5-10 concurrent uploads

### Phase 2: Staging
- Deploy to Gunicorn with WebSocket-enabled worker class
- Use PostgreSQL for job persistence
- Test with 30 concurrent uploads (max batch size)

### Phase 3: Production
- Use Nginx as reverse proxy with WebSocket forwarding
- Configure Redis for pub/sub if scaling across multiple servers
- Monitor WebSocket connection counts and performance
- Set up alerts for failed jobs and timeout errors

## Rollback Plan

If critical issues arise in production:
1. Disable WebSocket endpoint via configuration flag
2. Fall back to synchronous upload endpoint (existing /api/upload)
3. Existing functionality remains unchanged
4. Jobs in progress complete using SSE or polling fallback

## Dependencies

### Internal Dependencies
- Requires existing user authentication system
- Requires existing PDF processing pipeline (pdf_processor, llm_service)
- Requires existing file service (file_service)

### External Dependencies
- flask-socketio (new)
- python-socketio (new)
- Redis/RQ (optional, for production scaling)

## Testing Strategy

### Unit Tests
- JobManager service methods
- ProgressService pub/sub operations
- WebSocket authentication and subscription

### Integration Tests
- Full job lifecycle with progress updates
- Reconnection scenarios
- Error handling and recovery

### Load Tests
- 50 concurrent WebSocket connections
- 30 files per batch processing
- Measure latency and throughput

## Success Criteria

### Functional Success
- Users can upload 30 files and see real-time progress
- Job status persists across page refreshes
- Failed files show specific error messages
- Download available immediately after completion

### Performance Success
- Progress updates received within 2 seconds
- No UI blocking during processing
- Support for 50 concurrent progress connections

### User Experience Success
- Clear visual indication of processing status
- Per-file progress visible
- Reconnection automatic and seamless
- Error messages helpful and actionable
