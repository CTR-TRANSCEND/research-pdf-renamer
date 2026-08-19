# Changelog

All notable changes to Research PDF File Renamer are documented here.

## [0.4.10] - 2026-08-19

### Fixed

- **The tool name no longer eats the keywords.** v0.4.9 shipped with the tool name *competing* for the 5-word keyword budget instead of being added to it, and the budget loop used `break` rather than `continue` — so `MFS-MUnet` consumed 2 of the 5 words, the paper's first keyword phrase (`multi-scale frequency fusion`, 4 words) did not fit in the 3 that remained, and the loop stopped dead and discarded **every** keyword. Real observed output: `Li-Feng_2026_Pattern-Recognition_MFS-MUnet.pdf` — the tool name and nothing else. The tool is now genuinely *added* to the front of the keywords: keywords keep their own full 5-word allowance, filled greedily (a phrase that does not fit whole contributes its leading words), and the tool name sits ahead of them. Same paper now yields `Li-Feng_2026_Pattern-Recognition_MFS-MUnet-multi-scale-frequency-fusion-mamba.pdf`.
- `upload.py` no longer re-applies `_truncate_keywords()` to filenames that `build_filename()` produced. That downstream 5-word cut counted the tool name against the keyword allowance a second time, undoing the fix; it still guards the LLM-fallback filename path, which is the only place it was ever needed.
- Verified: keyword-only papers are **30/30 byte-identical end-to-end** to v0.4.8 across 5 metadata shapes x 6 formats — including the multi-word-phrase case that v0.4.9 changed, whose greedy partial fill is now reproduced exactly.

## [0.4.9] - 2026-08-19

### Added

- **The tool/software name a paper introduces now leads the keywords in the filename.** A paper titled `MFS-MUnet: Multi-scale Frequency Spatial Mamba U-Net for Medical Image Segmentation` previously had no reliable way to keep `MFS-MUnet` in its filename — the name was only ever a lucky third-priority keyword. It is now extracted explicitly and rendered first, e.g. `Yang-Wei_2024_<journal>_MFS-MUnet-medical-image-segmentation.pdf`. Two layers, matching the author-recovery design from v0.4.8:
  - A new **optional** `tool_name` field in the extraction prompt and `PaperMetadata` schema, instructing the model to copy a named model/method/software/database the paper contributes, exactly as written, and to return `""` when the paper introduces none. Optional by design — a blank must never discard an otherwise-good extraction (the v0.4.7 lesson).
  - A deterministic net, `PDFProcessor.extract_tool_name_from_title()`, which recovers the name from the title (leading token before a colon, or a parenthesized name) when the LLM returns nothing. Guarded by a stop-list so article types (`Review:`, `Correction:`, `Commentary:` …) and ordinary lowercase words are never mistaken for a tool name; it returns `""` rather than guessing.
- `LLMService.build_filename()` places the tool name as the first keyword and de-duplicates it when the model also listed it among the keywords. The keyword slot is now capped at 5 hyphen-separated **words** rather than 5 comma-keywords, so a multi-word name like `MFS-MUnet` cannot be split mid-name by the downstream truncation.

### Unchanged

- No new filename slot, preset, or profile setting: papers that introduce no named tool produce byte-identical filenames to v0.4.8.

## [0.4.8] - 2026-06-29

### Fixed

- **Author is now recovered even when the LLM returns a blank extraction.** Live logs showed gpt-oss-20b is non-deterministic: for the same PDF it sometimes returns a full extraction and sometimes an all-empty object (`{"author":"", ...}`) on every retry. A blank `author` legitimately fails validation, so such uploads fell through to all-`Unknown` despite the author being plainly on page 1. Added a deterministic safety net in `_process_files_background`: when the LLM yields no author, fall back to (1) the PDF's embedded author property, then (2) a best-effort parse of the author line from the page-1 text (`PDFProcessor.extract_author_from_text`, which targets the common `Title → Author1, Author2 …` layout with superscript affiliations). Result: a paper whose author the LLM dropped now still yields e.g. `Toro-Sabrina_Unknown_Unknown_Unknown.pdf` instead of `Unknown_Unknown_Unknown_paper.pdf`.
- The lenient parser's `"paper"` keyword sentinel is now normalised to a consistent `Unknown` slot when no real keywords were recovered (no more misleading `..._paper.pdf`).

