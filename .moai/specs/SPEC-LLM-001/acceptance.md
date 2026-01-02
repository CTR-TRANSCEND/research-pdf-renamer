# Acceptance Criteria - SPEC-LLM-001

| Metadata | Value |
|----------|-------|
| **SPEC ID** | SPEC-LLM-001 |
| **Document Version** | 1.0 |
| **Last Updated** | 2025-12-31 |
| **Test Format** | Given-When-Then (Gherkin) |

---

## Overview

This document defines detailed acceptance criteria for SPEC-LLM-001 (Ollama LLM Integration with Full Configuration Support). All test scenarios follow the Given-When-Then format for clarity and testability.

---

## Functional Acceptance Criteria

### AC-001: Ollama URL Configuration

**Feature**: Configure Ollama server URL in Admin Panel

**Scenario 1.1: Display URL input field when Ollama selected**
```gherkin
GIVEN the administrator is logged in
AND the Admin Panel LLM Settings page is displayed
WHEN the administrator selects "Ollama" from the LLM Provider dropdown
THEN the "Ollama Server URL" input field is displayed
AND the field has placeholder text "http://localhost:11434"
AND the field has help text explaining the format
```

**Scenario 1.2: Hide URL input field when OpenAI selected**
```gherkin
GIVEN the administrator is logged in
AND the Admin Panel LLM Settings page is displayed
AND "Ollama" is currently selected
WHEN the administrator selects "OpenAI" from the LLM Provider dropdown
THEN the "Ollama Server URL" input field is hidden
AND the API Key field is displayed (if not already visible)
```

**Scenario 1.3: Save valid Ollama URL**
```gherkin
GIVEN the administrator is logged in
AND the Admin Panel LLM Settings page is displayed
AND "Ollama" is selected as the provider
AND the administrator enters "http://localhost:11434" in the URL field
AND a valid model is selected
WHEN the administrator clicks "Save Settings"
THEN the settings are saved to the database
AND a success message is displayed
AND the URL field retains the saved value after page reload
```

**Scenario 1.4: Reject invalid URL format**
```gherkin
GIVEN the administrator is logged in
AND the Admin Panel LLM Settings page is displayed
AND "Ollama" is selected as the provider
WHEN the administrator enters "invalid-url" in the URL field (missing http://)
AND the administrator clicks "Save Settings"
THEN the settings are NOT saved
AND an error message is displayed: "Invalid Ollama URL format. Use http:// or https:// followed by hostname or IP."
AND the URL field is highlighted with error styling
```

**Scenario 1.5: Accept remote Ollama server URL**
```gherkin
GIVEN the administrator is logged in
AND the Admin Panel LLM Settings page is displayed
AND "Ollama" is selected as the provider
WHEN the administrator enters "http://ollama-server.example.com:11434" in the URL field
AND the administrator clicks "Save Settings"
THEN the settings are saved to the database
AND a success message is displayed
```

### AC-002: Ollama Connection Testing

**Feature**: Test Ollama server connectivity before saving configuration

**Scenario 2.1: Successful connection test**
```gherkin
GIVEN the administrator is logged in
AND the Admin Panel LLM Settings page is displayed
AND "Ollama" is selected as the provider
AND a running Ollama server is accessible at "http://localhost:11434"
WHEN the administrator enters "http://localhost:11434" in the URL field
AND the administrator clicks "Test Connection"
THEN a loading indicator is displayed during the test
AND within 10 seconds, a success message is displayed
AND a green checkmark icon appears next to the URL field
AND the available models dropdown is populated with models from the server
```

**Scenario 2.2: Connection test fails - server not running**
```gherkin
GIVEN the administrator is logged in
AND the Admin Panel LLM Settings page is displayed
AND "Ollama" is selected as the provider
AND no Ollama server is running
WHEN the administrator enters "http://localhost:11434" in the URL field
AND the administrator clicks "Test Connection"
THEN a loading indicator is displayed during the test
AND within 10 seconds, an error message is displayed
AND the error message includes: "Unable to connect to Ollama server"
AND troubleshooting suggestions are displayed
AND a red X icon appears next to the URL field
```

