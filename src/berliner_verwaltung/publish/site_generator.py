"""Static site generator for the public Transparenzplattform.

Renders approved dossiers as static HTML pages.
Simple, dependency-free approach using Python string templates.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — BVV FHK Transparenz</title>
<style>
  :root {{ --bg: #fafaf8; --text: #1a1a1a; --accent: #c0392b; --muted: #6b7280;
           --border: #e5e7eb; --card-bg: #fff; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: Georgia, serif; line-height: 1.6; color: var(--text);
          background: var(--bg); max-width: 720px; margin: 0 auto; padding: 2rem 1rem; }}
  h1 {{ font-size: 1.8rem; margin-bottom: 0.5rem; }}
  h2 {{ font-size: 1.3rem; margin: 1.5rem 0 0.5rem; border-bottom: 1px solid var(--border);
        padding-bottom: 0.3rem; }}
  .meta {{ color: var(--muted); font-size: 0.85rem; margin-bottom: 1.5rem; }}
  .priority {{ display: inline-block; padding: 2px 8px; border-radius: 3px;
               font-size: 0.75rem; font-weight: bold; text-transform: uppercase; }}
  .priority-high {{ background: #fee2e2; color: #991b1b; }}
  .priority-medium {{ background: #fef3c7; color: #92400e; }}
  .priority-low {{ background: #dbeafe; color: #1e40af; }}
  .summary {{ font-size: 1.1rem; margin-bottom: 1.5rem; font-style: italic; }}
  ul {{ margin-left: 1.2rem; margin-bottom: 1rem; }}
  li {{ margin-bottom: 0.3rem; }}
  .sources {{ background: var(--card-bg); border: 1px solid var(--border);
              padding: 1rem; border-radius: 4px; margin-top: 1.5rem; }}
  .methodology {{ background: #f9fafb; padding: 1rem; border-left: 3px solid var(--border);
                  margin-top: 1rem; font-size: 0.9rem; color: var(--muted); }}
  .disclaimer {{ margin-top: 2rem; padding: 1rem; background: #fffbeb;
                 border: 1px solid #fbbf24; border-radius: 4px; font-size: 0.85rem; }}
  footer {{ margin-top: 3rem; padding-top: 1rem; border-top: 1px solid var(--border);
            font-size: 0.8rem; color: var(--muted); }}
  a {{ color: var(--accent); }}
</style>
</head>
<body>
<header>
<div style="font-size:0.9rem;color:var(--muted);margin-bottom:0.5rem;">
  BVV Friedrichshain-Kreuzberg — Transparenzplattform
</div>
<h1>{title}</h1>
<div class="meta">
  <span class="priority priority-{priority}">{priority}</span>
  &middot; {date}
  &middot; Recherche-Material (nicht redaktionell geprueft)
</div>
</header>

<p class="summary">{summary}</p>

<h2>Befunde</h2>
<ul>
{findings_html}
</ul>

{context_html}

<h2>Offene Fragen</h2>
<ul>
{questions_html}
</ul>

<h2>Alternative Erklaerungen</h2>
<ul>
{alternatives_html}
</ul>

{related_html}

<div class="methodology">
<strong>Methodik:</strong> {methodology}
</div>

<div class="sources">
<strong>Quellen:</strong>
<ul>
{sources_html}
</ul>
</div>

<div class="disclaimer">
<strong>Hinweis:</strong> Dieses Dokument ist automatisch generiertes
Recherche-Material auf Basis oeffentlicher Haushaltsdaten. Es wurde
<strong>nicht redaktionell geprueft</strong> und stellt keine
journalistische Veroeffentlichung dar. Alle Angaben ohne Gewaehr.
Die Datenanalyse erfolgte teilweise KI-gestuetzt (Klassifikation,
Muster-Erkennung). Die finale Bewertung und Einordnung obliegt
menschlichen Redakteur:innen.
</div>

<footer>
Datenquelle: Bezirkshaushaltsplaene FHK, OParl BVV FHK, PARDOK AGH Berlin
&middot; Generiert am {generated}
&middot; <a href="https://github.com/llmjoe/berliner_verwaltung">Quellcode</a>
</footer>
</body>
</html>
"""

