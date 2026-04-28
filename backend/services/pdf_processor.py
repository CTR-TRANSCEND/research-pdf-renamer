import re
import hashlib
import os
import threading
import time
from typing import Tuple, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import logging

try:
    import pymupdf
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

# Configure logging
logger = logging.getLogger(__name__)

# Hard ceiling for a single PDF extraction. A malicious or corrupt PDF must
# not be able to hang a worker beyond this.
EXTRACTION_TIMEOUT_SECONDS = 30

# How often to recycle the executor to reclaim slots leaked by hung threads.
_EXECUTOR_RECYCLE_INTERVAL_SECONDS = 3600  # 1 hour

# Module-level, long-lived executor — intentionally NOT used as a context
# manager.  When a pymupdf call hangs past EXTRACTION_TIMEOUT_SECONDS the
# gunicorn request thread returns immediately (future.result() raises
# TimeoutError) while the zombie worker thread stays parked inside the
# executor.  Python threads cannot be killed, so the slot is permanently
# consumed by each hung call, but with max_workers=4 the application can
# absorb 4 simultaneous hangs before new submissions queue rather than
# returning instantly.  The periodic recycle (see _start_recycle_loop) swaps
# in a fresh executor every hour so leaked slots can't accumulate indefinitely.
_extraction_executor = ThreadPoolExecutor(
    max_workers=4, thread_name_prefix="pdf_extract"
)

# Lock that serialises executor swaps and health reads.
_executor_lock = threading.Lock()

# Tracks when the current executor was created (monotonic seconds).
_executor_created_at = time.monotonic()  # type: float

# ── Slot-leak counter ──────────────────────────────────────────────────────
# Incremented (under _timeout_count_lock) each time a pymupdf call exceeds
# EXTRACTION_TIMEOUT_SECONDS.  Useful for health monitoring.
_timeout_count = 0  # type: int
_timeout_count_lock = threading.Lock()

# Guard so the recycle daemon thread is started at most once per process.
_recycle_thread_started = False
_recycle_thread_lock = threading.Lock()


def _recycle_executor() -> None:
    """Swap in a fresh executor and shut down the old one (no wait)."""
    global _extraction_executor, _executor_created_at
    new_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="pdf_extract")
    with _executor_lock:
        old_executor = _extraction_executor
        _extraction_executor = new_executor
        _executor_created_at = time.monotonic()
    # Shut down the old executor without blocking; any hung pymupdf threads
    # inside it will eventually finish on their own.
    old_executor.shutdown(wait=False)
    logger.info(
        "pdf_processor: executor recycled — old executor shut down (wait=False)"
    )


def _recycle_loop() -> None:
    """Daemon loop: recycle the executor every _EXECUTOR_RECYCLE_INTERVAL_SECONDS."""
    while True:
        time.sleep(_EXECUTOR_RECYCLE_INTERVAL_SECONDS)
        try:
            _recycle_executor()
        except Exception:
            logger.exception("pdf_processor: unexpected error during executor recycle")


def _start_recycle_loop() -> None:
    """Start the background recycle daemon thread exactly once per process."""
    global _recycle_thread_started
    if _recycle_thread_started:
        return
    with _recycle_thread_lock:
        if _recycle_thread_started:
            return
        t = threading.Thread(target=_recycle_loop, name="pdf_extract_recycler", daemon=True)
        t.start()
        _recycle_thread_started = True
        logger.debug("pdf_processor: executor recycle daemon thread started")


def get_extraction_health() -> Dict[str, Any]:
    """
    Return a snapshot of executor health for admin/monitoring endpoints.

    Keys:
        timeouts_total        — cumulative count of timed-out extractions
        executor_max_workers  — fixed capacity of the current executor
        next_recycle_in_seconds — approximate seconds until the next scheduled
                                  recycle (may be negative if a recycle is late)
    """
    with _timeout_count_lock:
        tc = _timeout_count
    with _executor_lock:
        created = _executor_created_at
    elapsed = time.monotonic() - created
    next_recycle = max(0.0, _EXECUTOR_RECYCLE_INTERVAL_SECONDS - elapsed)
    return {
        "timeouts_total": tc,
        "executor_max_workers": 4,
        "next_recycle_in_seconds": round(next_recycle),
    }