**Scenario 2.3: Connection test fails - timeout**
```gherkin
GIVEN the administrator is logged in
AND the Admin Panel LLM Settings page is displayed
AND "Ollama" is selected as the provider
AND an Ollama server is running but takes >10 seconds to respond
WHEN the administrator enters the server URL in the URL field
AND the administrator clicks "Test Connection"
THEN the test terminates after 10 seconds
AND an error message is displayed: "Connection timeout. Ollama server did not respond within 10 seconds."
```

**Scenario 2.4: Connection test fails - invalid URL**
```gherkin
GIVEN the administrator is logged in
AND the Admin Panel LLM Settings page is displayed
AND "Ollama" is selected as the provider
WHEN the administrator enters "http://invalid-host-name-12345.com:11434" in the URL field
AND the administrator clicks "Test Connection"
THEN an error message is displayed within 5 seconds
AND the error message indicates the hostname could not be resolved
```

### AC-003: Dynamic Model Discovery

**Feature**: Fetch available models from Ollama server

**Scenario 3.1: Fetch models from successful connection**
```gherkin
GIVEN the administrator is logged in
AND the Admin Panel LLM Settings page is displayed
AND "Ollama" is selected as the provider
AND a connection test succeeded
WHEN the connection test completes successfully
THEN the Model dropdown is populated with models from the server
AND the models match those returned by the Ollama /api/tags endpoint
AND at least one model is listed (e.g., "llama2", "mistral", "codellama")
```

**Scenario 3.2: Fall back to default models on connection failure**
```gherkin
GIVEN the administrator is logged in
AND the Admin Panel LLM Settings page is displayed
AND "Ollama" is selected as the provider
AND a connection test failed
WHEN the Model dropdown is displayed
THEN the dropdown contains default models: ["llama2", "codellama", "mistral", "vicuna", "llama3.2"]
AND a warning message is displayed: "Could not fetch models from server. Using default model list."
```

**Scenario 3.3: Cache model list for performance**
```gherkin
GIVEN the administrator is logged in
AND the Admin Panel LLM Settings page is displayed
AND "Ollama" is selected as the provider
AND a connection test succeeded and models were fetched
AND less than 10 minutes have passed since the fetch
WHEN the administrator reloads the page
THEN the Model dropdown is populated immediately without API call
AND the models match the previously fetched list
```

**Scenario 3.4: Refresh model list after cache expiration**
```gherkin
GIVEN the administrator is logged in
AND the Admin Panel LLM Settings page is displayed
AND "Ollama" is selected as the provider
AND a connection test succeeded and models were cached
AND more than 10 minutes have passed since the fetch
WHEN the administrator clicks "Test Connection" again
THEN a new API call is made to the Ollama server
AND the Model dropdown is updated with the latest model list
```

### AC-004: Ollama PDF Metadata Extraction

**Feature**: Extract PDF metadata using Ollama API

**Scenario 4.1: Successful metadata extraction with Ollama**
```gherkin
GIVEN a user is logged in
AND the LLM provider is configured as "Ollama"
AND the LLM model is configured as "llama2"
AND a valid Ollama server URL is configured
AND the Ollama server is running and accessible
WHEN the user uploads a valid research PDF file
AND the system processes the file
THEN the text is extracted from the first 1-2 pages of the PDF
AND a request is sent to the Ollama /api/generate endpoint
AND the response includes JSON metadata with: author, year, title, keywords
AND the system returns the formatted filename to the user
AND processing completes within 30 seconds
```

**Scenario 4.2: Handle Ollama server error during extraction**
```gherkin
GIVEN a user is logged in
AND the LLM provider is configured as "Ollama"
AND a valid Ollama server URL is configured
WHEN the user uploads a valid research PDF file
AND the Ollama server returns an error during processing
THEN the system displays an error message to the user
AND the error message indicates the Ollama processing failed
AND the user is suggested to try again or switch to OpenAI
AND the error is logged for administrator review
```

