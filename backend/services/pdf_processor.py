import PyPDF2
import pdfplumber
import re
from typing import List, Tuple, Optional

class PDFProcessor:
    def __init__(self):
        self.keywords_abstract = ['abstract', 'a b s t r a c t']
        self.keywords_title = ['title', 'research paper', 'article']
        self.min_text_length = 100

    def extract_text_from_pdf(self, pdf_path: str) -> Tuple[str, int]:
        """
        Extract text from PDF up to the abstract section.
        Returns extracted text and number of pages processed.
        """
        text_content = ""
        pages_processed = 0

        try:
            with pdfplumber.open(pdf_path) as pdf:
                # First, check first page for title, author, and abstract
                for i, page in enumerate(pdf.pages):
                    page_text = page.extract_text()

                    if not page_text:
                        continue

                    text_content += f"\n--- Page {i+1} ---\n{page_text}\n"
                    pages_processed += 1

                    # Check if we have found the abstract
                    if self._contains_abstract(page_text):
                        break

                    # If first page doesn't have abstract, check second
                    if i == 0 and not self._has_required_info(page_text):
                        continue
                    elif i == 1:
                        break
                    elif i > 0:
                        break

            # Clean up the text
            text_content = self._clean_text(text_content)

            return text_content, pages_processed

        except Exception as e:
            print(f"Error processing PDF: {e}")
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
        """Fallback method using PyPDF2."""
        text = ""
        pages_processed = 0

        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)

                # Extract first 2 pages
                for i in range(min(2, len(pdf_reader.pages))):
                    page = pdf_reader.pages[i]
                    text += page.extract_text() + "\n"
                    pages_processed += 1

                    # Stop if we find abstract
                    if self._contains_abstract(text):
                        break

        except Exception as e:
            print(f"Fallback extraction failed: {e}")
            return "", 0

        return text.strip(), pages_processed

    def validate_pdf(self, pdf_path: str) -> bool:
        """Validate if the file is a proper PDF."""
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                return len(pdf_reader.pages) > 0
        except:
            return False