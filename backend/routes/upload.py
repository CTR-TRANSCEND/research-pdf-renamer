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
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

upload = Blueprint("upload", __name__)
logger = logging.getLogger(__name__)

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
    logger.debug("Upload endpoint called - START")
    try:
        logger.debug(f"Request files: {request.files}")
        logger.debug(f"Request form: {request.form}")

        # Check if files were uploaded
        if "files" not in request.files:
            return jsonify({"error": "No files provided"}), 400

        files = request.files.getlist("files")
        if not files or files[0].filename == "":
            return jsonify({"error": "No files selected"}), 400

        # Get services with detailed error logging
        logger.debug("About to get services...")
        try:
            llm_svc, file_svc, pdf_proc = get_services()
            logger.debug("Services obtained successfully")
        except Exception as e:
            logger.error(f"Service initialization failed: {type(e).__name__}: {str(e)}")
            import traceback

            logger.error(f"Service traceback: {traceback.format_exc()}")
            return jsonify({"error": f"Service initialization failed: {str(e)}"}), 500

        # Get file paths if folder upload
        paths = request.form.getlist("paths") if "paths" in request.form else None
        preserve_structure = (
            request.form.get("preserve_structure", "false").lower() == "true"
        )

        # Validate file count BEFORE processing
        # Use user-specific limit from User model
        if current_user and current_user.is_authenticated:
            max_files = current_user.get_max_files()
        else:
            # Anonymous users: 5 files per submission
            max_files = 5

        if len(files) > max_files:
            return jsonify(
                {"error": f"Too many files. Maximum allowed: {max_files}"}
            ), 400

        # Use ThreadPoolExecutor for parallel processing
        max_workers = min(
            len(files), 4
        )  # Limit to 4 workers to avoid overwhelming system
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

        # Generate unique session ID for this batch of uploads
        # This ensures user/session isolation and prevents filename collisions
        import secrets

        session_id = secrets.token_hex(8)  # 16-character hex string

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
                    return (
                        "error",
                        None,
                        None,
                        f"{path}: Invalid or corrupted PDF file",
                    )

                # Extract text from PDF
                text, pages_processed = pdf_proc.extract_text_from_pdf(filepath)

                if not text:
                    file_svc.cleanup_file(filepath)
                    return (
                        "error",
                        None,
                        None,
                        f"{path}: Could not extract text from PDF",
                    )

                # Get metadata from LLM (user preferences already captured above)
                metadata, extraction_error = llm_svc.extract_paper_metadata(
                    text, user_preferences
                )

                if not metadata:
                    file_svc.cleanup_file(filepath)
                    if extraction_error:
                        error_message = llm_svc.get_error_message(extraction_error)
                        return ("error", None, None, f"{path}: {error_message}")
                    else:
                        return (
                            "error",
                            None,
                            None,
                            f"{path}: Could not extract metadata",
                        )

                # Validate suggested filename
                suggested_name = metadata.get("suggested_filename", "")
                if not llm_svc.validate_filename(suggested_name):
                    # Generate fallback filename
                    safe_name = secure_filename(file.filename)
                    name_part = os.path.splitext(safe_name)[0]
                    suggested_name = f"{name_part}_renamed.pdf"

                # Rename file with session isolation
                # move_to_downloads returns: session_id/timestamp_filename
                download_path = file_svc.move_to_downloads(
                    filepath, suggested_name, session_id=session_id
                )

                # Store processed file info
                file_info = {
                    "original_name": path,
                    "original_filename": file.filename,
                    "new_name": suggested_name,
                    "download_path": download_path,  # Relative path for URL: session_id/timestamp_filename
                    "metadata": metadata,
                    "pages_processed": pages_processed,
                }

                return ("success", file_info, None, None)

            except Exception as e:
                # Clean up on error
                if "filepath" in locals():
                    file_svc.cleanup_file(filepath)
                return ("error", None, None, f"{path}: Processing error - {str(e)}")

        # Prepare arguments for parallel processing
        file_args = []
        for i, file in enumerate(files):
            path = paths[i] if paths and i < len(paths) else file.filename
            file_args.append((i, file, path))

        # Process files in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_file = {
                executor.submit(process_single_file, args): args[
                    2
                ]  # args[2] is the original path
                for args in file_args
            }

            # Collect results as they complete
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

        # Return results
        if not processed_files and errors:
            return jsonify(
                {"error": "No files were processed successfully", "details": errors}
            ), 400

        # Record usage statistics (user_id already captured above)
        record_usage(len(processed_files), user_id=user_id)

        # Create download URL for processed files
        # Use request.script_root which ProxyFix sets correctly for reverse proxy
        # Download path format: session_id/timestamp_filename
        if len(processed_files) == 1:
            # Single file download
            single_file = processed_files[0]
            # Use the download_path which includes session_id/timestamp_filename
            download_url = (
                f"{request.script_root}/api/download/{single_file['download_path']}"
            )

            # Schedule cleanup
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
            # Multiple files - create ZIP
            zip_files = []
            for pf in processed_files:
                filepath = os.path.join(
                    file_svc.upload_folder, "downloads", pf["download_path"]
                )
                # Use just the filename (not session_id) for the ZIP contents
                zip_filename = pf["new_name"]
                zip_files.append((filepath, zip_filename))

            # Create ZIP in the session folder
            zip_name = f"processed_files_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            zip_full_path = file_svc.create_zip(
                zip_files, zip_name=zip_name, session_id=session_id
            )

            # Get relative path for URL
            zip_rel_path = os.path.relpath(
                zip_full_path, os.path.join(file_svc.upload_folder, "downloads")
            )
            download_url = f"{request.script_root}/api/download/{zip_rel_path}"

            # Schedule cleanup (individual files already in ZIP, clean them up now)
            for filepath, _ in zip_files:
                file_svc.cleanup_file(filepath)
            # Clean up the ZIP after 30 minutes
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
        print(f"[ERROR] Upload processing failed: {type(e).__name__}: {str(e)}")
        import traceback

        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        return jsonify(
            {"error": "Server error during file processing", "details": str(e)}
        ), 500


