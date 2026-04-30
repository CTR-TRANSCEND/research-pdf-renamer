from flask import Blueprint, current_app, request, jsonify, send_file
from flask_login import current_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from backend.models import Usage
from backend.database import db
from backend.services import PDFProcessor, LLMService, FileService
from backend.utils.decorators import record_usage
from backend.utils.auth import auth_required
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename
import copy
import hashlib
import os
import logging
import time
import secrets
import threading
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()

upload = Blueprint("upload", __name__)
logger = logging.getLogger(__name__)

# PERF-001: Rate limiter for upload routes (lazy init — wired via init_app in create_app)
limiter = Limiter(key_func=get_remote_address)

MAX_WORKERS = 2  # Keep low to avoid overwhelming LLM server with concurrent requests

# Initialize services (lazy initialization to avoid config issues)
pdf_processor = None
llm_service = None
file_service = None


def reset_services():
    """Reset cached services so they reinitialize with fresh config on next use.
    Called when admin saves LLM settings."""
    global llm_service, file_service, pdf_processor
    llm_service = None
    file_service = None
    pdf_processor = None

# In-memory progress tracking for background jobs
# Format: { job_id: { status, completed, total, files, errors, download_url, elapsed_seconds, start_time, created_at } }
_job_progress = {}
_job_progress_lock = threading.Lock()

# Auto-clean interval tracking
_last_cleanup_time = time.time()
_CLEANUP_INTERVAL = 300  # Check every 5 minutes
_JOB_TTL = 1800  # 30 minutes


def _truncate_keywords(filename, max_keywords=5):
    """Enforce max keyword count in filename: Author_Year_Journal_kw1-kw2-kw3-kw4-kw5.pdf"""
    if not filename.endswith(".pdf"):
        return filename
    name = filename[:-4]  # strip .pdf
    parts = name.split("_")
    # Expected: Author_Year_Journal_keywords (4+ parts)
    # Keywords are the last part(s) joined by underscore after Author_Year_Journal
    if len(parts) < 4:
        return filename
    # First 3 parts: Author, Year, Journal. Rest is keywords.
    prefix = "_".join(parts[:3])
    keywords_part = "_".join(parts[3:])
    # Keywords are hyphen-separated words
    keywords = keywords_part.replace("_", "-").split("-")
    if len(keywords) <= max_keywords:
        return filename
    # Truncate to max_keywords
    truncated = "-".join(keywords[:max_keywords])
    return f"{prefix}_{truncated}.pdf"


def _cleanup_old_jobs():
    """Remove job entries older than 30 minutes."""
    global _last_cleanup_time
    now = time.time()
    if now - _last_cleanup_time < _CLEANUP_INTERVAL:
        return
    _last_cleanup_time = now
    expired = []
    with _job_progress_lock:
        for job_id, job in _job_progress.items():
            if now - job.get("created_at", now) > _JOB_TTL:
                expired.append(job_id)
        for job_id in expired:
            del _job_progress[job_id]
    if expired:
        logger.info(f"Cleaned up {len(expired)} expired job(s)")


def get_services():
    """Initialize services when needed"""
    global llm_service, file_service, pdf_processor
    if llm_service is None:
        from flask import current_app

        config = current_app.config if current_app else {}
        llm_service = LLMService(config)
        file_service = FileService(config)
        pdf_processor = PDFProcessor()
    return llm_service, file_service, pdf_processor


