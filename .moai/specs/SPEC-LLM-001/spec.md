# SPEC-LLM-001: Ollama LLM Integration with Full Configuration Support

| Metadata | Value |
|----------|-------|
| **SPEC ID** | SPEC-LLM-001 |
| **Title** | Ollama LLM Integration with Full Configuration Support |
| **Status** | Completed |
| **Priority** | High |
| **Created** | 2025-12-31 |
| **Domain** | LLM Service Configuration |
| **Complexity** | Medium |
| **Related SPECs** | None |
| **Assigned** | TBD |

---

## Executive Summary

Enhance the Admin Panel LLM Settings to support Ollama models with full configuration capabilities including configurable URL, port, and dynamic model discovery. The current system has placeholder support for Ollama but lacks actual API integration and configuration options for remote Ollama servers.

**Business Value:**
- Enables privacy-focused local LLM processing
- Supports flexible deployment scenarios (local and remote Ollama servers)
- Provides cost-free alternative to OpenAI API
- Maintains existing OpenAI functionality without changes

---

## Environment

### System Context
- **Application**: ResearchPDFFileRenamerGLM (Flask-based web application)
- **Current LLM Providers**: OpenAI (fully functional), Ollama (placeholder only)
- **Admin Panel**: `/admin` route with LLM Settings tab
- **Target Users**: System administrators configuring LLM services

### Technical Environment
- **Backend**: Flask 2.3.3, Python 3.12+
- **Frontend**: Vanilla JavaScript, Tailwind CSS
- **Database**: SQLite with SQLAlchemy ORM
- **Current Ollama Status**:
  - Hardcoded model list in backend (llama2, codellama, mistral, vicuna)
  - `ollama_url` setting exists in SystemSettings but not exposed in API
  - `_extract_with_ollama()` raises NotImplementedError
  - No URL/port configuration UI

### Dependencies
- **Ollama Server**: Must be running and accessible (local or remote)
- **Ollama API**: REST API at `/api/tags` (list models) and `/api/generate` (generate completion)
- **Python requests library**: Required for HTTP calls to Ollama API

---

## Assumptions

### Technical Assumptions

| Assumption | Confidence | Risk if Wrong | Validation Method |
|------------|------------|---------------|-------------------|
| Ollama server provides `/api/tags` endpoint for model listing | High | Medium - model discovery fails | Test with actual Ollama instance |
| Ollama server uses standard port 11434 by default | High | Low - user can configure | Verify Ollama documentation |
| Ollama API returns JSON responses | High | High - parsing errors | Review Ollama API specification |
| Python `requests` library available or can be added | High | Low - add dependency | Check requirements.txt |

### Business Assumptions

| Assumption | Confidence | Risk if Wrong | Validation Method |
|------------|------------|---------------|-------------------|
| Users want to use remote Ollama servers, not just local | Medium | Low - feature still useful for local | User survey or feedback |
| Ollama processing speed is acceptable for users | Medium | Medium - poor UX | Performance testing with typical PDFs |
| OpenAI configuration must remain unchanged | High | High - regression risk | User confirmation and testing |

### Integration Assumptions

| Assumption | Confidence | Risk if Wrong | Validation Method |
|------------|------------|---------------|-------------------|
| SystemSettings model can store Ollama URL | High | Low - already exists | Review settings.py line 103 |
| Admin panel UI can accommodate new input fields | High | Low - sufficient space | Review admin.html layout |
| LLM service architecture supports multiple providers | High | Low - already designed | Review llm_service.py structure |

---

## Requirements (EARS Format)

### Ubiquitous Requirements

**UB-001:** The system shall always validate Ollama URL format before saving to database.
WHY: Invalid URLs cause connection failures and poor user experience.
IMPACT: Prevents configuration errors and reduces support requests.

**UB-002:** The system shall always mask sensitive configuration information in API responses.
WHY: Security best practice to prevent information leakage.
IMPACT: Maintains security posture even with new configuration fields.

**UB-003:** The system shall always preserve existing OpenAI configuration functionality.
WHY: OpenAI is working correctly and must not be disrupted.
IMPACT: Zero regression risk for existing OpenAI users.

**UB-004:** The system shall always handle Ollama connection errors gracefully.
WHY: Network issues and server downtime are inevitable.
IMPACT: Prevents application crashes and provides clear error messages.

### Event-Driven Requirements

**ED-001:** WHEN administrator selects Ollama as LLM provider, THEN the system shall display Ollama URL and port configuration fields.
WHY: Configuration fields are only relevant for Ollama provider.
IMPACT: Cleaner UI and reduced user confusion.

