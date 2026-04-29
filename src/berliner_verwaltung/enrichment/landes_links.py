"""Extract references to Landes-level entities from BVV papers.

Links BVV Drucksachen to:
- Berlin state laws (Gesetze)
- Senate departments (Senatsverwaltungen)
- Federal laws (SGB, BauGB, etc.)
- Building code references (Bebauungspläne)

This prepares the data structure for later PARDOK integration.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berliner_verwaltung.db.models import File, Paper

logger = logging.getLogger(__name__)

BERLIN_LAWS = re.compile(
    r"((?:Berliner\s+)?"
    r"(?:Grünanlagen|Ladenöffnungs|Vergesellschaftungs|Straßen|Schul|Denkmalschutz|"
    r"Wohn(?:raum)?|Kinder(?:tagesförderungs)?|Sozial|Naturschutz|Daten(?:schutz)?|"
    r"Bau(?:ordnungs)?|Informationsfreiheits|Landes(?:gleichstellungs)?|"
    r"Allgemeines\s+Sicherheits\s+und\s+Ordnungs|Partizipations\s+und\s+Integrations|"
    r"Mobilitäts|Klimaschutz|Miet(?:en)?|Verwaltungsverfahrens|"
    r"Hundehalter|Gaststätten)"
    r"gesetz(?:es)?)",
    re.IGNORECASE,
)

FEDERAL_LAWS = re.compile(
    r"(SGB\s+[IVXL]+|BauGB|BauNVO|BauO\s+Bln|GG|BGB|StGB|"
    r"StVO|AGG|KJSG|AsylbLG|AufenthG|BTHG|GewO|BImSchG)",
)

SENATE_DEPTS = re.compile(
    r"Senatsverwaltung\s+für\s+([\w,\s]+?)(?:\s*[\.\,\;\)\n])",
    re.IGNORECASE,
)

BEBAUUNGSPLAN = re.compile(r"(?:B-Plan|Bebauungsplan)\s+((?:VI|V|IV|III|II)?-?\d+[a-z]?(?:-\d+)?)")


@dataclass
class LandesLink:
    paper_id: int
    paper_reference: str
    link_type: str
    target: str


async def extract_landes_links(
    session: AsyncSession,
    legislative_term: str = "VI",
    limit: int = 3000,
) -> list[LandesLink]:
    """Scan BVV papers for references to Landes-level entities."""

    result = await session.execute(
        select(Paper.id, Paper.reference, Paper.name, File.text)
        .outerjoin(File, File.paper_id == Paper.id)
        .where(Paper.reference.like(f"%/{legislative_term}"))
        .limit(limit)
    )
    rows = result.all()

    links: list[LandesLink] = []
    seen: set[tuple[int, str, str]] = set()

    for paper_id, reference, name, file_text in rows:
        search_text = (name or "") + " " + (file_text or "")[:5000]

        for match in BERLIN_LAWS.findall(search_text):
            key = (paper_id, "berlin_law", match)
            if key not in seen:
                seen.add(key)
                links.append(LandesLink(paper_id, reference, "berlin_law", match))

        for match in FEDERAL_LAWS.findall(search_text):
            key = (paper_id, "federal_law", match)
            if key not in seen:
                seen.add(key)
                links.append(LandesLink(paper_id, reference, "federal_law", match))

        for match in SENATE_DEPTS.findall(search_text):
            dept = match.strip().rstrip(",.")
            if len(dept) > 3:
                key = (paper_id, "senate_dept", dept)
                if key not in seen:
                    seen.add(key)
                    links.append(LandesLink(paper_id, reference, "senate_dept", dept))

        for match in BEBAUUNGSPLAN.findall(search_text):
            key = (paper_id, "bebauungsplan", match)
            if key not in seen:
                seen.add(key)
                links.append(LandesLink(paper_id, reference, "bebauungsplan", match))

    logger.info(
        "Extracted %d Landes-links from %d papers", len(links), len(rows),
    )
    return links


async def analyze_landes_links(session: AsyncSession) -> dict:
    """Aggregate Landes-link statistics."""
    links = await extract_landes_links(session)

    by_type: dict[str, Counter[str]] = {
        "berlin_law": Counter(),
        "federal_law": Counter(),
        "senate_dept": Counter(),
        "bebauungsplan": Counter(),
    }

    for link in links:
        by_type[link.link_type][link.target] += 1

    return {
        "total_links": len(links),
        "berlin_laws": by_type["berlin_law"].most_common(20),
        "federal_laws": by_type["federal_law"].most_common(20),
        "senate_depts": by_type["senate_dept"].most_common(20),
        "bebauungsplaene": by_type["bebauungsplan"].most_common(20),
    }
