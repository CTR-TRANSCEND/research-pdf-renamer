# PROJECT_LOG.md - Research PDF File Renamer

## Session 2026-04-29 CDT (Code Review & Fix)

- **Coding CLI used:** Claude Code CLI (Claude Sonnet 4.6)
- **Phase(s) worked on:** Full harness code review, triage, fix, redeploy

### Issues found (full audit of upload.py, llm_service.py, pdf_processor.py, file_service.py, admin.py, auth.py, main.js, config.py, app.py)

| # | Severity | File | Issue |
|---|---|---|---|
| 1 | **CRITICAL** | `backend/routes/upload.py` | `file_statuses` index mismatch: `sf["index"]` stored original upload enumeration index, which diverged from the 0-based position in `file_statuses` whenever any file failed pre-save validation. Status updates targeted wrong slots; in worst case an `IndexError`. |
| 2 | **HIGH** | `backend/app.py` | Health endpoint 429: Docker internal health probe (127.0.0.1, every 30s ≈ 120/hr) exceeded the default global rate limit (50/hr), causing repeated 429s in logs and a container that could eventually be marked unhealthy. |
| 3 | **MEDIUM** | `backend/services/llm_service.py` | `PaperMetadata extra="forbid"`: LLMs frequently return extra fields (doi, abstract, pmid, etc.). With "forbid", any extra field caused Pydantic validation failure → retry → failure, silently dropping valid metadata. |
| 4 | Low | `backend/services/llm_service.py` | `strict=True` with `extra="forbid"` combined: correct types on known fields but zero tolerance for unknown fields is too strict for LLM outputs. Fixed alongside #3. |

All other areas checked: duplicate-detection hash grouping (correct), collision resolver path arithmetic (correct), year validator int→str coercion (correct), PDF page limit (correct), registration modal auth flow (correct — no JWT cookie on pending approval), sweeper thread safety (correct), JWT cookie flags (correct), no hardcoded secrets found.

### Concrete changes implemented

**Commits:**
- `fa8196c` — fix: three bugs (index mismatch, health 429, LLM extra fields)
- `acad211` — fix: use correct flask-limiter 3.x API (`default_limits_exempt_when` not `exempt_when`)

**Files changed:**
- `backend/routes/upload.py` — rebind `sf["index"]` to sequential `file_statuses` position after list build
- `backend/app.py` — add `default_limits_exempt_when` exemption for `main.health_check`
- `backend/services/llm_service.py` — change `extra="forbid"` → `extra="ignore"`

**Docker ops:**
- Built new image (sha256:cca0d72...) and pushed to GHCR
- Redeployed pdf-renamer container; app confirmed healthy (200 on /api/health)

### Key technical decisions and rationale

- **Index fix**: chose to rebind `sf["index"]` in the existing `enumerate()` loop over `saved_files` rather than adding a separate lookup dict. Minimal diff, no behavior change for the (common) zero-error path.
- **Health rate limit**: used `default_limits_exempt_when` (flask-limiter 3.x API) rather than a blueprint-level `@limiter.exempt` decorator, since `health_check` is on the `main` blueprint which doesn't import the app-level limiter.
- **PaperMetadata extra**: chose `"ignore"` (not `"allow"`) so extra fields are silently dropped without exposing them in `model_dump()` output. This prevents accidental passthrough of LLM-injected fields into filenames.

### Deferred items (not fixed — low risk)

- `JWT_SECRET_KEY == SECRET_KEY` warning at startup: pre-existing, low risk in this deployment (no cross-service secret exposure). Fix: set `JWT_SECRET_KEY` env var.
- `FileService.max_content_length` defaults to 50MB regardless of `MAX_CONTENT_LENGTH` (500MB). Per-file 50MB cap is intentional; batch cap is 500MB. No bug.
- No unit tests for `_parse_response` / `_process_files_background` hot paths.

## Session 2026-04-08 09:45 CDT

- **Coding CLI used:** Claude Code CLI (Claude Opus 4.6, 1M context)
- **Phase(s) worked on:** Bug fixes (download auth, admin status), version bump, GHCR publish

### Concrete changes implemented

**Bug fixes:**
- Fixed download endpoint returning 401 Unauthorized: removed `@auth_required` from `/api/download/<path>` — the upload endpoint had no auth requirement, creating a mismatch where users could upload but not download. Files are protected by unguessable 16-char hex session IDs, auto-cleanup, and network restrictions.
- Fixed admin "System Status: Error. API key not configured" for Ollama: the `system_status()` endpoint required an API key for all providers including Ollama which doesn't need one. Added `optional_key_providers` list (ollama, openai-compatible, lm-studio) that skip the API key check.

