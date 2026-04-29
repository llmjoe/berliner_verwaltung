"""Extract text from PDF files using pdfplumber.

Pipeline: pdfplumber (primary) -> empty-page detection -> store in DB.
Future: qwen2.5vl OCR fallback for scanned documents.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pdfplumber
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berliner_verwaltung.db.models import File, Paper

logger = logging.getLogger(__name__)

MIN_CHARS_PER_PAGE = 20


MAX_PAGES = 200
MAX_FILE_SIZE_MB = 20


def extract_text_from_pdf(pdf_path: Path) -> tuple[str, dict]:
    """Extract text from a PDF file. Returns (text, metadata).

    metadata contains: page_count, extracted_pages, empty_pages, method.
    Skips files > MAX_FILE_SIZE_MB and caps at MAX_PAGES pages.
    """
    file_size_mb = pdf_path.stat().st_size / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        return "", {
            "page_count": 0, "extracted_pages": 0, "empty_pages": 0,
            "method": "skipped", "char_count": 0, "needs_ocr": False,
            "skip_reason": f"file too large ({file_size_mb:.1f}MB)",
        }

    text_parts: list[str] = []
    empty_pages = 0
    extracted_pages = 0

    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages[:MAX_PAGES]:
            page_text = page.extract_text() or ""
            if len(page_text.strip()) < MIN_CHARS_PER_PAGE:
                empty_pages += 1
            else:
                text_parts.append(page_text)
                extracted_pages += 1

    full_text = "\n\n".join(text_parts).strip()

    metadata = {
        "page_count": page_count,
        "extracted_pages": extracted_pages,
        "empty_pages": empty_pages,
        "method": "pdfplumber",
        "char_count": len(full_text),
        "needs_ocr": empty_pages > page_count * 0.5 and page_count > 0,
    }

    return full_text, metadata


class PdfExtractor:
    def __init__(
        self,
        session: AsyncSession,
        pdf_dir: Path = Path("data/pdfs"),
        legislative_term: str | None = None,
    ) -> None:
        self.session = session
        self.pdf_dir = pdf_dir
        self.legislative_term = legislative_term
        self.stats = {"extracted": 0, "empty": 0, "needs_ocr": 0, "errors": 0, "skipped": 0}

    async def get_files_needing_extraction(self, limit: int = 100) -> list[File]:
        query = (
            select(File)
            .where(File.mime_type == "application/pdf")
            .where(File.text.is_(None))
        )
        if self.legislative_term:
            query = query.join(Paper, File.paper_id == Paper.id).where(
                Paper.reference.like(f"%/{self.legislative_term}")
            )
        result = await self.session.execute(query.limit(limit))
        return list(result.scalars().all())

    def _pdf_path(self, file_id: int) -> Path:
        return self.pdf_dir / f"{file_id}.pdf"

    async def extract_one(self, file: File) -> str | None:
        pdf_path = self._pdf_path(file.id)
        if not pdf_path.exists():
            self.stats["skipped"] += 1
            return None

        try:
            text, metadata = extract_text_from_pdf(pdf_path)

            if not text:
                self.stats["empty"] += 1
                logger.debug(
                    "File %d: no text extracted (%d pages)", file.id, metadata["page_count"]
                )
                if metadata["needs_ocr"]:
                    self.stats["needs_ocr"] += 1
                return None

            file.text = text
            existing = file.data or {}
            file.data = {**existing, "extraction": metadata}
            self.stats["extracted"] += 1
            return text

        except Exception as e:
            logger.warning("File %d extraction failed: %s", file.id, e)
            self.stats["errors"] += 1
            return None

    async def extract_batch(self, limit: int = 100, chunk_size: int = 25) -> dict[str, int]:
        processed = 0
        while processed < limit:
            files = await self.get_files_needing_extraction(chunk_size)
            if not files:
                break
            if processed == 0:
                logger.info("Starting extraction (chunk_size=%d, limit=%d)", chunk_size, limit)

            for file in files:
                await self.extract_one(file)
                processed += 1

            await self.session.commit()
            logger.info("Progress: %d files processed so far", processed)

        logger.info(
            "Extraction done: %d extracted, %d empty, %d need OCR, %d errors, %d skipped",
            self.stats["extracted"],
            self.stats["empty"],
            self.stats["needs_ocr"],
            self.stats["errors"],
            self.stats["skipped"],
        )
        return self.stats
