# Changelog

All notable changes to Research PDF File Renamer are documented here.

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