@upload.route("/upload", methods=["POST"])
@limiter.limit(
    "20 per hour",
    exempt_when=lambda: current_user.is_authenticated and current_user.is_admin,
)
def upload_files():
    """Upload and process PDF files - saves files, starts background processing, returns job_id."""
    try:
        # Check if files were uploaded
        if "files" not in request.files:
            return jsonify({"error": "No files provided"}), 400

        files = request.files.getlist("files")
        if not files or files[0].filename == "":
            return jsonify({"error": "No files selected"}), 400

        # Get services
        try:
            llm_svc, file_svc, pdf_proc = get_services()
        except Exception as e:
            logger.error(f"Service initialization failed: {type(e).__name__}: {str(e)}")
            return jsonify({"error": f"Service initialization failed: {str(e)}"}), 500

        # Get file paths if folder upload
        paths = request.form.getlist("paths") if "paths" in request.form else None

        # Check file count limits
        if current_user and current_user.is_authenticated:
            max_files = current_user.get_max_files()
        else:
            max_files = 5

        if len(files) > max_files:
            return jsonify(
                {"error": f"Too many files. Maximum allowed: {max_files}"}
            ), 400

        # Get user info once before threading to avoid context issues
        user_id = (
            current_user.id if current_user and current_user.is_authenticated else None
        )
        user_preferences = None
        if current_user and current_user.is_authenticated:
            user_preferences = {
                "filename_format": current_user.filename_format,
                "custom_filename_format": current_user.custom_filename_format,
            }

        # Generate unique session ID for this batch
        session_id = secrets.token_hex(8)
        job_id = secrets.token_hex(16)

        # Capture request-context values before leaving the request handler.
        # These are needed by the background thread which has no request context.
        script_root = request.script_root
        client_ip = request.remote_addr
        client_ua = request.headers.get("User-Agent", "")

        # Save files to temp directory and collect file info for background processing
        saved_files = []
        save_errors = []
        for i, file in enumerate(files):
            path = paths[i] if paths and i < len(paths) else file.filename
            try:
                # Validate file size, magic bytes, and extension BEFORE writing to disk
                is_valid, validation_msg = file_svc.validate_file(file)
                if not is_valid:
                    save_errors.append(f"{path}: {validation_msg}")
                    continue

                filepath, unique_filename = file_svc.save_uploaded_file(file)
                saved_files.append({
                    "index": i,
                    "path": path,
                    "original_filename": file.filename,
                    "filepath": filepath,
                    "unique_filename": unique_filename,
                })
            except Exception as e:
                save_errors.append(f"{path}: Failed to save - {str(e)}")

        total_files = len(saved_files)
        if total_files == 0 and save_errors:
            return jsonify({"error": "No files were saved successfully", "details": save_errors}), 400

        # Initialize job progress
        # IMPORTANT: Reassign sf["index"] to the position in file_statuses (0-based)
        # so that background-thread status updates target the correct slot.
        # sf["index"] was previously the original upload enumeration index, which
        # diverges from the file_statuses position whenever save errors occur
        # (e.g. file 0 saves OK, file 1 fails → saved_files has index 0 and 2,
        # but file_statuses slots are 0 and 1 — off-by-one for the third file).
        file_statuses = []
        for status_idx, sf in enumerate(saved_files):
            sf["index"] = status_idx  # rebind to actual file_statuses slot
            file_statuses.append({
                "name": sf["path"],
                "status": "pending",
                "new_name": None,
                "error": None,
            })
        # Also add save errors as already-failed
        for err in save_errors:
            name = err.split(":")[0].strip() if ":" in err else err
            file_statuses.append({
                "name": name,
                "status": "error",
                "new_name": None,
                "error": err,
            })

        with _job_progress_lock:
            _job_progress[job_id] = {
                "status": "processing",
                "completed": 0,
                "total": total_files + len(save_errors),
                "files": file_statuses,
                "errors": list(save_errors),
                "download_url": None,
                "elapsed_seconds": 0,
                "start_time": time.time(),
                "created_at": time.time(),
            }

        # Get Flask app for context in background thread
        from flask import current_app
        app = current_app._get_current_object()

        # Start background processing thread
        thread = threading.Thread(
            target=_process_files_background,
            args=(app, job_id, saved_files, llm_svc, file_svc, pdf_proc,
                  user_preferences, session_id, script_root, user_id,
                  client_ip, client_ua),
            daemon=True,
        )
        thread.start()

        # Cleanup old jobs periodically
        _cleanup_old_jobs()

        return jsonify({"job_id": job_id, "total": total_files + len(save_errors)})

    except RequestEntityTooLarge:
        limit_mb = current_app.config.get("MAX_CONTENT_LENGTH", 500 * 1024 * 1024) // (1024 * 1024)
        received_mb = round((request.content_length or 0) / (1024 * 1024), 1)
        return jsonify({
            "error": f"Upload too large ({received_mb} MB). Maximum allowed per submission is {limit_mb} MB.",
            "limit_mb": limit_mb,
            "received_mb": received_mb,
            "details": [
                f"Your upload was {received_mb} MB, which exceeds the {limit_mb} MB limit.",
                "Try splitting your files into smaller batches.",
                f"Each batch must be under {limit_mb} MB total."
            ]
        }), 413
    except Exception as e:
        logger.error(f"Upload processing failed: {type(e).__name__}: {str(e)}", exc_info=True)
        return jsonify(
            {"error": "Server error during file processing"}
        ), 500


