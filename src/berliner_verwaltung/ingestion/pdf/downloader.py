"""Download PDF files referenced in the OParl files table.

Stores PDFs locally in data/pdfs/{file_id}.pdf. Tracks download status
in the database to enable incremental downloads.
"""

from __future__ import annotations

import logging
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berliner_verwaltung.db.models import File, Paper

logger = logging.getLogger(__name__)

USER_AGENT = (
    "BerlinerVerwaltungsdaten/0.1 "
    "(+https://github.com/llmjoe/berliner_verwaltung; "
    "Mozilla/5.0 compatible)"
)


class PdfDownloader:
    def __init__(
        self,
        session: AsyncSession,
        output_dir: Path = Path("data/pdfs"),
        timeout: float = 60.0,
        max_size_mb: float = 50.0,
        legislative_term: str | None = None,
    ) -> None:
        self.session = session
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_size = int(max_size_mb * 1024 * 1024)
        self.legislative_term = legislative_term
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
        self.stats = {"downloaded": 0, "skipped": 0, "errors": 0}

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> PdfDownloader:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    def _file_path(self, file_id: int) -> Path:
        return self.output_dir / f"{file_id}.pdf"

    async def get_pending_files(self, limit: int = 100) -> list[File]:
        query = (
            select(File)
            .where(File.mime_type == "application/pdf")
            .where(File.text.is_(None))
            .where(File.download_url.isnot(None) | File.access_url.isnot(None))
        )
        if self.legislative_term:
            query = query.join(Paper, File.paper_id == Paper.id).where(
                Paper.reference.like(f"%/{self.legislative_term}")
            )
        result = await self.session.execute(query.limit(limit))
        return list(result.scalars().all())

    async def download_one(self, file: File) -> Path | None:
        pdf_path = self._file_path(file.id)
        if pdf_path.exists():
            self.stats["skipped"] += 1
            return pdf_path

        url = file.download_url or file.access_url
        if not url:
            self.stats["skipped"] += 1
            return None

        try:
            response = await self._client.get(url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            if "pdf" not in content_type and response.content[:5] != b"%PDF-":
                logger.warning("File %d: expected PDF, got %s", file.id, content_type)
                self.stats["errors"] += 1
                return None

            if len(response.content) > self.max_size:
                logger.warning(
                    "File %d: %.1f MB exceeds limit", file.id, len(response.content) / 1e6
                )
                self.stats["skipped"] += 1
                return None

            pdf_path.write_bytes(response.content)
            self.stats["downloaded"] += 1
            logger.debug("Downloaded file %d (%d bytes)", file.id, len(response.content))
            return pdf_path

        except (httpx.HTTPStatusError, httpx.TransportError) as e:
            logger.warning("File %d download failed: %s", file.id, e)
            self.stats["errors"] += 1
            return None

    async def download_batch(self, limit: int = 100) -> dict[str, int]:
        files = await self.get_pending_files(limit)
        logger.info("Found %d PDF files to download", len(files))

        for file in files:
            await self.download_one(file)

            total = self.stats["downloaded"] + self.stats["skipped"] + self.stats["errors"]
            if total % 50 == 0:
                logger.info("Download progress: %d processed", total)

        logger.info(
            "Download batch done: %d downloaded, %d skipped, %d errors",
            self.stats["downloaded"],
            self.stats["skipped"],
            self.stats["errors"],
        )
        return self.stats
