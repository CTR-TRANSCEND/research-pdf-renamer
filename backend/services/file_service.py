import os
import shutil
import zipfile
import secrets
import hashlib
import io
import logging
import threading
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from typing import List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Module-level counter for cleanup tasks skipped due to a full queue.
_skipped_cleanup_count = 0
_skipped_cleanup_lock = threading.Lock()


def get_cleanup_stats() -> dict:
    """Return cleanup queue health statistics.

    Returns:
        dict with keys:
            skipped_total   - cumulative count of skipped scheduled cleanups
            queue_depth     - number of semaphore slots still available
                             (lower == more tasks queued), or None if unavailable
            executor_max_workers - max_workers of the shared cleanup executor
    """
    global _skipped_cleanup_count
    with _skipped_cleanup_lock:
        skipped = _skipped_cleanup_count

    # BoundedSemaphore exposes ._value as the count of available permits.
    try:
        queue_depth = FileService._cleanup_semaphore._value
    except AttributeError:
        queue_depth = None

    try:
        max_workers = FileService._cleanup_executor._max_workers
    except AttributeError:
        max_workers = None

    return {
        "skipped_total": skipped,
        "queue_depth": queue_depth,
        "executor_max_workers": max_workers,
    }


class FileService:
    # LOG-003: Class-level thread pool for cleanup tasks
    # PERF-002 FIX: Add bounded queue to prevent unbounded task accumulation
    # Using a BoundedSemaphore to limit concurrent cleanup operations
    _cleanup_executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="cleanup_")
    _cleanup_semaphore = threading.BoundedSemaphore(50)  # Max 50 pending cleanup tasks
    _cleanup_queue_lock = threading.Lock()

    def __init__(self, config=None):
        self.config = config or {}
        self.upload_folder = self.config.get("UPLOAD_FOLDER") or "uploads"
        self.temp_folder = self.config.get("TEMP_FOLDER") or "temp"
        self.max_content_length = (
            self.config.get("MAX_CONTENT_LENGTH") or 50 * 1024 * 1024
        )  # 50MB per file
        self.chunk_size = 64 * 1024  # 64KB chunks for streaming

        # Cache for file hashes to detect duplicates
        self._file_hash_cache = {}
        self._cache_max_size = 100
        # Lock to guard concurrent reads/writes of _file_hash_cache and its LRU eviction
        self._cache_lock = threading.Lock()

        # Create folders if they don't exist
        os.makedirs(self.upload_folder, exist_ok=True)
        os.makedirs(self.temp_folder, exist_ok=True)
        os.makedirs(os.path.join(self.upload_folder, "downloads"), exist_ok=True)

    def save_uploaded_file(
        self, file, filename: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Save uploaded file to temporary location with streaming and duplicate detection.

        Performs a single pass over the upload stream: each chunk is written to disk
        and incrementally fed to a SHA-256 hasher. After writing completes, the digest
        is compared against the duplicate-detection cache for informational logging.

        The cache is informational only — concurrent uploads of the same file each
        receive their own private temp path to prevent race-condition data loss.
        (If two threads shared a path, one thread's move_to_downloads could remove
        the file before the other thread reads it, causing an "Invalid PDF" error.)

        Returns (filepath, unique_filename).
        """
        if filename is None:
            filename = file.filename

        # Generate unique filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        name, ext = os.path.splitext(secure_filename(filename))
        unique_filename = f"{name}_{timestamp}{ext}"
        filepath = os.path.join(self.temp_folder, unique_filename)

        # Ensure we read from the start of the upload stream
        try:
            file.stream.seek(0)
        except (AttributeError, OSError, ValueError):
            # Some FileStorage-like objects may not be seekable; ignore and proceed
            pass

        # Single-pass: hash while writing
        hash_sha256 = hashlib.sha256()
        with open(filepath, "wb") as out_f:
            while True:
                chunk = file.stream.read(self.chunk_size)
                if not chunk:
                    break
                hash_sha256.update(chunk)
                out_f.write(chunk)

        file_hash = hash_sha256.hexdigest()

        # Informational duplicate check — do NOT delete the freshly written file or
        # return a cached path.  Each caller owns its own temp file; sharing paths
        # across threads would allow one thread's move_to_downloads to silently
        # remove the file from under another thread.
        with self._cache_lock:
            cached_path = self._file_hash_cache.get(file_hash)

        if cached_path and cached_path != filepath:
            logger.info(
                f"Duplicate upload detected (hash {file_hash[:8]}); "
                f"keeping independent copy at {filepath}"
            )

        # Update cache with the latest path for this hash (locked for thread-safe LRU eviction).
        # Storing the freshest path keeps cache entries from pointing at already-deleted files.
        self._update_cache(file_hash, filepath)

        return filepath, unique_filename

    def _update_cache(self, file_hash: str, filepath: str):
        """Update file hash cache with LRU eviction (thread-safe)."""
        with self._cache_lock:
            if (
                file_hash not in self._file_hash_cache
                and len(self._file_hash_cache) >= self._cache_max_size
            ):
                # Remove oldest entry (simple FIFO for now)
                oldest_key = next(iter(self._file_hash_cache))
                del self._file_hash_cache[oldest_key]

            self._file_hash_cache[file_hash] = filepath

    def create_zip(
        self,
        files: List[Tuple[str, str]],
        zip_name: str = None,
        session_id: Optional[str] = None,
    ) -> str:
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
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Add 6 random characters to prevent filename conflicts
            random_suffix = secrets.token_hex(3)  # 6 hex characters
            zip_name = f"renamed_pdfs_{timestamp}_{random_suffix}.zip"

        # Save ZIP to session-specific downloads folder
        download_folder = os.path.join(self.upload_folder, "downloads")

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
            os.path.getsize(filepath)
            for filepath, _ in files
            if os.path.exists(filepath)
        )

        # Use in-memory ZIP for small files (<10MB total)
        if total_size < 10 * 1024 * 1024:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(
                zip_buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=6
            ) as zipf:
                for filepath, new_filename in files:
                    if os.path.exists(filepath):
                        zipf.write(filepath, new_filename)

            # Write buffer to disk
            with open(zip_path, "wb") as f:
                f.write(zip_buffer.getvalue())
        else:
            # Use streaming ZIP for larger files
            with zipfile.ZipFile(
                zip_path,
                "w",
                zipfile.ZIP_DEFLATED,
                compresslevel=6,  # Balanced compression
                allowZip64=True,  # Support for large files
            ) as zipf:
                for filepath, new_filename in files:
                    if os.path.exists(filepath):
                        zipf.write(filepath, new_filename)

    def move_to_downloads(
        self, filepath: str, new_filename: str, session_id: Optional[str] = None
    ) -> str:
        """
        Move processed file to downloads folder with new name.

        Args:
            filepath: Source filepath
            new_filename: Desired filename (based on metadata)
            session_id: Optional session ID for user isolation

        Returns:
            New filepath (with session isolation and unique suffix)

        Files are organized as: uploads/downloads/{session_id}/{filename}
        Session folders provide user isolation; random suffix added only on collision.
        """
        download_folder = os.path.join(self.upload_folder, "downloads")

        # Use session_id if provided, otherwise use 'default'
        session_folder = session_id if session_id else "default"
        session_download_folder = os.path.join(download_folder, session_folder)
        os.makedirs(session_download_folder, exist_ok=True)

        # Use clean filename — session folder provides isolation
        # Add short random suffix only if file already exists
        unique_filename = new_filename
        if os.path.exists(os.path.join(session_download_folder, unique_filename)):
            import random
            suffix = random.randint(1000, 9999)
            name, ext = os.path.splitext(new_filename)
            unique_filename = f"{name}_{suffix}{ext}"

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
                                logger.error(f"Error removing file {filepath}: {e}")

    def get_file_size(self, filepath: str) -> int:
        """Get file size in bytes."""
        return os.path.getsize(filepath)

    def is_pdf(self, filename: str) -> bool:
        """Check if file is a PDF."""
        return filename.lower().endswith(".pdf")

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
            return (
                False,
                f"File too large. Maximum size is {self.max_content_length / (1024 * 1024):.1f}MB",
            )

        if size == 0:
            return False, "File is empty"

        # Quick PDF magic number check (only read first 4 bytes)
        magic_bytes = file.read(4)
        file.seek(0)
        if magic_bytes != b"%PDF":
            return False, "Invalid PDF file format"

        return True, "Valid file"

    def cleanup_file(self, filepath: str):
        """Remove a specific file."""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception as e:
            logger.error(f"Error removing file {filepath}: {e}")

    def schedule_cleanup(self, filepath: str, delay_minutes: int = 30):
        """
        Schedule a file for cleanup after specified delay.

        Args:
            filepath: Full path to the file to be cleaned up
            delay_minutes: Minutes to wait before cleanup (default: 30)

        LOG-003: Uses a class-level ThreadPoolExecutor to limit concurrent cleanup threads.
        PERF-002 FIX: Uses BoundedSemaphore to limit pending cleanup tasks.
        This prevents resource exhaustion from unbounded task accumulation.
        """
        # PERF-002 FIX: Acquire semaphore before submitting to limit pending tasks
        # If 50 tasks are already pending, this will block until a slot is available
        acquired = self._cleanup_semaphore.acquire(blocking=False)
        if not acquired:
            # Queue is full, skip cleanup for this file (will be cleaned by periodic cleanup)
            logger.warning(
                f"Cleanup queue full, skipping scheduled cleanup for: {filepath}"
            )
            global _skipped_cleanup_count
            with _skipped_cleanup_lock:
                _skipped_cleanup_count += 1
            return

        # Submit cleanup task to the shared thread pool with semaphore release wrapper
        self._cleanup_executor.submit(
            self._cleanup_task_with_semaphore, filepath, delay_minutes
        )
        logger.debug(f"Scheduled cleanup in {delay_minutes} minutes: {filepath}")

    def _cleanup_task_with_semaphore(self, filepath: str, delay_minutes: int):
        """
        Internal cleanup task that releases semaphore after completion.

        Args:
            filepath: Full path to the file to be cleaned up
            delay_minutes: Minutes to wait before cleanup
        """
        try:
            self._cleanup_task(filepath, delay_minutes)
        finally:
            # Always release semaphore, even if cleanup fails
            self._cleanup_semaphore.release()

    def _cleanup_task(self, filepath: str, delay_minutes: int):
        """
        Internal cleanup task executed by the thread pool.

        Args:
            filepath: Full path to the file to be cleaned up
            delay_minutes: Minutes to wait before cleanup
        """
        import time

        try:
            # Wait for the specified delay
            time.sleep(delay_minutes * 60)
            # Delete the file if it still exists
            if os.path.exists(filepath):
                os.remove(filepath)
                logger.debug(f"Removed file: {filepath}")
        except Exception as e:
            logger.error(f"Error removing {filepath}: {e}")

    def process_files_batch(
        self, files: List, paths: List = None, preserve_structure: bool = False
    ) -> Tuple[List, List]:
        """
        Process multiple files in batch for better performance.
        Returns (successful_files, errors).
        """

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

                successful_files.append(
                    {
                        "original_name": original_path,
                        "original_filename": file.filename,
                        "filepath": filepath,
                        "unique_filename": unique_filename,
                    }
                )

            except Exception as e:
                original_path = file.filename if not original_path else original_path
                errors.append(f"{original_path}: Processing error - {str(e)}")

        return successful_files, errors