**ED-002:** WHEN administrator saves LLM settings with Ollama provider, THEN the system shall validate the Ollama server connection before accepting configuration.
WHY: Prevents saving invalid configuration that would fail during actual use.
IMPACT: Higher configuration success rate and better UX.

**ED-003:** WHEN administrator changes Ollama URL, THEN the system shall fetch available models from the new server.
WHY: Different Ollama servers may have different models installed.
IMPACT: Accurate model selection and reduced errors.

**ED-004:** WHEN Ollama server connection fails during model listing, THEN the system shall display error message and fall back to default model list.
WHY: Graceful degradation prevents complete configuration failure.
IMPACT: Users can still configure Ollama even with temporary network issues.

**ED-005:** WHEN PDF metadata extraction is requested with Ollama provider, THEN the system shall call Ollama `/api/generate` endpoint with configured URL and model.
WHY: Actual integration replaces NotImplementedError placeholder.
IMPACT: Ollama becomes fully functional for PDF processing.

### State-Driven Requirements

**SD-001:** IF Ollama URL is not provided, THEN the system shall use default value `http://localhost:11434`.
WHY: Sensible default for local Ollama installations.
IMPACT: Simplifies setup for users with local Ollama.

**SD-002:** IF Ollama URL includes port (e.g., `http://server:11434`), THEN the system shall parse and use the full URL as provided.
WHY: Flexibility for non-standard port configurations.
IMPACT: Supports diverse deployment scenarios.

**SD-003:** IF Ollama server connection test succeeds, THEN the system shall cache model list for 10 minutes.
WHY: Reduces API calls and improves performance.
IMPACT: Faster configuration page loads and reduced server load.

**SD-004:** IF Ollama server is unreachable, THEN the system shall display descriptive error message with troubleshooting suggestions.
WHY: Helps users diagnose and fix configuration issues.
IMPACT: Reduced support burden and better self-service capability.

**SD-005:** IF OpenAI is selected as provider, THEN the system shall hide Ollama-specific configuration fields.
WHY: UI clarity and relevance.
IMPACT: Cleaner interface and reduced confusion.

### Unwanted Requirements

**UW-001:** The system shall not accept Ollama URLs that lack HTTP or HTTPS scheme.
WHY: Incomplete URLs cause connection failures.
IMPACT: Prevents invalid configuration and clear error messaging.

**UW-002:** The system shall not allow PDF processing when Ollama server is configured but unreachable.
WHY: Silent failures create poor user experience.
IMPACT: Users receive clear error messages instead of hangs.

**UW-003:** The system shall not expose Ollama server URLs in plain text in error logs or user-facing messages.
WHY: Security best practice to prevent information disclosure.
IMPACT: Maintains security even in error scenarios.

**UW-004:** The system shall not modify OpenAI configuration when Ollama settings are updated.
WHY: Isolation of provider configurations.
IMPACT: Zero regression risk for OpenAI functionality.

**UW-005:** The system shall not store API keys for Ollama provider.
WHY: Ollama does not require API keys (unlike OpenAI).
IMPACT: Accurate representation of Ollama authentication model.

### Optional Requirements

**OP-001:** WHERE feasible, the system shall provide connection test button to verify Ollama server reachability before saving.
WHY: Proactive validation improves user confidence.
IMPACT: Higher configuration success rate.

**OP-002:** WHERE feasible, the system shall display Ollama server response time in connection status.
WHY: Performance information helps users assess viability.
IMPACT: Better informed decisions about using Ollama.

**OP-003:** WHERE feasible, the system shall support Ollama server authentication if Ollama adds authentication in future versions.
WHY: Future-proofing for potential Ollama features.
IMPACT: Easier upgrade path if Ollama adds authentication.

**OP-004:** WHERE feasible, the system shall remember last successfully connected Ollama URL for suggestion.
WHY: Convenience for returning administrators.
IMPACT: Faster reconfiguration.

---

## Specifications

### Functional Specifications

#### Backend API Changes

**GET `/api/admin/llm-settings` Enhancements:**
- Add `ollama_url` field to response (current value from SystemSettings)
- Add `ollama_models` array with dynamically fetched or default models
- Add `ollama_connection_status` field with values: `not_tested`, `connected`, `failed`

**POST `/api/admin/llm-settings` Enhancements:**
- Accept `ollama_url` parameter in request body
- Validate URL format using regex or URL parsing library
- Test Ollama server connection if URL changed
- Return error if connection test fails
- Save valid URL to SystemSettings

