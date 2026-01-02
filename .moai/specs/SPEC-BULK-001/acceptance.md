# Acceptance Criteria: SPEC-BULK-001

## TAG BLOCK

```
SPEC-ID: SPEC-BULK-001
TITLE: Bulk PDF Processing with Progress Tracking
STATUS: Planned
PHASE: Acceptance Testing
ASSIGNED: TBD
CREATED: 2025-12-31
```

## Definition of Done

A requirement is considered complete when:
1. All acceptance criteria pass verification
2. Unit tests achieve 85%+ code coverage
3. Integration tests cover all normal and error scenarios
4. Documentation is updated (API docs, user guide)
5. Code review approved and merged
6. No critical bugs or security vulnerabilities

## Quality Gate Criteria

**TRUST 5 Validation**:
- Test-first: All requirements covered by automated tests
- Readable: Clear variable names and code comments
- Unified: Consistent formatting with existing codebase
- Secured: OWASP compliance for WebSocket authentication
- Trackable: Commit messages reference SPEC-BULK-001

## Test Scenarios (Given-When-Then Format)

### Scenario Group: Job Creation and Management

**Scenario 1: Create job on batch upload**
Given I am an authenticated approved user
When I upload 10 PDF files via /api/upload/batch
Then a processing job is created with unique job_id
And job status is "pending"
And total_files equals 10
And response includes job_id
And response returns within 1 second

**Scenario 2: Anonymous user job creation**
Given I am an anonymous user (not authenticated)
When I upload 5 PDF files via /api/upload/batch
Then a processing job is created with user_id = null
And job limit is enforced (maximum 5 files)
And response includes job_id

**Scenario 3: Exceed file limit rejection**
Given I am an anonymous user
When I attempt to upload 6 PDF files
Then request is rejected with 400 status
And error message specifies maximum file limit
And no job is created

### Scenario Group: Progress Tracking

**Scenario 4: Real-time progress updates**
Given I have created a batch processing job with job_id
When I connect to WebSocket endpoint /ws/job/{job_id}
Then connection is established successfully
And I receive "connected" confirmation message
And progress updates are broadcast for each file
And each update includes: file_index, status, progress_percent

**Scenario 5: Progress status transitions**
Given a file is being processed
When processing moves through stages
Then status transitions are: queued -> validating -> extracting -> analyzing -> renaming -> complete
And each status update is broadcast within 500ms
And progress_percent increases monotonically (0% to 100%)

**Scenario 6: Multiple subscribers receive updates**
Given a processing job is in progress
When multiple browser tabs subscribe to the same job_id
Then all tabs receive identical progress updates
And updates are broadcast to all subscribers simultaneously

**Scenario 7: WebSocket authentication required**
Given I am not authenticated (no JWT token)
When I attempt to connect to /ws/job/{job_id}
Then connection is rejected with 4011 error code
And error message indicates authentication required

**Scenario 8: WebSocket job ownership validation**
Given I am authenticated as user A
When I attempt to connect to job owned by user B
Then connection is rejected with 403 error code
And error message indicates unauthorized access

### Scenario Group: File Processing Pipeline

**Scenario 9: Successful file processing with progress**
Given a job contains 5 valid PDF files
When processing starts
Then progress updates show each file completing
And completed_files count increments after each file
And final job status is "finished"
And download_url is generated

**Scenario 10: Failed file processing**
Given a job contains 3 valid PDFs and 1 corrupted PDF
When processing starts
Then 3 files complete successfully
And corrupted file status changes to "failed"
And error message specifies "Invalid PDF file"
And job continues with remaining files
And failed_files count equals 1

**Scenario 11: All files fail**
Given a job contains 5 invalid PDF files
When processing starts
Then all 5 files fail with appropriate error messages
And job status changes to "finished" (not failed)
And download_url is null
And error_summary contains all 5 errors

### Scenario Group: Error Handling and Recovery

**Scenario 12: WebSocket disconnection during processing**
Given I am connected to job progress updates
When my WebSocket connection drops
Then processing continues in background
And job status is updated in database
And progress continues for other subscribers

**Scenario 13: Client reconnection to active job**
Given I was disconnected from an active job
When I reconnect with the same job_id
Then I receive current job status immediately
And progress updates resume from current state
And no progress messages are lost

**Scenario 14: LLM API failure handling**
Given LLM service is unavailable (API error)
When file processing reaches analysis stage
Then file status changes to "failed"
And error_category is "llm_error"
And error_message includes API error details
And remaining files continue processing

**Scenario 15: Database connection recovery**
Given database connection is lost during processing
When connection is restored
Then in-memory progress state is synchronized to database
And no job updates are lost

### Scenario Group: User Interface

**Scenario 16: Processing modal shows real-time progress**
Given I have uploaded 10 files
When processing begins
Then processing modal displays
And overall progress bar updates in real-time
And per-file status indicators show individual progress
And elapsed time counter increments

**Scenario 17: Progress indicators color coding**
Given files are in various processing states
When processing modal is displayed
Then queued files show gray color
And processing files show blue color
And completed files show green color
And failed files show red color