class PDFProcessor:
    def __init__(self):
        self.keywords_abstract = ['abstract', 'a b s t r a c t']
        self.keywords_title = ['title', 'research paper', 'article']
        self.min_text_length = 100

        # Cache for processed PDFs to avoid re-processing.
        # _cache_lock serialises all reads and writes; gunicorn runs multiple
        # threads per worker so unsynchronised dict access is a data race.
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_lock = threading.Lock()
        self._cache_max_size = 50

        # Optimization settings
        self.max_pages_to_process = 3  # Only process first 3 pages max

    def extract_text_from_pdf(self, pdf_path: str) -> Tuple[str, int]:
        """
        Extract text from PDF up to the abstract section.
        Returns extracted text and number of pages processed.

        Uses pymupdf only. Wrapped in a 30-second hard timeout so a
        malicious or corrupt PDF cannot hang the worker.
        """
        # Check cache first (lock because gunicorn threads share this object).
        file_hash = self._get_file_hash(pdf_path)
        with self._cache_lock:
            if file_hash in self._cache:
                logger.debug(f"Using cached result for {os.path.basename(pdf_path)}")
                cached_result = self._cache[file_hash]
                return cached_result['text'], cached_result['pages']

        # Ensure the background recycle daemon is running (lazy, once per process).
        _start_recycle_loop()

        # Re-read the module global each call so we always submit to the *current*
        # executor (never a locally-cached reference that may already be shut down).
        # The GIL ensures the pointer read is atomic.
        with _executor_lock:
            executor = _extraction_executor
            future = executor.submit(self._extract_with_pymupdf_full, pdf_path)
        try:
            text_content, pages_processed = future.result(
                timeout=EXTRACTION_TIMEOUT_SECONDS
            )
        except FuturesTimeoutError:
            future.cancel()  # no-op if already running; cleans up if still queued
            global _timeout_count
            with _timeout_count_lock:
                _timeout_count += 1
            logger.error(
                f"PDF extraction timed out after {EXTRACTION_TIMEOUT_SECONDS}s "
                f"for {os.path.basename(pdf_path)}"
            )
            return "", 0
        except Exception as e:
            logger.error(
                f"Error processing PDF {os.path.basename(pdf_path)}: {e}"
            )
            return "", 0

        if text_content and len(text_content.strip()) >= self.min_text_length:
            logger.info(
                f"pymupdf extracted {len(text_content)} chars from "
                f"{pages_processed} pages of {os.path.basename(pdf_path)}"
            )
            self._update_cache(file_hash, text_content, pages_processed)
            return text_content, pages_processed

        # Insufficient text — log a warning and return whatever we got.
        logger.warning(
            f"pymupdf returned insufficient text "
            f"({len((text_content or '').strip())} chars) for "
            f"{os.path.basename(pdf_path)}; returning partial result"
        )
        return text_content or "", pages_processed or 0

    def _extract_with_pymupdf_full(self, pdf_path: str) -> Tuple[str, int]:
        """Run the full pymupdf extraction (called inside the timeout-bound worker)."""
        return self._pymupdf_extraction(pdf_path)

    def _contains_abstract(self, text: str) -> bool:
        """Check if the page contains an abstract section."""
        text_lower = text.lower()
        for keyword in self.keywords_abstract:
            if keyword in text_lower:
                return True
        return False

    def _has_required_info(self, text: str) -> bool:
        """Check if the page has title and author information."""
        lines = text.split('\n')

        # Look for patterns that suggest title and author
        has_title = False
        has_author = False

        for line in lines[:10]:  # Check first 10 lines
            line = line.strip()
            if len(line) > 20 and len(line) < 200 and not line.lower().startswith(('abstract', 'introduction')):
                # Potential title
                if not has_title and self._is_likely_title(line):
                    has_title = True
                # Potential author (contains @ or University/College keywords)
                elif not has_author and self._is_likely_author(line):
                    has_author = True

        return has_title and has_author

    def _is_likely_title(self, line: str) -> bool:
        """Heuristic to identify if a line is likely a title."""
        # Title is usually title case and doesn't contain emails or URLs
        if re.search(r'[@\d\.]{3,}', line):
            return False

        # Check if most words are capitalized (title case)
        words = line.split()
        if len(words) < 3 or len(words) > 15:
            return False

        capitalized = sum(1 for w in words if w[0].isupper())
        return capitalized / len(words) > 0.6

    def _is_likely_author(self, line: str) -> bool:
        """Heuristic to identify if a line contains author information."""
        # Check for email, university, or typical author patterns
        author_patterns = [
            r'[\w\.-]+@[\w\.-]+\.\w+',  # Email
            r'university|college|institute|department',  # Institution
            r'^[A-Z][a-z]+ [A-Z][a-z]+,?'  # Name pattern
        ]

        for pattern in author_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                return True
        return False

    def _clean_text(self, text: str) -> str:
        """Clean extracted text by removing extra whitespace and artifacts."""
        # Remove excessive whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text)
        # Remove page markers
        text = re.sub(r'--- Page \d+ ---', '', text)
        # Clean up spaces
        text = re.sub(r' +', ' ', text)
        return text.strip()

    def _pymupdf_extraction(self, pdf_path: str) -> Tuple[str, int]:
        """Extract text using pymupdf (fitz). Sole extraction backend."""
        if not HAS_PYMUPDF:
            logger.error("pymupdf not installed; cannot extract PDF text")
            return "", 0

        text = ""
        pages_processed = 0

        try:
            doc = pymupdf.open(pdf_path)
            try:
                max_pages = min(self.max_pages_to_process, len(doc))

                for i in range(max_pages):
                    try:
                        page = doc[i]
                        page_text = page.get_text()

                        if page_text and page_text.strip():
                            page_text = page_text.replace('\x00', '')
                            text += f"\n--- Page {i+1} ---\n{page_text}\n"
                            pages_processed += 1

                            if self._contains_abstract(page_text) or len(page_text) > 500:
                                break

                    except Exception as page_error:
                        logger.warning(
                            f"pymupdf failed to extract page {i+1}: {page_error}"
                        )
                        continue
            finally:
                doc.close()

        except Exception as e:
            logger.error(f"pymupdf extraction failed: {e}")
            return "", 0

        if text:
            text = self._clean_text(text)

        return text, pages_processed

    def _get_file_hash(self, pdf_path: str) -> str:
        """Calculate SHA256 hash of PDF file for caching."""
        try:
            with open(pdf_path, 'rb') as f:
                # Only read first and last 1MB to generate hash efficiently
                file_size = os.path.getsize(pdf_path)
                hash_sha256 = hashlib.sha256()

                # Read first 1MB
                chunk = f.read(min(1024 * 1024, file_size))
                hash_sha256.update(chunk)

                # Read last 1MB if file is larger than 2MB
                if file_size > 2 * 1024 * 1024:
                    f.seek(-min(1024 * 1024, file_size), 2)
                    chunk = f.read()
                    hash_sha256.update(chunk)

                return hash_sha256.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating file hash: {e}")
            # Fallback to simple path-based hash
            return hashlib.md5(pdf_path.encode()).hexdigest()

    def _get_pdf_info(self, pdf_path: str) -> Optional[Dict[str, Any]]:
        """Get basic PDF info without full processing."""
        if not HAS_PYMUPDF:
            return None
        try:
            doc = pymupdf.open(pdf_path)
            try:
                return {
                    'pages': len(doc),
                    'encrypted': doc.is_encrypted,
                    'metadata': doc.metadata,
                }
            finally:
                doc.close()
        except Exception as e:
            logger.error(f"Error getting PDF info: {e}")
            return None

    def _update_cache(self, file_hash: str, text: str, pages: int):
        """Update PDF processing cache with LRU eviction (thread-safe)."""
        with self._cache_lock:
            # Remove oldest entry if cache is full
            if len(self._cache) >= self._cache_max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]

            self._cache[file_hash] = {
                'text': text,
                'pages': pages
            }

    def clear_cache(self):
        """Clear the PDF processing cache (thread-safe)."""
        with self._cache_lock:
            self._cache.clear()

    def validate_pdf(self, pdf_path: str) -> bool:
        """Validate if the file is a proper PDF with optimized checks."""
        try:
            # Quick check using file size and magic bytes
            file_size = os.path.getsize(pdf_path)
            if file_size < 100:  # PDFs are at least 100 bytes
                return False

            with open(pdf_path, 'rb') as file:
                # Check PDF magic bytes
                magic = file.read(4)
                if magic != b'%PDF':
                    return False

            # Quick page-count validation with pymupdf
            if not HAS_PYMUPDF:
                # Magic-byte check passed; no library available to verify pages
                logger.warning("pymupdf not available; skipping page-count validation")
                return True

            doc = pymupdf.open(pdf_path)
            try:
                return len(doc) > 0
            finally:
                doc.close()
        except Exception as e:
            logger.error(f"PDF validation error: {e}")
            return False
