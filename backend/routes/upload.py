from flask import Blueprint, request, jsonify, send_file
from flask_login import current_user
from backend.models import Usage
from backend.database import db
from backend.services import PDFProcessor, LLMService, FileService
from backend.utils.decorators import record_usage
from backend.utils.auth import auth_required
from werkzeug.utils import secure_filename
import os
import logging
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

upload = Blueprint("upload", __name__)
logger = logging.getLogger(__name__)

# PERF-002: Module-level shared thread pool for file processing
# Bounded by CPU count to prevent resource exhaustion
MAX_WORKERS = min(os.cpu_count() or 4, 4)
_file_processor_pool = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="file_processor")

# Initialize services (lazy initialization to avoid config issues)
pdf_processor = None
llm_service = None
file_service = None


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
def upload_files():
    """Upload and process PDF files."""
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

        processed_files = []
        errors = []

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
        import secrets
        session_id = secrets.token_hex(8)

        # Function to process a single file
        def process_single_file(args):
            i, file, path = args
            try:
                # Validate file
                is_valid, message = file_svc.validate_file(file)
                if not is_valid:
                    return ("error", None, None, f"{file.filename}: {message}")

                # Save file temporarily
                filepath, unique_filename = file_svc.save_uploaded_file(file)

                # Validate PDF
                if not pdf_proc.validate_pdf(filepath):
                    file_svc.cleanup_file(filepath)
                    return ("error", None, None, f"{path}: Invalid or corrupted PDF file")

                # Extract text from PDF
                text, pages_processed = pdf_proc.extract_text_from_pdf(filepath)
                if not text:
                    file_svc.cleanup_file(filepath)
                    return ("error", None, None, f"{path}: Could not extract text from PDF")

                # Get metadata from LLM
                metadata, extraction_error = llm_svc.extract_paper_metadata(
                    text, user_preferences
                )

                if not metadata:
                    file_svc.cleanup_file(filepath)
                    if extraction_error:
                        error_message = llm_svc.get_error_message(extraction_error)
                        return ("error", None, None, f"{path}: {error_message}")
                    else:
                        return ("error", None, None, f"{path}: Could not extract metadata")

                # Validate suggested filename
                suggested_name = metadata.get("suggested_filename", "")
                if not llm_svc.validate_filename(suggested_name):
                    safe_name = secure_filename(file.filename)
                    name_part = os.path.splitext(safe_name)[0]
                    suggested_name = f"{name_part}_renamed.pdf"

                # Rename file with session isolation
                download_path = file_svc.move_to_downloads(
                    filepath, suggested_name, session_id=session_id
                )

                file_info = {
                    "original_name": path,
                    "original_filename": file.filename,
                    "new_name": suggested_name,
                    "download_path": download_path,
                    "metadata": metadata,
                    "pages_processed": pages_processed,
                }
                return ("success", file_info, None, None)

            except Exception as e:
                if "filepath" in locals():
                    file_svc.cleanup_file(filepath)
                return ("error", None, None, f"{path}: Processing error - {str(e)}")

        # Prepare arguments for parallel processing
        file_args = []
        for i, file in enumerate(files):
            path = paths[i] if paths and i < len(paths) else file.filename
            file_args.append((i, file, path))

        # Process files in parallel using shared thread pool
        future_to_file = {
            _file_processor_pool.submit(process_single_file, args): args[2]
            for args in file_args
        }

        for future in as_completed(future_to_file):
            try:
                result, file_info, filepath, error = future.result()
                if result == "success":
                    processed_files.append(file_info)
                else:
                    errors.append(error)
            except Exception as e:
                path = future_to_file[future]
                errors.append(f"{path}: Processing error - {str(e)}")

        # Record upload metrics
        try:
            from backend.utils.metrics_collector import MetricsCollector
            _metrics = MetricsCollector.get_instance()
            for file_info in processed_files:
                _size = 0
                try:
                    _download_filepath = os.path.join(
                        file_svc.upload_folder, "downloads", file_info["download_path"]
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

        # Return results
        if not processed_files and errors:
            return jsonify(
                {"error": "No files were processed successfully", "details": errors}
            ), 400

        # Record usage statistics
        record_usage(len(processed_files), user_id=user_id)

        # Create download URL
        if len(processed_files) == 1:
            single_file = processed_files[0]
            download_url = (
                f"{request.script_root}/api/download/{single_file['download_path']}"
            )
            filepath = os.path.join(
                file_svc.upload_folder, "downloads", single_file["download_path"]
            )
            file_svc.schedule_cleanup(filepath)

            return jsonify(
                {
                    "message": "File processed successfully",
                    "download_url": download_url,
                    "file": single_file,
                    "errors": errors,
                }
            )
        else:
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
            download_url = f"{request.script_root}/api/download/{zip_rel_path}"

            for filepath, _ in zip_files:
                file_svc.cleanup_file(filepath)
            file_svc.schedule_cleanup(zip_full_path)

            return jsonify(
                {
                    "message": f"Successfully processed {len(processed_files)} files",
                    "download_url": download_url,
                    "files": processed_files,
                    "errors": errors,
                }
            )

    except Exception as e:
        logger.error(f"Upload processing failed: {type(e).__name__}: {str(e)}", exc_info=True)
        return jsonify(
            {"error": "Server error during file processing"}
        ), 500


@upload.route("/download/<path:filepath>")
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
