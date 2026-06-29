# PROJECT_HANDOFF.md - Research PDF File Renamer

## 1. Project Overview

AI-powered web application that automatically renames research PDF files using LLM-extracted metadata (author, year, journal, keywords). Deployed via Docker Compose with bundled Ollama LLM (CPU fallback) and configurable OpenAI-compatible GPU backend (LM Studio over private network), behind Nginx reverse proxy on hurlab.med.und.edu.

- **Repository:** https://github.com/CTR-TRANSCEND/research-pdf-renamer
- **Docker Image:** ghcr.io/ctr-transcend/research-pdf-renamer
- **Production URL:** https://hurlab.med.und.edu/pdf-renamer/ (HTTPS working; the recurring cert/HTTPS issue was root-caused + fixed May 2026 — see Risks + wiki)
- **Current version:** 0.4.6 (commit `339cc63`)
- **Last updated:** 2026-06-28 17:2x CDT (v0.4.6 extraction fix: recover author/year/journal on metadata-rich PDFs — abstract cap + 8000-char budget + PDF-metadata fallback)
- **Last coding CLI used:** Claude Code CLI (Claude Opus 4.8)
- **Related wiki:** `~/PROJECTS/wiki/concept/hurlab-https-outage` (the recurring HTTPS issue, root-caused + fixed May 2026); `concept/flask-limiter-behind-reverse-proxy` (the rate-limit "Lost connection" gotcha); `concept/browser-folder-upload-recursion-and-limits` (folder upload recursion + per-file vs request size-limit decoupling, from v0.4.5).

## 2. Current State

| Feature / Component | Status | Notes |
|---|---|---|
| **Nginx upload cap raised 50M → 500M** | **Completed 2026-06-25** | Active `location /pdf-renamer/` rejected >50 MB with 413 before Flask. Now `500M`, matches app `MAX_CONTENT_LENGTH`. Server-side only; `docs/deployment.md` example also corrected. |
| **v0.4.1: progress-poll rate-limit exemption** | **Completed 2026-06-25** | Fixed false "Lost connection" on multi-file jobs (poll endpoint hit global 50/hr → 429). Commit `dcbb19e`. |
| **v0.4.1: empty journal → "Unknown"** | **Completed 2026-06-25** | No more validation failure + 3 wasted retries when a paper has no journal. Commit `dcbb19e`. |
| **v0.4.2: admin rate-limit exemption** | **Completed 2026-06-25** | `is_admin` users exempt from default limits (`request_is_admin()`). Commit `0bee2e8`. |
| **v0.4.2: rebuild sparse filenames from fields** | **Completed 2026-06-25** | `Hribar_2023.pdf` → full name via `LLMService.build_filename()`. Commit `0bee2e8`. |
| **v0.4.3: LastName-FirstName author default** | **Completed 2026-06-25** | LLM extracts primary author first name (`author_first`); filenames always built from fields → `Hribar-Jason_2023_Journal_keywords`. All presets + Custom + UI labels updated. Commit `678623a`. Live + verified. |
| **v0.4.4: filename placeholder consistency** | **Completed 2026-06-28 16:27 CDT** | Missing fields keep `Unknown` placeholder (reversed v0.4.2 omit) → `Tu-Tao_2024_Unknown_diagnosticAI-LLM-selfplay`. Commit `134069c`. Live + verified. |
| **v0.4.5: 100-file/5GB limits + multi-folder + structure output** | **Completed 2026-06-28 16:27 CDT** | Per-session 30→100; request ceiling 5000MB + nginx 5000M; per-file 50MB decoupled (`MAX_FILE_SIZE`); multi-folder accumulate + recursive drag-drop; ZIP mirrors input tree. Commit `187922a`. Live + verified. |
| **v0.4.6: recover author/year/journal on metadata-rich PDFs** | **Deployed 2026-06-28 (live, container-verified; user re-upload pending)** | Root cause: text truncated to 3000 chars + the PDF `subject` (often the full abstract) injected ahead of page text pushed the title-page citation (journal+year) past the cap → LLM returned blank → `Unknown_Unknown_Unknown_paper.pdf`. Fix: cap injected subject @300; `MAX_TEXT_LENGTH` 3000→8000; new `PDFProcessor.extract_pdf_metadata_fields()` backfills author/title/keywords/year from PDF properties when the LLM misses them (`upload.py`). Verified on the real failing PDF: now `Langevin-Stephanie_2022_Int-J-Environ-Res-Public-Health_...`. Commits `0c17d13` + `339cc63`. |
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
| **v0.4.0 feature release** | **Completed 2026-04-29** | LM Studio fixes, smart download, PDF metadata extraction, duplicate detection, collision resolution |
| **v0.4.1→v0.4.3 fixes + LastName-FirstName** | **Completed 2026-06-25 13:45 CDT** | nginx 50M→500M; progress rate-limit exemption (Lost-connection fix); empty journal→Unknown; admin rate-limit exemption; deterministic filename build; LastName-FirstName author default. All live + verified on container. |
| **v0.4.4 + v0.4.5 limits/folders** | **Completed 2026-06-28 16:27 CDT** | Filename `Unknown` placeholder consistency; per-session 30→100; request ceiling 5000MB + nginx 5000M; per-file 50MB decoupled; multi-folder accumulate + recursive drag-drop; ZIP mirrors input tree. Live + verified. |
| v0.5.0 architecture work | Not started | — | Redis-backed jobs, async LLM I/O, LLMService split |