## [0.4.7] - 2026-06-28

### Fixed

- **A valid author/title is no longer discarded when year or journal is missing.** Root cause (found via live-container logs): the model correctly returned e.g. `{"author":"Toro","author_first":"Sabrina","title":"...","keywords":"ontology-generation,...","year":"","journal":""}` for a preprint with no year/journal on its first page — but the strict `PaperMetadata` schema **hard-required a 4-digit `year`** (and non-empty `keywords`/`suggested_filename`), so `validate_year("")` raised and the *entire* extraction was rejected. After exhausting retries the result fell to the lenient fallback and surfaced as `Unknown_Unknown_Unknown_paper.pdf` even though the author was right there on page 1.
- `PaperMetadata` now **coerces** missing/blank `year` → `Unknown` (mirroring the existing `journal` behavior) and treats `title`/`keywords`/`suggested_filename` as optional. `author` remains the single required field (an author-less response still triggers retry/lenient). The filename is rebuilt from the surviving fields by `build_filename()`, so a preprint now yields e.g. `Toro-Sabrina_Unknown_Unknown_ontology-generation-LLM-retrieval-augmented.pdf` instead of all-`Unknown`. Papers that do carry a year/journal are unaffected.
- This complements v0.4.6 (which fixed metadata-rich papers by getting the citation into the prompt); together they cover both "the year was truncated away" and "the year genuinely isn't on page 1".

## [0.4.6] - 2026-06-28

### Fixed

- **Author/year/journal no longer lost on metadata-rich papers.** Root cause: the extracted PDF text was hard-truncated to 3000 chars before the LLM saw it, and the PDF's embedded `subject` property (which for many LaTeX/MDPI PDFs holds the *entire abstract*, ~2500 chars) was injected ahead of the page text — so the title-page citation line carrying the journal and year was truncated away, and the LLM frequently returned a blank extraction (rendered as `Unknown_Unknown_Unknown_paper.pdf`). Three independent changes fix this:
  - The injected `subject`/abstract is now **capped at 300 chars** (`PDFProcessor._build_metadata_header`) so it can't crowd out the page text.
  - The LLM text budget is raised from **3000 → 8000 chars** (`MAX_TEXT_LENGTH`, configurable), comfortably covering the metadata header + first page within the gpt-oss-20b context.
  - The PDF's embedded document properties are now used as an **authoritative fallback** (`PDFProcessor.extract_pdf_metadata_fields`): when the LLM leaves author/title/keywords/year blank, they are filled from the PDF metadata (first-author last/first name, keywords, and a last-resort creation-year). The LLM result still wins whenever it found a value.
- Net effect: a metadata-rich paper that previously produced `Unknown_Unknown_Unknown_paper.pdf` now yields e.g. `Langevin-Stephanie_2022_Int-J-Environ-Res-Public-Health_antisocial-trajectories-...`. Genuine preprints with no journal/year on the first page (and none in metadata) still honestly report `Unknown` for those fields.

## [0.4.5] - 2026-06-25

### Changed

- **Per-session file limit for approved users raised 30 → 100.** `User.get_max_files()` default; admin per-user overrides (`max_files_per_session`) still apply. Surfaced to the UI via `/api/limits`.
- **Whole-request upload ceiling raised to 5000 MB** (`MAX_CONTENT_LENGTH`), sized for 100 files × 50 MB. Requires nginx `client_max_body_size 5000M` (server-side; see docs/deployment.md).
- **Per-file 50 MB cap decoupled from the request ceiling.** New `MAX_FILE_SIZE` (default 50 MB) drives `FileService.validate_file`; previously the per-file cap reused `MAX_CONTENT_LENGTH`, so raising the request ceiling would have silently allowed 5 GB single files. Now they're independent.

### Added

- **Multi-folder upload.** The folder picker now *accumulates* (add folders one at a time), and drag-dropping several folders at once works via recursive FileSystem-entry traversal. Subfolders were always included by the picker; drag-drop now recurses too.
- **Folder uploads preserve the directory tree in the output ZIP.** Renamed files are placed under their original subfolder paths (e.g. `projectA/sub/Hribar-Jason_2023_Journal_kw.pdf`) instead of being flattened. Driven by the `preserve_structure` flag the folder UI already sends.

