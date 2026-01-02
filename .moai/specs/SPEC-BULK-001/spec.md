# SPEC-BULK-001: Bulk PDF Processing with Progress Tracking

## TAG BLOCK

```
SPEC-ID: SPEC-BULK-001
TITLE: Bulk PDF Processing with Progress Tracking
STATUS: Completed
PRIORITY: High
ASSIGNED: moai-workflow-tdd
CREATED: 2025-12-31
COMPLETED: 2025-12-31
DOMAIN: FEAT (Feature)
LIFECYCLE: spec-anchored
```

## Environment

### System Context
ResearchPDFFileRenamerGLM is an AI-powered PDF file renaming web application that currently processes files synchronously. The system supports batch uploads (5 anonymous, 30 authenticated) but lacks real-time progress feedback during processing, leading to poor user experience for larger batches.

### Current Limitations
- Upload endpoint processes all files sequentially without progress updates
- Frontend shows static progress animation that doesn't reflect actual processing state
- No mechanism to track per-file processing status (validating, extracting, analyzing, renaming)
- Long-running requests may timeout for large batches
- Users cannot see which specific files have succeeded/failed during processing

### User Impact
- Academic researchers uploading 20-30 files experience uncertainty during processing
- Lab managers managing large collections cannot monitor processing status
- Poor user experience for folders with many PDF files

## Assumptions

### Technical Assumptions
- WebSocket or Server-Sent Events (SSE) infrastructure can be added to Flask application
- Existing PDF processing pipeline can be modified to support async status reporting
- Database can store processing job status (in-memory or persistent)
- Frontend can establish persistent connection for real-time updates

### Business Assumptions
- Users will process larger batches if progress tracking is available
- Real-time feedback reduces user abandonment during long operations
- Progress tracking enables better resource management and debugging

### User Assumptions
- Primary users (Academic Researchers) will upload 10-30 files per session
- Secondary users (Lab Managers) will process large collections (50+ files)
- Users want visibility into which specific files succeeded/failed

## Requirements (EARS Format)

### Ubiquitous Requirements

**REQ-U-001**: The system shall always validate file type and size before processing begins.

**REQ-U-002**: The system shall always track processing status for each file in a batch.

**REQ-U-003**: The system shall always limit concurrent processing based on user tier (anonymous: 5, registered: 30).

**REQ-U-004**: The system shall always maintain processing job records with unique job identifiers.

**REQ-U-005**: The system shall always clean up temporary files after processing completion or failure.

### Event-Driven Requirements

**REQ-E-001**: WHEN a user initiates bulk file upload, the system SHALL create a processing job with unique job ID and return the job ID immediately.

**REQ-E-002**: WHEN file upload begins, the system SHALL broadcast upload progress via WebSocket/SSE to connected clients.

**REQ-E-003**: WHEN each file processing starts, the system SHALL update job status to "processing" with file identifier.

**REQ-E-004**: WHEN PDF text extraction completes for a file, the system SHALL update progress to "extracting" and broadcast status.

**REQ-E-005**: WHEN LLM metadata extraction completes for a file, the system SHALL update progress to "analyzing" and broadcast status.

**REQ-E-006**: WHEN file renaming completes, the system SHALL update progress to "complete" and broadcast success with new filename.

**REQ-E-007**: WHEN any processing step fails for a file, the system SHALL update progress to "failed" and broadcast error message.

**REQ-E-008**: WHEN all files in a job complete processing, the system SHALL update job status to "finished" and generate download URL.

**REQ-E-009**: WHEN client disconnects during processing, the system SHALL continue processing in background and maintain job status for reconnection.

**REQ-E-010**: WHEN client reconnects with existing job ID, the system SHALL resume broadcasting current job status.

### State-Driven Requirements

**REQ-S-001**: IF processing job status is "uploading", THEN the system SHALL only accept file uploads and reject duplicate files.

**REQ-S-002**: IF processing job status is "processing", THEN the system SHALL reject new file uploads for that job.

**REQ-S-003**: IF processing job status is "finished", THEN the system SHALL generate ZIP archive of all processed files and cleanup temporary files.

