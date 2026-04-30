# PROJECT_HANDOFF.md - Research PDF File Renamer

## 1. Project Overview

AI-powered web application that automatically renames research PDF files using LLM-extracted metadata (author, year, journal, keywords). Deployed via Docker Compose with bundled Ollama LLM (CPU fallback) and configurable OpenAI-compatible GPU backend (LM Studio over private network), behind Nginx reverse proxy on hurlab.med.und.edu.

- **Repository:** https://github.com/CTR-TRANSCEND/research-pdf-renamer
- **Docker Image:** ghcr.io/ctr-transcend/research-pdf-renamer
- **Production URL:** http://hurlab.med.und.edu/pdf-renamer/ (HTTP only — HTTPS cert not yet accessible to external clients; see Risks)
- **Current version:** 0.3.7 (commit `acad211`, post-review patch)
- **Last updated:** 2026-04-29 CDT (code review & fix session)
- **Last coding CLI used:** Claude Code CLI (Claude Sonnet 4.6)

## 2. Current State

| Feature / Component | Status | Notes |
|---|---|---|
| All v0.3.5 critical/high/medium adversarial review items | Completed | 16 fixes — commits cb6ae8d + c755f2e |
| All v0.3.5 follow-on hotfix items (independent review batch) | Completed | 5 fixes — commit b517792 |
| All v0.3.6 hardening items (post-v0.3.5 review) | Completed | 7 parallel implementers — commit d45bc86 |
| v0.3.6 release tagged + GHCR push | Completed | sha256:f1e55a... |
| Playwright smoke test on live deployment (v0.3.6) | Completed | HTTPS, Escape modal, /api/admin/storage 401 |
| HTTPS certificate restoration | Completed | Cert is back; HSTS also confirmed active (see below) |
| **Post-review hotfix (3 bugs)** | **Completed 2026-04-29** | Index mismatch in file_statuses, health 429, LLM extra="forbid". Commits fa8196c + acad211. |
| **CR-1: Periodic file sweeper daemon** | **Completed 2026-04-27 session 3** | `_sweeper_loop` in file_service.py — scans temp/ + uploads/downloads/ every 5 min, deletes files >30 min old. Commit 32f82b3. |
| **CR-2: Executor submit() race fix** | **Completed 2026-04-27 session 3** | `executor.submit()` now inside `with _executor_lock:` in pdf_processor.py. Commit 32f82b3. |
| **CR-3: FileService gets current_app.config** | **Completed 2026-04-27 session 3** | Both admin endpoints now call `FileService(current_app.config)`. Commit 32f82b3. |
| **CR-4: Dead code removed** | **Completed 2026-04-27 session 3** | `FileService.process_files_batch` and `PDFProcessor.text_chunk_size` deleted. Commit 32f82b3. |
| **CR-5: system_status health fields** | **Completed 2026-04-27 session 3** | `cleanup` + `pdf_extraction` fields added to system_status response. Commit 32f82b3. |
| **HSTS header** | Still open | `curl -sI` from the server itself returns the HSTS header (Nginx config is uncommented), but external browser access is HTTP only — HTTPS cert is not accessible to external clients. This is the same recurring cert issue from prior sessions. |

## 3. Execution Plan Status

| Phase | Status | Last Updated | Notes |
|---|---|---|---|
| Initial deployment + GPU LLM + polling progress | Completed | 2026-04-20 | Sessions 2026-04-08 and 2026-04-20 |
| Adversarial review batches 1–2 + hotfix + post-fix hardening | Completed | 2026-04-27 | 21 issues fixed across 4 commits since v0.3.4 |
| v0.3.6 tag + GHCR publish + Playwright smoke test | Completed | 2026-04-27 | Final close-out for the v0.3.x line |
| End-of-session code review (CR-1…CR-5) — findings only | Completed | 2026-04-27 | 5 findings reported; no implementation |
| CR-1…CR-5 implementation + v0.3.7 release | Completed | 2026-04-27 session 3 | All 5 findings fixed; v0.3.7 live on production |
| v0.4.0 architecture work | Not started | — | Redis-backed jobs, async LLM I/O, LLMService split |

## 4. Outstanding Work

| Item | Status | Last Updated | Reference |
|---|---|---|---|
| **End-to-end real PDF upload smoke test** | Not yet performed by human | 2026-04-27 | No human has uploaded a real PDF to v0.3.7 yet. Playwright has only verified UI structure (v0.3.6). Recommend: upload 2–3 PDFs via browser, confirm per-file progress, renamed files, download. |
| **Tests for hot paths** | Not started | 2026-04-27 | No coverage for `LLMService._parse_response` (per-provider shapes including reasoning_content fallback) or per-file stage updates in `_process_files_background`. |
| **Anonymous-user code path decision** | Open | 2026-04-27 | The codebase supports anonymous uploads (5-file limit, IP-based rate limit on `Usage`). Either keep or commit to auth-required + delete. Not blocking. |
| **v0.4.0 architecture refactors** | Not started | 2026-04-27 | (a) Job state → Redis (multi-worker). (b) Async LLM I/O via httpx.AsyncClient + semaphore. (c) Split LLMService 939-line file per-provider. (d) Multi-stage pyproject migration if desired. |

## 5. Risks, Open Questions, and Assumptions

