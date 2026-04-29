"""LLM-based topic classification for BVV Drucksachen.

Two-stage approach:
1. Fast keyword pre-classification (no LLM cost)
2. LLM refinement for ambiguous cases or when keyword confidence is low

The classifier stores results with confidence scores and method attribution.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berliner_verwaltung.db.models import File, Paper
from berliner_verwaltung.enrichment.taxonomy import TAXONOMY, keyword_classify

logger = logging.getLogger(__name__)

CLASSIFICATION_PROMPT = """Du klassifizierst Drucksachen der BVV Friedrichshain-Kreuzberg.

Gegeben ist der Titel und ggf. der Volltext einer Drucksache. Ordne sie einem oder mehreren
der folgenden Themen zu. Antworte ausschliesslich im JSON-Format.

Themen:
{topics}

Drucksache:
Titel: {title}
Typ: {paper_type}
{text_section}

Antworte NUR mit diesem JSON-Format:
{{
  "topics": [
    {{"code": "THEMEN_CODE", "confidence": 0.0-1.0, "reason": "kurze Begruendung"}}
  ],
  "summary": "Ein-Satz-Zusammenfassung der Drucksache"
}}
"""


@dataclass
class ClassificationResult:
    paper_id: int
    topics: list[dict[str, Any]]
    summary: str
    method: str
    confidence: float


def build_classification_prompt(
    title: str, paper_type: str | None, text: str | None
) -> str:
    topics_str = "\n".join(f"- {t.code}: {t.name}" for t in TAXONOMY)
    text_section = f"Text (Auszug):\n{text[:2000]}" if text else "Kein Volltext verfuegbar."
    return CLASSIFICATION_PROMPT.format(
        topics=topics_str,
        title=title,
        paper_type=paper_type or "unbekannt",
        text_section=text_section,
    )


class PaperClassifier:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.stats = {"classified": 0, "skipped": 0, "errors": 0}

    async def get_unclassified_papers(
        self, legislative_term: str | None = None, limit: int = 100
    ) -> list[Paper]:
        query = select(Paper).where(
            Paper.data["classification"].is_(None)
            | ~Paper.data.has_key("classification")  # noqa: W601
        )
        if legislative_term:
            query = query.where(Paper.reference.like(f"%/{legislative_term}"))
        result = await self.session.execute(query.limit(limit))
        return list(result.scalars().all())

    async def _get_paper_text(self, paper_id: int) -> str | None:
        result = await self.session.execute(
            select(File.text)
            .where(File.paper_id == paper_id)
            .where(File.text.isnot(None))
            .limit(1)
        )
        row = result.first()
        return row[0] if row else None

    async def classify_keyword(self, paper: Paper) -> ClassificationResult | None:
        search_text = paper.name or ""
        file_text = await self._get_paper_text(paper.id)
        if file_text:
            search_text += " " + file_text[:5000]

        matches = keyword_classify(search_text)
        if not matches:
            return None

        top_code, top_count = matches[0]
        confidence = min(top_count / 5.0, 1.0)

        topics = [
            {"code": code, "confidence": min(count / 5.0, 1.0), "reason": "keyword match"}
            for code, count in matches[:3]
        ]

        return ClassificationResult(
            paper_id=paper.id,
            topics=topics,
            summary="",
            method="keyword",
            confidence=confidence,
        )

    async def classify_batch_keywords(
        self, legislative_term: str | None = None, limit: int = 100
    ) -> dict[str, int]:
        papers = await self.get_unclassified_papers(legislative_term, limit)
        logger.info("Classifying %d papers via keywords", len(papers))

        for paper in papers:
            try:
                result = await self.classify_keyword(paper)
                if result and result.topics:
                    existing = paper.data or {}
                    paper.data = {
                        **existing,
                        "classification": {
                            "topics": result.topics,
                            "summary": result.summary,
                            "method": result.method,
                            "confidence": result.confidence,
                        },
                    }
                    self.stats["classified"] += 1
                else:
                    self.stats["skipped"] += 1
            except Exception as e:
                logger.warning("Classification failed for paper %d: %s", paper.id, e)
                self.stats["errors"] += 1

        await self.session.flush()
        logger.info(
            "Classification done: %d classified, %d skipped, %d errors",
            self.stats["classified"],
            self.stats["skipped"],
            self.stats["errors"],
        )
        return self.stats