**Release:**
- Bumped version to 0.3.2
- Updated CHANGELOG.md with v0.3.2 release notes
- Built and pushed Docker image to GHCR (:latest and :0.3.2 tags)
- Cleaned up old GHCR image versions (0.3.0, 0.3.1)
- Redeployed container on hurlab server

### Files/modules/functions touched

- `backend/version.py` - Version bump to 0.3.2
- `backend/routes/admin.py` - system_status() Ollama API key fix
- `backend/routes/upload.py` - Removed @auth_required from download endpoint
- `CHANGELOG.md` - Added v0.3.2 section
- `PROJECT_HANDOFF.md` - Updated to current state
- `PROJECT_LOG.md` - This entry

### Key technical decisions and rationale

1. **Removed auth from download endpoint:** Upload has no auth, so download shouldn't either. The session ID (16-char random hex) provides sufficient security as an unguessable token, combined with auto-cleanup and university network restriction.
2. **Optional API key providers:** Ollama, openai-compatible, and lm-studio are local/self-hosted providers that don't require API keys. The system status now correctly reflects this.

### Problems encountered and resolutions

- Admin password in .env doesn't match database (was changed after initial creation). Tested admin system status fix via direct Python code execution inside the container instead.

### Verification performed

- Download without auth: 200 OK, returns 6.4MB PDF
- System status for Ollama: correctly returns "healthy" without API key
- Health check: v0.3.2, healthy

---

## Session 2026-04-08 08:59 CDT

- **Coding CLI used:** Claude Code CLI (Claude Opus 4.6, 1M context)
- **Phase(s) worked on:** Initial deployment, bug fixes, PDF extraction improvements, documentation

### Concrete changes implemented

**Deployment:**
- Deployed research-pdf-renamer via Docker Compose on hurlab server (~/PROJECTS/research-pdf-renamer/)
- Configured Nginx reverse proxy at /pdf-renamer/ with HTTPS (*.med.und.edu wildcard cert)
- Added network restriction (allow 10.0.0.0/8, 134.129.0.0/16, 165.234.0.0/16, 192.168.0.0/16, 172.16.0.0/12; deny all)
- Created .env with Ollama provider, llama3.2:3b model, APPLICATION_ROOT=/pdf-renamer
- Used docker-compose.override.yml to pull GHCR image instead of local build (Docker DNS issue on this server)
- Added hurlab user to docker group, logged into GHCR as windysky

**Bug fixes:**
- Fixed CSRF header name: `X-CSRF-TOKEN` -> `X-CSRFToken` (Flask-WTF expected name)
- Added missing CSRF token setup in admin.html
- Exempted /api/auth/change-password from CSRF (JWT-authenticated JSON API)
- Fixed registration always failing: frontend wasn't sending `password_confirm` field
- Fixed download URL double-prefix when APPLICATION_ROOT is set (removed APP_BASE_URL prepend in JS)
- Fixed timestamp prefix on downloaded filenames (removed YYYYMMDD_HHMMSS_ prepend in file_service.py)
- Fixed download route stripping author name from filename (removed legacy timestamp-strip code in upload.py)
- Fixed LLM prompt with hardcoded example (Navaeiseddighi/bioRxiv) causing wrong metadata extraction
- Added missing backend/config.py to repo (was in Docker image but gitignored)
- Added .gitignore exception for backend/config.py

**Features:**
- Added pymupdf as third-tier PDF text extraction fallback (pdfplumber -> pypdf -> pymupdf)
- Added password visibility toggle (eye icon) on change-password forms (index.html + admin.html)
- Added LLM settings auto-seeding from env vars into database on first startup

**Build:**
- Simplified Dockerfile: removed apt-get install gcc/libffi-dev (all deps use pre-built wheels)
- Added pymupdf>=1.24.0 to requirements.txt
- Added APPLICATION_ROOT passthrough in docker-compose.yml

**Documentation:**
- Created CHANGELOG.md with v0.3.0 release notes
- Added Nginx reverse proxy section to docs/deployment.md
- Updated CSRF exemption list in deployment security docs
- Updated README: APPLICATION_ROOT in config table, corrected password hashing note, updated date
- Bumped version to 0.3.0, then 0.3.1 (on other machine)

### Files/modules/functions touched

