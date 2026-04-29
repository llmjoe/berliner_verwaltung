"""Extract budget line items from Bezirkshaushaltsplan PDFs.

Parses the standardized table format used in Berlin district budgets:
  Titel | Fkt | Bezeichnung | Ansatz year1 | Ansatz year2 | Ansatz prev | Ist prev

Berlin budget Titel numbering:
  1xxxx-2xxxx = Einnahmen (revenue)
  4xxxx-9xxxx = Ausgaben (expenditure)

IKT pages (MG 32) contain duplicate IT cost titles — these are merged
with the main entry by keeping the version that has amounts.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

logger = logging.getLogger(__name__)

KAPITEL_PATTERN = re.compile(r"Friedrichshain-Kreuzberg\s+(\d{4})")


def _parse_amount(s: str | None) -> float | None:
    if not s or s.strip() in ("", "—", "-", "–"):
        return None
    cleaned = s.strip().replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _fix_hyphenation(text: str) -> str:
    """Rejoin hyphenated words split across lines: 'Be- träge' -> 'Beträge'."""
    text = re.sub(r"(\w)- [\d.,\-]+ (\w)", r"\1\2", text)
    text = re.sub(r"(\w)- (\w)", r"\1\2", text)
    return text


def _classify_section(titel: str) -> str:
    """Derive Einnahmen/Ausgaben from the Titel number (Berlin convention)."""
    if not titel or not titel[0].isdigit():
        return ""
    first = int(titel[0])
    if first <= 3:
        return "Einnahmen"
    return "Ausgaben"


@dataclass
class BudgetItem:
    kapitel: str
    titel: str
    funktion: str
    bezeichnung: str
    ansatz_year1: float | None = None
    ansatz_year2: float | None = None
    ansatz_prev: float | None = None
    ist_prev: float | None = None
    section: str = ""
    kennbuchstabe: str = ""
    page: int = 0
    erlaeuterung: str = ""

    @property
    def key(self) -> str:
        return f"{self.kapitel}/{self.titel}"

    def has_amounts(self) -> bool:
        return any(
            v is not None
            for v in [self.ansatz_year1, self.ansatz_year2, self.ansatz_prev, self.ist_prev]
        )


@dataclass
class BudgetPlan:
    file_id: int
    reference: str
    year1: int
    year2: int
    items: list[BudgetItem] = field(default_factory=list)
    kapitel_names: dict[str, str] = field(default_factory=dict)


def _extract_item_from_table(
    rows: list[list[str | None]], kapitel: str, page: int
) -> BudgetItem | None:
    if not rows or not rows[0]:
        return None

    cells = [c.strip() if c else "" for c in rows[0]]

    titel = ""
    funktion = ""
    bezeichnung_parts: list[str] = []
    amounts: list[str] = []

    for cell in cells:
        if not cell:
            continue
        if not titel and re.match(r"^\d{5}$", cell):
            titel = cell
        elif not funktion and re.match(r"^\d{3}$", cell):
            funktion = cell
        elif re.match(r"^[\d.,]+$", cell) or cell in ("—", "-", "–"):
            amounts.append(cell)
        elif not re.match(r"^[A-Z]\d{2}$", cell) and not re.match(r"^[A-Z]$", cell):
            bezeichnung_parts.append(cell)

    if not titel:
        return None

    kennbuchstabe = ""
    if len(rows) > 1 and rows[1]:
        for cell in rows[1]:
            if cell and cell.strip():
                c = cell.strip()
                if re.match(r"^[A-Z]\d{2}$", c) or re.match(r"^[A-Z]$", c):
                    kennbuchstabe = c
                elif not re.match(r"^\d", c):
                    bezeichnung_parts.append(c)

    bezeichnung = " ".join(bezeichnung_parts).strip()
    bezeichnung = re.sub(r"\s+", " ", bezeichnung)
    bezeichnung = _fix_hyphenation(bezeichnung)

    item = BudgetItem(
        kapitel=kapitel,
        titel=titel,
        funktion=funktion,
        bezeichnung=bezeichnung,
        section=_classify_section(titel),
        kennbuchstabe=kennbuchstabe,
        page=page,
    )

    if len(amounts) >= 1:
        item.ansatz_year1 = _parse_amount(amounts[0])
    if len(amounts) >= 2:
        item.ansatz_year2 = _parse_amount(amounts[1])
    if len(amounts) >= 3:
        item.ansatz_prev = _parse_amount(amounts[2])
    if len(amounts) >= 4:
        item.ist_prev = _parse_amount(amounts[3])

    return item


def _dedup_items(items: list[BudgetItem]) -> list[BudgetItem]:
    """Merge duplicate items (e.g. IKT pages). Keep the version with amounts."""
    seen: dict[str, BudgetItem] = {}
    for item in items:
        key = item.key
        if key not in seen:
            seen[key] = item
        elif item.has_amounts() and not seen[key].has_amounts():
            item.bezeichnung = item.bezeichnung or seen[key].bezeichnung
            seen[key] = item
        elif item.has_amounts() and seen[key].has_amounts():
            seen[key] = item
    return list(seen.values())


def extract_budget_plan(
    pdf_path: Path, reference: str = "", file_id: int = 0
) -> BudgetPlan:
    """Extract all budget line items from a Bezirkshaushaltsplan PDF."""
    plan = BudgetPlan(file_id=file_id, reference=reference, year1=0, year2=0)
    current_kapitel = ""
    raw_items: list[BudgetItem] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[:10]:
            text = page.extract_text() or ""
            year_match = re.search(r"(\d{4})\s*(?:und|/)\s*(\d{4})", text)
            if year_match:
                plan.year1 = int(year_match.group(1))
                plan.year2 = int(year_match.group(2))
                break

        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text() or ""

            kapitel_match = KAPITEL_PATTERN.search(text)
            if kapitel_match:
                current_kapitel = kapitel_match.group(1)

            lines = text.split("\n")
            for line in lines[1:5]:
                line = line.strip()
                if (
                    line
                    and not re.match(r"^\d|^Beträge|^Titel|^Kb|^Ansatz|^Ist|^MG", line)
                    and line != "Friedrichshain-Kreuzberg"
                    and len(line) > 3
                ):
                    plan.kapitel_names[current_kapitel] = line
                    break

            tables = page.extract_tables()
            for table in tables:
                if not table or len(table) < 1:
                    continue

                first_row = table[0]
                has_titel = any(
                    c and re.match(r"^\d{5}$", c.strip())
                    for c in first_row
                    if c
                )
                if not has_titel:
                    continue

                item = _extract_item_from_table(table, current_kapitel, page_num + 1)
                if item:
                    raw_items.append(item)

    plan.items = _dedup_items(raw_items)

    logger.info(
        "Extracted %d items (%d raw, %d deduped) from %s (%d-%d), %d Kapitel",
        len(plan.items),
        len(raw_items),
        len(raw_items) - len(plan.items),
        reference or pdf_path.name,
        plan.year1,
        plan.year2,
        len(plan.kapitel_names),
    )
    return plan