## [0.4.4] - 2026-06-25

### Fixed

- **Missing fields now keep an `Unknown` placeholder in the filename instead of being dropped.** v0.4.2's `build_filename` omitted empty/Unknown components, so a paper with no journal produced e.g. `Tu-Tao_2024_diagnosticAI-LLM-selfplay` — a 3-section name that misaligns the slots (keywords sitting in the journal position). Filenames now always preserve the configured `_`-separated structure: `Tu-Tao_2024_Unknown_diagnosticAI-LLM-selfplay`. Applies to every field (author/year/journal/title/keywords) and all preset + Custom formats.

## [0.4.3] - 2026-06-25

### Changed

- **Default author format is now `LastName-FirstName`.** Filenames render the primary author as `Hribar-Jason` (last name + first name, hyphen-joined) when a first name can be determined, falling back to last-name-only otherwise. Applies to every preset and Custom `{author}` token. The LLM now also extracts the primary author's first name (new optional `author_first` field on `PaperMetadata`; empty when not found).
- **Filenames are now built deterministically from the validated fields** (`LLMService.build_filename`) for every file, rather than trusting the LLM's `suggested_filename` (which was inconsistent — sparse names, last-name-only). The LLM's `suggested_filename` is kept only as a fallback if the rebuild yields nothing. This subsumes the v0.4.2 sparse-name fix and guarantees the configured format, the first name, and journal/keywords all appear when available.
- Profile preferences labels and the homepage hint updated to show `LastName-FirstName_...`.

## [0.4.2] - 2026-06-25

### Added

- **Admin accounts exempt from the default rate limit.** Authenticated admins (`is_admin`) are now exempt from the global `200/day` + `50/hour` defaults — this is a trusted internal tool and admins legitimately make many requests (dashboard polling, bulk uploads). Detection mirrors `auth_required` (JWT cookie/header), so it works before Flask-Login populates `current_user`. Per-route limits still apply.

### Fixed

- **Sparse filenames when the LLM emitted a lazy `suggested_filename`.** The app used the LLM's `suggested_filename` verbatim, so a paper could land as `Hribar_2023.pdf` even though the journal and keywords were correctly extracted into the structured fields. The filename is now rebuilt from the validated fields (`LLMService.build_filename`) whenever the LLM's name dropped sections it had data for; empty/Unknown components are omitted, so papers genuinely lacking a journal still yield a clean `Author_Year` name. Honors all preset formats and Custom templates.

## [0.4.1] - 2026-06-25

### Fixed

- **False "Lost connection to server" on multi-file jobs.** The progress-polling endpoint (`GET /api/upload/progress/<job_id>`) was subject to the global default rate limit (`50 per hour`) in addition to its own `600 per minute` cap — Flask-Limiter stacks per-route limits on top of the defaults rather than replacing them. The UI polls every 5 s while a job runs, so a long batch (e.g. 20 files) exhausted 50/hour and started receiving HTTP 429; six consecutive failures (~30 s) tripped the frontend's "Lost connection" guard and aborted an otherwise-healthy job. The endpoint is now exempt from the default limits (it keeps its 600/min cap), matching how the health-check endpoint is handled.
- **Empty journal no longer fails extraction.** `PaperMetadata.journal` required ≥1 character, so papers whose extracted text omits a journal (preprints, template PDFs) failed schema validation, burned all 3 escalating-temperature retries, and fell through to the lenient parser. A blank/missing journal is now coerced to `"Unknown"` on first parse, eliminating the wasted retries and log noise.

### Infrastructure (server-side, not in image)

- Nginx `location /pdf-renamer/` `client_max_body_size` raised from `50M` to `500M` to match the app's `MAX_CONTENT_LENGTH` (500 MB). Previously any submission over 50 MB total was rejected by the proxy before reaching Flask.

## [0.4.0] - 2026-04-29

### Added

- LM Studio / OpenAI-compatible backend fixes, smart download, PDF metadata extraction, duplicate detection (same-content grouping), and output-filename collision resolution. (Backfilled entry — see PROJECT_LOG.md for detail.)