**REQ-S-004**: IF processing job has any failed files, THEN the system SHALL include error details in final job summary.

**REQ-S-005**: IF user is authenticated and approved, THEN the system SHALL allow up to 30 files per job.

**REQ-S-006**: IF user is anonymous or pending approval, THEN the system SHALL allow up to 5 files per job.

**REQ-S-007**: IF processing exceeds 5 minutes, THEN the system SHALL send warning notification to client.

**REQ-S-008**: IF processing exceeds 10 minutes, THEN the system SHALL terminate job and return partial results with timeout error.

### Optional Requirements

**REQ-O-001**: WHERE possible, the system SHALL provide estimated time remaining for job completion.

**REQ-O-002**: WHERE possible, the system SHALL support pause/resume functionality for large batch jobs.

**REQ-O-003**: WHERE possible, the system SHALL allow users to remove individual files from queued jobs before processing starts.

**REQ-O-004**: WHERE possible, the system SHALL send email notification when long-running jobs complete.

**REQ-O-005**: WHERE possible, the system SHALL provide detailed processing metrics (time per file, average processing speed).

### Unwanted Behavior Requirements

**REQ-UW-001**: The system shall not process files beyond user tier limits.

**REQ-UW-002**: The system shall not broadcast sensitive file content in progress updates.

**REQ-UW-003**: The system shall not allow clients to access job IDs belonging to other users.

**REQ-UW-004**: The system shall not lose processing job status if server restarts occurs.

**REQ-UW-005**: The system shall not block UI while waiting for progress updates.

## Specifications

### Functional Specifications

**SP-F-001: Job Management**
- System shall generate unique job ID using UUID format
- Job status enum: pending, uploading, processing, finished, failed, timeout
- Job record contains: job_id, user_id, total_files, completed_files, failed_files, created_at, updated_at, status
- Job records persist for 24 hours in database

**SP-F-002: Progress Tracking**
- Progress updates include: job_id, file_index, total_files, current_file, status, progress_percent, message
- Status values: queued, uploading, validating, extracting, analyzing, renaming, complete, failed
- Progress broadcast via WebSocket or Server-Sent Events (SSE)
- Client subscribes to job-specific progress channel: /progress/{job_id}

**SP-F-003: File Processing Pipeline**
- Pipeline stages: upload -> validate -> extract_text -> llm_analyze -> rename -> complete
- Each stage updates job progress before proceeding to next stage
- Failed files skip to next file without stopping entire batch
- Successful files accumulate in download folder

**SP-F-004: Real-Time Communication**
- WebSocket endpoint: /ws/job/{job_id}
- Fallback to SSE if WebSocket unavailable: /api/jobs/{job_id}/events
- Heartbeat mechanism every 30 seconds to detect disconnections
- Automatic reconnection with exponential backoff (1s, 2s, 4s, 8s, 15s max)

**SP-F-005: Error Handling**
- Per-file errors include: file_id, error_category, error_message, timestamp
- Error categories: validation_error, pdf_error, extraction_error, llm_error, file_system_error
- Job continues despite individual file failures
- Final job summary includes success_count, failed_count, error_details

### Non-Functional Specifications

**SP-NF-001: Performance**
- Progress updates broadcast within 500ms of status change
- WebSocket connection establishment under 1 second
- Client receives progress updates with maximum 2 second latency
- Support 50 concurrent progress connections

**SP-NF-002: Scalability**
- Job records stored in database for persistence across restarts
- Progress channel supports multiple subscribers (same user on multiple devices)
- Database queries for job status use indexes on job_id and user_id
- Cleanup job removes stale job records older than 24 hours

**SP-NF-003: Security**
- Job access restricted to creator (user_id match)
- WebSocket connection validates JWT token on handshake
- No sensitive file content transmitted in progress messages
- Rate limiting on WebSocket connections (10 connections per user)

**SP-NF-004: Reliability**
- At-least-once delivery guarantee for progress messages
- Client ack mechanism for critical messages (job completion)
- Automatic retry on connection failure with message replay
- Job status recoverable from database after reconnection

### Technical Specifications

**SP-T-001: Backend Components**

