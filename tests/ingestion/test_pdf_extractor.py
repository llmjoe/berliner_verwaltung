"""Tests for PDF text extraction."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from berliner_verwaltung.ingestion.pdf.extractor import extract_text_from_pdf


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """Create a minimal valid PDF for testing."""
    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R"
        b"/Resources<</Font<</F1 4 0 R>>>>"
        b"/Contents 5 0 R>>endobj\n"
        b"4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
        b"5 0 obj<</Length 44>>\nstream\n"
        b"BT /F1 12 Tf 100 700 Td (Testdokument) Tj ET\n"
        b"endstream\nendobj\n"
        b"xref\n0 6\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"0000000298 00000 n \n"
        b"0000000371 00000 n \n"
        b"trailer<</Size 6/Root 1 0 R>>\n"
        b"startxref\n466\n%%EOF"
    )
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(pdf_content)
    return pdf_path


def test_extract_returns_metadata(sample_pdf: Path) -> None:
    text, metadata = extract_text_from_pdf(sample_pdf)
    assert "page_count" in metadata
    assert "method" in metadata
    assert metadata["method"] == "pdfplumber"
    assert metadata["page_count"] >= 1
    assert isinstance(metadata["char_count"], int)


def test_extract_nonexistent_file() -> None:
    with pytest.raises(FileNotFoundError):
        extract_text_from_pdf(Path("/nonexistent/test.pdf"))


def test_extract_metadata_flags_ocr_need(tmp_path: Path) -> None:
    """When most pages are empty, needs_ocr should be True."""
    fake_pdf = tmp_path / "dummy.pdf"
    fake_pdf.write_bytes(b"x" * 1000)

    with patch("berliner_verwaltung.ingestion.pdf.extractor.pdfplumber") as mock_plumber:
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""
        mock_pdf.pages = [mock_page] * 5
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)
        mock_plumber.open.return_value = mock_pdf

        text, metadata = extract_text_from_pdf(fake_pdf)
        assert text == ""
        assert metadata["needs_ocr"] is True
        assert metadata["empty_pages"] == 5