def _process_files_background(app, job_id, saved_files, llm_svc, file_svc, pdf_proc,
                               user_preferences, session_id, script_root, user_id,
                               client_ip, client_ua):
    """Background thread that processes files and updates progress dict."""
    processed_files = []
    errors = []

    def _update_file_stage(file_info, stage):
        """Update the processing stage for a file in the progress dict."""
        with _job_progress_lock:
            job = _job_progress.get(job_id)
            if job:
                file_index = file_info["index"]
                job["files"][file_index]["status"] = stage

    def process_single_file(file_info):
        """Process a single file. Returns (status, file_result, error_msg)."""
        path = file_info["path"]
        filepath = file_info["filepath"]
        original_filename = file_info["original_filename"]

        try:
            # Validate PDF
            if not pdf_proc.validate_pdf(filepath):
                file_svc.cleanup_file(filepath)
                return ("error", None, f"{path}: Invalid or corrupted PDF file")

            # Extract text from PDF
            _update_file_stage(file_info, "extracting")
            text, pages_processed = pdf_proc.extract_text_from_pdf(filepath)
            if not text:
                file_svc.cleanup_file(filepath)
                return ("error", None, f"{path}: Could not extract text from PDF")

            # Get metadata from LLM (auto-retry once on INVALID_RESPONSE)
            _update_file_stage(file_info, "analyzing")
            metadata, extraction_error = llm_svc.extract_paper_metadata(
                text, user_preferences
            )

            if not metadata and extraction_error and extraction_error.value == "invalid_response":
                # Retry once — LLM responses can be non-deterministic
                _update_file_stage(file_info, "retrying")
                logger.info(f"Retrying LLM extraction for {path} (first attempt returned invalid response)")
                metadata, extraction_error = llm_svc.extract_paper_metadata(
                    text, user_preferences
                )

            if not metadata:
                file_svc.cleanup_file(filepath)
                if extraction_error:
                    error_message = llm_svc.get_error_message(extraction_error)
                    return ("error", None, f"{path}: {error_message}")
                else:
                    return ("error", None, f"{path}: Could not extract metadata")

            # Post-processing and renaming
            _update_file_stage(file_info, "renaming")

            # Validate suggested filename
            suggested_name = metadata.get("suggested_filename", "")
            if not llm_svc.validate_filename(suggested_name):
                safe_name = secure_filename(original_filename)
                name_part = os.path.splitext(safe_name)[0]
                suggested_name = f"{name_part}_renamed.pdf"

            # Enforce max 5 keywords: Author_Year_Journal_kw1-kw2-kw3-kw4-kw5.pdf
            # Split by underscore, find the keywords portion (after Author_Year_Journal),
            # and truncate if more than 5 hyphen-separated words
            suggested_name = _truncate_keywords(suggested_name, max_keywords=5)

            # Rename file with session isolation
            download_path = file_svc.move_to_downloads(
                filepath, suggested_name, session_id=session_id
            )

            file_result = {
                "original_name": path,
                "original_filename": original_filename,
                "new_name": suggested_name,
                "download_path": download_path,
                "metadata": metadata,
                "pages_processed": pages_processed,
            }
            return ("success", file_result, None)

        except Exception as e:
            try:
                file_svc.cleanup_file(filepath)
            except Exception:
                pass
            return ("error", None, f"{path}: Processing error - {str(e)}")

    # Part A: Detect true duplicates (same content, different filenames)
    duplicate_filepaths = set()
    duplicate_results = []

    # Group by file size first (cheap filter before hashing)
    size_groups = {}
    for sf in saved_files:
        try:
            sz = os.path.getsize(sf["filepath"])
        except OSError:
            sz = -1
        size_groups.setdefault(sz, []).append(sf)

    for sz, group in size_groups.items():
        if len(group) < 2:
            continue
        # Hash the extracted text for each file in this size group
        hash_groups = {}
        for sf in group:
            try:
                text, _ = pdf_proc.extract_text_from_pdf(sf["filepath"])
                h = _text_hash(text) if text else None
            except Exception:
                h = None
            if h is None:
                continue
            hash_groups.setdefault(h, []).append(sf)

        for h, hgroup in hash_groups.items():
            if len(hgroup) < 2:
                continue
            # First file is canonical; the rest are duplicates
            canonical = hgroup[0]
            for dup in hgroup[1:]:
                duplicate_filepaths.add(dup["filepath"])
                # Clean up temp file
                try:
                    file_svc.cleanup_file(dup["filepath"])
                except Exception:
                    pass
                # Update job progress entry for this duplicate
                with _job_progress_lock:
                    job = _job_progress.get(job_id)
                    if job:
                        job["files"][dup["index"]] = {
                            "status": "duplicate",
                            "duplicate_of": canonical["original_filename"],
                            "name": dup["path"],
                        }
                # Collect result for final output
                duplicate_results.append({
                    "original_name": dup["path"],
                    "original_filename": dup["original_filename"],
                    "status": "duplicate",
                    "duplicate_of": canonical["original_filename"],
                    "note": f"Duplicate of '{canonical['original_filename']}' — processed once",
                })

    # Only submit non-duplicate files to the executor
    files_to_process = [sf for sf in saved_files if sf["filepath"] not in duplicate_filepaths]

    # Process files using ThreadPoolExecutor within this background thread
    # Stagger submissions by 0.5s to avoid overwhelming the LLM server
    with ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="bg_processor") as executor:
        future_to_info = {}
        for i, sf in enumerate(files_to_process):
            future_to_info[executor.submit(process_single_file, sf)] = sf
            if i < len(files_to_process) - 1:
                time.sleep(1.0)

        for future in as_completed(future_to_info):
            file_info = future_to_info[future]
            try:
                status, file_result, error_msg = future.result()
            except Exception as e:
                status = "error"
                file_result = None
                error_msg = f"{file_info['path']}: Processing error - {str(e)}"

            # Update progress
            with _job_progress_lock:
                job = _job_progress.get(job_id)
                if job is None:
                    return
                job["completed"] += 1
                job["elapsed_seconds"] = round(time.time() - job["start_time"], 1)

                # Find and update the file entry
                file_index = file_info["index"]
                f = job["files"][file_index]
                if status == "success":
                    f["status"] = "complete"
                    f["new_name"] = file_result["new_name"]
                else:
                    f["status"] = "error"
                    f["error"] = error_msg

                if status == "success":
                    processed_files.append(file_result)
                else:
                    errors.append(error_msg)
                    job["errors"].append(error_msg)

    # Part B: Resolve output name collisions
    seen_names = {}
    for result in processed_files:
        name = result["new_name"]
        if name not in seen_names:
            seen_names[name] = result
        else:
            # Collision: append original stem to disambiguate
            stem = os.path.splitext(name)[0]
            original_stem = os.path.splitext(result["original_filename"])[0]
            separator = "" if stem.endswith("__") else "__"
            new_name = f"{stem}{separator}{original_stem}.pdf"
            # Rename the actual file on disk
            old_full_path = os.path.join(
                file_svc.upload_folder, "downloads", result["download_path"]
            )
            new_full_path = os.path.join(
                os.path.dirname(old_full_path), new_name
            )
            try:
                os.rename(old_full_path, new_full_path)
                # Update download_path to reflect the new filename
                result["download_path"] = os.path.join(
                    os.path.dirname(result["download_path"]), new_name
                )
            except Exception:
                pass
            result["new_name"] = new_name
            result["renamed_collision"] = True
            result["rename_note"] = (
                f"Renamed to avoid conflict with '{seen_names[name]['original_filename']}'"
            )
            # Register the new name so further collisions chain correctly
            seen_names[new_name] = result
            # Update the corresponding job["files"] entry
            with _job_progress_lock:
                job = _job_progress.get(job_id)
                if job:
                    for f in job["files"]:
                        if f.get("name") == result["original_name"]:
                            f["new_name"] = new_name
                            f["renamed_collision"] = True
                            f["rename_note"] = result["rename_note"]
                            break

    # All files processed - finalize
    with app.app_context():
        # Record upload metrics
        try:
            from backend.utils.metrics_collector import MetricsCollector
            _metrics = MetricsCollector.get_instance()
            for file_result in processed_files:
                _size = 0
                try:
                    _download_filepath = os.path.join(
                        file_svc.upload_folder, "downloads", file_result["download_path"]
                    )
                    if os.path.exists(_download_filepath):
                        _size = os.path.getsize(_download_filepath)
                except Exception:
                    pass
                _metrics.record_upload(size_bytes=_size, success=True)
            for _ in errors:
                _metrics.record_upload(size_bytes=0, success=False)
        except Exception:
            pass

        # Record usage statistics (pass ip/ua captured from the original request
        # because there is no Flask request context in this background thread).
        if processed_files:
            record_usage(len(processed_files), user_id=user_id,
                         ip_address=client_ip, user_agent=client_ua)

        # Create download URL
        download_url = None
        if len(processed_files) == 1:
            single_file = processed_files[0]
            download_url = f"{script_root}/api/download/{single_file['download_path']}"
            filepath = os.path.join(
                file_svc.upload_folder, "downloads", single_file["download_path"]
            )
            file_svc.schedule_cleanup(filepath)
        elif len(processed_files) > 1:
            zip_files = []
            for pf in processed_files:
                filepath = os.path.join(
                    file_svc.upload_folder, "downloads", pf["download_path"]
                )
                zip_files.append((filepath, pf["new_name"]))

            zip_name = f"processed_files_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            zip_full_path = file_svc.create_zip(
                zip_files, zip_name=zip_name, session_id=session_id
            )
            zip_rel_path = os.path.relpath(
                zip_full_path, os.path.join(file_svc.upload_folder, "downloads")
            )
            download_url = f"{script_root}/api/download/{zip_rel_path}"

            for filepath, _ in zip_files:
                file_svc.cleanup_file(filepath)
            file_svc.schedule_cleanup(zip_full_path)

    # Mark job as complete
    with _job_progress_lock:
        job = _job_progress.get(job_id)
        if job:
            job["status"] = "complete"
            job["download_url"] = download_url
            job["elapsed_seconds"] = round(time.time() - job["start_time"], 1)
            # Store processed file details for the final response
            job["processed_files"] = processed_files + duplicate_results


