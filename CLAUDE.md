# Berliner Verwaltungsdaten

Transparenzplattform fuer Berliner Verwaltungsdaten mit Fokus auf Bezirk Friedrichshain-Kreuzberg.
Stark automatisierte, LLM-getriebene Pipeline-Architektur: Datenerhebung, Aufbereitung, Muster-Erkennung, redaktionelle Vorarbeit. Finale journalistische Verantwortung traegt ein Mensch.

## Tech Stack

- Python 3.11+, src-Layout unter `src/berliner_verwaltung/`
- PostgreSQL 16 mit pgvector, asyncpg, SQLAlchemy 2.0 (async)
- Alembic fuer Migrationen
- Pydantic 2.x fuer Validierung und Settings
- Prefect fuer Workflow-Orchestrierung
- httpx fuer async HTTP
- Lokale LLMs via Ollama (qwen2.5:14b, bge-m3)
- Cloud LLMs via Anthropic/OpenAI APIs

## Projekt-Konventionen

- Sprache im Code: Englisch (Variablen, Funktionen, Kommentare)
- Sprache in Docs/README: Deutsch
- Linting: ruff, Type-Checking: mypy (strict)
- Tests: pytest mit pytest-asyncio
- DB-Modelle in `src/berliner_verwaltung/db/models.py`
- Rohdaten und normalisierte Daten getrennt (raw_ Tabellen als Single Source of Truth)
- Jeder LLM-Output traegt Quellenreferenz und Konfidenz-Score

## Wichtige Befehle

```bash
# Dev-Installation
uv pip install -e ".[all]"

# Tests
pytest

# Linting
ruff check src/ tests/
mypy src/

# Migrationen
alembic upgrade head
alembic revision --autogenerate -m "beschreibung"
```

## Pipeline-Stufen

A: Daten-Ingestion (OParl, PARDOK, Haushalt)
B: Anreicherung und Verknuepfung (Klassifikation, Embeddings)
C: Pattern- und Anomalie-Erkennung
D: Recherche-Materialien und Hypothesen
E: Visualisierungs-Vorschlaege
F: Artikel-Skelette
G: Menschliche Recherche und Redaktion (nicht automatisiert)
H: Veroeffentlichung (nicht automatisiert)

## Architektur-Prinzipien

- Rohdaten als Single Source of Truth, normalisierte Daten davon abgeleitet
- Strukturierte Daten zuerst: SQL vor Volltext vor semantisch vor LLM
- Halluzinations-Schutz: Jede LLM-Referenz wird gegen DB validiert
- Pipeline produziert Recherche-Material, keinen Journalismus
- Cross-Validation ist Sicherheitsnetz, nicht Ersatz fuer menschliche Pruefung