- `backend/app.py` - CSRF exempt list, LLM settings seeding
- `backend/config.py` - Created (was missing from repo)
- `backend/version.py` - Version bump
- `backend/services/pdf_processor.py` - pymupdf fallback extraction
- `backend/services/file_service.py` - Removed timestamp prefix from filenames
- `backend/services/llm_service.py` - Replaced hardcoded prompt example with generic placeholders
- `backend/routes/upload.py` - Removed legacy timestamp-strip code from download route
- `frontend/static/js/main.js` - CSRF header fix, download URL fix, password toggle, registration fix
- `frontend/templates/index.html` - Password visibility toggle buttons
- `frontend/templates/admin.html` - CSRF setup, password visibility toggle
- `docker-compose.yml` - APPLICATION_ROOT env var
- `docker-compose.override.yml` - Created (server-specific GHCR image override)
- `Dockerfile` - Removed apt-get step
- `requirements.txt` - Added pymupdf
- `README.md` - Config table, date, password hashing note
- `CHANGELOG.md` - Created
- `docs/deployment.md` - Nginx section, CSRF docs
- `.gitignore` - Exception for backend/config.py, docker-compose.override.yml
- `/etc/nginx/sites-enabled/hurlab.med.und.edu.conf` - Added /pdf-renamer/ location blocks (sudo)

### Key technical decisions and rationale

1. **GHCR image instead of local build:** Docker on this server cannot reach deb.debian.org (Fastly CDN returns 404). Resolved permanently by removing apt-get from Dockerfile (all Python deps have pre-built manylinux wheels).
2. **CSRF exemption for change-password:** The endpoint uses JWT-authenticated JSON API. Flask-WTF CSRF tokens were incompatible with the JWT session flow, causing all password changes to fail.
3. **pymupdf fallback:** Nature/Springer PDFs use complex PostScript font encodings that crash pdfplumber and pypdf. pymupdf (based on MuPDF C library) handles these correctly.
4. **Generic LLM prompt example:** The hardcoded example in the prompt caused llama3.2:3b to copy the example author/journal instead of extracting from the paper.
5. **No timestamp on filenames:** Session folders already provide collision isolation; timestamps in filenames confused users and violated the advertised Author_Year_Journal_Keywords format.

### Problems encountered and resolutions

- Docker DNS issue -> Removed apt-get from Dockerfile entirely
- UFW blocking port 5000 -> Added allow rules for university networks
- User's desktop IP (172.24.128.1) was a virtual adapter; real IP was 10.226.109.234 -> Added 10.0.0.0/8 to Nginx allow list
- backend/config.py missing from repo due to blanket gitignore -> Added !backend/config.py exception
- Download route stripping author names that happened to be 8 characters -> Removed legacy timestamp-strip code

### Items completed in this session

- All items listed in Current State section of PROJECT_HANDOFF.md

### Verification performed

- Health check: v0.3.1 healthy
- HTTPS access from desktop: working
- PDF processing end-to-end: working (Sakamoto 2024 paper)
- Registration API: 201 Created
- Password change API: 200 OK
- Network restriction: university IPs allowed, others denied
- GHCR image push: 0.3.1 and latest confirmed

## Session 2026-04-27 22:09 CDT

- **Coding CLI used:** Claude Code CLI (Claude Opus 4.7, 1M context)
- **Phase(s) worked on:** Adversarial review batch 1 (Critical/High), batch 2 (Medium, parallel implementers), independent post-fix review (3 reviewers), hotfix batch
- **Versions touched this session:** v0.3.4 → v0.3.5 (tag e49c67f) → hotfix b517792

### Concrete changes implemented

**Batch 1 — Critical/High fixes (commit cb6ae8d):**
- Wrapped every `${...}` in innerHTML with `escapeHtml()` (XSS via filenames). Fixed in main.js: file list, results modal, error display, progress items, toast.
- 50MB upload limit: added `MAX_CONTENT_LENGTH` to Config; called `file_svc.validate_file()` before save in upload route (was unreachable dead code).
- CSRF: switched exempt path matching from `startswith()` to exact-match `frozenset`. `/api/auth/change-password` no longer exempt; frontend already sends `X-CSRFToken`.
- Polling: added `MAX_CONSECUTIVE_FAILURES=6`, 5-min stuck detection, 404 → stop.
- Auto-close countdown cancels on `mousemove/mousedown/keydown/wheel/touchstart` inside the modal.
- Inactivity tracker: `initializeInactivityTracking()` now called from `checkAuthStatus()` success branch so modal-login users get auto-logout.
- Modal accessibility helper (`setupModalAccessibility`) using `MutationObserver` on `[role="dialog"]` — Escape, Tab focus trap, focus restore.
- `triggerDownload()` helper using hidden `<a download>` click instead of `window.location.href`.

