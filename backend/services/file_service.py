import os
import shutil
import zipfile
import secrets
import hashlib
import io
import threading
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from typing import List, Optional, Tuple, BinaryIO

class FileService:
    def __init__(self, config=None):
        self.config = config or {}
        self.upload_folder = self.config.get('UPLOAD_FOLDER') or 'uploads'
        self.temp_folder = self.config.get('TEMP_FOLDER') or 'temp'
        self.max_content_length = self.config.get('MAX_CONTENT_LENGTH') or 100 * 1024 * 1024  # 100MB
        self.chunk_size = 64 * 1024  # 64KB chunks for streaming

        # Cache for file hashes to detect duplicates
        self._file_hash_cache = {}
        self._cache_max_size = 100

        # Create folders if they don't exist
        os.makedirs(self.upload_folder, exist_ok=True)
        os.makedirs(self.temp_folder, exist_ok=True)
        os.makedirs(os.path.join(self.upload_folder, 'downloads'), exist_ok=True)

    def save_uploaded_file(self, file, filename: Optional[str] = None) -> Tuple[str, str]:
        """
        Save uploaded file to temporary location with streaming and duplicate detection.
        Returns (filepath, unique_filename).
        """
        if filename is None:
            filename = file.filename

        # Calculate file hash while streaming to detect duplicates
        file_hash = self._calculate_file_hash(file)

        # Check cache for duplicate
        if file_hash in self._file_hash_cache:
            existing_path = self._file_hash_cache[file_hash]
            if os.path.exists(existing_path):
                return existing_path, os.path.basename(existing_path)

        # Reset file pointer after hash calculation
        file.seek(0)

        # Generate unique filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        name, ext = os.path.splitext(secure_filename(filename))
        unique_filename = f"{name}_{timestamp}{ext}"
        filepath = os.path.join(self.temp_folder, unique_filename)

        # Save file with streaming
        self._save_file_streaming(file, filepath)

        # Update cache
        self._update_cache(file_hash, filepath)

        return filepath, unique_filename

    def _calculate_file_hash(self, file) -> str:
        """Calculate SHA256 hash of file while streaming."""
        hash_sha256 = hashlib.sha256()

        # Read file in chunks to handle large files efficiently
        while True:
            chunk = file.read(self.chunk_size)
            if not chunk:
                break
            hash_sha256.update(chunk)

        return hash_sha256.hexdigest()

    def _save_file_streaming(self, file, filepath: str):
        """Save file using streaming to handle large files efficiently."""
        with open(filepath, 'wb') as f:
            file.seek(0)  # Reset file pointer
            while True:
                chunk = file.read(self.chunk_size)
                if not chunk:
                    break
                f.write(chunk)

    def _update_cache(self, file_hash: str, filepath: str):
        """Update file hash cache with LRU eviction."""
        if len(self._file_hash_cache) >= self._cache_max_size:
            # Remove oldest entry (simple FIFO for now)
            oldest_key = next(iter(self._file_hash_cache))
            del self._file_hash_cache[oldest_key]

        self._file_hash_cache[file_hash] = filepath

    def create_zip(self, files: List[Tuple[str, str]], zip_name: str = None, session_id: Optional[str] = None) -> str:
        """
        Create a ZIP file containing multiple files with optimized compression.

        Args:
            files: List of (filepath, new_filename) tuples
            zip_name: Name for the ZIP file
            session_id: Optional session ID for user isolation

        Returns:
            Full path to created ZIP file
        """
        if zip_name is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            # Add 6 random characters to prevent filename conflicts
            random_suffix = secrets.token_hex(3)  # 6 hex characters
            zip_name = f"renamed_pdfs_{timestamp}_{random_suffix}.zip"

        # Save ZIP to session-specific downloads folder
        download_folder = os.path.join(self.upload_folder, 'downloads')

        # Use session_id if provided, otherwise use 'default'
        if session_id:
            session_folder = session_id
            session_download_folder = os.path.join(download_folder, session_folder)
            os.makedirs(session_download_folder, exist_ok=True)
            zip_path = os.path.join(session_download_folder, zip_name)
        else:
            os.makedirs(download_folder, exist_ok=True)
            zip_path = os.path.join(download_folder, zip_name)

        # Use optimized ZIP creation
        self._create_zip_optimized(files, zip_path)

        return zip_path

    def _create_zip_optimized(self, files: List[Tuple[str, str]], zip_path: str):
        """Create ZIP with optimized settings and streaming."""
        # Calculate total size to determine best approach
        total_size = sum(
            os.path.getsize(filepath) for filepath, _ in files
            if os.path.exists(filepath)
        )

        # Use in-memory ZIP for small files (<10MB total)
        if total_size < 10 * 1024 * 1024:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
                for filepath, new_filename in files:
                    if os.path.exists(filepath):
                        zipf.write(filepath, new_filename)

            # Write buffer to disk
            with open(zip_path, 'wb') as f:
                f.write(zip_buffer.getvalue())
        else:
            # Use streaming ZIP for larger files
            with zipfile.ZipFile(
                zip_path,
                'w',
                zipfile.ZIP_DEFLATED,
                compresslevel=6,  # Balanced compression
                allowZip64=True  # Support for large files
            ) as zipf:
                for filepath, new_filename in files:
                    if os.path.exists(filepath):
                        zipf.write(filepath, new_filename)

    def move_to_downloads(self, filepath: str, new_filename: str, session_id: Optional[str] = None) -> str:
        """
        Move processed file to downloads folder with new name.

        Args:
            filepath: Source filepath
            new_filename: Desired filename (based on metadata)
            session_id: Optional session ID for user isolation

        Returns:
            New filepath (with session isolation and unique suffix)

        Files are organized as: uploads/downloads/{session_id}/{timestamp}_{filename}
        This prevents collisions when multiple users process files with same metadata.
        """
        download_folder = os.path.join(self.upload_folder, 'downloads')

        # Use session_id if provided, otherwise use 'default'
        session_folder = session_id if session_id else 'default'
        session_download_folder = os.path.join(download_folder, session_folder)
        os.makedirs(session_download_folder, exist_ok=True)

        # Add timestamp to filename to prevent collisions
        # Format: YYYYMMDD_HHMMSS_{original_filename}
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        name, ext = os.path.splitext(new_filename)
        unique_filename = f"{timestamp}_{name}{ext}"

        new_filepath = os.path.join(session_download_folder, unique_filename)
        shutil.move(filepath, new_filepath)

        # Return the relative path from downloads folder (session_id/filename)
        # This is used in the download URL
        return os.path.join(session_folder, unique_filename)

    def cleanup_temp_files(self, older_than_hours: int = 1):
        """Remove temporary files older than specified hours."""
        cutoff_time = datetime.now() - timedelta(hours=older_than_hours)

        for folder in [self.temp_folder, self.upload_folder]:
            if os.path.exists(folder):
                for filename in os.listdir(folder):
                    filepath = os.path.join(folder, filename)
                    if os.path.isfile(filepath):
                        file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                        if file_time < cutoff_time:
                            try:
                                os.remove(filepath)
                            except Exception as e:
                                print(f"Error removing file {filepath}: {e}")

    def get_file_size(self, filepath: str) -> int:
        """Get file size in bytes."""
        return os.path.getsize(filepath)

    def is_pdf(self, filename: str) -> bool:
        """Check if file is a PDF."""
        return filename.lower().endswith('.pdf')

    def validate_file(self, file) -> Tuple[bool, str]:
        """Validate uploaded file with streaming and early checks."""
        if file is None:
            return False, "No file provided"

        # Quick filename check first
        if not self.is_pdf(file.filename):
            return False, "File must be a PDF"

        # Check file size without loading entire file
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)

        if size > self.max_content_length:
            return False, f"File too large. Maximum size is {self.max_content_length / (1024*1024):.1f}MB"

        if size == 0:
            return False, "File is empty"

        # Quick PDF magic number check (only read first 4 bytes)
        magic_bytes = file.read(4)
        file.seek(0)
        if magic_bytes != b'%PDF':
            return False, "Invalid PDF file format"

        return True, "Valid file"

    def cleanup_file(self, filepath: str):
        """Remove a specific file."""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception as e:
            print(f"Error removing file {filepath}: {e}")

    def schedule_cleanup(self, filepath: str, delay_minutes: int = 30):
        """
        Schedule a file for cleanup after specified delay.

        Args:
            filepath: Full path to the file to be cleaned up
            delay_minutes: Minutes to wait before cleanup (default: 30)

        Uses a daemon thread to delete the file after the delay.
        The thread runs as a daemon so it won't prevent the app from shutting down.
        """
        def cleanup_task():
            try:
                # Wait for the specified delay
                threading.Event().wait(delay_minutes * 60)
                # Delete the file if it still exists
                if os.path.exists(filepath):
                    os.remove(filepath)
                    print(f"[Cleanup] Removed file: {filepath}")
            except Exception as e:
                print(f"[Cleanup] Error removing {filepath}: {e}")

        # Start cleanup in a daemon thread (won't block app shutdown)
        cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
        cleanup_thread.start()

        # Log for debugging
        print(f"[Cleanup] Scheduled removal in {delay_minutes} minutes: {filepath}")

    def process_files_batch(self, files: List, paths: List = None, preserve_structure: bool = False) -> Tuple[List, List]:
        """
        Process multiple files in batch for better performance.
        Returns (successful_files, errors).
        """
        from flask import request

        successful_files = []
        errors = []

        # Pre-validate all files first (fast operations)
        valid_files = []
        for i, file in enumerate(files):
            is_valid, message = self.validate_file(file)
            if not is_valid:
                original_path = paths[i] if paths and i < len(paths) else file.filename
                errors.append(f"{original_path}: {message}")
            else:
                valid_files.append((i, file))

        # Process valid files
        for i, file in valid_files:
            try:
                # Get original path if folder upload
                original_path = None
                if preserve_structure and paths and i < len(paths):
                    original_path = paths[i]
                else:
                    original_path = file.filename

                # Save file with streaming
                filepath, unique_filename = self.save_uploaded_file(file, original_path)

                successful_files.append({
                    'original_name': original_path,
                    'original_filename': file.filename,
                    'filepath': filepath,
                    'unique_filename': unique_filename
                })

            except Exception as e:
                original_path = file.filename if not original_path else original_path
                errors.append(f"{original_path}: Processing error - {str(e)}")

        return successful_files, errors