## 4. Outstanding Work

| Item | Status | Last Updated | Reference |
|---|---|---|---|
| **End-to-end real PDF upload smoke test (v0.4.6)** | In progress (user-driven) | 2026-06-28 | Pending user re-upload on v0.4.6 of the two PDFs that exposed the bug: Langevin paper should now yield `Langevin-Stephanie_2022_<journal>_...` (was `Unknown_Unknown_Unknown_paper`); DRAGON-AI preprint keeps author+keywords with `Unknown` year/journal (honest — not on page 1). Also still-open from v0.4.5: multi-folder ZIP-mirrors-tree + batch >30. See Session 2026-06-28 (v0.4.6). |
| **Tests for hot paths** | Not started | 2026-04-27 | No coverage for `LLMService._parse_response` (per-provider shapes including reasoning_content fallback) or per-file stage updates in `_process_files_background`. |
| **Anonymous-user code path decision** | Open | 2026-04-27 | The codebase supports anonymous uploads (5-file limit, IP-based rate limit on `Usage`). Either keep or commit to auth-required + delete. Not blocking. |
| **v0.4.0 architecture refactors** | Not started | 2026-04-27 | (a) Job state → Redis (multi-worker). (b) Async LLM I/O via httpx.AsyncClient + semaphore. (c) Split LLMService 939-line file per-provider. (d) Multi-stage pyproject migration if desired. |

## 5. Risks, Open Questions, and Assumptions

