"""Article skeleton generator (Pipeline Stufe F).

Generates structured article skeletons from dossiers as research material.
These are NOT publication-ready articles — they are scaffolds for human editors.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from berliner_verwaltung.llm.client import LLMClient
from berliner_verwaltung.research.dossier import Dossier

logger = logging.getLogger(__name__)

SKELETON_PROMPT = """Erstelle ein Artikel-Skelett basierend auf diesem Recherche-Dossier.

Das Skelett ist Recherche-Material fuer einen Journalisten, KEIN fertiger Artikel.
Formuliere nuechtern und datenbasiert, keine dramatisierende Sprache.

Dossier:
Headline: {headline}
Summary: {summary}

Befunde:
{findings}

Kontext:
{context}

Offene Fragen:
{questions}

Alternative Erklaerungen:
{alternatives}

Quellen:
{sources}

Erstelle das Skelett im JSON-Format:
{{
  "working_title": "Arbeitstitel",
  "sections": [
    {{
      "heading": "Abschnitts-Ueberschrift",
      "content_notes": "Was in diesem Abschnitt stehen soll (Stichpunkte)",
      "data_references": ["Welche Datenpunkte hier relevant sind"],
      "status": "draft_notes"
    }}
  ],
  "suggested_visualizations": [
    {{
      "type": "bar_chart|line_chart|table|map",
      "description": "Was die Visualisierung zeigt",
      "data_needed": "Welche Daten benoetigt werden"
    }}
  ],
  "research_todos": ["Was der Journalist noch recherchieren muss"],
  "limitations": ["Einschraenkungen und Vorbehalte"]
}}

Pflicht-Sektionen:
1. Was zeigen die Daten (objektiv)
2. Kontext und Hintergrund
3. Offene Fragen
4. Methodik und Limitationen"""


@dataclass
class ArticleSkeleton:
    dossier_id: str
    working_title: str
    sections: list[dict]
    suggested_visualizations: list[dict]
    research_todos: list[str]
    limitations: list[str]


async def generate_skeleton(
    dossier: Dossier,
    llm: LLMClient | None = None,
) -> ArticleSkeleton:
    """Generate an article skeleton from a dossier."""

    if llm:
        prompt = SKELETON_PROMPT.format(
            headline=dossier.headline,
            summary=dossier.summary,
            findings="\n".join(f"- {f}" for f in dossier.key_findings),
            context=dossier.context or "Kein Kontext verfuegbar",
            questions="\n".join(f"- {q}" for q in dossier.open_questions),
            alternatives="\n".join(
                f"- {a}" for a in dossier.alternative_explanations
            ),
            sources="\n".join(f"- {s}" for s in dossier.sources),
        )
        try:
            result = await llm.complete_json(prompt)
            if result and isinstance(result, dict):
                return ArticleSkeleton(
                    dossier_id=dossier.id,
                    working_title=result.get("working_title", dossier.headline),
                    sections=result.get("sections", []),
                    suggested_visualizations=result.get(
                        "suggested_visualizations", []
                    ),
                    research_todos=result.get("research_todos", []),
                    limitations=result.get("limitations", []),
                )
        except Exception as e:
            logger.warning("LLM skeleton generation failed: %s", e)

    return ArticleSkeleton(
        dossier_id=dossier.id,
        working_title=dossier.headline,
        sections=[
            {
                "heading": "Was zeigen die Daten",
                "content_notes": "; ".join(dossier.key_findings),
                "data_references": [dp for dp in dossier.data_points[:3]],
                "status": "draft_notes",
            },
            {
                "heading": "Kontext und Hintergrund",
                "content_notes": dossier.context or "Recherche noetig",
                "data_references": [],
                "status": "needs_research",
            },
            {
                "heading": "Offene Fragen",
                "content_notes": "; ".join(dossier.open_questions),
                "data_references": [],
                "status": "needs_research",
            },
            {
                "heading": "Methodik und Limitationen",
                "content_notes": dossier.methodology_notes,
                "data_references": [],
                "status": "draft_notes",
            },
        ],
        suggested_visualizations=[
            {
                "type": "bar_chart",
                "description": f"Vergleich {dossier.data_points[0].get('year', '?')} "
                f"vs {dossier.data_points[-1].get('year', '?')}"
                if len(dossier.data_points) >= 2
                else "Zeitreihe",
                "data_needed": "Ansaetze aus Haushaltsplaenen",
            }
        ],
        research_todos=[
            "Bezirksamt um Stellungnahme bitten",
            "Vergleich mit anderen Bezirken recherchieren",
            "Betroffene Akteure identifizieren und kontaktieren",
        ],
        limitations=[
            "Datenquelle: Bezirkshaushaltsplaene (Soll, nicht Ist)",
            "Inflationsbereinigung mit geschaetzten Jahresraten",
            "Nur Ansaetze verglichen, keine Nachtraege oder Haushaltssperren",
        ],
    )


def save_skeletons(
    skeletons: list[ArticleSkeleton],
    output_dir: Path = Path("data/skeletons"),
) -> None:
    """Save article skeletons as JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for s in skeletons:
        path = output_dir / f"{s.dossier_id}-skeleton.json"
        path.write_text(json.dumps(
            {
                "dossier_id": s.dossier_id,
                "working_title": s.working_title,
                "sections": s.sections,
                "suggested_visualizations": s.suggested_visualizations,
                "research_todos": s.research_todos,
                "limitations": s.limitations,
            },
            indent=2,
            ensure_ascii=False,
        ))
    logger.info("Saved %d skeletons to %s", len(skeletons), output_dir)
