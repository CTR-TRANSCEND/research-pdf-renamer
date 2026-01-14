import PyPDF2
import pdfplumber
import re
import hashlib
import os
from typing import List, Tuple, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

# Configure logging
logger = logging.getLogger(__name__)

class PDFProcessor:
    def __init__(self):
        self.keywords_abstract = ['abstract', 'a b s t r a c t']
        self.keywords_title = ['title', 'research paper', 'article']
        self.min_text_length = 100

        # Cache for processed PDFs to avoid re-processing
        self._cache = {}
        self._cache_max_size = 50

        # Optimization settings
        self.max_pages_to_process = 3  # Only process first 3 pages max
        self.use_parallel_processing = True  # Use parallel processing for multi-page PDFs
        self.text_chunk_size = 4096  # Process text in chunks to reduce memory usage

    def extract_text_from_pdf(self, pdf_path: str) -> Tuple[str, int]:
        """
        Extract text from PDF up to the abstract section.
        Returns extracted text and number of pages processed.
        Optimized with caching, parallel processing, and early termination.
        """
        # Check cache first
        file_hash = self._get_file_hash(pdf_path)
        if file_hash in self._cache:
            logger.debug(f"Using cached result for {os.path.basename(pdf_path)}")
            cached_result = self._cache[file_hash]
            return cached_result['text'], cached_result['pages']

        text_content = ""
        pages_processed = 0
        found_abstract = False
        found_required_info = False

        try:
            # Get PDF info first to optimize processing
            pdf_info = self._get_pdf_info(pdf_path)
            if not pdf_info or pdf_info['pages'] == 0:
                return "", 0

            # Use optimized extraction strategy based on PDF characteristics
            if pdf_info['pages'] == 1 or not self.use_parallel_processing:
                # Sequential processing for single page or when parallel is disabled
                text_content, pages_processed, found_abstract, found_required_info = self._extract_sequential(pdf_path)
            else:
                # Parallel processing for multi-page PDFs
                text_content, pages_processed, found_abstract, found_required_info = self._extract_parallel(pdf_path)

            # Clean up the text
            text_content = self._clean_text(text_content)

            # Cache the result
            self._update_cache(file_hash, text_content, pages_processed)

            return text_content, pages_processed

        except Exception as e:
            logger.error(f"Error processing PDF {os.path.basename(pdf_path)}: {e}")
            # Fallback to PyPDF2 if pdfplumber fails
            return self._fallback_extraction(pdf_path)

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

    def _fallback_extraction(self, pdf_path: str) -> Tuple[str, int]:
        """Fallback method using PyPDF2 with enhanced error handling."""
        text = ""
        pages_processed = 0

        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)

                # Extract first 3 pages (more than before for better coverage)
                max_pages = min(3, len(pdf_reader.pages))

                for i in range(max_pages):
                    try:
                        page = pdf_reader.pages[i]
                        page_text = page.extract_text()

                        # Only add page text if it contains actual content
                        if page_text and page_text.strip():
                            # Clean up common PyPDF2 artifacts
                            page_text = page_text.replace('\x00', '')  # Remove null bytes
                            page_text = page_text.replace('\n\n', '\n')  # Reduce excessive newlines

                            text += f"\n--- Page {i+1} ---\n{page_text}\n"
                            pages_processed += 1

                            # Stop if we find abstract or sufficient content
                            if self._contains_abstract(page_text) or len(page_text) > 500:
                                break

                    except Exception as page_error:
                        logger.warning(f"PyPDF2 failed to extract page {i+1}: {page_error}")
                        continue

        except Exception as e:
            logger.error(f"PyPDF2 fallback extraction failed: {e}")
            return "", 0

        # Clean up the final text
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
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                return {
                    'pages': len(pdf_reader.pages),
                    'encrypted': pdf_reader.is_encrypted,
                    'metadata': pdf_reader.metadata
                }
        except Exception as e:
            logger.error(f"Error getting PDF info: {e}")
            return None

    def _extract_sequential(self, pdf_path: str) -> Tuple[str, int, bool, bool]:
        """Extract text sequentially from PDF pages with PyPDF2 fallback."""
        text_content = ""
        pages_processed = 0
        found_abstract = False
        found_required_info = False

        # First try pdfplumber with comprehensive fallbacks
        with pdfplumber.open(pdf_path) as pdf:
            # Limit processing to first few pages for performance
            max_pages = min(self.max_pages_to_process, len(pdf.pages))

            for i in range(max_pages):
                page = pdf.pages[i]
                # Use robust text extraction with fallbacks
                page_text = self._extract_page_text(page, i)

                if not page_text or page_text.strip() == "":
                    logger.debug(f"No text found on page {i+1} with pdfplumber")
                    continue

                text_content += f"\n--- Page {i+1} ---\n{page_text}\n"
                pages_processed += 1

                # Early termination checks
                if self._contains_abstract(page_text):
                    found_abstract = True
                    break

                if i == 0:
                    found_required_info = self._has_required_info(page_text)
                elif i == 1 and not found_required_info:
                    # Continue to second page if first didn't have required info
                    continue
                elif i >= 1:
                    # Stop after second page if we still don't have what we need
                    break

        # If pdfplumber failed completely or got minimal text, try PyPDF2
        if pages_processed == 0 or len(text_content.strip()) < 100:
            logger.warning(f"pdfplumber extraction was insufficient, trying PyPDF2 fallback")
            fallback_text, fallback_pages = self._fallback_extraction(pdf_path)

            if fallback_text and len(fallback_text.strip()) > len(text_content.strip()):
                text_content = fallback_text
                pages_processed = fallback_pages
                logger.info(f"PyPDF2 fallback extracted {len(fallback_text)} characters from {fallback_pages} pages")
            else:
                logger.warning("PyPDF2 fallback also failed or produced less text")

        return text_content, pages_processed, found_abstract, found_required_info

    def _extract_parallel(self, pdf_path: str) -> Tuple[str, int, bool, bool]:
        """Extract text from multiple pages in parallel."""
        text_content = ""
        pages_processed = 0
        found_abstract = False
        found_required_info = False

        with pdfplumber.open(pdf_path) as pdf:
            # Limit processing to first few pages for performance
            max_pages = min(self.max_pages_to_process, len(pdf.pages))

            # Process pages in parallel, but maintain order for results
            with ThreadPoolExecutor(max_workers=min(3, max_pages)) as executor:
                # Submit page extraction tasks
                future_to_page = {
                    executor.submit(self._extract_page_text, page, i): i
                    for i, page in enumerate(pdf.pages[:max_pages])
                }

                # Collect results in order
                page_results = []
                for future in as_completed(future_to_page):
                    page_idx = future_to_page[future]
                    try:
                        page_text = future.result(timeout=10)  # 10 second timeout per page
                        if page_text:
                            page_results.append((page_idx, page_text))
                    except Exception as e:
                        logger.error(f"Error extracting page {page_idx + 1}: {e}")
                        continue

                # Sort results by page index to maintain order
                page_results.sort(key=lambda x: x[0])

                # Process results in order
                for page_idx, page_text in page_results:
                    text_content += f"\n--- Page {page_idx+1} ---\n{page_text}\n"
                    pages_processed += 1

                    # Early termination checks
                    if self._contains_abstract(page_text):
                        found_abstract = True
                        break

                    if page_idx == 0:
                        found_required_info = self._has_required_info(page_text)
                    elif page_idx == 1 and not found_required_info:
                        continue
                    elif page_idx >= 1:
                        break

        return text_content, pages_processed, found_abstract, found_required_info

    def _extract_page_text(self, page, page_idx: int) -> Optional[str]:
        """Extract text from a single page with comprehensive fallback options."""
        # First try basic extraction (most compatible)
        try:
            text = page.extract_text()
            if text and text.strip():
                return text
        except Exception as e:
            logger.warning(f"Basic text extraction failed for page {page_idx + 1}: {e}")

        # Try with optimized settings as second option
        try:
            settings = {
                "vertical_strategy": "text",
                "horizontal_strategy": "text",
                "keep_blank_chars": False
            }
            text = page.extract_text(settings=settings)
            if text and text.strip():
                return text
        except Exception as e:
            logger.warning(f"Optimized text extraction failed for page {page_idx + 1}: {e}")

        # Try with minimal settings as third option
        try:
            settings = {
                "layout": True,
                "x_tolerance": 1,
                "y_tolerance": 1
            }
            text = page.extract_text(settings=settings)
            if text and text.strip():
                return text
        except Exception as e:
            logger.warning(f"Layout-based extraction failed for page {page_idx + 1}: {e}")

        # Try with basic x/y settings
        try:
            text = page.extract_text(x_tolerance=1, y_tolerance=1)
            if text and text.strip():
                return text
        except Exception as e:
            logger.warning(f"X/Y tolerance extraction failed for page {page_idx + 1}: {e}")

        # Try with different strategy
        try:
            settings = {
                "vertical_strategy": "explicit",
                "horizontal_strategy": "explicit",
                "explicit_vertical_lines": [],
                "explicit_horizontal_lines": []
            }
            text = page.extract_text(settings=settings)
            if text and text.strip():
                return text
        except Exception as e:
            logger.warning(f"Explicit strategy extraction failed for page {page_idx + 1}: {e}")

        logger.error(f"All pdfplumber extraction methods failed for page {page_idx + 1}")
        return None

    def _update_cache(self, file_hash: str, text: str, pages: int):
        """Update PDF processing cache with LRU eviction."""
        # Remove oldest entry if cache is full
        if len(self._cache) >= self._cache_max_size:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]

        self._cache[file_hash] = {
            'text': text,
            'pages': pages
        }

    def clear_cache(self):
        """Clear the PDF processing cache."""
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

                # Quick validation with PyPDF2
                file.seek(0)
                pdf_reader = PyPDF2.PdfReader(file)
                return len(pdf_reader.pages) > 0
        except Exception as e:
            logger.error(f"PDF validation error: {e}")
            return False