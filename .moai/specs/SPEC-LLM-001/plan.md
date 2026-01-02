# Implementation Plan - SPEC-LLM-001

| Metadata | Value |
|----------|-------|
| **SPEC ID** | SPEC-LLM-001 |
| **Plan Version** | 1.0 |
| **Last Updated** | 2025-12-31 |
| **Estimated Complexity** | Medium |
| **File Changes** | 4 backend, 2 frontend, 2 test files |

---

## Milestones (Priority-Based)

### Primary Goal - Core Ollama Integration
**Priority**: High
**Dependencies**: None
**Deliverables**:
- Functional Ollama API integration in llm_service.py
- Backend API endpoints for Ollama configuration
- Basic frontend UI for Ollama URL input
- Connection testing functionality

**Success Criteria**:
- Ollama PDF extraction working end-to-end
- Admin panel can configure Ollama URL
- Connection tests pass with local Ollama server
- OpenAI functionality unchanged (regression test pass)

### Secondary Goal - Enhanced User Experience
**Priority**: Medium
**Dependencies**: Primary Goal completion
**Deliverables**:
- Dynamic model listing from Ollama server
- Model list caching for performance
- Improved error messages with troubleshooting guidance
- Visual feedback for connection status

**Success Criteria**:
- Model dropdown populated from actual Ollama server
- Connection status indicator shows accurate state
- Error messages guide users to resolution
- Model list cache reduces API calls effectively

### Final Goal - Polish and Documentation
**Priority**: Low
**Dependencies**: Secondary Goal completion
**Deliverables**:
- Comprehensive test coverage (>=85%)
- Admin user guide for Ollama setup
- API documentation updates
- Performance optimization review

**Success Criteria**:
- All tests passing with high coverage
- User documentation complete and clear
- Code reviewed and optimized
- Performance benchmarks documented

### Optional Goal - Advanced Features
**Priority**: Optional
**Dependencies**: Final Goal completion
**Deliverables**:
- Response time display for Ollama server
- Connection test button with live feedback
- URL suggestions from history
- Authentication preparation for future Ollama versions

**Success Criteria**:
- Advanced features working as designed
- No negative impact on core functionality
- Well-documented for future maintenance

---

## Technical Approach

### Architecture Overview

The implementation follows a layered approach:

1. **Data Layer**: SystemSettings model already supports `ollama_url` (no changes needed)
2. **Service Layer**: LLMService class with Ollama integration
3. **API Layer**: Admin routes with Ollama-specific endpoints
4. **Presentation Layer**: Admin panel UI with dynamic forms

### Component Design

#### Backend Components

**1. LLMService Ollama Integration**
- File: `backend/services/llm_service.py`
- Method: `_extract_with_ollama()` - Replace NotImplementedError
- Method: `_fetch_ollama_models(ollama_url)` - New method for model discovery
- Method: `_test_ollama_connection(ollama_url)` - New method for connection testing
- Caching: In-memory cache with 10-minute TTL for model lists

**2. Admin API Enhancements**
- File: `backend/routes/admin.py`
- GET `/api/admin/llm-settings` - Add ollama_url and ollama_models to response
- POST `/api/admin/llm-settings` - Accept and validate ollama_url parameter
- POST `/api/admin/test-ollama` - New endpoint for connection testing

**3. URL Validation**
- Use Python `urllib.parse` for URL parsing
- Validate HTTP/HTTPS scheme
- Validate hostname format
- Optional port validation (1-65535)

#### Frontend Components

**1. Admin Panel Form**
- File: `frontend/templates/admin.html`
- Add URL input field (conditional display based on provider)
- Add connection status indicator
- Add test connection button
- Update model dropdown to be dynamic

**2. JavaScript Logic**
- File: `frontend/static/js/main.js`
- Provider selection change handler
- Connection test AJAX call
- Model dropdown population
- Error message display

### Data Flow

**Configuration Flow:**
1. Admin selects Ollama provider in dropdown
2. Frontend shows Ollama URL input field
3. Admin enters URL and clicks Test Connection
4. Frontend calls `/api/admin/test-ollama` endpoint
5. Backend validates URL and tests connection
6. Backend returns connection status and model list
7. Frontend updates UI with status and populates model dropdown
8. Admin clicks Save Settings
9. Frontend sends POST to `/api/admin/llm-settings`
10. Backend saves configuration to database

**PDF Extraction Flow:**
1. User uploads PDF via main interface
2. Backend extracts text from first 1-2 pages
3. LLMService checks configured provider (OpenAI or Ollama)
4. If Ollama: calls `_extract_with_ollama()` with configured URL and model
5. Backend constructs request to `{ollama_url}/api/generate`
6. Backend sends POST request with prompt and options
7. Ollama server returns JSON response
8. Backend parses response and extracts metadata
9. Backend returns formatted metadata to frontend
10. Frontend displays results and offers download

### Error Handling Strategy

