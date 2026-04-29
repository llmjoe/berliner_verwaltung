"""Extract Zuwendungsempfänger (grant recipients) from budget plan PDFs.

Uses pdfplumber to extract explanation texts following 68xxx budget titles,
then LLM to parse structured recipient data from those texts.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

from berliner_verwaltung.llm.client import LLMClient

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """Extrahiere Zuwendungsempfaenger aus diesem Haushaltserlaeuterungstext.

Der Text stammt aus dem Bezirkshaushaltsplan Friedrichshain-Kreuzberg.
Extrahiere ALLE genannten Empfaenger, Betraege und Zwecke.

Text:
Kapitel: {kapitel}
Titel: {titel} - {bezeichnung}
Ansatz {year1}: {ansatz_year1} EUR
Ansatz {year2}: {ansatz_year2} EUR

Erlaeuterung:
{erlaeuterung}

Antworte NUR mit diesem JSON-Format:
{{
  "recipients": [
    {{
      "name": "Name des Empfaengers (Organisation, Verein, Programm)",
      "amount_year1": 0,
      "amount_year2": 0,
      "purpose": "Kurzbeschreibung des Zwecks",
      "type": "verein|traeger|programm|sonstige"
    }}
  ],
  "total_zuwendung_year1": 0,
  "total_zuwendung_year2": 0,
  "notes": "Besonderheiten oder Aenderungen gegenueber Vorjahren"
}}

Wenn keine konkreten Empfaenger genannt werden, gib eine leere Liste zurueck.
Extrahiere NUR was im Text steht, erfinde nichts."""


@dataclass
class GrantRecipient:
    kapitel: str
    titel: str
    bezeichnung: str
    recipient_name: str
    amount_year1: float | None
    amount_year2: float | None
    purpose: str
    recipient_type: str
    plan_year1: int
    plan_year2: int


def extract_explanations_from_pdf(
    pdf_path: Path, year1: int = 0, year2: int = 0
) -> list[dict]:
    """Extract explanation texts that follow 68xxx budget titles."""
    results = []
    current_kapitel = ""

    with pdfplumber.open(pdf_path) as pdf:
        if not year1:
            for page in pdf.pages[:10]:
                text = page.extract_text() or ""
                m = re.search(r"(\d{4})\s*(?:und|/)\s*(\d{4})", text)
                if m:
                    year1, year2 = int(m.group(1)), int(m.group(2))
                    break

        for page in pdf.pages:
            text = page.extract_text() or ""
            kapitel_match = re.search(
                r"Friedrichshain-Kreuzberg\s+(\d{4})", text
            )
            if kapitel_match:
                current_kapitel = kapitel_match.group(1)

            titel_blocks = re.split(r"(?=\b\d{5}\s+\d{3}\s)", text)
            for block in titel_blocks:
                titel_match = re.match(r"(\d{5})\s+(\d{3})\s+(.*)", block, re.DOTALL)
                if not titel_match:
                    continue

                titel = titel_match.group(1)
                if not titel.startswith("68"):
                    continue

                full_text = titel_match.group(3)
                if len(full_text) < 50:
                    continue

                amounts = re.findall(r"[\d.]+,\d{2}|[\d.]+(?:\s|$)", full_text)
                bezeichnung_end = full_text.find("\n")
                bezeichnung = full_text[:bezeichnung_end].strip() if bezeichnung_end > 0 else ""
                erlaeuterung = (
                    full_text[bezeichnung_end:].strip() if bezeichnung_end > 0 else full_text
                )

                if len(erlaeuterung) < 30:
                    continue

                results.append({
                    "kapitel": current_kapitel,
                    "titel": titel,
                    "bezeichnung": re.sub(r"\s+", " ", bezeichnung)[:200],
                    "erlaeuterung": erlaeuterung[:3000],
                    "year1": year1,
                    "year2": year2,
                    "amounts": amounts[:4],
                })

    logger.info("Extracted %d explanation texts from %s", len(results), pdf_path.name)
    return results


async def extract_recipients_with_llm(
    llm: LLMClient,
    explanations: list[dict],
    commit_every: int = 10,
) -> list[GrantRecipient]:
    """Use LLM to extract structured recipient data from explanation texts."""
    all_recipients: list[GrantRecipient] = []

    for i, exp in enumerate(explanations):
        prompt = EXTRACTION_PROMPT.format(
            kapitel=exp["kapitel"],
            titel=exp["titel"],
            bezeichnung=exp["bezeichnung"],
            year1=exp["year1"],
            year2=exp["year2"],
            ansatz_year1=exp["amounts"][0] if exp["amounts"] else "unbekannt",
            ansatz_year2=exp["amounts"][1] if len(exp["amounts"]) > 1 else "unbekannt",
            erlaeuterung=exp["erlaeuterung"],
        )

        try:
            result = await llm.complete_json(prompt)
            if not result or not isinstance(result, dict):
                continue

            for r in result.get("recipients", []):
                all_recipients.append(GrantRecipient(
                    kapitel=exp["kapitel"],
                    titel=exp["titel"],
                    bezeichnung=exp["bezeichnung"],
                    recipient_name=r.get("name", ""),
                    amount_year1=r.get("amount_year1"),
                    amount_year2=r.get("amount_year2"),
                    purpose=r.get("purpose", ""),
                    recipient_type=r.get("type", "sonstige"),
                    plan_year1=exp["year1"],
                    plan_year2=exp["year2"],
                ))

        except Exception as e:
            logger.warning("LLM extraction failed for %s/%s: %s", exp["kapitel"], exp["titel"], e)

        if (i + 1) % commit_every == 0:
            logger.info("Recipient extraction: %d/%d processed, %d recipients found",
                        i + 1, len(explanations), len(all_recipients))

    logger.info(
        "Extracted %d recipients from %d explanations",
        len(all_recipients), len(explanations),
    )
    return all_recipients
