# PROJECT_LOG.md (active) — Research PDF File Renamer

Append-only history. Active file holds the most recent sessions; older ones
live in logs/. Newest first.

## Archives
- logs/PROJECT_LOG_2026-H1.md — 5 sessions (2026-04-08 … 2026-04-27)

## Session Index (active, newest first)
- 2026-08-19 — v0.4.9: named tool/software (e.g. MFS-MUnet) now leads the filename keywords; deployed + live-verified; stale sudo/docker-group handoff instructions corrected
- 2026-06-29 09:02 CDT — Extraction reliability cont. (v0.4.7 schema tolerance, v0.4.8 deterministic author fallback); diagnosed via live logs, user-confirmed
- 2026-06-28 17:2x CDT — Extraction bug fix (v0.4.6): metadata-rich PDFs lost author/year/journal due to 3000-char truncation + abstract crowding the prompt; fixed via abstract cap + 8000-char budget + PDF-metadata fallback
- 2026-06-28 16:27 CDT — Filename placeholder consistency (v0.4.4) + 100-file/5GB limits, decoupled per-file cap, multi-folder + structure-preserving output (v0.4.5)
- 2026-06-25 13:45 CDT — Upload-size + processing-failure fixes + LastName-FirstName default (v0.4.1 → v0.4.3)
- 2026-04-29 CDT — Full harness code review & fix (index mismatch, health 429, LLM extra fields)

---

## Session 2026-08-19 (v0.4.9 — named tool/software in the filename)

- **Coding CLI used:** Claude Code CLI (Claude Sonnet 5)
- **Phase(s):** Session-start reconciliation → feature request → approach approval → implement → verify → deploy → docs

### Request
User wanted the renamed file to keep the app/software name when the title carries one — e.g. `MFS-MUnet: Multi-scale Frequency Spatial Mamba U-Net for Medical Image Segmentation` should yield a filename containing `MFS-MUnet`.

### Why it did not already work
The prompt listed "specific named tools or algorithms that are the paper's contribution" only as keyword **priority #3** (behind disease and biological system), it was never required, and gpt-oss-20b is non-deterministic (the v0.4.8 finding). So the name appeared by luck and never in a predictable position. There was no `tool_name` concept anywhere in the prompt, schema, or `build_filename`.

### Decision (user-selected from 3 options)
Render the tool as the **first keyword** rather than adding a dedicated `{tool}` slot. Rationale: no new preset/UI/DB change, works with the format the user already runs, and — decisively — a dedicated slot would add an `Unknown` section to the majority of papers that name no tool (the v0.4.4 placeholder rule). Leading position also protects it from the 5-word truncation.

### Fix (commit `5a9907d`)
- `llm_service.py` — optional `tool_name` field on `PaperMetadata` (+ `coerce_tool_name`: null/list/`"none"`/`"n/a"` → `""`); prompt item 6 instructing exact-copy extraction with explicit "return empty, do not invent"; JSON example updated.
- `llm_service.py::build_filename` — tool prepended to keyword tokens, case-insensitive de-dup when the LLM also listed it, and the keyword cap changed from **5 comma-keywords to 5 hyphen-separated words**. That last part is load-bearing: `upload._truncate_keywords` counts hyphen-words, so an uncapped list could split `MFS-MUnet` into a bare `MFS`.
- `pdf_processor.py` — new `extract_tool_name_from_title()`: leading-token-before-colon, else parenthesized name; `_NOT_A_TOOL` stop-list + shape test (needs an internal capital/all-caps run/digit, or a capitalized token containing `-_+.`). Conservative by design — a wrong tool name in a filename is worse than an absent one.
- `upload.py` — one backfill beside the existing author/keyword ones: LLM wins, title regex is the net.
- `.gitignore` — restored the `tmp/` rule that a MoAI template refresh had dropped (it had re-exposed local research PDFs to `git add`).