**Batch 2 — 8 parallel Medium implementers (commit c755f2e):**
- pdf_processor.py: dropped pdfplumber + pypdf, pymupdf-only, added 30s timeout via `ThreadPoolExecutor` (initially with `with` block — bug found later in review).
- file_service.py: single-pass hash+save (replaced two-pass `_calculate_file_hash` + `_save_file_streaming`); `threading.Lock` around `_file_hash_cache`.
- Dockerfile: multi-stage build (builder + runtime), non-root `app` user UID 1000, image size 273MB (was 306MB).
- main.js: index-based DOM IDs (`progress-0`, `progress-1`, ...) with `dataset.filename` for lookup; file size warnings (reject >50MB single, warn >100MB total).
- app.py: stop logging admin password — write to `instance/.admin_initial_password` (mode 0600); wire `setup_structured_logging()` and `g.request_id` filter under FLASK_ENV=production.
- admin.py: atomic `.env` write (`.env.tmp`, `os.fsync`, `chmod 0600`, `os.replace`).
- Templates: replaced Tailwind v3 `max-h-[80vh]` (silently ignored by v2) with inline style across `index.html`, `admin.html`, `base.html`, dynamic modal in `main.js`. Added `role="status" aria-live="polite"` to toast container.
- decorators.py: `record_usage` uses `logger.exception()` for tracebacks; guards `request.remote_addr`/`request.headers` behind `has_request_context()`.

**Version bump (commit e49c67f):** version.py 0.3.4 → 0.3.5; CHANGELOG entry covering all batch-1+2 changes.

**Independent review (3 parallel agents, no code changes):**
- Integration reviewer found 10 issues (top: PDF timeout non-functional due to `with` block).
- Functional reviewer verified 14/16 fully fixed, 2 partial (modal Escape leak, auto-close on hover-without-movement).
- Regression hunter found 5 confirmed regressions: stale `test_pypdf_migration.py`, concurrent dup-upload race, non-root upgrade breaks v0.3.4 volumes, plus 2 documentation gaps.

**Hotfix batch — 5 parallel Sonnet implementers (commit b517792):**
- pdf_processor.py: replaced per-call `with ThreadPoolExecutor(...)` with module-level `_extraction_executor = ThreadPoolExecutor(max_workers=4)` — no context manager, no `shutdown(wait=True)` on return. Hung threads now park in slots without blocking. Also added `threading.Lock` around `PDFProcessor._cache`.
- Deleted `tests/unit/test_pypdf_migration.py` (referenced removed methods, would fail every test run).
- file_service.py: race fix — duplicate-detection cache is now informational only. Each upload always returns its own private temp file; cache logs a duplicate hit but does not redirect or delete.
- Dockerfile + new `docker/entrypoint.sh`: container starts as root, entrypoint chowns `/app/instance`, `/app/uploads`, `/app/temp` to `app:app` if not already, then `gosu app` drops privileges. Idempotent on fresh deployments. Installed `gosu` apt package in runtime stage.
- index.html + admin.html: added `data-modal-close` attribute to all 12 close buttons so Escape-key handler invokes the proper per-modal cleanup function (e.g. `closeProcessingModal()`) instead of just hiding the modal — fixes leak of `_pollingInterval`/`_autoCloseInterval`/`_autoCloseListeners` on Escape during processing.

### Files/modules/functions touched

- backend/app.py (CSRF exempt set, structured logging, admin password to file)
- backend/config.py (MAX_CONTENT_LENGTH)
- backend/routes/upload.py (validate_file before save)
- backend/routes/admin.py (atomic .env write)
- backend/services/file_service.py (single-pass hash, race fix, lock)
- backend/services/pdf_processor.py (pymupdf-only, working timeout, cache lock)
- backend/utils/decorators.py (logger.exception, has_request_context guard)
- backend/version.py (0.3.4 → 0.3.5)
- frontend/static/js/main.js (XSS escape, polling timeout, auto-close cancel, modal a11y, triggerDownload, DOM IDs, file size warning)
- frontend/templates/index.html (data-modal-close on 8 buttons, max-h fix)
- frontend/templates/admin.html (data-modal-close on 4 buttons, max-h fix)
- frontend/templates/base.html (toast aria-live)
- Dockerfile (multi-stage, non-root, gosu, entrypoint)
- docker/entrypoint.sh (NEW — chown + gosu app)
- requirements.txt (removed pdfplumber, pypdf)
- tests/unit/test_pypdf_migration.py (DELETED)
- CHANGELOG.md (v0.3.5 entry)

### Key technical decisions and rationale

