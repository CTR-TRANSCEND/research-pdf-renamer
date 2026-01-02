import os
import shutil
import zipfile
import secrets
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from typing import List, Optional, Tuple

class FileService:
    def __init__(self, config=None):
        self.config = config or {}
        self.upload_folder = self.config.get('UPLOAD_FOLDER', 'uploads')
        self.temp_folder = self.config.get('TEMP_FOLDER', 'temp')
        self.max_content_length = self.config.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024)  # 16MB

        # Create folders if they don't exist
        os.makedirs(self.upload_folder, exist_ok=True)
        os.makedirs(self.temp_folder, exist_ok=True)

    def save_uploaded_file(self, file, filename: Optional[str] = None) -> Tuple[str, str]:
        """
        Save uploaded file to temporary location.
        Returns (filepath, unique_filename).
        """
        if filename is None:
            filename = file.filename

        # Generate unique filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        name, ext = os.path.splitext(secure_filename(filename))
        unique_filename = f"{name}_{timestamp}{ext}"
        filepath = os.path.join(self.temp_folder, unique_filename)

        file.save(filepath)
        return filepath, unique_filename

    def create_zip(self, files: List[Tuple[str, str]], zip_name: str = None) -> str:
        """
        Create a ZIP file containing multiple files.
        files: List of (filepath, new_filename) tuples
        Returns path to created ZIP file.
        """
        if zip_name is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            # Add 6 random characters to prevent filename conflicts
            random_suffix = secrets.token_hex(3)  # 6 hex characters
            zip_name = f"renamed_pdfs_{timestamp}_{random_suffix}.zip"

        # Save ZIP to downloads folder so it can be downloaded
        download_folder = os.path.join(self.upload_folder, 'downloads')
        os.makedirs(download_folder, exist_ok=True)
        zip_path = os.path.join(download_folder, zip_name)

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for filepath, new_filename in files:
                if os.path.exists(filepath):
                    zipf.write(filepath, new_filename)

        return zip_path

    def move_to_downloads(self, filepath: str, new_filename: str) -> str:
        """
        Move processed file to downloads folder with new name.
        Returns new filepath.
        """
        download_folder = os.path.join(self.upload_folder, 'downloads')
        os.makedirs(download_folder, exist_ok=True)

        new_filepath = os.path.join(download_folder, new_filename)
        shutil.move(filepath, new_filepath)
        return new_filepath

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
        """Validate uploaded file."""
        if file is None:
            return False, "No file provided"

        if not self.is_pdf(file.filename):
            return False, "File must be a PDF"

        # Check file size
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)

        if size > self.max_content_length:
            return False, f"File too large. Maximum size is {self.max_content_length / (1024*1024):.1f}MB"

        if size == 0:
            return False, "File is empty"

        return True, "Valid file"

    def cleanup_file(self, filepath: str):
        """Remove a specific file."""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception as e:
            print(f"Error removing file {filepath}: {e}")

    def schedule_cleanup(self, filepath: str, delay_minutes: int = 30):
        """Schedule a file for cleanup after delay."""
        # In a production environment, you might use a task queue like Celery
        # For now, we'll just rely on the periodic cleanup
        pass