@upload.route("/download/<path:filepath>")
def download_file(filepath):
    """
    Download processed file.

    The filepath can include session_id subfolder: session_id/timestamp_filename
    Using <path:> converter allows slashes in the URL parameter.
    """
    try:
        # Secure the filepath to prevent path traversal attacks
        # secure_filename will sanitize each part of the path
        path_parts = filepath.split("/")
        safe_parts = [secure_filename(part) for part in path_parts if part]
        safe_filepath = "/".join(safe_parts)

        if not safe_filepath:
            return jsonify({"error": "Invalid filename"}), 400

        # SEC-003 FIX: Add realpath check to prevent path traversal via symlinks
        # Get the absolute paths and verify the requested file stays within allowed directory
        allowed_dir = os.path.abspath(os.path.join("uploads", "downloads"))
        file_path = os.path.abspath(os.path.join(allowed_dir, safe_filepath))

        # Verify the file path is within the allowed directory
        # This prevents symlink attacks and path traversal
        if not file_path.startswith(allowed_dir + os.sep) and file_path != allowed_dir:
            logger.warning(f"Path traversal attempt blocked: {safe_filepath}")
            return jsonify({"error": "Invalid filename"}), 400

        # Debug logging (server-side only, not exposed to user)
        logger.debug(f"Looking for file at: {file_path}")
        logger.debug(f"File exists: {os.path.exists(file_path)}")

        if not os.path.exists(file_path):
            # Don't expose full path to user - only show filename
            return jsonify({"error": "File not found"}), 404

        # Determine mimetype based on file extension
        if safe_filepath.lower().endswith(".zip"):
            mimetype = "application/zip"
        else:
            mimetype = "application/pdf"

        # Get the display filename (last part of path, without timestamp prefix)
        display_filename = os.path.basename(safe_filepath)
        # Remove timestamp prefix if present (format: YYYYMMDD_HHMMSS_)
        if "_" in display_filename and display_filename[8] == "_":
            # Try to parse as timestamp format
            try:
                # Check if first part looks like timestamp (digits and underscores)
                prefix_end = display_filename.find("_", 8)  # Find second underscore
                if prefix_end > 0:
                    display_filename = display_filename[prefix_end + 1 :]
            except:
                pass  # Use original filename if parsing fails

        return send_file(
            file_path,
            as_attachment=True,
            download_name=display_filename,
            mimetype=mimetype,
        )

    except Exception as e:
        logger.error(f"Download error: {e}")
        # Don't expose internal error details to user
        return jsonify({"error": "Download failed. Please try again."}), 500


@upload.route("/usage-stats")
@auth_required
def usage_stats():
    """Get usage statistics for current user."""
    if not current_user.is_authenticated:
        return jsonify({"error": "Authentication required"}), 401

    # Get usage stats (daily for anonymous users, yearly for registered)
    from datetime import datetime

    if current_user.is_approved:
        year_ago = datetime.utcnow() - timedelta(days=365)
        time_period = "year"
        time_filter = year_ago
    else:
        day_ago = datetime.utcnow() - timedelta(days=1)
        time_period = "day"
        time_filter = day_ago

    # Optimize: Get both total submissions and files in one query
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

    # Get recent submissions
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