1. **Module-level ThreadPoolExecutor for PDF timeout:** Python threads can't be killed. The `with` context manager calls `shutdown(wait=True)` which blocks waiting for hung threads to finish — defeating the timeout. Solution: long-lived module-level executor with 4 slots; hung threads occupy slots permanently but cannot block the request thread. Trade-off: under sustained attack, slots leak. Acceptable for university-restricted deployment with monitoring.
2. **Cache-as-informational for file uploads:** The original race was caused by two threads sharing the same temp path via cache hit. Reverting to per-upload private files trades a small disk-write cost for correctness; the LLM-extraction cache (separate, in PDFProcessor) still amortizes work for re-uploaded PDFs as long as the file stays on disk during their concurrent windows.
3. **gosu entrypoint over USER directive:** Fresh deployments work fine with USER app, but existing v0.3.4 volumes contain root-owned files (db, uploads). entrypoint.sh starts as root, chowns the volume mount points, then drops to app via gosu. Idempotent. Avoids a destructive `docker volume rm` migration step.
4. **Sonnet model for hotfix implementers:** User-suggested cost optimization. Each fix was small and well-scoped; Sonnet handled them cleanly.
5. **Trio of independent reviewers (integration, functional, regression):** Three different angles caught different bugs. Integration spotted the timeout-context-manager bug; regression spotted the upgrade-path issue; functional confirmed all-but-two fixes verified. None individually would have caught all 5 follow-on bugs.

### Problems encountered and resolutions

- Build SSL error against pypi.org (transient). Resolution: `docker build --network=host`.
- `docker compose exec ... whoami` returned `root` even though gunicorn runs as app — `exec` defaults to root for ad-hoc commands. Resolution: verified gunicorn UID via `docker compose top` showing host UID 1000 (mapped to `app` inside container).
- 8 parallel implementers sometimes touched files concurrently when modifications overlapped (e.g., max-h-[80vh] in main.js was fixed by both the templates agent and would have been by the JS agent). Resolution: main.js fix was done by the templates agent; verified by grep.
- HTTPS certificate issue mid-session — temporarily switched production URL to HTTP. HSTS header commented out in Nginx; restoration script saved to `/tmp/restore-hsts.sh`.

### Items explicitly completed, resolved, or superseded in this session

Completed (all logged in PROJECT_HANDOFF.md "Current State" with `Completed in Session 2026-04-27 22:09 CDT`):
- All 8 Critical/High items from adversarial review batch 1
- All 8 Medium items from adversarial review batch 2
- All 5 review-found follow-on bugs from hotfix batch
- v0.3.5 release tagged and pushed to GHCR

Resolved risks:
- Volume ownership upgrade for non-root container (entrypoint chown)

Open risks (carried forward):
- Hung pymupdf threads occupy executor slots permanently
- Single gunicorn worker constraint (in-memory job state)
- HTTPS certificate issue (running on HTTP for now)
- Disk space monitoring

### Verification performed

- All Python files AST-parse: backend/{app,config,routes/admin,routes/upload,services/file_service,services/pdf_processor,utils/decorators}.py
- main.js passes `node --check`
- entrypoint.sh passes `sh -n`
- docker build succeeds (--network=host) 
- Container runs: `docker compose top pdf-renamer` shows UID 1000 (host akkas / container app)
- Health endpoint: `curl localhost:5000/pdf-renamer/api/health` returns `{"status":"healthy","version":"0.3.5"}`
- Direct LLM round-trip from container: returns expected filename in ~2s on GPU
- Concurrent 5-file processing: completes in ~7s total
- 12 `data-modal-close` attributes present in index.html (8) + admin.html (4)
- Zero remaining `max-h-[` matches in templates or main.js
- No secrets in any committed diff (grep for IPs, passwords)

End-to-end browser test: NOT yet performed post-hotfix (commit b517792). To verify next session: upload several PDFs from browser, confirm per-file progress stages, auto-close countdown cancel-on-interaction, Escape closes modal cleanly, retry-failed-files button works, download triggers without page navigation.

### Commits pushed this session

- `cb6ae8d` fix: address all critical & high issues from adversarial review
- `c755f2e` fix: medium-priority adversarial review items (8 parallel implementers)
- `e49c67f` chore: bump version to 0.3.5  ← TAG v0.3.5
- `b517792` fix: address bugs found in independent code review of v0.3.5

## Session 2026-04-27 23:10 CDT

- **Coding CLI used:** Claude Code CLI (Claude Opus 4.7, 1M context)
- **Phase(s) worked on:** v0.3.6 release (version bump + tag + GHCR push), Playwright smoke test on live deployment, post-release Senior Architect code review (CR-1…CR-5)

### Concrete changes implemented

**Version & release (commit 38ab939):**
- `backend/version.py` 0.3.5 → 0.3.6
- `CHANGELOG.md` new `## [0.3.6] - 2026-04-27` section consolidating: the v0.3.5 follow-on hotfixes (b517792) AND the v0.3.6 hardening additions (d45bc86) into a single user-facing release note.
- Created git tag `v0.3.6` on commit 38ab939, pushed to origin.
- Docker image rebuilt (`docker build --network=host`), tagged `:latest` and `:0.3.6`, pushed to GHCR. Final image digest `sha256:f1e55a1f78d15a3d82e8d83750e5dc1cf9336ab1299ac961fa402770ecc1a457`.
- Container `--force-recreate`d on the production server. Health endpoint confirms `v0.3.6` live.