**Scenario 4.3: Handle Ollama server unreachable during extraction**
```gherkin
GIVEN a user is logged in
AND the LLM provider is configured as "Ollama"
AND a valid Ollama server URL is configured
WHEN the user uploads a valid research PDF file
AND the Ollama server is not reachable
THEN the system displays an error message within 15 seconds
AND the error message states: "Unable to reach Ollama server. Verify the server is running."
AND no indefinite hanging occurs
```

**Scenario 4.4: Parse Ollama JSON response correctly**
```gherkin
GIVEN a user is logged in
AND the LLM provider is configured as "Ollama"
AND the Ollama server returns a valid response
WHEN the system receives the response from /api/generate
THEN the response body is extracted from the JSON
AND the response body is parsed as JSON
AND author, year, title, and keywords fields are extracted
AND the data is validated for required fields
AND the metadata is returned in the expected format
```

### AC-005: OpenAI Functionality Preservation

**Feature**: Ensure OpenAI configuration and functionality remain unchanged

**Scenario 5.1: OpenAI configuration UI unchanged**
```gherkin
GIVEN the administrator is logged in
AND the Admin Panel LLM Settings page is displayed
WHEN "OpenAI" is selected as the provider
THEN the Ollama-specific fields are hidden
AND the API Key field is displayed
AND the Model dropdown shows OpenAI models
AND the UI appearance matches the previous implementation
```

**Scenario 5.2: OpenAI settings save correctly**
```gherkin
GIVEN the administrator is logged in
AND the Admin Panel LLM Settings page is displayed
AND "OpenAI" is selected as the provider
WHEN the administrator enters a valid API key
AND selects a valid OpenAI model
AND clicks "Save Settings"
THEN the settings are saved to the database
AND a success message is displayed
AND the settings persist after page reload
```

**Scenario 5.3: OpenAI PDF extraction unchanged**
```gherkin
GIVEN a user is logged in
AND the LLM provider is configured as "OpenAI"
AND a valid API key is configured
WHEN the user uploads a valid research PDF file
THEN the system processes the file using OpenAI API
AND the response is parsed correctly
AND the metadata is extracted successfully
AND the formatted filename is returned to the user
AND the behavior matches the previous implementation
```

**Scenario 5.4: Switching between providers**
```gherkin
GIVEN the administrator is logged in
AND both OpenAI and Ollama are configured
WHEN the administrator switches from OpenAI to Ollama
AND saves the settings
AND uploads a PDF file
THEN the system uses Ollama for processing
WHEN the administrator switches back to OpenAI
AND saves the settings
AND uploads a PDF file
THEN the system uses OpenAI for processing
AND both providers work correctly
```

---

## Non-Functional Acceptance Criteria

### AC-NFR-001: Performance

**Criterion 1.1: Connection test response time**
```gherkin
GIVEN a valid Ollama server URL is configured
AND the server is running and accessible
WHEN the administrator clicks "Test Connection"
THEN the test completes within 10 seconds
AND the UI remains responsive during the test
```

**Criterion 1.2: Model listing response time**
```gherkin
GIVEN a valid Ollama server URL is configured
AND the server is running and accessible
WHEN the system fetches the model list
THEN the request completes within 5 seconds
AND the models are displayed in the dropdown
```

**Criterion 1.3: PDF extraction response time**
```gherkin
GIVEN a user uploads a typical research PDF (5-10 pages)
AND the LLM provider is configured as "Ollama"
AND the Ollama server is running
WHEN the system processes the PDF
THEN processing completes within 30 seconds
AND the user receives the result
```

### AC-NFR-002: Security

**Criterion 2.1: URL validation prevents SSRF**
```gherkin
GIVEN the administrator is logged in
AND the Admin Panel LLM Settings page is displayed
WHEN the administrator enters "http://localhost:11434" or "http://192.168.1.1:11434"
AND clicks "Save Settings"
THEN the URL is validated for safe format
AND private IP addresses are allowed (server-side use)
AND internal URLs are logged for security auditing
```

