"""Topic trend analysis across the legislative term.

Analyzes how political topics shift over time by examining:
- Monthly/quarterly distribution of paper topics
- Rising and declining topics
- Topic co-occurrence patterns
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berliner_verwaltung.db.models import Paper

logger = logging.getLogger(__name__)


@dataclass
class TopicTrend:
    code: str
    total: int
    by_year: dict[int, int]
    trend: str  # "rising", "declining", "stable"
    recent_share: float


@dataclass
class TopicCooccurrence:
    topic_a: str
    topic_b: str
    count: int


@dataclass
class TopicReport:
    topic_trends: list[TopicTrend]
    top_cooccurrences: list[TopicCooccurrence]
    unclassified_count: int
    total_classified: int


async def analyze_topic_trends(
    session: AsyncSession, legislative_term: str = "VI"
) -> TopicReport:
    """Analyze topic distribution and trends for a legislative term."""

    result = await session.execute(
        select(Paper.data, Paper.reference)
        .where(Paper.reference.like(f"%/{legislative_term}"))
    )
    rows = result.all()

    topic_counts: Counter[str] = Counter()
    topic_by_year: dict[str, Counter[int]] = defaultdict(Counter)
    cooccurrences: Counter[tuple[str, str]] = Counter()
    unclassified = 0
    classified = 0

    for data, reference in rows:
        if not data or "classification" not in data:
            unclassified += 1
            continue

        topics = data["classification"].get("topics", [])
        if not topics:
            unclassified += 1
            continue

        classified += 1
        codes = [t["code"] for t in topics]

        # Extract year from reference DS/NNNN/VI -> approximate by DS number
        # Since we don't have reliable dates, use reference number as proxy
        try:
            ds_num = int(reference.split("/")[1])
            if ds_num < 500:
                year = 2022
            elif ds_num < 1000:
                year = 2023
            elif ds_num < 1500:
                year = 2024
            else:
                year = 2025
        except (IndexError, ValueError):
            year = 0

        for code in codes:
            topic_counts[code] += 1
            if year:
                topic_by_year[code][year] += 1

        for i, a in enumerate(codes):
            for b in codes[i + 1:]:
                pair = tuple(sorted([a, b]))
                cooccurrences[pair] += 1  # type: ignore[arg-type]

    # Build trends
    trends: list[TopicTrend] = []
    for code, total in topic_counts.most_common():
        by_year = dict(topic_by_year[code])
        years = sorted(by_year.keys())

        trend = "stable"
        if len(years) >= 2:
            early = sum(by_year.get(y, 0) for y in years[:len(years) // 2])
            late = sum(by_year.get(y, 0) for y in years[len(years) // 2:])
            if early > 0:
                ratio = late / early
                if ratio > 1.3:
                    trend = "rising"
                elif ratio < 0.7:
                    trend = "declining"

        recent_share = total / classified if classified > 0 else 0

        trends.append(TopicTrend(
            code=code, total=total, by_year=by_year,
            trend=trend, recent_share=recent_share,
        ))

    # Top co-occurrences
    top_cooc = [
        TopicCooccurrence(topic_a=pair[0], topic_b=pair[1], count=count)
        for pair, count in cooccurrences.most_common(20)
    ]

    logger.info(
        "Topic analysis: %d classified, %d unclassified, %d topics, %d co-occurrences",
        classified, unclassified, len(trends), len(cooccurrences),
    )

    return TopicReport(
        topic_trends=trends,
        top_cooccurrences=top_cooc,
        unclassified_count=unclassified,
        total_classified=classified,
    )
