"""Build full-text search index (tsvector) for papers from extracted PDF text.

Updates the papers.search_vector column using PostgreSQL's to_tsvector
with 'german' configuration. Combines paper name, reference, and all
associated file texts into one searchable vector.
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from berliner_verwaltung.db.models import File, Paper

logger = logging.getLogger(__name__)


class SearchIndexer:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.stats = {"indexed": 0, "skipped": 0}

    async def index_paper(self, paper: Paper) -> bool:
        """Build search vector for a single paper from its files' text."""
        result = await self.session.execute(
            select(File.text).where(File.paper_id == paper.id).where(File.text.isnot(None))
        )
        file_texts = [row[0] for row in result.all()]

        parts = []
        if paper.name:
            parts.append(paper.name)
        if paper.reference:
            parts.append(paper.reference)
        parts.extend(file_texts)

        if not parts:
            self.stats["skipped"] += 1
            return False

        combined = " ".join(parts)

        await self.session.execute(
            update(Paper)
            .where(Paper.id == paper.id)
            .values(search_vector=func.to_tsvector(text("'german'"), combined))
        )
        self.stats["indexed"] += 1
        return True

    async def index_all(self, limit: int = 500) -> dict[str, int]:
        """Index papers that have file text but no search vector yet."""
        result = await self.session.execute(
            select(Paper)
            .where(Paper.search_vector.is_(None))
            .where(
                Paper.id.in_(
                    select(File.paper_id).where(File.text.isnot(None)).distinct()
                )
            )
            .limit(limit)
        )
        papers = list(result.scalars().all())
        logger.info("Found %d papers to index", len(papers))

        for paper in papers:
            await self.index_paper(paper)

        await self.session.flush()

        logger.info(
            "Indexing done: %d indexed, %d skipped",
            self.stats["indexed"],
            self.stats["skipped"],
        )
        return self.stats

    async def search(self, query: str, limit: int = 20) -> list[dict]:
        """Full-text search across indexed papers."""
        result = await self.session.execute(
            select(
                Paper.id,
                Paper.oparl_id,
                Paper.name,
                Paper.reference,
                Paper.paper_type,
                Paper.date,
                func.ts_rank(Paper.search_vector, func.plainto_tsquery(text("'german'"), query)).label(
                    "rank"
                ),
                func.ts_headline(
                    text("'german'"),
                    Paper.name,
                    func.plainto_tsquery(text("'german'"), query),
                    text("'MaxWords=30, MinWords=10, StartSel=**, StopSel=**'"),
                ).label("headline"),
            )
            .where(Paper.search_vector.op("@@")(func.plainto_tsquery(text("'german'"), query)))
            .order_by(text("rank DESC"))
            .limit(limit)
        )
        rows = result.all()
        return [
            {
                "id": r.id,
                "oparl_id": r.oparl_id,
                "name": r.name,
                "reference": r.reference,
                "paper_type": r.paper_type,
                "date": str(r.date) if r.date else None,
                "rank": float(r.rank),
                "headline": r.headline,
            }
            for r in rows
        ]