## [0.3.7] - 2026-04-27

### Fixed

- **Disk leak under cleanup queue exhaustion (CR-1).** `schedule_cleanup()` silently dropped cleanup tasks when the BoundedSemaphore(50) was exhausted; the comment promising a "periodic cleanup" referred to code that did not exist. Added a daemon sweeper thread (`_sweeper_loop`) that scans `temp/` and `uploads/downloads/` every 5 minutes and deletes files older than 30 minutes. This backstop fires regardless of whether the semaphore queue is full.
- **PDF executor recycle race (CR-2).** `extract_text_from_pdf()` read `_extraction_executor` under `_executor_lock` then released the lock before calling `submit()`. The hourly recycle daemon could `shutdown(wait=False)` the old executor in that gap, causing `RuntimeError` on submit (caught silently, returning empty text). Lock is now held across `submit()`, which is non-blocking.
- **FileService instantiated with no config in admin endpoints (CR-3).** The `/api/admin/cleanup` and `/api/admin/storage` endpoints called bare `FileService()`, getting cwd-relative folder paths instead of the Flask-configured `UPLOAD_FOLDER`/`TEMP_FOLDER`. Both now call `FileService(current_app.config)`.
- **Dead code removed (CR-4).** `FileService.process_files_batch` (unreachable — all uploads go through the background worker) and `PDFProcessor.text_chunk_size` (set but never read) deleted.

### Added

- **Cleanup and PDF extraction health in system status (CR-5).** `GET /api/admin/system-status` now includes `cleanup` (queue depth, skipped total) and `pdf_extraction` (timeout count, recycle countdown) fields, matching what `/api/admin/storage` already exposed. Admin dashboard "healthy" indicator now reflects operational distress in these subsystems.

## [0.3.6] - 2026-04-27

### Fixed (post-v0.3.5 review hotfix)

- **PDF extraction timeout was non-functional.** The `with ThreadPoolExecutor(...)` context manager called `shutdown(wait=True)` on exit, blocking until the hung worker finished — defeating the timeout entirely. Replaced with module-level long-lived executor; hung threads now park in pool slots without blocking the request thread. Also added thread-safety lock around `PDFProcessor._cache`.
- **Concurrent duplicate-upload race.** Post-write cache lookup returned the same temp path to two threads; when thread A's `move_to_downloads` ran, thread B's file vanished. Each upload now keeps its own private temp file; cache is informational only.
- **Non-root container couldn't upgrade from v0.3.4** because Docker named volumes contained root-owned files. Added `docker/entrypoint.sh` that starts as root, chowns `/app/instance`, `/app/uploads`, `/app/temp` to the `app` user, then drops privileges via `gosu`. Idempotent on fresh deployments.
- **Modal Escape key bypassed per-modal cleanup**, leaking `_pollingInterval` / `_autoCloseInterval` / `_autoCloseListeners`. Added `data-modal-close` attribute to all 12 close buttons in templates so the Escape handler invokes the proper cleanup function.
- **Stale `tests/unit/test_pypdf_migration.py`** referenced removed methods and `import pypdf` — would fail entire test run. Deleted.

### Added (v0.3.6 hardening)

- **PDF extraction executor hourly recycle** — daemon thread atomically swaps the executor every hour and calls `shutdown(wait=False)` on the old one so leaked timeout-hung threads can eventually exit. New `get_extraction_health()` helper exposes timeout count and recycle countdown.
- **Storage health endpoint** `GET /api/admin/storage` — returns disk usage, downloads dir size/count, cleanup queue stats, PDF extraction health. New `_skipped_cleanup_count` metric in `FileService` (locked).
- **System status LLM probe is now cached for 60 seconds**. Was hitting the LLM API on every admin dashboard load.
- **Per-route rate limits**: `/api/upload` 20/hr (admin exempt), `/api/upload/progress/<id>` 600/min, `/api/download` 60/min. Removed dead `_file_processor_pool` module global from `upload.py`.
- **JWT_SECRET_KEY** environment variable for separating JWT signing from Flask `SECRET_KEY`. Defaults to `SECRET_KEY` for backward compatibility; startup warning emitted when shared.
- **Structured logging extended to gunicorn handlers** — `gunicorn.access` and `gunicorn.error` loggers now emit JSON with `request_id` correlation under `FLASK_ENV=production`.
- **Upgrade guide** added to README.md explaining the non-root container migration (auto-handled by entrypoint, no manual action needed).