| Item | Status | Date Opened | Notes |
|---|---|---|---|
| Single gunicorn worker constraint | Open | 2026-04-20 | In-memory `_job_progress` dict requires `--workers 1`. Restart loses in-flight jobs; no rolling deploys. Solution: move to Redis (deferred to v0.5.0). |
| Large batches (100 files / up to 5GB) on single worker | **Open** | 2026-06-28 | v0.4.5 raised limits to 100 files / 5000MB. On the single worker a very large job can run long AND the 30-min temp sweeper could clip in-progress files if a job exceeds 30 min. Realistic batches are fine. Mitigations if it bites: widen `_SWEEP_MAX_AGE_SECONDS` / make cleanup job-aware; proper fix is v0.5.0. |
| Upload size cap (nginx ↔ app) | **Resolved 2026-06-28** | 2026-06-25 | nginx `/pdf-renamer/` `client_max_body_size` now 5000M, matching app `MAX_CONTENT_LENGTH` 5000MB (was 50M, then 500M). Per-file cap is separate (`MAX_FILE_SIZE` 50MB). `docs/deployment.md` updated. |
| False "Lost connection" on multi-file jobs | **Resolved 2026-06-25** | 2026-06-25 | Progress-poll endpoint hit the global 50/hr default → 429×6. Exempted from defaults in v0.4.1 (keeps 600/min). |
| GHCR push from server | **Open** | 2026-06-25 | Server `docker login` to GHCR expired → `docker push` 401. Non-fatal (prod runs from locally-built `:latest`). Re-login to archive versioned images. |
| Hung pymupdf threads occupy executor slots | Mitigated | 2026-04-27 | Module-level executor with hourly recycle. CR-2 race closed in v0.3.7. |
| Tailscale IP not in repo | Mitigated | 2026-04-20 | Verified by grep on each commit; only present in gitignored `.env`. |
| HTTPS/HSTS not accessible externally | **Resolved (May 2026)** | 2026-04-27 session 3 | Root cause was a stray iptables `:443→:8080` REDIRECT persisted in BOTH `/etc/ufw/before.rules` and `/etc/iptables/rules.v4`. Durably fixed May 2026; HTTPS verified healthy this session. See wiki `concept/hurlab-https-outage`. |
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
| App health (v0.4.5) | `curl …/api/health` | `{"status":"healthy","version":"0.4.5"}` | 2026-06-28 16:27 CDT |
| Size config (v0.4.5) | container `Config` | `MAX_CONTENT_LENGTH=5000MB MAX_FILE_SIZE=50MB` | 2026-06-28 |
| Approved-user file limit (v0.4.5) | container `User().get_max_files()` | `100` | 2026-06-28 |
| nginx body size (v0.4.5) | script grep after edit | pdf-renamer `client_max_body_size 5000M` + `proxy_read_timeout 600`; admin :8443 50M, /coai 300M unchanged; `nginx -t` pass + reload | 2026-06-28 |
| Filename placeholder (v0.4.4) | container `build_filename` | no-journal → `Tu-Tao_2024_Unknown_diagnosticAI-LLM-selfplay.pdf` | 2026-06-28 |
| App health (v0.4.3) | `curl …/api/health` | `{"status":"healthy","version":"0.4.3"}` | 2026-06-25 13:xx CDT |
| nginx `/pdf-renamer/` body size | script: grep active conf after edit | `client_max_body_size 500M` (admin :8443 50M + /coai 300M unchanged); `nginx -t` pass + reload | 2026-06-25 |
| Progress rate-limit exemption live | container: `request_is_admin`/`upload.get_progress` in `create_app` source | True | 2026-06-25 |
| Empty journal coercion | container: `PaperMetadata(journal="")` | `journal == "Unknown"` | 2026-06-25 |
| `build_filename` LastName-FirstName | container: `LLMService.build_filename` | `Hribar-Jason_2023_Ophthalmology_ophthalmology-data-standards-OMOP-CDM.pdf`; fallback `Hribar_2023_…` | 2026-06-25 |
| Disconnect cause (logs) | `docker logs` during failed 20-file run | 6× HTTP 429 on progress poll; RestartCount=0, OOMKilled=false (not a crash) | 2026-06-25 |
| **End-to-end real PDF upload (v0.4.3)** | Awaiting human verification | 20-file batch + LastName-FirstName filenames not yet user-confirmed on v0.4.3 | — |

## 7. Restart Instructions

- **Starting point:** Tip of `main` is commit `339cc63` (v0.4.6; `0c17d13` is the fix, `339cc63` gitignores `tmp/`). Version `0.4.6`, live in production (container-verified).
- **Deploy dir (server):** `/home/hurlab/PROJECTS/research-pdf-renamer` (owned by `hurlab`; has the gitignored `docker-compose.override.yml`). The `~/PROJECTS/research-pdf-renamer` in the build steps below means THIS path. `/data/juhurSync/.../10_apps/...` is only the rsync mirror — not the deployment.
- **Privileged ops:** `juhur` is not in the `docker` group and sudo needs an interactive password. Run docker/nginx/deploy via a script placed in `/home/juhur/tmp/` that the user executes; read results back over SSH. Never use `! sudo` (does not work in Claude Code CLI).
- **Live deployment:** v0.4.2 at https://hurlab.med.und.edu/pdf-renamer/ via `docker-compose.override.yml`. HTTPS works (the recurring outage was root-caused to a stray iptables `:443→:8080` REDIRECT in `/etc/ufw/before.rules` + `rules.v4` and durably fixed May 2026 — see wiki `concept/hurlab-https-outage`).
- **LLM backend:** Provider=`openai-compatible`, model=`gpt-oss-20b` (last known). URL via private network → spark-562c LM Studio. Fallback: switch admin panel → Ollama (Local CPU) `llama3.2:3b`. Settings persist in DB; admin save resets cached service immediately.