@upload.route("/upload/progress/<job_id>", methods=["GET"])
@limiter.limit("600 per minute")
def get_progress(job_id):
    """Get the processing progress for a job."""
    _cleanup_old_jobs()

    with _job_progress_lock:
        job = _job_progress.get(job_id)
        if job is None:
            return jsonify({"error": "Job not found"}), 404

        # Snapshot all values under the lock so the background thread
        # cannot mutate them while we build the response.
        job_snapshot = copy.deepcopy(job)

    # Build response (don't expose internal fields like start_time)
    response = {
        "status": job_snapshot["status"],
        "completed": job_snapshot["completed"],
        "total": job_snapshot["total"],
        "files": job_snapshot["files"],
        "errors": job_snapshot["errors"],
        "download_url": job_snapshot["download_url"],
        "elapsed_seconds": round(time.time() - job_snapshot["start_time"], 1) if job_snapshot["status"] == "processing" else job_snapshot["elapsed_seconds"],
    }

    # Include processed file details when complete
    if job_snapshot["status"] == "complete" and "processed_files" in job_snapshot:
        response["processed_files"] = job_snapshot["processed_files"]

    return jsonify(response)


@upload.route("/download/<path:filepath>")
@limiter.limit("60 per minute")
def download_file(filepath):
    """
    Download processed file.

    No auth required: files are protected by unguessable 16-char hex session IDs,
    auto-cleaned after 30 minutes, and the server is network-restricted.
    """
    try:
        path_parts = filepath.split("/")
        safe_parts = [secure_filename(part) for part in path_parts if part]
        safe_filepath = "/".join(safe_parts)

        if not safe_filepath:
            return jsonify({"error": "Invalid filename"}), 400

        allowed_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'uploads', 'downloads'))
        file_path = os.path.abspath(os.path.join(allowed_dir, safe_filepath))

        if not file_path.startswith(allowed_dir + os.sep) and file_path != allowed_dir:
            logger.warning(f"Path traversal attempt blocked: {safe_filepath}")
            return jsonify({"error": "Invalid filename"}), 400

        if not os.path.exists(file_path):
            return jsonify({"error": "File not found"}), 404

        if safe_filepath.lower().endswith(".zip"):
            mimetype = "application/zip"
        else:
            mimetype = "application/pdf"

        display_filename = os.path.basename(safe_filepath)

        return send_file(
            file_path,
            as_attachment=True,
            download_name=display_filename,
            mimetype=mimetype,
        )

    except Exception as e:
        logger.error(f"Download error: {e}")
        return jsonify({"error": "Download failed. Please try again."}), 500