**Scenario 18: Results display after completion**
Given all files complete processing
When job finishes
Then modal shows completion summary
And success_count and failed_count are displayed
And success_rate percentage is calculated
And download button is available
And processed files list shows old_name -> new_name mappings

**Scenario 19: Failed files error details**
Given a job completed with 2 failed files
When results are displayed
Then failed files section shows error details
And error messages are specific and actionable
And error categories are displayed

### Scenario Group: Performance and Scalability

**Scenario 20: Large batch processing (30 files)**
Given I am an approved registered user
When I upload 30 PDF files
Then job is created successfully
And progress updates are broadcast for all 30 files
And processing completes without timeout
And UI remains responsive during processing

**Scenario 21: Concurrent job processing**
Given 5 users each upload 10 files simultaneously
When all jobs process concurrently
Then each job receives correct progress updates
And no cross-talk between jobs occurs
And all jobs complete successfully

**Scenario 22: Progress update latency**
Given a job is processing files
When status changes occur
Then progress updates are broadcast within 500ms
And client receives updates within 2 seconds
And progress_percent reflects current state accurately

### Scenario Group: Data Persistence

**Scenario 23: Job status survives server restart**
Given a job is in progress
When server restarts
Then job status is persisted in database
And job status is recoverable on restart
And reconnection resumes progress updates

**Scenario 24: Historical job access**
Given I completed a job 2 hours ago
When I attempt to access job status
Then job record is still available
And job details are accurate
And download_url is still valid (if within cleanup window)

### Scenario Group: Security and Access Control

**Scenario 25: Job isolation between users**
Given user A has created a job
When user B attempts to access user A's job_id
Then access is denied with 403 error
And no job details are revealed

**Scenario 26: WebSocket rate limiting**
Given I attempt to open 20 WebSocket connections
When connection limit is exceeded
Then connection 11+ are rejected with 429 error
And error message specifies connection limit

**Scenario 27: No sensitive data in progress messages**
Given a file contains sensitive research data
When progress updates are broadcast
Then file content is never included in messages
And extracted text is never transmitted
And only filename and status are shared

### Scenario Group: Cleanup and Maintenance

**Scenario 28: Automatic job cleanup**
Given jobs older than 24 hours exist
When cleanup job runs
Then old jobs are marked for deletion
And associated job_files records are deleted
And disk space is reclaimed

**Scenario 29: Temporary file cleanup**
Given a job has completed (success or failure)
When 30 minutes have elapsed
Then temporary files are deleted
And processed files remain available for download
And cleanup job updates download status

### Scenario Group: Optional Features

**Scenario 30: Estimated time remaining (O)**
Given I am processing a batch of files
When 5 files have completed
Then estimated time remaining is displayed
And estimate is based on average processing time
And estimate updates every 30 seconds

**Scenario 31: Retry failed files (O)**
Given a job completed with 3 failed files
When I click "Retry Failed Files" button
Then new job is created with only failed files
And previous errors are displayed for reference
And new job processes only the failed files

**Scenario 32: Email notification for long job (O)**
Given a job takes 6 minutes to complete
When job finishes
Then email notification is sent to user
And email includes job summary and download link
And email notification feature can be disabled

## Test Data Requirements

### Valid PDF Files
- Standard academic paper PDF (text extractable)
- PDF with abstract on page 2
- PDF with complex formatting
- Large PDF (>5MB)

### Invalid PDF Files
- Corrupted PDF file
- Scanned image-only PDF (no extractable text)
- Password-protected PDF
- Empty PDF file

### User Accounts
- Anonymous user (no authentication)
- Registered unapproved user
- Registered approved user
- Admin user

## Verification Methods

### Automated Testing
- pytest for unit and integration tests
- pytest-flask for Flask endpoint testing
- pytest-socketio for WebSocket testing
- Coverage reporting with pytest-cov

### Manual Testing
- Browser-based testing for UI interactions
- WebSocket connection testing with browser DevTools
- Multi-tab testing for subscriber scenarios
- Mobile browser testing for responsive design

### Performance Testing
- Locust for load testing
- Custom scripts for concurrent WebSocket connections
- Database query performance analysis with EXPLAIN

### Security Testing
- OWASP ZAP for WebSocket security
- Authentication bypass testing
- Job isolation testing
- Input validation testing

## Success Metrics

### Functional Metrics
- Job creation success rate: 100%
- Progress delivery success rate: 99%+
- File processing success rate: 95%+ (existing baseline)
- Reconnection success rate: 95%+

### Performance Metrics
- Progress update latency: <500ms (backend), <2s (end-to-end)
- WebSocket connection establishment: <1s
- Job creation response time: <200ms
- Database query times: <100ms for job status

### User Experience Metrics
- User satisfaction with progress visibility: 90%+
- Reduction in support tickets about "stuck" uploads: 80%+
- Average session duration increase (users upload more files)

### Reliability Metrics
- WebSocket connection uptime: 99%+
- Job status persistence: 100% (survives restarts)
- Failed file error accuracy: 95%+

## Rollback Criteria

Rollback to synchronous processing if:
- Progress updates fail to deliver for >10% of jobs
- WebSocket connections cause server instability
- Database performance degrades >50%
- Security vulnerabilities identified in WebSocket implementation
- User experience worsens compared to current system
