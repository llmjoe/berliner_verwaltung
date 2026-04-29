"""Download and parse PARDOK XML exports from the Berlin Abgeordnetenhaus.

XML files are published at parlament-berlin.de/opendata/ and updated daily.
Uses streaming XML parser to handle 50 MB files efficiently.
"""

from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path
from xml.etree.ElementTree import iterparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berliner_verwaltung.db.models import PardokDokument, PardokVorgang

logger = logging.getLogger(__name__)

PARDOK_URLS = {
    19: "https://www.parlament-berlin.de/opendata/pardok-wp19.xml",
    18: "https://www.parlament-berlin.de/opendata/pardok-wp18.xml",
}

FHK_KEYWORDS = {"Friedrichshain-Kreuzberg", "Friedrichshain", "Kreuzberg"}


def _text(elem, tag: str) -> str | None:  # type: ignore[no-untyped-def]
    child = elem.find(tag)
    return child.text.strip() if child is not None and child.text else None


def _parse_date(s: str | None) -> dt.date | None:
    if not s:
        return None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def parse_pardok_xml(xml_path: Path) -> tuple[list[dict], list[dict]]:
    """Parse PARDOK XML file using streaming parser.

    Returns (vorgaenge, dokumente) as lists of dicts.
    """
    vorgaenge: list[dict] = []
    dokumente: list[dict] = []
    delete_ids: set[str] = set()

    for _event, elem in iterparse(str(xml_path), events=("end",)):
        if elem.tag != "Vorgang":
            continue

        vid = _text(elem, "VID") or _text(elem, "VNr") or ""
        vfunktion = _text(elem, "VFunktion")

        if vfunktion == "delete":
            delete_ids.add(vid)
            elem.clear()
            continue

        deskriptoren = []
        for ne in elem.findall("Nebeneintrag"):
            desk = _text(ne, "Desk")
            if desk:
                deskriptoren.append(desk)

        is_fhk = any(
            kw in d for d in deskriptoren for kw in FHK_KEYWORDS
        )

        vorgang = {
            "vorgang_id": vid,
            "vorgang_typ": _text(elem, "VTyp"),
            "systematik": _text(elem, "VSys"),
            "systematik_label": _text(elem, "VSysL"),
            "deskriptoren": deskriptoren,
            "is_fhk": is_fhk,
        }
        vorgaenge.append(vorgang)

        for dok_elem in elem.findall("Dokument"):
            dok = {
                "dokument_id": _text(dok_elem, "DBID") or "",
                "vorgang_id_ref": vid,
                "dok_art": _text(dok_elem, "DokArt"),
                "dok_typ": _text(dok_elem, "DokTyp"),
                "dok_nr": _text(dok_elem, "DokNr"),
                "titel": _text(dok_elem, "Titel"),
                "datum": _text(dok_elem, "DokDat"),
                "urheber": _text(dok_elem, "Urheber"),
                "abstract": _text(dok_elem, "Abstract"),
                "pdf_url": _text(dok_elem, "LokURL"),
                "wahlperiode": _text(dok_elem, "Wp"),
            }
            dokumente.append(dok)

        elem.clear()

    logger.info(
        "Parsed %d Vorgaenge (%d FHK), %d Dokumente, %d deletes",
        len(vorgaenge),
        sum(1 for v in vorgaenge if v["is_fhk"]),
        len(dokumente),
        len(delete_ids),
    )
    return vorgaenge, dokumente


async def download_pardok_xml(
    wp: int = 19, output_dir: Path = Path("data")
) -> Path:
    """Download PARDOK XML for a Wahlperiode."""
    url = PARDOK_URLS.get(wp)
    if not url:
        raise ValueError(f"No URL for WP {wp}")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"pardok-wp{wp}.xml"

    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        logger.info("Downloading PARDOK WP%d from %s", wp, url)
        response = await client.get(url)
        response.raise_for_status()
        output_path.write_bytes(response.content)
        logger.info("Downloaded %d MB to %s", len(response.content) // (1024 * 1024), output_path)

    return output_path


async def load_pardok_to_db(
    session: AsyncSession,
    vorgaenge: list[dict],
    dokumente: list[dict],
    wp: int = 19,
) -> dict[str, int]:
    """Load parsed PARDOK data into the database."""
    stats = {"vorgaenge_new": 0, "vorgaenge_skip": 0, "dokumente_new": 0, "dokumente_skip": 0}

    vorgang_db_ids: dict[str, int] = {}

    for i, v in enumerate(vorgaenge):
        existing = await session.execute(
            select(PardokVorgang).where(PardokVorgang.vorgang_id == v["vorgang_id"])
        )
        if existing.scalar_one_or_none():
            stats["vorgaenge_skip"] += 1
            result = await session.execute(
                select(PardokVorgang.id).where(
                    PardokVorgang.vorgang_id == v["vorgang_id"]
                )
            )
            vorgang_db_ids[v["vorgang_id"]] = result.scalar()  # type: ignore[assignment]
            continue

        db_v = PardokVorgang(
            vorgang_id=v["vorgang_id"],
            vorgang_typ=v["vorgang_typ"],
            systematik=v["systematik"],
            systematik_label=v["systematik_label"],
            wahlperiode=wp,
            deskriptoren=v["deskriptoren"],
            is_fhk=v["is_fhk"],
        )
        session.add(db_v)
        await session.flush()
        vorgang_db_ids[v["vorgang_id"]] = db_v.id
        stats["vorgaenge_new"] += 1

        if (i + 1) % 500 == 0:
            await session.commit()
            logger.info("Vorgaenge: %d/%d loaded", i + 1, len(vorgaenge))

    await session.commit()

    for i, d in enumerate(dokumente):
        parent_id = vorgang_db_ids.get(d["vorgang_id_ref"])
        if not parent_id:
            continue

        existing = await session.execute(
            select(PardokDokument).where(
                PardokDokument.dokument_id == d["dokument_id"]
            )
        )
        if existing.scalar_one_or_none():
            stats["dokumente_skip"] += 1
            continue

        session.add(PardokDokument(
            dokument_id=d["dokument_id"],
            vorgang_id=parent_id,
            dok_art=d["dok_art"],
            dok_typ=d["dok_typ"],
            dok_nr=d["dok_nr"],
            titel=d["titel"],
            datum=_parse_date(d["datum"]),
            urheber=d["urheber"],
            abstract=d["abstract"],
            pdf_url=d["pdf_url"],
        ))
        stats["dokumente_new"] += 1

        if (i + 1) % 1000 == 0:
            await session.commit()
            logger.info("Dokumente: %d/%d loaded", i + 1, len(dokumente))

    await session.commit()

    logger.info(
        "PARDOK loaded: %d new Vorgaenge, %d new Dokumente",
        stats["vorgaenge_new"], stats["dokumente_new"],
    )
    return stats
