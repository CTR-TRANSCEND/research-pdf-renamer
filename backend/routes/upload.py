from flask import Blueprint, request, jsonify, send_file, current_app, g
from flask_login import login_required, current_user
from backend.models import Usage
from backend.database import db
from backend.services import PDFProcessor, LLMService, FileService
from backend.utils import track_usage, check_rate_limit
from backend.utils.decorators import log_usage, record_usage
from backend.utils.auth import auth_required
from werkzeug.utils import secure_filename
import tempfile
import os
from datetime import datetime, timedelta

upload = Blueprint('upload', __name__)

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

@upload.route('/upload', methods=['POST'])
def upload_files():
    """Upload and process PDF files."""
    print(f"[DEBUG] Upload endpoint called - START")
    try:
        print(f"[DEBUG] Request files: {request.files}")
        print(f"[DEBUG] Request form: {request.form}")

        # Check if files were uploaded
        if 'files' not in request.files:
            return jsonify({'error': 'No files provided'}), 400

        files = request.files.getlist('files')
        if not files or files[0].filename == '':
            return jsonify({'error': 'No files selected'}), 400

        # Get services with detailed error logging
        print(f"[DEBUG] About to get services...")
        try:
            llm_svc, file_svc, pdf_proc = get_services()
            print(f"[DEBUG] Services obtained successfully")
        except Exception as e:
            print(f"[ERROR] Service initialization failed: {type(e).__name__}: {str(e)}")
            import traceback
            print(f"[ERROR] Service traceback: {traceback.format_exc()}")
            return jsonify({'error': f'Service initialization failed: {str(e)}'}), 500

        # Get file paths if folder upload
        paths = request.form.getlist('paths') if 'paths' in request.form else None
        preserve_structure = request.form.get('preserve_structure', 'false').lower() == 'true'

        # Validate file count (simple limit for testing)
        max_files = 5
        if len(files) > max_files:
            return jsonify({
                'error': f'Too many files. Maximum allowed: {max_files}'
            }), 400

        processed_files = []
        errors = []

        # Process each file
        for i, file in enumerate(files):
            print(f"[DEBUG] Processing file {i+1}: {file.filename}")
            try:
                # Validate file
                is_valid, message = file_svc.validate_file(file)
                if not is_valid:
                    errors.append(f"{file.filename}: {message}")
                    continue

                # Get original path if folder upload
                original_path = paths[i] if paths and i < len(paths) else file.filename

                # Save file temporarily
                filepath, unique_filename = file_svc.save_uploaded_file(file)
                print(f"[DEBUG] File saved to: {filepath}")

                # Validate PDF
                if not pdf_proc.validate_pdf(filepath):
                    file_svc.cleanup_file(filepath)
                    errors.append(f"{original_path}: Invalid or corrupted PDF file")
                    continue

                # Extract text from PDF
                text, pages_processed = pdf_proc.extract_text_from_pdf(filepath)
                print(f"[DEBUG] Extracted {len(text) if text else 0} characters from {pages_processed} pages")

                if not text:
                    file_svc.cleanup_file(filepath)
                    errors.append(f"{original_path}: Could not extract text from PDF")
                    continue

                # Get user preferences for filename format
                user_preferences = None
                if current_user.is_authenticated:
                    user_preferences = {
                        'filename_format': current_user.filename_format,
                        'custom_filename_format': current_user.custom_filename_format
                    }

                # Get metadata from LLM
                metadata = llm_svc.extract_paper_metadata(text, user_preferences)
                print(f"[DEBUG] Extracted metadata: {metadata}")

                if not metadata:
                    file_svc.cleanup_file(filepath)
                    errors.append(f"{original_path}: Could not extract metadata")
                    continue

                # Validate suggested filename
                suggested_name = metadata.get('suggested_filename', '')
                if not llm_svc.validate_filename(suggested_name):
                    # Generate fallback filename
                    safe_name = secure_filename(file.filename)
                    name_part = os.path.splitext(safe_name)[0]
                    suggested_name = f"{name_part}_renamed.pdf"

                # Rename file
                new_filepath = file_svc.move_to_downloads(filepath, suggested_name)

                # Store processed file info
                file_info = {
                    'original_name': original_path,
                    'original_filename': file.filename,
                    'new_name': suggested_name,
                    'new_filepath': new_filepath,
                    'metadata': metadata,
                    'pages_processed': pages_processed
                }

                processed_files.append(file_info)
                print(f"[DEBUG] Successfully processed file: {suggested_name}")

            except Exception as e:
                # Clean up on error
                if 'filepath' in locals():
                    file_svc.cleanup_file(filepath)
                original_path = paths[i] if paths and i < len(paths) else file.filename
                print(f"[ERROR] Error processing {original_path}: {type(e).__name__}: {str(e)}")
                errors.append(f"{original_path}: Processing error - {str(e)}")

        # Return results
        if not processed_files and errors:
            return jsonify({
                'error': 'No files were processed successfully',
                'details': errors
            }), 400

        # Record usage statistics
        user_id = current_user.id if current_user.is_authenticated else None
        record_usage(len(processed_files), user_id=user_id)

        # Create download URL for processed files
        if len(processed_files) == 1:
            # Single file download
            single_file = processed_files[0]
            download_url = f"/api/download/{single_file['new_name']}"

            # Schedule cleanup
            filepath = os.path.join(
                file_svc.upload_folder,
                'downloads',
                single_file['new_name']
            )
            file_svc.schedule_cleanup(filepath)

            return jsonify({
                'message': 'File processed successfully',
                'download_url': download_url,
                'file': single_file,
                'errors': errors
            })
        else:
            # Multiple files - create ZIP
            zip_files = []
            for pf in processed_files:
                filepath = os.path.join(
                    file_svc.upload_folder,
                    'downloads',
                    pf['new_name']
                )
                zip_files.append((filepath, pf['new_name']))

            zip_path = file_svc.create_zip(zip_files)
            download_url = f"/api/download/{os.path.basename(zip_path)}"

            # Schedule cleanup
            for filepath, _ in zip_files:
                file_svc.cleanup_file(filepath)
            file_svc.schedule_cleanup(zip_path)

            return jsonify({
                'message': f'Successfully processed {len(processed_files)} files',
                'download_url': download_url,
                'files': processed_files,
                'errors': errors
            })

    except Exception as e:
        print(f"[ERROR] Upload processing failed: {type(e).__name__}: {str(e)}")
        import traceback
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        return jsonify({
            'error': 'Server error during file processing',
            'details': str(e)
        }), 500