---

### ⚠️ CRITICAL: How to Build and Deploy on This Server

`docker-compose.override.yml` (gitignored, server-local) pins the image to:
```
ghcr.io/ctr-transcend/research-pdf-renamer:latest
```
This means Docker Compose **always** uses that tag, not a generic local build tag.
**If you build with any other tag, the container will NOT use your changes.**

#### Step 1 — Build (always target the GHCR tag directly):
```bash
newgrp docker <<'EOF'
docker build --no-cache --network=host \
  -t ghcr.io/ctr-transcend/research-pdf-renamer:latest \
  .
EOF
```
> Use `--no-cache` whenever source files changed. Without it, Docker may serve stale layers.

#### Step 2 — Restart the container:
```bash
newgrp docker <<'EOF'
docker compose up -d --force-recreate pdf-renamer
EOF
```
> `--force-recreate` is required. Plain `docker compose up -d` will reuse the running container and ignore the new image.

#### Step 3 — Verify the new code is live:
```bash
newgrp docker <<'EOF'
docker exec research-pdf-renamer-pdf-renamer-1 python3 -c "
from backend.version import __version__; print('version:', __version__)
"
EOF
```

#### To also push to GHCR (optional, for versioned releases):
```bash
newgrp docker <<'EOF'
docker tag ghcr.io/ctr-transcend/research-pdf-renamer:latest \
           ghcr.io/ctr-transcend/research-pdf-renamer:0.4.0
docker push ghcr.io/ctr-transcend/research-pdf-renamer:latest
docker push ghcr.io/ctr-transcend/research-pdf-renamer:0.4.0
EOF
```

---

- **Admin credentials (live DB):** `junguk.hur@med.und.edu` / `FIctmidYcpPwlVJy` (reset 2026-04-27; admin should change). `admin@local` password unknown — was changed via UI on 2026-04-08.
- **Key config files:** `.env` (gitignored — APPLICATION_ROOT=/pdf-renamer, LLM settings, OPENAI_COMPATIBLE_API_URL, OPENAI_COMPATIBLE_API_KEY=lm-studio, MAX_CONTENT_LENGTH is commented out → app uses the 500MB code default. Optionally add JWT_SECRET_KEY=<new random hex> to silence the startup warning.), `docker-compose.override.yml` (gitignored — pins image to `ghcr.io/ctr-transcend/research-pdf-renamer:latest`), Nginx at `/etc/nginx/sites-enabled/hurlab.med.und.edu.conf` (HSTS active, client_max_body_size 500M, proxy_read_timeout 600, proxy_buffering off).
- **Test users in DB:** `admin@local` (admin), `junguk.hur@med.und.edu` (admin).
- **Recommended next actions (in priority order):**
  1. **End-to-end retest on v0.4.5 (user)** — multi-folder upload (add 2+ folders / drop several, with subfolders) → confirm count accumulates + downloaded ZIP mirrors the input tree; a batch >30 files; and a missing-journal paper shows the `Unknown` slot.
  2. **GHCR re-login** on the server (`docker login ghcr.io`) so versioned images archive again (push currently 401s; non-fatal — prod runs from locally-built `:latest`).
  3. **Large-batch hardening** (only if pushing big batches): widen the temp sweeper window / make cleanup job-aware so a >30-min job isn't clipped (see Risks).
  4. **Tests** — golden-case coverage for `LLMService._parse_response`, `build_filename`, and `_process_files_background`.
  5. **v0.5.0 architecture** — Redis-backed jobs, async LLM I/O, LLMService split per-provider.
- **Deploy how-to:** edit locally → commit/push to GitHub → on server run a script in `/home/juhur/tmp/` that `git pull`s `/home/hurlab/PROJECTS/research-pdf-renamer` (as `hurlab`), `sudo docker build --no-cache --network=host -t ghcr.io/ctr-transcend/research-pdf-renamer:latest .`, `sudo docker compose up -d --force-recreate pdf-renamer`, then verifies. Template: `/home/juhur/tmp/pdf_v045.sh` (latest; also does the nginx step). nginx config changes need a similar sudo script (juhur not in docker group; sudo is interactive; never use `! sudo`).
- **Last updated:** 2026-06-28 16:27 CDT (v0.4.4 + v0.4.5 session)