INDEX_TEMPLATE = """\
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BVV FHK Transparenzplattform</title>
<style>
  :root {{ --bg: #fafaf8; --text: #1a1a1a; --accent: #c0392b; --muted: #6b7280;
           --border: #e5e7eb; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: Georgia, serif; line-height: 1.6; color: var(--text);
          background: var(--bg); max-width: 720px; margin: 0 auto; padding: 2rem 1rem; }}
  h1 {{ font-size: 2rem; margin-bottom: 0.3rem; }}
  .subtitle {{ color: var(--muted); margin-bottom: 2rem; }}
  .dossier {{ border: 1px solid var(--border); padding: 1rem; margin-bottom: 1rem;
              border-radius: 4px; background: #fff; }}
  .dossier h3 {{ font-size: 1.1rem; }}
  .dossier h3 a {{ color: var(--text); text-decoration: none; }}
  .dossier h3 a:hover {{ color: var(--accent); }}
  .priority {{ display: inline-block; padding: 2px 8px; border-radius: 3px;
               font-size: 0.7rem; font-weight: bold; text-transform: uppercase; }}
  .priority-high {{ background: #fee2e2; color: #991b1b; }}
  .priority-medium {{ background: #fef3c7; color: #92400e; }}
  .priority-low {{ background: #dbeafe; color: #1e40af; }}
  footer {{ margin-top: 3rem; padding-top: 1rem; border-top: 1px solid var(--border);
            font-size: 0.8rem; color: var(--muted); }}
</style>
</head>
<body>
<h1>BVV Friedrichshain-Kreuzberg</h1>
<p class="subtitle">Transparenzplattform — Datenbasierte Recherche-Materialien</p>

<p style="margin-bottom:2rem;color:var(--muted);font-size:0.9rem;">
  Diese Seite zeigt automatisch generierte Recherche-Dossiers auf Basis
  oeffentlicher Verwaltungsdaten. Die Materialien dienen der journalistischen
  Vorarbeit und sind nicht redaktionell geprueft.
</p>

{dossier_cards}

<footer>
Datenquellen: OParl BVV FHK, PARDOK AGH Berlin, Bezirkshaushaltplaene
&middot; <a href="https://github.com/llmjoe/berliner_verwaltung">Quellcode (Open Source)</a>
&middot; Generiert am {generated}
</footer>
</body>
</html>
"""


def _list_html(items: list[str]) -> str:
    return "\n".join(f"<li>{item}</li>" for item in items)


def generate_site(
    dossier_dir: Path = Path("data/dossiers"),
    output_dir: Path = Path("public"),
) -> int:
    """Generate static HTML site from dossier JSON files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    index_path = dossier_dir / "index.json"
    if not index_path.exists():
        logger.warning("No dossier index found at %s", index_path)
        return 0

    index = json.loads(index_path.read_text())
    generated = datetime.now().strftime("%d.%m.%Y %H:%M")
    cards = []

    for entry in index:
        dossier_path = dossier_dir / f"{entry['id']}.json"
        if not dossier_path.exists():
            continue

        dossier = json.loads(dossier_path.read_text())

        context_html = ""
        if dossier.get("context"):
            context_html = f"<h2>Kontext</h2>\n<p>{dossier['context']}</p>"

        related_parts = []
        if dossier.get("related_papers"):
            items = "\n".join(
                f"<li>[{p.get('reference', '?')}] {p.get('name', '?')[:70]}</li>"
                for p in dossier["related_papers"][:5]
            )
            related_parts.append(
                f"<h2>Verwandte BVV-Drucksachen</h2>\n<ul>{items}</ul>"
            )
        if dossier.get("related_pardok"):
            items = "\n".join(
                f"<li>[{p.get('dok_nr', '?')}] {p.get('titel', '?')[:70]}</li>"
                for p in dossier["related_pardok"][:3]
            )
            related_parts.append(
                f"<h2>Verwandte AGH-Dokumente</h2>\n<ul>{items}</ul>"
            )
        related_html = "\n".join(related_parts)

        html = HTML_TEMPLATE.format(
            title=dossier["headline"],
            priority=dossier["priority"],
            date=dossier.get("created_at", "")[:10],
            summary=dossier["summary"],
            findings_html=_list_html(dossier["key_findings"]),
            context_html=context_html,
            questions_html=_list_html(dossier["open_questions"]),
            alternatives_html=_list_html(dossier["alternative_explanations"]),
            related_html=related_html,
            methodology=dossier.get("methodology_notes", ""),
            sources_html=_list_html(dossier.get("sources", [])),
            generated=generated,
        )

        page_path = output_dir / f"{entry['id']}.html"
        page_path.write_text(html)

        cards.append(
            f'<div class="dossier">'
            f'<span class="priority priority-{dossier["priority"]}">'
            f'{dossier["priority"]}</span> '
            f'<h3><a href="{entry["id"]}.html">{dossier["headline"]}</a></h3>'
            f'<p style="color:var(--muted);font-size:0.9rem;">'
            f'{dossier["summary"][:150]}...</p>'
            f"</div>"
        )

    index_html = INDEX_TEMPLATE.format(
        dossier_cards="\n".join(cards),
        generated=generated,
    )
    (output_dir / "index.html").write_text(index_html)

    logger.info("Generated %d pages to %s", len(cards), output_dir)
    return len(cards)