New File: backend/services/job_manager.py
```python
class JobManager:
    - create_job(user_id, file_count) -> job_id
    - update_job_progress(job_id, file_index, status, message)
    - get_job_status(job_id) -> job_record
    - complete_job(job_id, success_count, failed_count)
    - fail_job(job_id, error_message)
    - cleanup_old_jobs(older_than_hours=24)
```

New File: backend/services/progress_service.py
```python
class ProgressService:
    - subscribe(job_id, connection)
    - unsubscribe(job_id, connection)
    - broadcast(job_id, progress_data)
    - get_subscribers(job_id) -> list
```

Modified: backend/routes/upload.py
- Refactor to create job before processing
- Call job_manager for each processing stage
- Return job_id immediately instead of waiting for completion

New File: backend/routes/websocket.py
```python
@ws.route('/ws/job/<job_id>')
def job_progress_socket(job_id):
    - Authenticate JWT token
    - Validate job ownership
    - Subscribe to progress updates
    - Handle heartbeat/ack messages
```

**SP-T-002: Database Schema**

New Table: processing_jobs
```sql
CREATE TABLE processing_jobs (
    id UUID PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    total_files INTEGER NOT NULL,
    completed_files INTEGER DEFAULT 0,
    failed_files INTEGER DEFAULT 0,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    download_url TEXT,
    error_summary TEXT,
    INDEX idx_user_jobs (user_id, created_at),
    INDEX idx_job_status (status, updated_at)
);
```

New Table: job_files
```sql
CREATE TABLE job_files (
    id UUID PRIMARY KEY,
    job_id UUID REFERENCES processing_jobs(id),
    original_filename VARCHAR(255) NOT NULL,
    new_filename VARCHAR(255),
    status VARCHAR(20) NOT NULL,
    error_message TEXT,
    processing_time_seconds INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_job_files (job_id, status)
);
```

**SP-T-003: Frontend Components**

Modified: frontend/static/js/main.js
- New class: ProgressWebSocket
- Methods: connect(), disconnect(), onMessage(), onError(), reconnect()
- Progress modal updates to show real-time status per file
- Job status polling fallback if WebSocket unavailable

New UI Elements:
- Real-time progress bar with per-file status
- Processing queue visualization (queued, processing, complete, failed)
- Elapsed time and estimated time remaining
- Retry failed files button

**SP-T-004: Communication Protocol**

Progress Message Format (JSON):
```json
{
    "job_id": "uuid",
    "file_index": 3,
    "total_files": 10,
    "current_file": "paper1.pdf",
    "status": "analyzing",
    "progress_percent": 35,
    "message": "Extracting metadata with AI...",
    "timestamp": "2025-12-31T10:30:45Z"
}
```

Job Completion Message:
```json
{
    "job_id": "uuid",
    "status": "finished",
    "success_count": 8,
    "failed_count": 2,
    "download_url": "/api/download/renamed_pdfs_20251231.zip",
    "processing_time_seconds": 45,
    "errors": [
        {"file": "corrupt.pdf", "error": "Invalid PDF file"}
    ]
}
```

## Traceability

### Requirements to Components Mapping

| Requirement | Backend Component | Frontend Component | Database |
|-------------|------------------|-------------------|----------|
| REQ-E-001 | job_manager.create_job | - | processing_jobs |
| REQ-E-002 | progress_service.broadcast | ProgressWebSocket | - |
| REQ-E-003 to REQ-E-007 | job_manager.update_progress | ProgressWebSocket.onMessage | job_files |
| REQ-E-008 | job_manager.complete_job | showResultsInModal | processing_jobs |
| REQ-E-009 to REQ-E-010 | websocket.py | ProgressWebSocket.reconnect | processing_jobs |
| REQ-S-001 to REQ-S-006 | upload.py (validation) | processFiles | processing_jobs |
| REQ-S-007 to REQ-S-008 | job_manager (timeout) | ProgressWebSocket (warning) | processing_jobs |
| REQ-UW-003 | websocket.py (auth) | - | - |
| REQ-UW-004 | Database persistence | ProgressWebSocket.reconnect | processing_jobs |

### Test Scenarios Reference

See acceptance.md for detailed test scenarios for each requirement.
