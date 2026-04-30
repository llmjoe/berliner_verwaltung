"""Recherche-Dossier generator (Pipeline Stufe D).

Generates structured research dossiers for detected patterns.
Each dossier contains: data points, context, related documents,
open questions, and source references.

This is research material for human journalists, not publication-ready text.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berliner_verwaltung.analysis.budget_trends import analyze_budget_trends
from berliner_verwaltung.db.models import (
    Paper,
    PardokDokument,
)
from berliner_verwaltung.llm.client import LLMClient

logger = logging.getLogger(__name__)

DOSSIER_PROMPT = """Du erstellst ein Recherche-Dossier fuer einen Journalisten.

Kontext: BVV Friedrichshain-Kreuzberg, Bezirkspolitik Berlin.

Erkanntes Muster:
{pattern_description}

Datenpunkte:
{data_points}

Verwandte Drucksachen:
{related_papers}

Verwandte AGH-Dokumente:
{related_pardok}

Erstelle ein strukturiertes Recherche-Dossier im JSON-Format:
{{
  "headline": "Praegnante Ueberschrift die das Muster beschreibt",
  "summary": "2-3 Saetze: Was zeigen die Daten objektiv?",
  "key_findings": ["Objektive Datenpunkte, keine Bewertung"],
  "context": "Hintergrund: relevante Gesetze, Zustaendigkeiten, Rahmenbedingungen",
  "open_questions": ["Fragen die ein Journalist recherchieren sollte"],
  "alternative_explanations": ["Moegliche alternative Erklaerungen fuer das Muster"],
  "methodology_notes": "Wie wurden die Daten erhoben, welche Limitationen gibt es",
  "priority": "low|medium|high"
}}