**Criterion 2.2: No sensitive data leakage in errors**
```gherkin
GIVEN the administrator is logged in
AND an error occurs during Ollama processing
WHEN the error is displayed to the user
THEN the error message does not include API keys
AND the error message does not include full server paths
AND the error message does not include internal stack traces
AND technical details are logged separately for administrators
```

**Criterion 2.3: HTTPS URL support**
```gherkin
GIVEN the administrator is logged in
AND the Admin Panel LLM Settings page is displayed
WHEN the administrator enters "https://ollama-server.example.com:11434"
AND clicks "Test Connection"
THEN the system accepts the HTTPS URL
AND the connection test is performed over HTTPS
AND SSL certificate validation is performed
```

### AC-NFR-003: Usability

**Criterion 3.1: Clear error messages**
```gherkin
GIVEN the administrator is logged in
AND an error occurs during configuration
WHEN the error is displayed
THEN the error message is in plain language
AND the error message suggests specific actions to resolve
AND the error message includes relevant context (URL, server status)
```

**Criterion 3.2: Intuitive UI flow**
```gherkin
GIVEN the administrator is new to the system
AND the Admin Panel LLM Settings page is displayed
WHEN the administrator selects "Ollama"
THEN the URL input field appears smoothly
AND placeholder text guides the expected format
AND help text explains what to enter
AND a "Test Connection" button is prominently displayed
```

**Criterion 3.3: Visual feedback**
```gherkin
GIVEN the administrator is configuring Ollama
WHEN a connection test is in progress
THEN a loading spinner or progress indicator is displayed
AND the button is disabled during the test
WHEN the test completes
THEN a success or error icon is displayed
AND the status is color-coded (green for success, red for failure)
```

### AC-NFR-004: Reliability

**Criterion 4.1: Graceful degradation**
```gherkin
GIVEN the administrator is configuring Ollama
AND the Ollama server is temporarily unavailable
WHEN the configuration page loads
THEN the page loads successfully
AND a default model list is displayed
AND the administrator can still configure other settings
AND the application does not crash or hang
```

**Criterion 4.2: Error recovery**
```gherkin
GIVEN the administrator is configuring Ollama
AND a connection test fails
WHEN the administrator fixes the URL (e.g., corrects typo)
AND clicks "Test Connection" again
THEN the test is reattempted
AND if successful, the success status is displayed
AND the model dropdown is populated
```

**Criterion 4.3: Configuration persistence**
```gherkin
GIVEN the administrator has configured Ollama successfully
AND the settings are saved to the database
WHEN the administrator logs out
AND logs back in
AND navigates to the LLM Settings page
THEN the previously configured Ollama URL is displayed
AND the selected model is displayed
AND the configuration matches what was saved
```

---

## Regression Testing Criteria

### AC-REG-001: Existing Functionality

**Criterion 1: OpenAI workflow unchanged**
```gherkin
GIVEN the system has been updated with Ollama support
WHEN a user uses the system with OpenAI provider
THEN all existing OpenAI functionality works as before
AND no regressions are present in PDF processing
AND the UI for OpenAI configuration is unchanged
AND error handling for OpenAI is unchanged
```

**Criterion 2: User authentication unchanged**
```gherkin
GIVEN the system has been updated with Ollama support
WHEN a user logs in or registers
THEN the authentication flow works as before
AND admin approval workflow is unchanged
AND user session management is unchanged
```

**Criterion 3: File upload unchanged**
```gherkin
GIVEN the system has been updated with Ollama support
WHEN a user uploads a PDF file
THEN the file upload process works as before
AND file validation is unchanged
AND the drag-and-drop interface works as before
```

---

## Quality Gate Checklist

### Code Quality
- [ ] All new code follows project coding standards
- [ ] Code is reviewed by at least one other developer
- [ ] No linting errors or warnings
- [ ] All functions have appropriate error handling
- [ ] Code is well-commented for complex logic