### Verification
- **14/14** title cases, including 4 false-positive guards (`Review:`, `Correction:`, `Commentary:`, `Background:`) and the "colon but no tool" case (`…adolescent risk: a longitudinal study`).
- **36/36 no-tool filenames byte-identical to v0.4.8** — diffed the new `build_filename` against `git show HEAD:backend/services/llm_service.py`, 6 real metadata sets × 6 formats. This was a claim I had made, so it was measured rather than asserted.
- Schema: v0.4.8-shaped responses (no `tool_name`) still accepted; author-less still rejected (v0.4.8 invariant intact).
- Live in-container after deploy: `MFS-MUnet` → `Yang-Wei_2024_Neurocomputing_MFS-MUnet-medical-image-segmentation.pdf`; guards return `""`; health `{"status":"healthy","version":"0.4.9"}`.

### Deploy — and a corrected long-standing assumption
The handoff stated "`juhur` is not in the `docker` group and sudo needs an interactive password → all privileged ops via a script the user runs." **Half of that was stale.** Probed and found `juhur` IS in the `docker` group and `docker ps/build/compose/exec` all work unprivileged. The genuine constraint is narrower: the deploy dir is `hurlab:hurlab`, group-writable, **without a setgid bit** — so a pull run as juhur would create `juhur:juhur` files and silently strip hurlab's group-write, breaking future hurlab pulls. New split: **user runs only `sudo -u hurlab git pull`** (~10 s, ownership preserved — verified `-rw-rw-r-- hurlab hurlab` afterward), **agent runs build + recreate + verify** unprivileged. Handoff §7 rewritten accordingly.

### Problems / notes
- The `Hurlab` ssh alias points at bare hostname `hurlab`, which does not resolve from the WSL2 dev box; `ssh juhur@hurlab.med.und.edu` works. Recorded in the handoff.
- `git -C <deploy dir>` as juhur needs `-c safe.directory=<dir>` for read-only inspection (dubious-ownership guard).
- Docker build prints a harmless `failed to read current commit information` warning from the same guard — cosmetic.
- **Behavioral edge to watch:** the keyword cap changed units (comma-keywords → hyphen-words). A paper whose LLM returns many multi-word keywords may now show slightly fewer of them. The 36/36 parity run covers realistic cases but does not prove this invisible on every input.
- Keywords still depend entirely on the LLM — the deterministic nets now guarantee author (v0.4.8) and tool name (v0.4.9), but keywords are semantic and unrecoverable by regex. Unchanged low-priority open item.

### Commits (pushed to origin/main)
- `5a9907d` feat — include the paper's named tool in the filename (v0.4.9)

## Session 2026-06-29 09:02 CDT (extraction reliability v0.4.7 + v0.4.8)

- **Coding CLI used:** Claude Code CLI (Claude Opus 4.8)
- **Phase(s):** Continuation of the v0.4.6 extraction fix — user reported the DRAGON-AI PDF still returned `Unknown_Unknown_Unknown_paper.pdf`; diagnosed via live-container logs and shipped two more fixes; user confirmed working.

