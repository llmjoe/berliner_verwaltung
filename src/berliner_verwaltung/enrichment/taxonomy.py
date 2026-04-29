"""Topic taxonomy for BVV Friedrichshain-Kreuzberg Drucksachen.

Derived from the actual committee structure and common political topics
at the district level. Each topic has a code, name, and keywords for
rule-based pre-classification before LLM refinement.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Topic:
    code: str
    name: str
    keywords: list[str] = field(default_factory=list)
    parent: str | None = None


TAXONOMY: list[Topic] = [
    # Stadtentwicklung & Bauen
    Topic("STADT", "Stadtentwicklung und Bauen", [
        "bebauungsplan", "bauvorhaben", "stadtplanung", "verdichtung",
        "nachverdichtung", "bauleitplanung", "flächennutzungsplan",
        "milieuschutz", "erhaltungsverordnung", "gentrifizierung",
    ]),
    Topic("WOHNEN", "Wohnen und Mieten", [
        "miete", "mieterschutz", "wohnungsbau", "sozialwohnung",
        "wohnungslosigkeit", "zweckentfremdung", "vorkaufsrecht",
        "mietendeckel", "wohnraumversorgung",
    ], parent="STADT"),
    # Verkehr & Mobilität
    Topic("VERKEHR", "Verkehr und Mobilität", [
        "radweg", "fahrrad", "verkehrsberuhigung", "tempo 30",
        "parkraum", "fussgänger", "barrierefreiheit", "öpnv",
        "strassenumbau", "verkehrssicherheit", "spielstrasse",
    ]),
    # Umwelt & Klima
    Topic("UMWELT", "Umwelt und Klimaschutz", [
        "klimaschutz", "klimaanpassung", "grünfläche", "park",
        "baumpflanzung", "baumfällung", "luftqualität", "lärm",
        "stadtgrün", "biodiversität", "hitzevorsorge",
    ]),
    # Bildung & Schule
    Topic("SCHULE", "Schule und Bildung", [
        "schule", "schulplatz", "schulbau", "schulanierung",
        "schulwegsicherheit", "hort", "ganztagsschule",
        "inklusion", "schulentwicklungsplan",
    ]),
    Topic("KULTUR", "Kultur", [
        "kultur", "bibliothek", "museum", "galerie", "kunst",
        "denkmal", "denkmalschutz", "kulturförderung",
        "musikschule", "volkshochschule",
    ]),
    # Soziales
    Topic("SOZIALES", "Soziales und Gesundheit", [
        "sozial", "armut", "obdachlosigkeit", "geflüchtete",
        "integration", "teilhabe", "inklusion", "pflege",
        "suchtprävention", "psychosozial",
    ]),
    Topic("GESUNDHEIT", "Gesundheit", [
        "gesundheit", "krankenhaus", "gesundheitsamt", "impfung",
        "prävention", "corona", "pandemie",
    ], parent="SOZIALES"),
    Topic("JUGEND", "Jugend und Familie", [
        "jugend", "jugendhilfe", "kita", "kinderbetreuung",
        "kinderschutz", "spielplatz", "jugendclub",
        "familienförderung", "jugendbeteiligung",
    ]),
    # Ordnung & Sicherheit
    Topic("ORDNUNG", "Ordnung und Sicherheit", [
        "ordnungsamt", "sauberkeit", "lärm", "sicherheit",
        "kriminalität", "prävention", "nachtruhestörung",
        "gewerbeanmeldung", "gastronomie",
    ]),
    # Haushalt & Verwaltung
    Topic("HAUSHALT", "Haushalt und Finanzen", [
        "haushalt", "haushaltsplan", "bezirkshaushalt", "finanzen",
        "investition", "zuwendung", "förderung", "vergabe",
        "rechnungsprüfung", "haushaltssperre",
    ]),
    Topic("VERWALTUNG", "Verwaltung und Personal", [
        "verwaltung", "bürgeramt", "bürgerdienste", "digitalisierung",
        "personal", "stellenbesetzung", "verwaltungsmodernisierung",
        "e-government", "öffnungszeiten",
    ]),
    # Wirtschaft
    Topic("WIRTSCHAFT", "Wirtschaft", [
        "gewerbe", "wirtschaftsförderung", "einzelhandel", "markt",
        "tourismus", "startup", "coworking",
    ]),
    # Partizipation & Demokratie
    Topic("PARTIZIPATION", "Partizipation und Demokratie", [
        "beteiligung", "bürgerbeteiligung", "partizipation",
        "transparenz", "demokratie", "ehrenamt", "engagement",
        "quartiersmanagement", "bürgerhaushalt",
    ]),
    # Diversity & Antidiskriminierung
    Topic("DIVERSITY", "Diversity und Antidiskriminierung", [
        "antidiskriminierung", "rassismus", "antisemitismus",
        "queer", "lgbtiq", "gleichstellung", "frauen",
        "gender", "barrierefreiheit", "inklusion",
    ]),
]

TOPIC_BY_CODE = {t.code: t for t in TAXONOMY}


def keyword_classify(text: str) -> list[tuple[str, int]]:
    """Simple keyword-based classification. Returns [(topic_code, match_count)]."""
    text_lower = text.lower()
    results = []
    for topic in TAXONOMY:
        count = sum(1 for kw in topic.keywords if kw in text_lower)
        if count > 0:
            results.append((topic.code, count))
    return sorted(results, key=lambda x: x[1], reverse=True)