### Testing Coverage
- [ ] Unit tests for all new LLM service methods
- [ ] Integration tests for API endpoints
- [ ] Frontend tests for UI components
- [ ] End-to-end tests for complete workflows
- [ ] Test coverage >=85% for new code

### Documentation
- [ ] API documentation updated for new endpoints
- [ ] Admin user guide includes Ollama setup instructions
- [ ] Troubleshooting guide covers common Ollama issues
- [ ] Code comments explain Ollama integration logic

### Security
- [ ] URL input validated to prevent injection attacks
- [ ] No sensitive data leakage in error messages
- [ ] HTTPS URLs supported for encrypted connections
- [ ] Security review completed

### Performance
- [ ] Connection test completes within 10 seconds
- [ ] Model listing completes within 5 seconds
- [ ] PDF extraction completes within 30 seconds
- [ ] No memory leaks or performance regressions

### User Experience
- [ ] Error messages are clear and actionable
- [ ] UI is responsive during async operations
- [ ] Visual feedback provided for all actions
- [ ] Workflow is intuitive for new users

---

## Definition of Done

A feature is considered complete when:

1. **Functional Requirements Met**
   - All acceptance criteria (AC-001 to AC-005) pass
   - All non-functional criteria (AC-NFR-001 to AC-NFR-004) pass
   - All regression criteria (AC-REG-001) pass

2. **Quality Gates Passed**
   - All items in Quality Gate Checklist are completed
   - Test coverage >=85% for new code
   - Zero critical bugs
   - Zero security vulnerabilities

3. **Documentation Complete**
   - Admin user guide updated
   - API documentation updated
   - Troubleshooting guide created
   - Code comments added

4. **Testing Complete**
   - Unit tests written and passing
   - Integration tests written and passing
   - End-to-end tests written and passing
   - Manual testing completed

5. **Code Review Complete**
   - Code reviewed by peers
   - Feedback addressed
   - Final approval received

6. **Deployment Ready**
   - Migration scripts (if needed) prepared
   - Rollback plan documented
   - Monitoring and logging configured
   - Support team trained

---

## Test Execution Log

### Test Results

| Test ID | Scenario | Status | Date | Tested By | Notes |
|---------|----------|--------|------|-----------|-------|
| AC-001-1 | Display URL input field | Pending | - | - | - |
| AC-001-2 | Hide URL input field | Pending | - | - | - |
| AC-001-3 | Save valid URL | Pending | - | - | - |
| AC-001-4 | Reject invalid URL | Pending | - | - | - |
| AC-001-5 | Accept remote URL | Pending | - | - | - |
| AC-002-1 | Successful connection | Pending | - | - | - |
| AC-002-2 | Server not running | Pending | - | - | - |
| AC-002-3 | Connection timeout | Pending | - | - | - |
| AC-002-4 | Invalid URL | Pending | - | - | - |
| AC-003-1 | Fetch models | Pending | - | - | - |
| AC-003-2 | Fallback to defaults | Pending | - | - | - |
| AC-003-3 | Cache model list | Pending | - | - | - |
| AC-003-4 | Refresh after expiration | Pending | - | - | - |
| AC-004-1 | Successful extraction | Pending | - | - | - |
| AC-004-2 | Ollama server error | Pending | - | - | - |
| AC-004-3 | Server unreachable | Pending | - | - | - |
| AC-004-4 | Parse JSON response | Pending | - | - | - |
| AC-005-1 | OpenAI UI unchanged | Pending | - | - | - |
| AC-005-2 | OpenAI settings save | Pending | - | - | - |
| AC-005-3 | OpenAI extraction | Pending | - | - | - |
| AC-005-4 | Provider switching | Pending | - | - | - |

---

## HISTORY

### 2025-12-31 - Initial Acceptance Criteria
- Created comprehensive Gherkin-format acceptance criteria
- Defined functional scenarios (AC-001 to AC-005)
- Defined non-functional criteria (AC-NFR-001 to AC-NFR-004)
- Defined regression testing criteria (AC-REG-001)
- Created quality gate checklist
- Created test execution log template