@upload.route('/download/<filename>')
def download_file(filename):
    """Download processed file."""
    try:
        # Secure the filename to prevent path traversal attacks
        safe_filename = secure_filename(filename)
        if not safe_filename:
            return jsonify({'error': 'Invalid filename'}), 400

        # Use absolute path to ensure we find the file
        file_path = os.path.abspath(os.path.join('uploads', 'downloads', safe_filename))

        # Debug print (server-side only, not exposed to user)
        print(f"[DEBUG] Looking for file at: {file_path}")
        print(f"[DEBUG] File exists: {os.path.exists(file_path)}")

        if not os.path.exists(file_path):
            # Don't expose full path to user - only show filename
            return jsonify({'error': f'File not found: {safe_filename}'}), 404

        # Determine mimetype based on file extension
        if safe_filename.lower().endswith('.zip'):
            mimetype = 'application/zip'
        else:
            mimetype = 'application/pdf'

        return send_file(
            file_path,
            as_attachment=True,
            download_name=safe_filename,
            mimetype=mimetype
        )

    except Exception as e:
        print(f"[ERROR] Download error: {e}")
        # Don't expose internal error details to user
        return jsonify({'error': 'Download failed. Please try again.'}), 500

@upload.route('/usage-stats')
@auth_required
def usage_stats():
    """Get usage statistics for current user."""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401

    # Get usage stats (daily for anonymous users, yearly for registered)
    from datetime import datetime, timedelta
    if current_user.is_approved:
        year_ago = datetime.utcnow() - timedelta(days=365)
        time_period = "year"
        time_filter = year_ago
    else:
        day_ago = datetime.utcnow() - timedelta(days=1)
        time_period = "day"
        time_filter = day_ago

    total_submissions = Usage.query.filter(
        Usage.user_id == current_user.id,
        Usage.timestamp > time_filter
    ).count()

    total_files = Usage.query.filter(
        Usage.user_id == current_user.id,
        Usage.timestamp > time_filter
    ).with_entities(db.func.sum(Usage.files_processed)).scalar() or 0

    # Get recent submissions
    recent = Usage.query.filter(
        Usage.user_id == current_user.id
    ).order_by(Usage.timestamp.desc()).limit(10).all()

    recent_data = [{
        'timestamp': u.timestamp.isoformat(),
        'files_processed': u.files_processed,
        'ip_address': u.ip_address
    } for u in recent]

    return jsonify({
        'total_submissions': total_submissions,
        'total_files_processed': total_files,
        'recent_submissions': recent_data,
        'max_files_per_submission': current_user.get_max_files(),
        'is_approved': current_user.is_approved
    })