# Berliner Verwaltungsdaten

Transparenzplattform fuer Berliner Verwaltungsdaten mit Fokus auf den Bezirk Friedrichshain-Kreuzberg.

Stark automatisierte, LLM-getriebene Pipeline-Architektur die kontinuierlich Daten erhebt, aufbereitet, Muster erkennt und redaktionelle Vorarbeit leistet. Die finale journalistische Verantwortung traegt ein Mensch.

## Drei-Saeulen-Strategie

1. **Datenplattform** – Durchsuchbare Datenbank mit OParl, PARDOK, Haushaltsdaten, Vergabedaten
2. **Analyse-Pipeline** – Mehrstufige Verarbeitung von Rohdaten zu Recherche-Materialien
3. **Redaktionelle Webseite** – Datenjournalistische Analysen, Visualisierungen, Geschichten

## Status

Phase 1: OParl-Crawler fuer BVV Friedrichshain-Kreuzberg (in Arbeit)

## Voraussetzungen

- Python 3.11+
- PostgreSQL 16 mit pgvector-Extension
- Optional: Ollama fuer lokale LLM-Verarbeitung

## Installation

```bash
# Repository klonen
git clone https://github.com/llmjoe/berliner_verwaltung.git
cd berliner_verwaltung

# Virtuelle Umgebung und Installation
python -m venv .venv
source .venv/bin/activate
pip install -e ".[all]"

# Alternativ mit uv
uv pip install -e ".[all]"

# Umgebungsvariablen konfigurieren
cp .env.example .env
# .env bearbeiten (Datenbank-URL, API-Keys)

# Datenbank einrichten
createdb berliner_verwaltung
psql berliner_verwaltung -c "CREATE EXTENSION IF NOT EXISTS vector;"
alembic upgrade head
```

## Verwendung

```bash
# OParl-Daten crawlen (BVV Friedrichshain-Kreuzberg)
bv crawl-oparl

# Mit ausfuehrlichem Logging
bv -v crawl-oparl
```

## Entwicklung

```bash
# Tests ausfuehren
pytest

# Linting
ruff check src/ tests/

# Type-Checking
mypy src/
```

## Projektstruktur

```
src/berliner_verwaltung/
  config.py          – Pydantic Settings
  cli.py             – CLI-Einstiegspunkt
  db/
    models.py        – SQLAlchemy-Modelle (Raw + Normalized)
    connection.py    – Async DB-Session
  ingestion/
    oparl/           – OParl-Crawler (Phase 1)
    pardok/           – PARDOK-XML (Phase 6)
    haushalt/         – Haushaltsdaten-PDF (Phase 5)
  enrichment/         – Klassifikation, Embeddings (Phase 3)
  analysis/           – Pattern-Detection (Phase 9)
  research/           – Dossiers, Visualisierungen (Phase 10-11)
  quality/            – Validierung, Halluzinations-Check
  llm/                – LLM-Abstraktion (Ollama, Cloud)
```

## Datenquellen

- OParl 1.1 (BVV Friedrichshain-Kreuzberg)
- PARDOK-XML (Abgeordnetenhaus Berlin)
- Bezirkshaushaltplaene (PDF)
- Vergabeplattform Berlin
- TED (EU-Vergaben)

## Redaktionelle Prinzipien

- Jede Aussage verlinkt zur Originalquelle
- Politische Neutralitaet – analysieren, nicht kommentieren
- KI-Nutzung explizit ausgewiesen pro Artikel
- Menschliche Letztverantwortung fuer jede Veroeffentlichung
- Aktive Suche nach Gegenargumenten und alternativen Erklaerungen

## Lizenz

MIT