### What was actually wrong (three layered causes)
- **v0.4.6** (prior entry) fixed metadata-rich papers (Langevin) via abstract cap + `MAX_TEXT_LENGTH` 3000->8000 + PDF-metadata backfill. Langevin now -> `Langevin-Stephanie_2022_International-Journal-of-Environmental-R_antisocial-biological-aging-crime.pdf` (confirmed via the downloaded file's Zone.Identifier).
- **v0.4.7** (`a349e17`): strict `PaperMetadata` hard-required a 4-digit `year`. The model returned author+title+keywords for the DRAGON-AI preprint but with `year=""`/`journal=""` (neither is on page 1), so `validate_year("")` raised and the ENTIRE extraction was discarded -> retries -> lenient -> all-Unknown. Fix: `PaperMetadata` now coerces blank year/journal/title->"Unknown" and makes keywords/suggested_filename optional; `author` is the only required field. Verified by loading the real `PaperMetadata` (deps stubbed) against the exact logged responses.
- **v0.4.8** (`ce24848`): live logs proved gpt-oss-20b is non-deterministic — for the user's upload it returned an all-blank `{"author":"",...}` on all 3 attempts, while an in-container replay seconds later returned the correct author+keywords. A blank author legitimately fails validation. Fix: new `PDFProcessor.extract_author_from_text()` parses the first author from the page-1 author line (Title -> "First Last1, ..." layout) as a deterministic net, wired into the `upload.py` backfill (PDF-metadata author -> page-text author); "paper" keyword sentinel normalized to Unknown.

### Files/modules touched
- `backend/services/llm_service.py` — `PaperMetadata` field/validator tolerance (year/journal/title/keywords/suggested_filename); `MAX_TEXT_LENGTH` default 8000 (v0.4.6).
- `backend/services/pdf_processor.py` — `_build_metadata_header` subject cap (v0.4.6); new `extract_pdf_metadata_fields()` (v0.4.6) + `extract_author_from_text()` (v0.4.8).
- `backend/routes/upload.py` — metadata backfill (PDF-meta + page-text author; keyword sentinel normalize).
- `backend/config.py` — `MAX_TEXT_LENGTH` (v0.4.6). `backend/version.py`, `CHANGELOG.md` — 0.4.6/0.4.7/0.4.8.

### Key decisions
- Author is the single required field; everything else coerces to Unknown/empty and the filename is rebuilt by `build_filename`. Keywords are semantic -> can only come from the LLM (no regex parse), so blank-LLM runs still lose keywords (author is guaranteed). Documented as a low-priority open item.
- Diagnosed entirely from live-container logs + in-container replay (the only ground truth) after the local repro kept failing on `ModuleNotFoundError: backend` until `-e PYTHONPATH=/app` was set.

### Problems / notes
- Wasted a couple of round-trips: conflated the local dev tree with the remote deploy server (scripts must be written to the server via `ssh Hurlab` and run by the user — sudo is interactive), and the in-container python repro needed `PYTHONPATH=/app`.
- A bare `LLMService()` outside app context defaults provider->openai and demands `OPENAI_API_KEY` — a red herring, NOT a production issue.
- `llm_probe.sh` (in `/home/juhur/tmp/`, unrun) measures the LLM blank-rate vs max_tokens/temperature if keyword reliability needs hardening.

### Verification
- Local: real `PaperMetadata` accepts the logged DRAGON response -> `Toro-Sabrina_Unknown_Unknown_ontology-generation-LLM-retrieval.pdf`; author-less still rejects. `extract_author_from_text` -> Toro/Sabrina on DRAGON, `{}` on Langevin citation. Worst-case all-blank LLM -> `Toro-Sabrina_Unknown_Unknown_Unknown.pdf`.
- Live: deploy dir + container at `ce24848` / 0.4.8, `MAX_TEXT_LENGTH=8000`, health healthy. In-container replay produced the correct filename. User re-uploaded both PDFs -> "works well now".

### Commits (pushed to origin/main)
- `0c17d13` v0.4.6 — prompt-budget + abstract cap + PDF-metadata backfill
- `339cc63` chore — gitignore tmp/
- `900b398` docs — record v0.4.6
- `a349e17` v0.4.7 — schema tolerates missing year/journal
- `ce24848` v0.4.8 — deterministic author-from-text fallback


## Session 2026-06-28 17:2x CDT (v0.4.6 — extraction fix for metadata-rich PDFs)

- **Coding CLI used:** Claude Code CLI (Claude Opus 4.8)
- **Phase(s):** User-reported bug → diagnosis from real PDFs → fix → deploy → live verify

### Symptom
User uploaded two "easy" PDFs; the renamer returned `Toro-Sabrina_Unknown_Unknown_ontology-...` (author only) and `Unknown_Unknown_Unknown_paper.pdf` (everything blank).

### Root cause (diagnosed from the actual PDFs + confirmed live config)
- Extracted PDF text is hard-truncated to `MAX_TEXT_LENGTH` = **3000 chars** before the LLM call (confirmed live: provider `openai-compatible`, model `openai/gpt-oss-20b`, url `http://100.67.76.96:1234`).
- `PDFProcessor._build_metadata_header` injects the PDF `subject` property *ahead* of page text. For LaTeX/MDPI PDFs `subject` holds the **entire abstract** (~2500 chars). For the Langevin paper this pushed the title-page `Citation:` line (`Int. J. Environ. Res. Public Health 2022, 19, 14402`) and the keywords/year **past the 3000-char cut** — the LLM never saw journal/year and returned a blank extraction → lenient fallback produced `Unknown_..._paper` (keyword default "paper", `llm_service.py:1064`).
- DRAGON-AI is a 31-page Google-Docs preprint: journal/year are genuinely absent from page 1 and from PDF metadata, so `Unknown` there is honest. Author worked (on page 1).
- Confirmed measured char offsets locally with pymupdf (the app extracts effectively page 1 only — breaks at `len(page_text)>500`, `pdf_processor.py:298`).
- NOTE: the per-job container logs were unrecoverable — the container had been recreated ~3 min after the upload (16:23 job vs 16:26 gunicorn restart), wiping stdout + in-memory job state (the known single-worker limitation).

### Fix (commit 0c17d13)
- `_build_metadata_header`: cap injected `subject`/abstract at **300 chars**.
- `MAX_TEXT_LENGTH` **3000 → 8000** (`config.py` new key + `llm_service.py` default).
- New `PDFProcessor.extract_pdf_metadata_fields()`: parses author (first-author last/first), title, keywords (`;`/`,`-split), and a last-resort creation-year from PDF properties.
- `upload.py` `process_one_file`: backfills blank/`Unknown`/`paper` author/title/keywords/year from those PDF fields (LLM result still wins when present).

### Verification
- Local (real PDFs, standalone-loaded real module): after fix, Langevin extracted text 8414→5888 chars (header shrank ~2900→~700); `Keywords`/`Publication year`/`2022`/`Citation` now all within the 8000 budget; `extract_pdf_metadata_fields` → `author=Langevin, author_first=Stephanie, keywords=…, year=2022, title=…`. Citation block now visible to LLM contains journal `Int. J. Environ. Res. Public Health` + year 2022.
- `py_compile` OK on all 4 changed modules.
- Deployed (commit 339cc63 after gitignoring `tmp/`): container `version: 0.4.6`, `MAX_TEXT_LENGTH=8000`, health healthy. Image `sha256:02d815ca…`.

### Commits
- `0c17d13` fix: recover author/year/journal on metadata-rich PDFs (v0.4.6)
- `339cc63` chore: gitignore `tmp/` (local test PDFs + scratch scripts)

### Next (user-driven)
- Re-upload the two PDFs on v0.4.6: Langevin → `Langevin-Stephanie_2022_<journal>_…`; DRAGON-AI → author+keywords, `Unknown` year/journal (honest).
- Deferred (unchanged): hot-path tests; v0.5.0 (Redis jobs, async LLM I/O, LLMService split); GHCR re-login. Consider extracting >1 page or reading XMP for preprints (would help DRAGON-AI-style files) — optional future enhancement.

## Session 2026-06-28 16:27 CDT (v0.4.4 placeholder consistency + v0.4.5 limits/folders)

- **Coding CLI used:** Claude Code CLI (Claude Opus 4.8)
- **Phase(s):** Two user-driven fixes/features shipped + deployed + verified

### v0.4.4 — filename placeholder consistency (commit 134069c)
- User reported `Tu-Tao_2024_diagnosticAI-LLM-selfplay` (3 sections) — a missing journal was being DROPPED, misaligning the `_`-separated slots. This reversed the v0.4.2 "omit empty components" decision.
- `LLMService.build_filename`: every field now falls back to the literal `Unknown` placeholder instead of being omitted → `Tu-Tao_2024_Unknown_diagnosticAI-LLM-selfplay`. Applies to all preset + Custom formats.
- Deployed; container-verified (no-journal → Unknown slot kept; full case unchanged).

### v0.4.5 — limits + multi-folder + structure-preserving output (commit 187922a)
- **Per-session limit 30 → 100** for approved users (`User.get_max_files`); admin per-user overrides still apply.
- **Whole-request ceiling 500MB → 5000MB** (`MAX_CONTENT_LENGTH`, sized for 100×50MB) + nginx `client_max_body_size 5000M` (+ `proxy_read_timeout 300→600`).
- **Decoupled per-file cap:** new `MAX_FILE_SIZE` (50MB) drives `FileService.validate_file` — previously the per-file cap reused `MAX_CONTENT_LENGTH`, so bumping the request ceiling would have silently allowed 5GB single files. Renamed `FileService.max_content_length` → `max_file_size`.
- **Multi-folder upload:** picker now accumulates (add folders one-by-one); drag-dropping several folders recurses via FileSystem entry API (`webkitGetAsEntry` + `_collectEntry`/`_readAllEntries`). Subfolders were always included by the webkitdirectory picker.
- **Folder output preserves directory tree:** ZIP arcname = original subfolder path + renamed file, gated by the `preserve_structure` flag the UI already sends. Threaded `preserve_structure` through `_process_files_background`.
- Frontend size caps: 50MB/file hard, 1GB warn, 5GB total hard.

### Files/modules touched
- `backend/config.py` (MAX_CONTENT_LENGTH 5000MB + new MAX_FILE_SIZE)
- `backend/models/user.py` (get_max_files 30→100)
- `backend/services/file_service.py` (max_file_size rename + per-file cap)
- `backend/services/llm_service.py` (build_filename placeholders)
- `backend/routes/upload.py` (preserve_structure flag + ZIP arcname structure)
- `frontend/static/js/main.js` (size caps, addFolderItems accumulate, recursive folder drag-drop)
- `frontend/templates/index.html` (folder zone text), `docs/deployment.md`, `CHANGELOG.md`, `backend/version.py`

### Key decisions
- Reversed v0.4.2 omit-empty → placeholder-keep, per user's consistency requirement.
- Decoupled per-file vs whole-request size — a latent bug if left coupled when raising the ceiling.
- Multi-folder: picker accumulates (browser dialogs only allow one dir per pick); drag-drop recurses via entry API. Output mirrors input tree per user's choice.

### Problems / notes
- Deploy quality gate (moai pre-tool pytest) is intermittent and pytest can't collect locally (no flask deps in dev tree — they live in the Docker image). v0.4.4/v0.4.5 commits went through without bypass this time.
- Caveat carried forward: 100 files / up to 5GB on the single gunicorn worker + 30-min temp sweeper could clip jobs running >30 min. Proper fix = v0.5.0 (Redis jobs + async I/O).

### Verification (container + nginx, 2026-06-28)
- v0.4.4: `build_filename` no-journal → `Tu-Tao_2024_Unknown_diagnosticAI-LLM-selfplay.pdf`; full → `Hribar-Jason_2023_Ophthalmology_OMOP-CDM.pdf`.
- v0.4.5: version 0.4.5; `MAX_CONTENT_LENGTH=5000MB MAX_FILE_SIZE=50MB`; approved-user limit 100; nginx pdf-renamer `client_max_body_size 5000M` + `proxy_read_timeout 600` (admin :8443 50M, /coai 300M untouched); `nginx -t` OK + reload; health healthy.

### Commits (pushed to origin/main)
- `134069c` v0.4.4 — keep Unknown placeholder for missing filename fields
- `187922a` v0.4.5 — 100-file/5GB limits, decoupled per-file cap, multi-folder + structure-preserving output

### Next (user-driven)
- Real-world: multi-folder upload (accumulate + drag several) with subfolders → confirm ZIP mirrors tree; batch >30 files.
- Deferred (unchanged): hot-path tests; v0.5.0 (Redis jobs, async LLM I/O, LLMService split); GHCR re-login on server.

## Session 2026-06-25 13:45 CDT (Upload-size + processing-failure fixes + LastName-FirstName, v0.4.1 → v0.4.3)

- **Coding CLI used:** Claude Code CLI (Claude Opus 4.8)
- **Phase(s):** Sync reconciliation, three production fixes shipped, docs

### Sync reconciliation
- GitHub `origin/main`, deployment (`/home/hurlab/PROJECTS/research-pdf-renamer`), and local home WSL2 were aligned. Home WSL2 was 1 commit behind (`e4a96e2` vs `ff621b6`); fast-forwarded. Handoff's claimed tip `7fad242` was stale — actual was `ff621b6` ("add Reset PW").
- Deploy dir confirmed: `/home/hurlab/PROJECTS/research-pdf-renamer` (owned by `hurlab`, has gitignored `docker-compose.override.yml` pinning GHCR `:latest`). `/data/juhurSync/.../10_apps/...` is only the rsync mirror. `juhur` is NOT in the `docker` group and sudo needs an interactive password → all privileged ops run via scripts in `/home/juhur/tmp/` that the user executes.

### Fixes shipped
1. **Upload >50 MB rejected (nginx).** Active nginx `location /pdf-renamer/` had `client_max_body_size 50M` while the app allows 500 MB; nginx 413'd a 71.2 MB batch before Flask saw it. Raised to `500M`, `nginx -t` + reload. Server-side only (not in image); also fixed the `50M` example in `docs/deployment.md`.
2. **"Lost connection to server" on multi-file jobs (v0.4.1).** Progress-poll endpoint `/api/upload/progress/<job_id>` was still subject to the global `50/hour` default (flask-limiter stacks per-route limits over defaults), so a 20-file job polling every 5 s hit HTTP 429 → 6 consecutive failures → false "Lost connection". Exempted it from defaults (keeps its `600/min`). Verified via container logs (RestartCount=0, OOMKilled=false — NOT a crash, NOT the DGX).
3. **Empty journal failed validation (v0.4.1).** `PaperMetadata.journal` required ≥1 char; papers with no journal burned 3 retries → lenient fallback. Now coerced to "Unknown" on first parse.
4. **Admin rate-limit exemption (v0.4.2).** `is_admin` users exempt from default limits via new `request_is_admin()` (decodes JWT like `auth_required`, runs in the limiter before-request hook).
5. **Sparse filenames like `Hribar_2023.pdf` (v0.4.2).** App used the LLM's `suggested_filename` verbatim; LLM sometimes emitted a sparse name despite extracting journal/keywords into fields. New `LLMService.build_filename()` rebuilds from validated fields (honors all preset + Custom formats, omits empty/Unknown components); `upload.py` swaps it in when the LLM name dropped sections. Verified on container.

### Commits (pushed to origin/main)
- `dcbb19e` v0.4.1 — progress rate-limit exemption + empty-journal coercion
- `0bee2e8` v0.4.2 — admin exemption + build_filename
- `1a2eb4e` docs — record v0.4.1/v0.4.2 + nginx 500M
- `678623a` v0.4.3 — LastName-FirstName author default + always-build-from-fields

### Verification
- v0.4.1 and v0.4.2 both built (`--no-cache`), `--force-recreate`d, health = healthy. `build_filename` confirmed on container: `Hribar_2023_Ophthalmology_ophthalmology-data-standards-OMOP-CDM.pdf`.
- GHCR push fails (server `docker login` to GHCR expired) — non-fatal; production runs from locally-built `:latest`.

### v0.4.3 — shipped & verified (live)
- New DEFAULT author format `Lastname-Firstname` (e.g. `Hribar-Jason`). LLM now extracts primary author first name (`author_first`, optional). `build_filename` renders `Lastname-Firstname` (fallback last-name-only). `upload.py` ALWAYS builds the filename from validated fields now (LLM `suggested_filename` only a fallback) — subsumes the v0.4.2 sparse fix. Profile labels + homepage hint updated. Container verified: `Hribar-Jason_2023_Ophthalmology_ophthalmology-data-standards-OMOP-CDM.pdf`.

### Next
- User-driven end-to-end retest: upload real papers on v0.4.3, confirm `LastName-FirstName` filenames + the 20-file batch no longer disconnects.
- Deferred (unchanged): test coverage for `_parse_response`/`_process_files_background`; v0.5.0 architecture (Redis jobs, async LLM I/O, LLMService split); re-login `docker` to GHCR so versioned images archive again.

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