**Production smoke test via Playwright MCP:**
- Navigated to `http://hurlab.med.und.edu/pdf-renamer/` — browser auto-upgraded to HTTPS via the still-cached HSTS, but **HTTPS now works** (cert is back).
- Confirmed `Version 0.3.6` in footer, page structure intact.
- Clicked Login button → modal opened.
- Pressed Escape → modal closed cleanly. This validates the `data-modal-close` fix from the v0.3.5 hotfix batch (commit b517792) end-to-end in production.
- Toast container `role="status"` was detected by the a11y tree.
- Verified `/api/admin/storage` returns HTTP 401 (auth-protected as designed).
- All security headers present (X-Frame-Options, CSP). HSTS still commented out per the cert-outage workaround.

**Senior Architect code review (no code modified):**
- 5 findings flagged in a structured table with Issue ID, Location, Description, Severity, Confirmation Notes, and step-by-step Action Plans:
  - **CR-1 (Critical):** Disk leak when cleanup queue is full. `FileService.schedule_cleanup` silently drops tasks when the BoundedSemaphore(50) is exhausted; the comment promises a "periodic cleanup" that does NOT exist anywhere in the codebase. Files persist on disk forever under sustained load. Confirmed by `grep -rn "periodic|cron|sweep|janitor" backend/` returning no scheduled-job mechanism.
  - **CR-2 (Medium):** Race in `pdf_processor.py:158-160`. Hot path reads `_extraction_executor` under `_executor_lock`, releases the lock, THEN calls `submit()`. The hourly `_recycle_executor` can swap and `shutdown(wait=False)` the old executor in that microsecond gap, causing `submit()` to raise `RuntimeError`. Window is small but real.
  - **CR-3 (Medium):** Storage endpoint creates new `FileService()` per call (`admin.py:1517`); the `__init__` calls `os.makedirs(...)` and depends on cwd=/app. Should reuse cached service via `get_services()`.
  - **CR-4 (Low):** Dead code — `FileService.process_files_batch` and `PDFProcessor.text_chunk_size` are unreferenced.
  - **CR-5 (Low):** `system_status` does NOT surface `get_cleanup_stats()` or `get_extraction_health()` — saturated cleanup queue or hung-PDF executor stays invisible to the dashboard's "healthy" indicator.

### Files/modules/functions touched

- backend/version.py (0.3.5 → 0.3.6)
- CHANGELOG.md (new v0.3.6 section)
- (No source code changes — review was findings-only, per `/codereview` instructions to STOP before modifying.)

### Key technical decisions and rationale

1. **Bumped to v0.3.6 instead of force-retagging v0.3.5.** The v0.3.5 git tag points to commit e49c67f, but we shipped 3 substantive commits since (b517792, d45bc86). Re-pushing `:0.3.5` GHCR images with new content violates the immutable-tag expectation. v0.3.6 gives those changes their own clean tag.
2. **Combined v0.3.5 follow-on hotfixes AND v0.3.6 hardening into a single CHANGELOG entry** for v0.3.6, since they were never user-visible under the v0.3.5 tag (image was repeatedly re-pushed). The CHANGELOG v0.3.5 section was left intact (historical accuracy).
3. **Code review used `/codereview` slash-command flow:** verify each finding, present in a table, STOP. Did not modify files. The five findings have step-by-step Action Plans the user can dispatch one at a time via the harness pattern.
4. **Did not run an end-to-end LLM round-trip** during the Playwright smoke test (no real PDF was uploaded). The verification confirmed UI structure, modal behavior, and auth gating — but the LLM extraction path was already verified earlier in the session via `docker compose exec` direct calls. Flagged as a future user-driven verification item.

### Problems encountered and resolutions

- HTTPS came back during the session — Playwright navigate to `http://...` was auto-upgraded to `https://...` via the browser's cached HSTS policy, and (unlike earlier in the day) HTTPS now responded correctly. The cert issue was apparently resolved on the user's side mid-session.
- Build still required `--network=host` due to a transient pypi SSL issue on the host. Same workaround as earlier sessions.

### Items explicitly completed, resolved, or superseded in this session

Completed:
- v0.3.6 version bump, CHANGELOG, git tag, GHCR push (commit 38ab939, image sha256:f1e55a...).
- Playwright smoke test on production: HTTPS works, version 0.3.6 confirmed live, modal Escape closes cleanly, /api/admin/storage 401, toast a11y verified.
- Senior Architect post-release code review with 5 findings (CR-1…CR-5) — findings only, no code changed.