**New POST `/api/admin/test-ollama-connection`:**
- Accept `ollama_url` parameter
- Attempt connection to Ollama server
- Fetch model list from `/api/tags` endpoint
- Return connection status and available models or error details

#### LLM Service Implementation

**`_extract_with_ollama()` Method:**
- Remove NotImplementedError
- Construct Ollama API URL: `{ollama_url}/api/generate`
- Prepare request body with model, prompt, and options
- Send POST request using requests library
- Handle connection errors gracefully
- Parse JSON response and extract metadata
- Return formatted metadata dict or None on failure

**Model Listing Function:**
- Fetch from `{ollama_url}/api/tags`
- Parse response to extract model names
- Return array of model names
- Cache results with 10-minute expiration

#### Frontend UI Changes

**Admin Panel LLM Settings Form:**
- Add "Ollama Server URL" input field (shown only when Ollama selected)
- Add placeholder text: `http://localhost:11434`
- Add help text: "Enter Ollama server URL (local or remote)"
- Add "Test Connection" button next to URL field
- Add connection status indicator (success/error/neutral)
- Populate model dropdown dynamically from fetched list

**JavaScript Logic:**
- Show/hide Ollama URL field based on provider selection
- Call `/api/admin/test-ollama-connection` on test button click
- Update model dropdown when connection test succeeds
- Display connection error message on test failure
- Disable save button if connection test fails

### Data Model Changes

**SystemSettings Model:**
- `ollama_url` setting already exists (default: `http://localhost:11434`)
- No schema changes required
- Add caching mechanism for model list (in-memory cache with TTL)

### Error Handling

**Connection Errors:**
- Timeout after 10 seconds
- Catch `requests.exceptions.RequestException`
- Return user-friendly error: "Unable to connect to Ollama server at {url}. Verify the server is running and accessible."
- Log technical details for debugging

**Invalid URL Errors:**
- Validate URL format before connection attempt
- Return error: "Invalid Ollama URL format. Use http:// or https:// followed by hostname or IP."

**Model Listing Errors:**
- Fall back to default model list if API call fails
- Display warning: "Could not fetch models from server. Using default model list."
- Default models: `['llama2', 'codellama', 'mistral', 'vicuna', 'llama3.2']`

---

## Traceability

### TAG Mapping

```
[TAG:SPEC-LLM-001]
├── [TAG:REQ-UB-001 to UB-004]    Ubiquitous Requirements
├── [TAG:REQ-ED-001 to ED-005]    Event-Driven Requirements
├── [TAG:REQ-SD-001 to SD-005]    State-Driven Requirements
├── [TAG:REQ-UW-001 to UW-005]    Unwanted Requirements
├── [TAG:REQ-OP-001 to OP-004]    Optional Requirements
├── [TAG:SPEC-BACKEND-API]        Backend API Specifications
├── [TAG:SPEC-LLM-SERVICE]        LLM Service Implementation
├── [TAG:SPEC-FRONTEND-UI]        Frontend UI Changes
├── [TAG:SPEC-DATA-MODEL]         Data Model Changes
└── [TAG:SPEC-ERROR-HANDLING]     Error Handling Specifications
```

### Implementation Traceability

**Backend Files:**
- `backend/routes/admin.py` - API endpoint modifications
- `backend/services/llm_service.py` - Ollama integration implementation
- `backend/models/settings.py` - No changes required (ollama_url exists)

**Frontend Files:**
- `frontend/templates/admin.html` - UI form enhancements
- `frontend/static/js/main.js` - Dynamic form logic

**Test Files:**
- `tests/test_llm_service.py` - Ollama integration tests (NEW)
- `tests/test_admin_api.py` - Admin API tests (NEW)

---

## Success Criteria

### Functional Completion
- [x] Ollama URL field displayed when Ollama provider selected
- [x] Ollama URL validated and saved to database
- [x] Connection test functionality working
- [x] Dynamic model listing from Ollama server
- [x] Fallback to default models on connection failure
- [x] Actual Ollama API integration for PDF extraction
- [x] OpenAI configuration unchanged and working

### Quality Gates
- [x] All existing tests passing (regression test)
- [x] New test coverage for Ollama integration >= 85%
- [x] Zero security vulnerabilities in URL handling
- [x] Error messages clear and actionable
- [x] Admin panel UI responsive and intuitive
- [x] Connection failures handled gracefully

### Performance Criteria
- [x] Connection test completes within 10 seconds
- [x] Model listing completes within 5 seconds
- [x] Ollama PDF extraction completes within 30 seconds
- [x] Admin panel page load time < 2 seconds

