# PROJECT_LOG archive — Research PDF File Renamer — 2026 H1 (Jan–Jun)

Archived sessions moved verbatim from the active PROJECT_LOG.md. Newest first.

## Session Index (newest first)
- 2026-04-08 09:45 CDT — Download auth + admin status fixes, v0.3.2 release
- 2026-04-08 08:59 CDT — Initial deployment, bug fixes, PDF extraction, docs (v0.3.0/0.3.1)

---

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