**Connection Errors:**
- Timeout after 10 seconds
- Catch all `requests.exceptions.RequestException`
- Return user-friendly error message
- Log technical details for debugging
- Fall back to default model list

**Validation Errors:**
- Validate URL format before connection attempt
- Return specific error for invalid URL format
- Suggest correct URL format in error message

**Runtime Errors:**
- Handle Ollama server errors during PDF extraction
- Return error to user with retry suggestion
- Log full error stack for administrators

---

## File Changes

### Backend Files

#### 1. `backend/services/llm_service.py`
**Changes**:
- Implement `_extract_with_ollama()` method
- Add `_fetch_ollama_models(ollama_url)` method
- Add `_test_ollama_connection(ollama_url)` method
- Add model list caching with TTL

**Lines to Add**: ~150 lines
**Complexity**: Medium

#### 2. `backend/routes/admin.py`
**Changes**:
- GET `/api/admin/llm-settings`: Add ollama_url and ollama_models to response
- POST `/api/admin/llm-settings`: Accept ollama_url parameter, validate, test connection
- Add POST `/api/admin/test-ollama` endpoint

**Lines to Add**: ~80 lines
**Lines to Modify**: ~20 lines
**Complexity**: Medium

#### 3. `backend/models/settings.py`
**Changes**: None required (ollama_url already exists)
**Complexity**: None

#### 4. `requirements.txt`
**Changes**:
- Add `requests>=2.31.0` if not present (verify existing dependencies)

**Lines to Add**: 0-1 lines
**Complexity**: Low

### Frontend Files

#### 5. `frontend/templates/admin.html`
**Changes**:
- Add Ollama URL input field (conditional display)
- Add connection status indicator
- Add test connection button
- Update model dropdown ID for dynamic population

**Lines to Add**: ~30 lines
**Lines to Modify**: ~10 lines
**Complexity**: Low

#### 6. `frontend/static/js/main.js`
**Changes**:
- Add provider selection change handler
- Add connection test button handler
- Add model dropdown population logic
- Add error message display logic

**Lines to Add**: ~80 lines
**Complexity**: Medium

### Test Files (New)

#### 7. `tests/test_llm_service.py` (NEW)
**Tests**:
- Test Ollama connection success
- Test Ollama connection failure
- Test model listing with mocked API
- Test model caching mechanism
- Test PDF extraction with Ollama
- Test error handling

**Lines to Add**: ~200 lines
**Complexity**: Medium

#### 8. `tests/test_admin_api.py` (NEW)
**Tests**:
- Test GET llm-settings returns ollama_url
- Test POST llm-settings accepts valid ollama_url
- Test POST llm-settings rejects invalid ollama_url
- Test test-ollama endpoint with real server
- Test test-ollama endpoint with unreachable server

**Lines to Add**: ~150 lines
**Complexity**: Medium

---

## Implementation Steps

### Step 1: Backend Foundation
**Priority**: High
**File**: `backend/services/llm_service.py`
**Tasks**:
- Implement `_test_ollama_connection(ollama_url)` method
- Implement `_fetch_ollama_models(ollama_url)` method
- Implement `_extract_with_ollama()` method
- Add model list caching
- Write unit tests for new methods

**Acceptance**:
- Unit tests pass
- Connection test works with real Ollama server
- Model listing returns array of model names
- PDF extraction returns formatted metadata

### Step 2: API Layer
**Priority**: High
**File**: `backend/routes/admin.py`
**Tasks**:
- Update GET `/api/admin/llm-settings` to include ollama_url and models
- Update POST `/api/admin/llm-settings` to accept and validate ollama_url
- Add POST `/api/admin/test-ollama` endpoint
- Write integration tests for API endpoints

**Acceptance**:
- API tests pass
- GET returns ollama_url in response
- POST saves valid ollama_url to database
- Connection test endpoint returns status and models

### Step 3: Frontend UI
**Priority**: High
**Files**: `frontend/templates/admin.html`, `frontend/static/js/main.js`
**Tasks**:
- Add Ollama URL input field to admin form
- Add connection test button
- Add provider selection handler
- Add connection test handler
- Add model dropdown population logic
- Write frontend tests (manual or automated)

**Acceptance**:
- URL field shows/hides based on provider
- Connection test button works
- Model dropdown populates from API
- Error messages display correctly

### Step 4: Integration Testing
**Priority**: High
**Tasks**:
- End-to-end test: Configure Ollama, extract PDF metadata
- Regression test: Verify OpenAI still works
- Performance test: Measure Ollama response time
- Error handling test: Test with unreachable Ollama server

**Acceptance**:
- End-to-end workflow succeeds
- OpenAI functionality unchanged
- Performance acceptable (<30 seconds per PDF)
- Errors handled gracefully

### Step 5: Polish and Documentation
**Priority**: Medium
**Tasks**:
- Review code and refactor if needed
- Add code comments
- Update admin user guide
- Add troubleshooting section
- Performance optimization if needed

