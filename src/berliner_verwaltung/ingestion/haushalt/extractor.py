"""Extract budget line items from Bezirkshaushaltsplan PDFs.

Parses the standardized table format used in Berlin district budgets:
  Titel | Fkt | Bezeichnung | Ansatz 2026 | Ansatz 2027 | Ansatz 2025 | Ist 2024

Each page belongs to a Kapitel (e.g. 3300 = Bezirksbuergermeisterin) and
contains Einnahmen (revenue) or Ausgaben (expenditure) items.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

logger = logging.getLogger(__name__)

KAPITEL_PATTERN = re.compile(r"Friedrichshain-Kreuzberg\s+(\d{4})")
TITEL_PATTERN = re.compile(r"^(\d{5})")
YEAR_HEADER_PATTERN = re.compile(r"(\d{4})\s+(\d{4})\s+(\d{4})")


def _parse_amount(s: str | None) -> float | None:
    if not s or s.strip() in ("", "—", "-", "–"):
        return None
    cleaned = s.strip().replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


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
    section: str = ""  # "Einnahmen" or "Ausgaben"
    kennbuchstabe: str = ""  # e.g. "E03", "A05", "T", "Z"
    page: int = 0
    erlaeuterung: str = ""


@dataclass
class BudgetPlan:
    file_id: int
    reference: str
    year1: int
    year2: int
    items: list[BudgetItem] = field(default_factory=list)
    kapitel_names: dict[str, str] = field(default_factory=dict)


def _extract_item_from_table(
    rows: list[list[str | None]], kapitel: str, section: str, page: int
) -> BudgetItem | None:
    if not rows or not rows[0]:
        return None

    cells = [c.strip() if c else "" for c in rows[0]]

    titel = ""
    funktion = ""
    bezeichnung_parts = []
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

    # Second row often has continuation of Bezeichnung and Kennbuchstabe
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
    bezeichnung = bezeichnung.rstrip("-").strip()

    item = BudgetItem(
        kapitel=kapitel,
        titel=titel,
        funktion=funktion,
        bezeichnung=bezeichnung,
        section=section,
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


def extract_budget_plan(pdf_path: Path, reference: str = "", file_id: int = 0) -> BudgetPlan:
    """Extract all budget line items from a Bezirkshaushaltsplan PDF."""
    plan = BudgetPlan(file_id=file_id, reference=reference, year1=0, year2=0)
    current_kapitel = ""
    current_section = ""
    current_kapitel_name = ""

    with pdfplumber.open(pdf_path) as pdf:
        # Detect years from header
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

            if "Einnahmen" in text:
                current_section = "Einnahmen"
            elif "Ausgaben" in text:
                current_section = "Ausgaben"

            # Detect Kapitel name from page header
            lines = text.split("\n")
            for line in lines[1:5]:
                line = line.strip()
                if (
                    line
                    and not re.match(r"^\d|^Beträge|^Titel|^Kb|^Ansatz|^Ist", line)
                    and line != "Friedrichshain-Kreuzberg"
                    and len(line) > 3
                ):
                        current_kapitel_name = line
                        break

            if current_kapitel and current_kapitel_name:
                plan.kapitel_names[current_kapitel] = current_kapitel_name

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

                item = _extract_item_from_table(
                    table, current_kapitel, current_section, page_num + 1
                )
                if item:
                    plan.items.append(item)

    logger.info(
        "Extracted %d items from %s (%d-%d), %d Kapitel",
        len(plan.items),
        reference or pdf_path.name,
        plan.year1,
        plan.year2,
        len(plan.kapitel_names),
    )
    return plan
