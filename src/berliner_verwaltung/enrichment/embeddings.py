"""Generate and store vector embeddings for semantic search.

Uses Ollama's bge-m3 model locally or falls back to OpenAI embeddings.
Stores 1024-dim vectors in the papers.embedding column (pgvector).
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berliner_verwaltung.config import settings
from berliner_verwaltung.db.models import File, Paper

logger = logging.getLogger(__name__)


async def embed_ollama(texts: list[str], model: str = "bge-m3") -> list[list[float]]:
    import ollama

    client = ollama.AsyncClient(host=settings.ollama_base_url)
    response = await client.embed(model=model, input=texts)
    return response["embeddings"]


async def embed_single_ollama(text: str, model: str = "bge-m3") -> list[float]:
    result = await embed_ollama([text], model)
    return result[0]


class EmbeddingPipeline:
    def __init__(
        self,
        session: AsyncSession,
        model: str = "bge-m3",
        batch_size: int = 10,
    ) -> None:
        self.session = session
        self.model = model
        self.batch_size = batch_size
        self.stats = {"embedded": 0, "skipped": 0, "errors": 0}

    async def get_papers_needing_embeddings(
        self, legislative_term: str | None = None, limit: int = 100
    ) -> list[Paper]:
        query = select(Paper).where(Paper.embedding.is_(None))
        if legislative_term:
            query = query.where(Paper.reference.like(f"%/{legislative_term}"))
        result = await self.session.execute(query.limit(limit))
        return list(result.scalars().all())

    async def _build_text(self, paper: Paper) -> str:
        parts = []
        if paper.name:
            parts.append(paper.name)
        if paper.reference:
            parts.append(paper.reference)
        if paper.paper_type:
            parts.append(paper.paper_type)

        result = await self.session.execute(
            select(File.text)
            .where(File.paper_id == paper.id)
            .where(File.text.isnot(None))
            .limit(1)
        )
        row = result.first()
        if row and row[0]:
            parts.append(row[0][:4000])

        return " ".join(parts)

    async def embed_batch(
        self, legislative_term: str | None = None, limit: int = 100
    ) -> dict[str, int]:
        papers = await self.get_papers_needing_embeddings(legislative_term, limit)
        logger.info("Embedding %d papers", len(papers))

        for i in range(0, len(papers), self.batch_size):
            batch = papers[i : i + self.batch_size]
            texts = []
            valid_papers = []

            for paper in batch:
                text = await self._build_text(paper)
                if len(text.strip()) < 10:
                    self.stats["skipped"] += 1
                    continue
                texts.append(text)
                valid_papers.append(paper)

            if not texts:
                continue

            try:
                embeddings = await embed_ollama(texts, self.model)
                for paper, embedding in zip(valid_papers, embeddings, strict=True):
                    paper.embedding = embedding
                    self.stats["embedded"] += 1
                await self.session.flush()
            except Exception as e:
                logger.warning("Embedding batch failed: %s", e)
                self.stats["errors"] += len(texts)

            if (i + self.batch_size) % 50 == 0:
                logger.info("Embedding progress: %d/%d", i + self.batch_size, len(papers))

        logger.info(
            "Embedding done: %d embedded, %d skipped, %d errors",
            self.stats["embedded"],
            self.stats["skipped"],
            self.stats["errors"],
        )
        return self.stats

    async def semantic_search(
        self, query: str, limit: int = 20
    ) -> list[dict]:
        query_embedding = await embed_single_ollama(query, self.model)

        result = await self.session.execute(
            select(
                Paper.id,
                Paper.oparl_id,
                Paper.name,
                Paper.reference,
                Paper.paper_type,
                Paper.date,
                Paper.embedding.cosine_distance(query_embedding).label("distance"),
            )
            .where(Paper.embedding.isnot(None))
            .order_by("distance")
            .limit(limit)
        )

        return [
            {
                "id": r.id,
                "oparl_id": r.oparl_id,
                "name": r.name,
                "reference": r.reference,
                "paper_type": r.paper_type,
                "date": str(r.date) if r.date else None,
                "similarity": 1.0 - float(r.distance),
            }
            for r in result.all()
        ]