**Acceptance**:
- Code reviewed and clean
- Documentation complete
- Performance meets criteria
- User guide tested by non-technical user

### Step 6: Advanced Features (Optional)
**Priority**: Low
**Tasks**:
- Add response time display
- Implement URL history suggestions
- Add connection test progress indicator
- Prepare for future Ollama authentication

**Acceptance**:
- Advanced features work as designed
- No negative impact on core functionality

---

## Testing Strategy

### Unit Testing
**Framework**: pytest
**Coverage Target**: >=85%

**Tests to Write**:
- `test_ollama_connection_success()`
- `test_ollama_connection_timeout()`
- `test_ollama_connection_invalid_url()`
- `test_fetch_ollama_models_success()`
- `test_fetch_ollama_models_caching()`
- `test_extract_with_ollama_success()`
- `test_extract_with_ollama_error_handling()`

### Integration Testing
**Framework**: pytest with test fixtures

**Tests to Write**:
- `test_get_llm_settings_includes_ollama_url()`
- `test_post_llm_settings_saves_ollama_url()`
- `test_post_llm_settings_validates_url_format()`
- `test_test_ollama_connection_endpoint()`
- `test_ollama_pdf_extraction_end_to_end()`

### Frontend Testing
**Approach**: Manual testing + optional automated tests

**Test Scenarios**:
- Select Ollama provider, verify URL field appears
- Enter invalid URL, verify validation error
- Enter valid URL, click test, verify success status
- Change URL, verify model list updates
- Save settings, reload page, verify URL persists

### Regression Testing
**Focus**: OpenAI functionality

**Test Scenarios**:
- Select OpenAI provider, verify Ollama fields hidden
- Save OpenAI settings, verify configuration unchanged
- Upload PDF with OpenAI, verify extraction works
- Verify no errors in logs when using OpenAI

---

## Risk Mitigation

### Risk: Ollama API Changes
**Mitigation**:
- Version-specific checks in code
- Graceful degradation on API mismatches
- Clear error messages for users

### Risk: Performance Issues
**Mitigation**:
- Model list caching to reduce API calls
- Connection timeout to prevent hangs
- Performance benchmarks before implementation
- User expectations set in documentation

### Risk: OpenAI Regression
**Mitigation**:
- Comprehensive regression test suite
- Code review focused on OpenAI paths
- Isolation of Ollama logic from OpenAI logic
- Beta testing with selected users

### Risk: Network/Firewall Issues
**Mitigation**:
- Clear error messages with troubleshooting steps
- Specific error for timeout vs connection refused
- Documentation for common firewall scenarios
- Support for HTTPS URLs

---

## Performance Considerations

### Expected Performance
- Connection test: <10 seconds (timeout)
- Model listing: <5 seconds for typical servers
- PDF extraction: <30 seconds (depends on model and hardware)

### Optimization Strategies
- Model list caching (10-minute TTL)
- Connection timeout (10 seconds)
- Asynchronous UI updates
- Efficient error handling without blocking

### Monitoring
- Log Ollama response times
- Track connection failure rates
- Monitor cache hit rates
- Measure user-reported issues

---

## Dependencies and Prerequisites

### External Dependencies
- Ollama server installed and running
- Python `requests` library
- Network connectivity to Ollama server

### Internal Dependencies
- SystemSettings model (already exists)
- Admin panel infrastructure (already exists)
- LLM service architecture (already exists)

### Setup Requirements
- Ollama server for testing
- Test PDF files
- Local development environment

---

## Rollout Plan

### Phase 1: Development
- Implement backend changes
- Implement frontend changes
- Write comprehensive tests
- Internal testing with development team

### Phase 2: Alpha Testing
- Deploy to staging environment
- Test with internal Ollama server
- Fix bugs and refine UX
- Gather feedback from alpha users

### Phase 3: Beta Release
- Deploy to production
- Monitor error logs and performance
- Gather user feedback
- Fix any remaining issues

### Phase 4: Documentation
- Complete user guide
- Add troubleshooting section
- Update API documentation
- Create video tutorial (optional)

---

## Success Metrics

### Functional Metrics
- Ollama configuration success rate: >95%
- PDF extraction success rate with Ollama: >90%
- Connection test completion time: <10 seconds
- Error message clarity score: >4/5 from user feedback

### Quality Metrics
- Test coverage: >=85%
- Zero regression bugs in OpenAI functionality
- Code review approval
- No security vulnerabilities

### User Experience Metrics
- Time to configure Ollama: <5 minutes
- User satisfaction score: >4/5
- Support ticket reduction for LLM configuration
- Documentation helpfulness rating

---

## HISTORY

### 2025-12-31 - Initial Implementation Plan
- Created comprehensive implementation plan
- Defined priority-based milestones
- Detailed technical approach and architecture
- Listed all file changes with complexity estimates
- Outlined testing strategy and risk mitigation