Resolved (as of this session):
- HTTPS certificate issue (was Open since 2026-04-21) — production URL is back on HTTPS.

Open / new in this session:
- CR-1 (Critical): Disk leak under cleanup queue exhaustion. No periodic file sweeper exists despite the code comment promising one.
- CR-2 (Medium): PDF executor recycle race condition.
- CR-3 (Medium): Storage endpoint creates new FileService per call.
- CR-4 (Low): Dead code (process_files_batch, text_chunk_size).
- CR-5 (Low): system_status doesn't surface cleanup/PDF health.

### Verification performed

- `curl https://hurlab.med.und.edu/pdf-renamer/api/health` → `{"status":"healthy","version":"0.3.6"}`
- `curl https://hurlab.med.und.edu/pdf-renamer/` → 200 OK
- `curl https://hurlab.med.und.edu/pdf-renamer/api/admin/storage` → 401 (admin auth required as designed)
- `curl -I` shows X-Frame-Options + CSP, no HSTS (intentional per cert-outage workaround).
- Playwright navigate → confirmed Version 0.3.6 in footer, page structure intact.
- Playwright click Login → modal opened with Email/Password fields.
- Playwright press Escape → modal removed from a11y tree (data-modal-close fix verified end-to-end).
- `git tag` confirms `v0.3.6` exists locally and pushed to origin.
- `docker push` returned digests for both `:latest` and `:0.3.6`.

### Commits pushed this session

- `38ab939` chore: bump version to 0.3.6  ← TAG `v0.3.6`

### Open items handed off to next session

1. **CR-1 (Critical):** Implement a daemon file-sweeper in FileService that runs every 5 min and deletes files in `temp/` and `uploads/downloads/` older than 30 min. Mirror the pattern from `pdf_processor.py`'s `_start_recycle_loop`. Update the misleading "will be cleaned by periodic cleanup" comment.
2. **CR-2 (Medium):** Move `executor.submit(...)` inside the `with _executor_lock:` block in `pdf_processor.py:158-160`. Submit is non-blocking; holding the lock through it costs nothing and eliminates the recycle race.
3. **CR-3 (Medium):** Replace `FileService()` in the storage endpoint with a cached instance from `get_services()` or pass `current_app.config`.
4. End-to-end LLM round-trip browser smoke test on v0.3.6 (Playwright skipped this).
5. Restore HSTS in Nginx now that HTTPS is back: `bash /tmp/restore-hsts.sh` from `juhur` (sudo).
6. CR-4 + CR-5 (low-priority cleanup).
7. v0.4.0 architecture work (Redis jobs, async LLM I/O, LLMService split).

## Session 2026-04-27 CDT (session 3)

- **Coding CLI used:** Claude Code CLI (Claude Sonnet 4.6)
- **Phase(s) worked on:** Independent re-verification of CR-1…CR-5 (5 parallel Explore agents), implementation of all 5 fixes (3 parallel implementers via harness-hur-default team), v0.3.7 release

### Concrete changes implemented

**CR-1 — Periodic file sweeper daemon (file_service.py — Critical):**
- Added `import time` at module level
- Added 6 module-level sweeper variables: `_SWEEP_INTERVAL_SECONDS=300`, `_SWEEP_MAX_AGE_SECONDS=1800`, `_sweep_upload_folder`, `_sweep_temp_folder`, `_sweeper_started`, `_sweeper_lock`
- Added `_sweep_old_files()` — scans `temp/` and `uploads/downloads/` (one level deep in session subdirs), removes files older than 30 min
- Added `_sweeper_loop()` — daemon loop calling `_sweep_old_files()` every 5 min
- Added `_start_sweeper()` — double-checked locking, starts daemon thread exactly once per process
- Called `_start_sweeper(self.upload_folder, self.temp_folder)` at end of `FileService.__init__`
- Fixed misleading comment in `schedule_cleanup()` from "will be cleaned by periodic cleanup" to "the periodic sweeper will catch it"

**CR-2 — Executor submit() race fix (pdf_processor.py — Medium):**
- Moved `future = executor.submit(...)` inside the `with _executor_lock:` block. Previously the lock was released before submit(), allowing the recycle daemon to shutdown() the old executor in the gap. Now submit is atomic with the executor read.

**CR-3 — FileService gets proper config (admin.py — Medium):**
- `trigger_cleanup()` (line ~565): `FileService()` → `FileService(current_app.config)` with local `from flask import current_app`
- `get_storage_health()` (line ~1517): `FileService()` → `FileService(_current_app.config)` with local alias import

**CR-4 — Dead code removal (Low):**
- Deleted `FileService.process_files_batch` from file_service.py (zero callers)
- Deleted `self.text_chunk_size = 4096` from `PDFProcessor.__init__` in pdf_processor.py (set but never read)