@upload.route("/usage-stats")
@auth_required
def usage_stats():
    """Get usage statistics for current user."""
    if not current_user.is_authenticated:
        return jsonify({"error": "Authentication required"}), 401

    if current_user.is_approved:
        year_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=365)
        time_filter = year_ago
    else:
        day_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
        time_filter = day_ago

    usage_stats = (
        db.session.query(
            db.func.count(Usage.id).label("total_submissions"),
            db.func.sum(Usage.files_processed).label("total_files"),
        )
        .filter(Usage.user_id == current_user.id, Usage.timestamp > time_filter)
        .first()
    )

    total_submissions = usage_stats.total_submissions or 0
    total_files = usage_stats.total_files or 0

    recent = (
        Usage.query.filter(Usage.user_id == current_user.id)
        .order_by(Usage.timestamp.desc())
        .limit(10)
        .all()
    )

    recent_data = [
        {
            "timestamp": u.timestamp.isoformat(),
            "files_processed": u.files_processed,
            "ip_address": u.ip_address,
        }
        for u in recent
    ]

    return jsonify(
        {
            "total_submissions": total_submissions,
            "total_files_processed": total_files,
            "recent_submissions": recent_data,
            "max_files_per_submission": current_user.get_max_files(),
            "is_approved": current_user.is_approved,
        }
    )