WICHTIG:
- Nur objektive Datenbeschreibung, keine politische Bewertung
- Aktiv nach Gegenargumenten und alternativen Erklaerungen suchen
- Alle Aussagen muessen auf die genannten Datenpunkte zurueckfuehrbar sein
- Offene Fragen formulieren statt Schlussfolgerungen zu ziehen"""


@dataclass
class Dossier:
    id: str
    pattern_type: str
    headline: str
    summary: str
    key_findings: list[str]
    context: str
    open_questions: list[str]
    alternative_explanations: list[str]
    methodology_notes: str
    priority: str
    data_points: list[dict] = field(default_factory=list)
    related_papers: list[dict] = field(default_factory=list)
    related_pardok: list[dict] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    created_at: str = ""


async def _find_related_papers(
    session: AsyncSession, keywords: list[str], limit: int = 10
) -> list[dict]:
    """Find BVV papers related to given keywords."""
    conditions = []
    for kw in keywords[:5]:
        conditions.append(Paper.name.ilike(f"%{kw}%"))

    if not conditions:
        return []

    from sqlalchemy import or_

    result = await session.execute(
        select(Paper.reference, Paper.name, Paper.paper_type, Paper.date)
        .where(or_(*conditions))
        .where(Paper.reference.like("%/VI"))
        .order_by(Paper.date.desc().nullslast())
        .limit(limit)
    )
    return [
        {"reference": r[0], "name": r[1], "type": r[2],
         "date": str(r[3]) if r[3] else None}
        for r in result.all()
    ]


async def _find_related_pardok(
    session: AsyncSession, keywords: list[str], limit: int = 5
) -> list[dict]:
    """Find AGH documents related to given keywords."""
    conditions = []
    for kw in keywords[:3]:
        conditions.append(PardokDokument.titel.ilike(f"%{kw}%"))

    if not conditions:
        return []

    from sqlalchemy import or_

    result = await session.execute(
        select(PardokDokument.dok_nr, PardokDokument.titel,
               PardokDokument.dok_typ, PardokDokument.datum)
        .where(or_(*conditions))
        .order_by(PardokDokument.datum.desc().nullslast())
        .limit(limit)
    )
    return [
        {"dok_nr": r[0], "titel": r[1], "typ": r[2],
         "datum": str(r[3]) if r[3] else None}
        for r in result.all()
    ]


async def generate_budget_dossiers(
    session: AsyncSession,
    llm: LLMClient | None = None,
    limit: int = 5,
) -> list[Dossier]:
    """Generate dossiers for the most significant budget changes."""
    budget = await analyze_budget_trends(session, limit=limit)
    dossiers: list[Dossier] = []

    for i, change in enumerate(budget.biggest_increases[:limit]):
        keywords = [
            w for w in change.bezeichnung.split()
            if len(w) > 4 and w[0].isupper()
        ][:3]

        related = await _find_related_papers(session, keywords)
        pardok = await _find_related_pardok(session, keywords)

        pattern_desc = (
            f"Budgetposten {change.kapitel}/{change.titel} "
            f"({change.bezeichnung}) stieg von "
            f"{change.amount_from:,.0f} EUR ({change.year_from}) auf "
            f"{change.amount_to:,.0f} EUR ({change.year_to}), "
            f"eine Steigerung von {change.change_pct:+.1f}% nominal "
            f"({change.change_real_pct:+.1f}% inflationsbereinigt)."
        )

        data_points = [
            {"year": change.year_from, "amount": change.amount_from},
            {"year": change.year_to, "amount": change.amount_to},
            {"change_pct": change.change_pct},
            {"change_real_pct": change.change_real_pct},
        ]

        dossier = Dossier(
            id=f"budget-increase-{i+1}",
            pattern_type="budget_increase",
            headline=f"Anstieg: {change.bezeichnung[:60]}",
            summary=pattern_desc,
            key_findings=[
                f"Anstieg um {change.change_pct:+.1f}% "
                f"({change.amount_from:,.0f} -> {change.amount_to:,.0f} EUR)",
                f"Inflationsbereinigt: {change.change_real_pct:+.1f}%",
                f"Kapitel: {change.kapitel}, Titel: {change.titel}",
            ],
            context="",
            open_questions=[
                "Was hat den Anstieg verursacht?",
                "Gibt es korrespondierende BVV-Beschluesse?",
                "Wie entwickelt sich der Posten im Vergleich zu anderen Bezirken?",
            ],
            alternative_explanations=[
                "Inflation und allgemeine Kostensteigerung",
                "Gesetzliche Pflichtaufgaben mit steigenden Fallzahlen",
                "Einmaleffekte oder Nachholbedarf",
            ],
            methodology_notes=(
                "Vergleich Ansatz Haushaltsjahr 1 zwischen aeltestem und "
                "neuestem Doppelhaushalt. Inflationsbereinigung mit "
                "kumulierten Jahresraten."
            ),
            priority="medium" if abs(change.change_real_pct) > 50 else "low",
            data_points=data_points,
            related_papers=[
                {"reference": r["reference"], "name": r["name"]}
                for r in related[:5]
            ],
            related_pardok=[
                {"dok_nr": r["dok_nr"], "titel": r["titel"]}
                for r in pardok[:3]
            ],
            sources=[
                f"Bezirkshaushaltsplan {change.year_from}/{change.year_from+1}",
                f"Bezirkshaushaltsplan {change.year_to}/{change.year_to+1}",
            ],
            created_at=dt.datetime.now(dt.UTC).isoformat(),
        )

        if llm:
            papers_str = "\n".join(
                f"- [{r['reference']}] {r['name']}" for r in related[:5]
            )
            pardok_str = "\n".join(
                f"- [{r['dok_nr']}] {r['titel']}" for r in pardok[:3]
            )
            data_str = "\n".join(
                f"- {change.year_from}: {change.amount_from:,.0f} EUR\n"
                f"- {change.year_to}: {change.amount_to:,.0f} EUR\n"
                f"- Veraenderung: {change.change_pct:+.1f}% nominal, "
                f"{change.change_real_pct:+.1f}% real"
            )
            prompt = DOSSIER_PROMPT.format(
                pattern_description=pattern_desc,
                data_points=data_str,
                related_papers=papers_str or "Keine gefunden",
                related_pardok=pardok_str or "Keine gefunden",
            )
            try:
                result = await llm.complete_json(prompt)
                if result and isinstance(result, dict):
                    dossier.headline = result.get("headline", dossier.headline)
                    dossier.summary = result.get("summary", dossier.summary)
                    dossier.key_findings = result.get(
                        "key_findings", dossier.key_findings
                    )
                    dossier.context = result.get("context", "")
                    dossier.open_questions = result.get(
                        "open_questions", dossier.open_questions
                    )
                    dossier.alternative_explanations = result.get(
                        "alternative_explanations",
                        dossier.alternative_explanations,
                    )
                    dossier.priority = result.get("priority", dossier.priority)
            except Exception as e:
                logger.warning("LLM dossier generation failed: %s", e)

        dossiers.append(dossier)

    logger.info("Generated %d dossiers", len(dossiers))
    return dossiers


def save_dossiers(dossiers: list[Dossier], output_dir: Path = Path("data/dossiers")) -> None:
    """Save dossiers as JSON files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    for d in dossiers:
        path = output_dir / f"{d.id}.json"
        path.write_text(json.dumps(
            {
                "id": d.id,
                "pattern_type": d.pattern_type,
                "headline": d.headline,
                "summary": d.summary,
                "key_findings": d.key_findings,
                "context": d.context,
                "open_questions": d.open_questions,
                "alternative_explanations": d.alternative_explanations,
                "methodology_notes": d.methodology_notes,
                "priority": d.priority,
                "data_points": d.data_points,
                "related_papers": d.related_papers,
                "related_pardok": d.related_pardok,
                "sources": d.sources,
                "created_at": d.created_at,
            },
            indent=2,
            ensure_ascii=False,
        ))

    index = [
        {"id": d.id, "headline": d.headline, "priority": d.priority,
         "pattern_type": d.pattern_type}
        for d in dossiers
    ]
    (output_dir / "index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False)
    )
    logger.info("Saved %d dossiers to %s", len(dossiers), output_dir)