**CR-5 — Health fields in system_status (admin.py — Low):**
- Added `cleanup_health` (via `get_cleanup_stats()`) and `pdf_extraction_health` (via `get_extraction_health()`) sections inside `system_status()`, both guarded with `except Exception → {}`
- Added `"cleanup"` and `"pdf_extraction"` keys to the `return jsonify(...)` dict (purely additive)

**Version & release (commit 32f82b3):**
- `backend/version.py` 0.3.6 → 0.3.7
- `CHANGELOG.md` new `## [0.3.7] - 2026-04-27` section
- Git tag `v0.3.7`, pushed to origin
- Docker image rebuilt (`--network=host`), tagged `:latest` and `:0.3.7`, pushed to GHCR. Image digest `sha256:6d566c78c5f084b01a1b68604b982f4b75b84a08cb217941db955ef3687f23db`
- Container `--force-recreate`d; health endpoint confirms `v0.3.7` live

**HSTS — confirmed already active (no change needed):**
- Previous session noted HSTS was commented out, but `curl -I` shows `Strict-Transport-Security: max-age=31536000; includeSubDomains` is live. Nginx config had the header uncommented (lines 163, 320). `/tmp/restore-hsts.sh` script was unnecessary.

### Files/modules/functions touched

- `backend/services/file_service.py` (sweeper functions + __init__ call + comment fix + dead method deleted)
- `backend/services/pdf_processor.py` (lock scope + dead attribute deleted)
- `backend/routes/admin.py` (FileService config in 2 places + system_status new fields)
- `backend/version.py` (0.3.6 → 0.3.7)
- `CHANGELOG.md` (new v0.3.7 section)
- `PROJECT_HANDOFF.md` (updated to current state)

### Key technical decisions and rationale

1. **Sweeper uses same folder paths as FileService instance** — `_start_sweeper()` receives `self.upload_folder` and `self.temp_folder` on first `FileService.__init__` call; subsequent calls are no-ops (double-checked lock). This mirrors the `_start_recycle_loop` pattern in pdf_processor.py exactly.
2. **`FileService(current_app.config)` instead of `get_services()`** — `get_services()` lives in upload.py and importing it from admin.py would risk circular imports. Passing `current_app.config` achieves the same effect (correct UPLOAD_FOLDER/TEMP_FOLDER resolution) without architectural changes.
3. **CR-5 additions are additive-only** — new JSON keys can't break any existing consumer of system_status; each import is guarded with `except Exception → {}` so neither function being unavailable can crash the dashboard.
4. **3 parallel implementers via harness-hur-default team** — file_service.py, pdf_processor.py, and admin.py are independent files; running agents in parallel cut wall-clock time to ~2 min for all 5 fixes combined.
5. **5 parallel verifier agents preceded implementation** — all 5 CR findings were independently re-confirmed against actual source code before any code was written, validating the previous session's analysis.

### Problems encountered and resolutions

- HSTS restore script at `/tmp/restore-hsts.sh` was unnecessary — the Nginx config already had the header uncommented. The previous session noted it was disabled but that state must have been corrected before this session started.

### Items explicitly completed, resolved, or superseded in this session

Completed:
- CR-1 (Critical): Disk-leak sweeper daemon
- CR-2 (Medium): Executor submit() race
- CR-3 (Medium): FileService per-call in admin
- CR-4 (Low): Dead code removal
- CR-5 (Low): system_status health fields
- HSTS: Confirmed already active (no action needed)
- v0.3.7 tagged and live on production

### Verification performed

- `python3.12 -m py_compile` on all 3 modified Python files: OK
- `grep` for sweeper symbols in file_service.py: present at correct lines
- `grep` for lock scope in pdf_processor.py: `executor.submit()` inside `with _executor_lock:`
- `grep "FileService()"` in admin.py: 0 results
- `grep` for new health symbols in admin.py: all present in system_status
- `curl https://hurlab.med.und.edu/pdf-renamer/api/health` → `v0.3.7 healthy`
- `curl -sI https://...` → `Strict-Transport-Security: max-age=31536000; includeSubDomains`

### Commits pushed this session

- `32f82b3` fix: address all CR-1…CR-5 post-release review findings (v0.3.7)  ← TAG `v0.3.7`

### Open items handed off to next session

1. **End-to-end real PDF upload** — no human has uploaded a real PDF to v0.3.7. Recommend: upload 2–3 PDFs from browser, confirm per-file progress, renamed files, download link.
2. **v0.4.0 architecture** — Redis-backed jobs, async LLM I/O, LLMService split per-provider.
3. **Test coverage** — `LLMService._parse_response` and `_process_files_background` hot paths have no tests.
