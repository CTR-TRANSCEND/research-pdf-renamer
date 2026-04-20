# Changelog

All notable changes to Research PDF File Renamer are documented here.

## [0.3.3] - 2026-04-20

### Added
- **GPU LLM support via OpenAI-compatible API** -- New provider option for remote GPU servers (LM Studio, vLLM) via Tailscale or local network. Configurable from admin panel.
- **Polling-based real-time progress** -- Upload returns immediately with a job ID; frontend polls every 5 seconds for per-file status updates (Extracting → Analyzing → Renaming → Done).
- **Per-file processing stages** -- Progress modal shows current stage for each file with percentage indicators.
- **Elapsed time display** -- Results modal shows total processing time ("Completed in X.X seconds").
- **Auto-retry on invalid LLM response** -- Files that fail with unparseable AI response are automatically retried once before reporting failure.
- **Retry Failed Files button** -- Results modal includes a button to reprocess only the files that failed.
- **Auto-close modal** -- Results modal auto-closes after 20 seconds when all files succeed.
- **Close button** -- Explicit close button at bottom-right of results modal.
- **Admin: service reset on settings save** -- Changing LLM settings in admin panel takes effect immediately without container restart.

### Fixed
- **PDF extraction 84s → instant** -- Switched to pymupdf-first extraction strategy. Previously pdfplumber wasted 80+ seconds failing on complex Nature/Springer PDFs before falling back. Now pymupdf (fastest, handles all PDFs) is tried first.
- **CSRF blocking file uploads** -- Upload/download endpoints fully exempt from CSRF (they use JWT cookie auth, not form sessions).
- **Nginx 413 rejection for large batches** -- Documented need for `client_max_body_size 500M` in Nginx config.
- **Ollama timeout error shown as "Network error"** -- Added dedicated TIMEOUT error type with clear message: "AI processing timed out on this file."
- **Filename keywords exceeding 5 words** -- Backend post-processing now truncates keywords to max 5 regardless of what the LLM returns.
- **Filename spaces causing validation failure** -- Auto-sanitizes spaces to hyphens (e.g., "NEJM AI" → "NEJM-AI") instead of rejecting the file.
- **LLM context overflow (400 errors)** -- Reduced text sent to LLM from 8000 to 3000 chars (metadata is always in first ~1000 chars).
- **Multi-worker polling 404s** -- Switched to 1 gunicorn worker with 12 threads so in-memory progress dict is shared across all requests.
- **Stale LLM config after admin save** -- Admin panel now resets cached LLM service on save.

### Changed
- **Gunicorn config** -- 1 worker × 12 threads (was 3 × 4). Better for background job progress tracking with in-memory state.
- **Gunicorn timeout** -- Increased to 600s (was 300s) for large batch processing.
- **LLM per-file timeout** -- Increased to 180s (was 60s) for complex PDFs on CPU.
- **0.5s stagger between parallel LLM requests** -- Prevents overwhelming the LLM server with simultaneous requests.
- **Keyword prompt stricter** -- Explicit WRONG/RIGHT examples and max 5 keyword enforcement.
- **Compact UI** -- Tighter file list spacing, Process button next to file list header, compact results display.
- **Ollama always visible in admin** -- Shows as "Ollama (Local CPU)" with models pre-fetched regardless of current provider.

## [0.3.2] - 2026-04-08

### Fixed
- **Download failing with 401 Unauthorized** -- The download endpoint required authentication but the upload endpoint did not, causing automatic downloads to fail for users who hadn't logged in. Removed auth requirement from downloads; files are protected by unguessable session IDs, auto-cleanup, and network restrictions.
- **Admin "System Status: Error. API key not configured"** -- The system status check incorrectly required an API key for all LLM providers, including Ollama and other local providers that don't need one. Local providers (Ollama, OpenAI-compatible, LM Studio) now show "Healthy" without an API key.
- **Download stripping author name from filename** -- Legacy timestamp-strip code was removing author names that happened to match the timestamp pattern.
- **LLM prompt with hardcoded example** -- The extraction prompt contained a specific paper example (Navaeiseddighi/bioRxiv) that caused the model to copy the example instead of extracting actual metadata. Replaced with generic placeholders.
- **Timestamp prefix on downloaded filenames** -- Removed YYYYMMDD_HHMMSS_ prefix from download filenames; session folders already provide collision isolation.

## [0.3.0] - 2026-04-08

### Added
- **pymupdf PDF extraction fallback** -- Third-tier text extraction for complex PDFs (Nature, Springer) that pdfplumber and pypdf cannot handle. Extraction chain: pdfplumber -> pypdf -> pymupdf.
- **Password visibility toggle** -- Eye icon on all password change form fields (index and admin pages) to show/hide entered passwords.
- **LLM settings auto-seeding** -- Environment variables (`LLM_PROVIDER`, `LLM_MODEL`, `OLLAMA_URL`) are now seeded into the database on first startup, so the admin panel shows the correct provider configuration out of the box.
- **`APPLICATION_ROOT` support in Docker Compose** -- Passed through as an environment variable for reverse proxy sub-path deployments.
- **Nginx reverse proxy documentation** in deployment guide.

### Fixed
- **CSRF header name** -- Changed `X-CSRF-TOKEN` to `X-CSRFToken` to match Flask-WTF's expected header. This was preventing password changes and other state-changing operations from the frontend.
- **Missing CSRF setup in admin panel** -- Added CSRF token header configuration to `admin.html` (was absent, causing all admin state-changing requests to fail).
- **CSRF exemption for password change** -- `/api/auth/change-password` is now exempt from CSRF validation as it uses JWT-authenticated JSON API.
- **Double URL prefix on downloads** -- Download URLs were prefixed twice with `APPLICATION_ROOT` when deployed behind a reverse proxy, causing 404 errors on file downloads.
- **Password hashing documentation** -- Corrected README to reference bcrypt (actual implementation) instead of werkzeug.

### Changed
- **Dockerfile simplified** -- Removed `apt-get install gcc libffi-dev` step. All Python dependencies now install from pre-built manylinux wheels, making builds faster and eliminating failures on networks where Debian repos are unreachable from Docker.
- Version bumped to 0.3.0.

## [0.2.1] - 2025-01-14

- Initial public release with OpenAI, Ollama, LM Studio, and OpenAI-compatible provider support.
- User management with registration, admin approval, and role-based access control.
- Docker and Docker Compose deployment options.
- Systemd + Apache reverse proxy production deployment.