## [0.3.5] - 2026-04-27

### Breaking

- **Container now runs as non-root user (UID 1000 `app`).** Existing deployments are auto-migrated by the new entrypoint script (`docker/entrypoint.sh`), which `chown`s the writable volumes on first start before dropping privileges via `gosu`. No manual action required.

### Security & Reliability

#### Critical
- **XSS via unescaped filenames** -- `escapeHtml()` now wraps every server-controlled string interpolated into `innerHTML` (results modal, progress items, file list, error messages, toasts). A maliciously named PDF can no longer execute JS in the page.

#### High
- **50MB upload size limit** enforced via Flask `MAX_CONTENT_LENGTH`; `validate_file()` is now actually called before saving (was unreachable dead code).
- **CSRF exempt path matching tightened** -- exact-match only, no `startswith()` bypass surface. `/api/auth/change-password` is no longer exempt.
- **Polling timeout** -- progress polling stops after 6 consecutive failures, 5 minutes stuck-state, or job-id 404.
- **Auto-close countdown cancels on user interaction** -- mousemove/keydown/scroll/touch in the results modal stops the timer so users can read or copy filenames.
- **Inactivity tracker initializes for modal-login users** -- previously users who logged in via the page-modal never got the auto-logout protection.
- **Modal accessibility** -- Escape closes, Tab focus is trapped, focus is restored to the trigger on close. Applied to all 6 dialogs via `MutationObserver` on `role="dialog"` elements.
- **Download via hidden `<a download>`** -- replaces `window.location.href` so a failing/HTML response no longer navigates the page away from the results modal.

#### Medium
- **PDF extraction hard timeout (30s)** -- a corrupt or malicious PDF can no longer hang a worker. Fallback chain reduced to pymupdf only; pdfplumber and pypdf removed from `requirements.txt`.
- **Atomic `.env` writes** in `save_api_key` (write to `.env.tmp`, fsync, `os.replace`) — no more truncation risk if the process dies mid-write.
- **Stop logging auto-admin password to stdout** -- written to `instance/.admin_initial_password` (mode 0600) and only the file path is logged.
- **Single-pass hash+save** in `FileService` (was double I/O); `threading.Lock` around the duplicate-detection cache.
- **Background-thread DB writes** -- `record_usage` now uses `logger.exception()` for full tracebacks and guards `request.remote_addr` behind `has_request_context()`.
- **Dockerfile: multi-stage build + non-root user** (`useradd -m -u 1000 app`). Final image ~33MB smaller (273MB vs 306MB).
- **Filename-based DOM ID collisions** -- replaced with stable index-based IDs (`progress-0`, `progress-1`, ...) and `dataset.filename` for lookup.
- **File-size warnings before upload** -- reject single file > 50MB, warn at total > 100MB.
- **Tailwind `max-h-[80vh]`** (v3 syntax silently ignored by v2) replaced with inline styles across templates and dynamic modals.
- **Toast a11y** -- `role="status" aria-live="polite"` on `#toast-container` so screen readers announce notifications.
- **Structured logging wired** -- `setup_structured_logging()` runs in production; `g.request_id` is now correlated onto every log record.

## [0.3.4] - 2026-04-20

### Fixed
- **`record_usage()` crash in background thread** -- Was accessing `request.remote_addr` outside request context. Now accepts pre-captured IP/UA parameters.
- **Race condition in progress endpoint** -- Job dict was read outside the lock; background thread could mutate it mid-response. Now uses `copy.deepcopy()` under the lock.
- **`max_tokens` too low for reasoning models** -- Gemma-4 and other thinking models use tokens for internal reasoning. Increased to 1000 for openai-compatible provider to accommodate chain-of-thought overhead.

## [0.3.3] - 2026-04-20

### Added
- **GPU LLM support via OpenAI-compatible API** -- New provider option for remote GPU servers (LM Studio, vLLM) over local network. Configurable from admin panel.
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