### Documentation
- [x] Admin user guide updated with Ollama setup instructions
- [x] API documentation updated for new endpoints
- [x] Code comments explain Ollama integration logic
- [x] Troubleshooting guide for common Ollama issues

---

## Non-Functional Requirements

### Security
- URL validation prevents SSRF attacks
- No sensitive information leakage in error messages
- Input sanitization for all user-provided URLs
- HTTPS URLs supported for encrypted connections

### Performance
- Model list caching reduces API calls
- Connection timeout prevents indefinite hangs
- Asynchronous connection testing in UI
- Efficient error handling without blocking

### Usability
- Clear, helpful error messages
- Progressive disclosure of Ollama-specific fields
- Visual feedback for connection status
- Intuitive URL input format validation

### Maintainability
- Minimal changes to existing code
- Clear separation between OpenAI and Ollama logic
- Comprehensive error logging for debugging
- Configuration flexibility for future Ollama features

### Compatibility
- Backward compatible with existing OpenAI configuration
- No database migration required
- Works with Ollama 0.1.0+ API
- Compatible with local and remote Ollama servers

---

## Testing Strategy

### Unit Tests
- Test URL validation logic
- Test model listing with mocked Ollama API
- Test error handling for connection failures
- Test caching mechanism with TTL

### Integration Tests
- Test admin API endpoints with real Ollama server
- Test LLM service PDF extraction with Ollama
- Test connection test endpoint
- Test fallback to default models

### Frontend Tests
- Test URL field show/hide based on provider
- Test connection test button functionality
- Test model dropdown population
- Test error message display

### End-to-End Tests
- Complete Ollama configuration workflow
- PDF extraction with Ollama provider
- Verify OpenAI still works after Ollama configuration
- Test switching between providers

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Ollama API changes break integration | Low | High | Version-specific checks, graceful degradation |
| Users have network/firewall issues | Medium | Medium | Clear error messages with troubleshooting steps |
| Performance slower than OpenAI | High | Low | Set expectations, provide performance feedback |
| Regression in OpenAI functionality | Low | High | Comprehensive regression testing |
| Invalid URL causes application errors | Medium | Medium | Robust URL validation and error handling |

---

## Dependencies

### External Dependencies
- **Ollama Server**: Must be installed and running locally or accessible remotely
- **Python requests library**: Add to requirements.txt if not present
- **Ollama API stability**: Depends on Ollama project maintenance

### Internal Dependencies
- SystemSettings model (already has ollama_url field)
- Admin panel infrastructure (already exists)
- LLM service architecture (already designed)

---

## Open Questions

1. **Model Caching Duration**: Is 10 minutes appropriate for model list cache? Should this be configurable?

2. **Connection Timeout**: Is 10 seconds timeout appropriate for Ollama connection test? Should this vary based on local vs remote server?

3. **Default Models**: Should default model list be updated to include newer models like llama3.2?

4. **Authentication**: Should we prepare for potential Ollama authentication even though it doesn't exist yet?

5. **Performance Metrics**: Should we track and display Ollama response times to help users compare with OpenAI?

---

## HISTORY

### 2026-01-01 - Implementation Completed
- Implemented Ollama URL field with conditional display
- Added Ollama server connection testing functionality
- Implemented dynamic model listing from Ollama API
- Added fallback to default models on connection failure
- Completed actual Ollama API integration for PDF extraction
- Verified OpenAI configuration remains unchanged
- All tests passing with >=85% coverage
- Zero security vulnerabilities in URL handling
- Documentation updated with Ollama setup instructions

### 2025-12-31 - Initial SPEC Creation
- Created comprehensive EARS format specification
- Analyzed current Ollama placeholder implementation
- Identified all required backend and frontend changes
- Defined success criteria and testing strategy
- Documented risks and mitigations

---

## Appendix: Ollama API Reference

### List Models Endpoint
```
GET http://localhost:11434/api/tags
Response:
{
  "models": [
    {"name": "llama2", "modified_at": "2024-01-01T00:00:00Z"},
    {"name": "codellama", "modified_at": "2024-01-01T00:00:00Z"}
  ]
}
```

### Generate Completion Endpoint
```
POST http://localhost:11434/api/generate
Request:
{
  "model": "llama2",
  "prompt": "Extract metadata from this text...",
  "stream": false,
  "options": {
    "temperature": 0.0
  }
}
Response:
{
  "model": "llama2",
  "response": "{\"author\": \"...\", \"year\": 2024, ...}",
  "done": true
}
```
