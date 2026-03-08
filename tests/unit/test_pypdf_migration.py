"""
SPEC-MAINT-001: PyPDF2 to pypdf migration tests.

RED phase: These tests define the expected state after migration.
They verify pypdf is the installed library and PyPDF2 is removed.
"""

import sys
import importlib
import pytest


class TestPypdfInstalled:
    """Verify pypdf is the installed PDF library (REQ-1, REQ-2)."""

    def test_pypdf_can_be_imported(self):
        """pypdf must be importable after migration."""
        import pypdf
        assert pypdf is not None

    def test_pypdf_pdfreader_available(self):
        """pypdf.PdfReader must be accessible."""
        import pypdf
        assert hasattr(pypdf, "PdfReader")

    def test_pypdf_version_is_4_or_higher(self):
        """pypdf version must be 4.0.0 or higher (per requirements.txt spec)."""
        import pypdf
        version_parts = pypdf.__version__.split(".")
        major = int(version_parts[0])
        assert major >= 4, f"Expected pypdf >= 4.0.0, got {pypdf.__version__}"


class TestPdfProcessorUsesPypdf:
    """Verify pdf_processor.py uses pypdf instead of PyPDF2 (REQ-2, REQ-6)."""

    def test_pdf_processor_imports_pypdf_not_pypdf2(self):
        """pdf_processor module must import pypdf, not PyPDF2."""
        # Force fresh import to avoid cached module
        if "backend.services.pdf_processor" in sys.modules:
            del sys.modules["backend.services.pdf_processor"]

        import backend.services.pdf_processor as processor_module
        source_file = processor_module.__file__

        with open(source_file, "r") as f:
            source = f.read()

        assert "import pypdf" in source, "pdf_processor.py must contain 'import pypdf'"
        assert "import PyPDF2" not in source, "pdf_processor.py must not contain 'import PyPDF2'"

    def test_pdf_processor_has_no_pypdf2_references(self):
        """pdf_processor.py must have no remaining PyPDF2 references."""
        import backend.services.pdf_processor as processor_module
        source_file = processor_module.__file__

        with open(source_file, "r") as f:
            source = f.read()

        assert "PyPDF2" not in source, (
            "pdf_processor.py must not contain any 'PyPDF2' references"
        )


class TestCharacterizationPdfProcessorFallback:
    """Characterization tests: capture fallback PDF extraction behavior (REQ-5)."""

    def test_pdf_processor_can_be_instantiated(self):
        """PDFProcessor can be created without errors after migration."""
        from backend.services.pdf_processor import PDFProcessor
        processor = PDFProcessor()
        assert processor is not None

    def test_fallback_extraction_returns_tuple(self, tmp_path, mocker):
        """_fallback_extraction returns (str, int) tuple on error path."""
        from backend.services.pdf_processor import PDFProcessor

        processor = PDFProcessor()

        # Create a minimal valid-looking but empty PDF that triggers fallback
        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4\n")

        # Call the fallback method directly; expect graceful (empty, 0) on failure
        text, pages = processor._fallback_extraction(str(fake_pdf))
        assert isinstance(text, str)
        assert isinstance(pages, int)

    def test_get_pdf_info_returns_none_on_invalid_pdf(self, tmp_path):
        """_get_pdf_info returns None for invalid/minimal PDF files."""
        from backend.services.pdf_processor import PDFProcessor

        processor = PDFProcessor()
        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.write_bytes(b"not a pdf")

        result = processor._get_pdf_info(str(fake_pdf))
        assert result is None

    def test_validate_pdf_returns_false_for_non_pdf(self, tmp_path):
        """validate_pdf returns False for non-PDF bytes."""
        from backend.services.pdf_processor import PDFProcessor

        processor = PDFProcessor()
        fake_file = tmp_path / "test.txt"
        fake_file.write_bytes(b"not a pdf file")

        result = processor.validate_pdf(str(fake_file))
        assert result is False

    def test_fallback_with_mocked_pdfreader(self, tmp_path, mocker):
        """_fallback_extraction uses pypdf.PdfReader (not PyPDF2.PdfReader)."""
        import pypdf
        from backend.services.pdf_processor import PDFProcessor

        processor = PDFProcessor()

        # Mock pypdf.PdfReader to verify it is called
        mock_page = mocker.MagicMock()
        mock_page.extract_text.return_value = "Abstract: Test content for the paper."

        mock_reader = mocker.MagicMock()
        mock_reader.pages = [mock_page]

        # Patch pypdf.PdfReader at the module level where it is used
        mocker.patch("pypdf.PdfReader", return_value=mock_reader)

        # Need a real file to open (the method uses open())
        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")

        text, pages = processor._fallback_extraction(str(fake_pdf))

        # Verify pypdf.PdfReader was called (not PyPDF2)
        assert pypdf.PdfReader.called  # type: ignore[attr-defined]
        assert isinstance(text, str)
        assert isinstance(pages, int)