| Item | Status | Date Opened | Notes |
|---|---|---|---|
| Single gunicorn worker constraint | Open | 2026-04-20 | In-memory `_job_progress` dict requires `--workers 1`. Restart loses in-flight jobs; no rolling deploys. Solution: move to Redis (deferred to v0.4.0). |
| Hung pymupdf threads occupy executor slots | Mitigated | 2026-04-27 | Module-level executor with hourly recycle. CR-2 race closed in v0.3.7. |
| Tailscale IP not in repo | Mitigated | 2026-04-20 | Verified by grep on each commit; only present in gitignored `.env`. |
| HTTPS/HSTS not accessible externally | **Open (recurring)** | 2026-04-27 session 3 | HTTPS cert works from server-internal curl but not from external browser. Same cert issue as prior sessions. Nginx config has HSTS uncommented; problem is cert availability/validity for external clients. Needs investigation outside Claude Code (cert renewal or firewall/port 443 issue). |
| JWT_SECRET_KEY equals SECRET_KEY in production | Open | 2026-04-27 | Backward-compatible default. Startup logs a warning. To silence, set `JWT_SECRET_KEY=<new random hex>` in `.env`. Not blocking. |
| Disk leak under load (CR-1) | **Resolved** | 2026-04-27 session 3 | Periodic sweeper daemon added in v0.3.7 — runs every 5 min, deletes files >30 min old from temp/ and uploads/downloads/. |

## 6. Verification Status

| Item | Method | Result | Date/Time |
|---|---|---|---|
| App health check (v0.3.7) | `curl https://hurlab.med.und.edu/pdf-renamer/api/health` | `{"status":"healthy","version":"0.3.7"}` | 2026-04-27 session 3 |
| GHCR push (v0.3.7) | docker push :latest + :0.3.7 | sha256:6d566c78... | 2026-04-27 session 3 |
| HSTS header (internal curl only) | `curl -sI https://...` from server | Header present in Nginx response internally, but HTTPS not accessible to external browsers — corrected after user confirmation | 2026-04-27 session 3 |
| Python AST parse — all 3 modified files | `python3.12 -m py_compile` | OK | 2026-04-27 session 3 |
| No bare FileService() in admin.py | grep | 0 results | 2026-04-27 session 3 |
| Sweeper symbols in file_service.py | grep | `_start_sweeper`, `_sweep_old_files`, `_sweeper_loop` present | 2026-04-27 session 3 |
| Lock scope in pdf_processor.py | grep | `executor.submit()` at line 159 inside `with _executor_lock:` | 2026-04-27 session 3 |
| system_status health fields | grep | `cleanup_health`, `pdf_extraction_health` in response dict | 2026-04-27 session 3 |
| Production HTTPS | curl | 200 OK, valid cert, HSTS active | 2026-04-27 session 3 |
| **End-to-end real PDF upload** | Awaiting human verification | Not yet performed against v0.3.7 | — |

## 7. Restart Instructions

- **Starting point:** Tip of `main` is commit `32f82b3` (fix: address all CR-1…CR-5 post-release review findings). Tag `v0.3.7`. GHCR `:latest` and `:0.3.7` digest `sha256:6d566c78c5f084b01a1b68604b982f4b75b84a08cb217941db955ef3687f23db`.
- **Live deployment:** v0.3.7 at http://hurlab.med.und.edu/pdf-renamer/ via `docker-compose.override.yml` (pulls GHCR `:latest`). HTTPS cert not yet accessible externally.
- **LLM backend:** Provider=`openai-compatible`, model=`meta/llama-3.2-3b` (last known). URL via private network → spark-562c LM Studio. Fallback: switch admin panel → Ollama (Local CPU) `llama3.2:3b`. Settings persist in DB; admin save resets cached service immediately.
- **To redeploy:** `cd ~/PROJECTS/research-pdf-renamer && newgrp docker <<<"docker compose up -d --force-recreate pdf-renamer"`
- **To rebuild image:** `newgrp docker <<<"docker build --network=host -t ghcr.io/ctr-transcend/research-pdf-renamer:latest -t ghcr.io/ctr-transcend/research-pdf-renamer:0.3.7 . && docker push ghcr.io/ctr-transcend/research-pdf-renamer:latest && docker push ghcr.io/ctr-transcend/research-pdf-renamer:0.3.7"`
- **Admin credentials (live DB):** `junguk.hur@med.und.edu` / `FIctmidYcpPwlVJy` (reset 2026-04-27; admin should change). `admin@local` password unknown — was changed via UI on 2026-04-08.
- **Key config files:** `.env` (gitignored — APPLICATION_ROOT=/pdf-renamer, LLM settings, OPENAI_COMPATIBLE_API_URL, OPENAI_COMPATIBLE_API_KEY=lm-studio, MAX_CONTENT_LENGTH=50MB. Optionally add JWT_SECRET_KEY=<new random hex> to silence the startup warning.), `docker-compose.override.yml` (gitignored — pulls GHCR `:latest`), Nginx at `/etc/nginx/sites-enabled/hurlab.med.und.edu.conf` (HSTS active, client_max_body_size 500M, proxy_read_timeout 600, proxy_buffering off).
- **Test users in DB:** `admin@local` (admin), `junguk.hur@med.und.edu` (admin).
- **Recommended next actions (in priority order):**
  1. **End-to-end real PDF upload** — upload 2–3 PDFs from browser, confirm per-file progress stages, renamed files appear, download works. No human has done this against v0.3.7.
  2. **v0.4.0 architecture** — Redis-backed jobs, async LLM I/O, LLMService split per-provider.
  3. **Tests** — golden-case coverage for `LLMService._parse_response` and `_process_files_background`.
- **Last updated:** 2026-04-27 CDT (session 3)
