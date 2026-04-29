"""Scrape Berlin Vergabeplattform for procurement notices.

Parses the paginated listing at berlin.de/vergabeplattform and extracts
structured tender data from HTML cards. Stores in the tenders table.
"""

from __future__ import annotations

import logging
import re

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berliner_verwaltung.db.models import Tender

logger = logging.getLogger(__name__)

BASE_URL = "https://www.berlin.de/vergabeplattform/veroeffentlichungen/bekanntmachungen/"
USER_AGENT = (
    "BerlinerVerwaltungsdaten/0.1 "
    "(+https://github.com/llmjoe/berliner_verwaltung; "
    "Mozilla/5.0 compatible)"
)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _parse_listing_page(html: str) -> list[dict]:
    """Parse tender cards from a listing page."""
    articles = re.findall(r"<article[^>]*>(.*?)</article>", html, re.DOTALL)
    results = []

    for article in articles:
        item: dict[str, str | None] = {}

        title_match = re.search(r'<h3[^>]*class="title">(.*?)</h3>', article, re.DOTALL)
        if title_match:
            item["title"] = _clean(re.sub(r"<[^>]+>", "", title_match.group(1)))

        link_match = re.search(r'href="(https://meinauftrag[^"]+)"', article)
        if link_match:
            item["url"] = link_match.group(1)
            tid = re.search(r"tenderId/(\d+)", item["url"])
            if tid:
                item["source_id"] = f"berlin-{tid.group(1)}"

        dts = re.findall(r"<dt>(.*?)</dt>\s*<dd>(.*?)</dd>", article, re.DOTALL)
        for dt, dd in dts:
            key = _clean(re.sub(r"<[^>]+>", "", dt)).lower()
            val = _clean(re.sub(r"<[^>]+>", "", dd))
            if "verfahrensart" in key:
                item["procedure_type"] = val
            elif "ausführungsort" in key or "erfüllungsort" in key:
                item["location"] = val
            elif "auftraggeber" in key:
                item["contracting_authority"] = val
            elif "angebotsfrist" in key or "teilnahmefrist" in key:
                date_match = re.search(r"(\d{2}\.\d{2}\.\d{4})", val)
                if date_match:
                    item["deadline"] = date_match.group(1)
            elif "vergabenr" in key or "vergabenummer" in key:
                item["reference"] = val
            elif "leistungsart" in key or "auftragsart" in key:
                item["contract_type"] = val

        if item.get("title"):
            results.append(item)

    return results


class VergabeScraper:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._client = httpx.AsyncClient(
            timeout=30,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
        self.stats = {"scraped": 0, "new": 0, "skipped": 0, "errors": 0}

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> VergabeScraper:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def _fetch_page(self, start: int = 0) -> str:
        url = f"{BASE_URL}?start={start}"
        response = await self._client.get(url)
        response.raise_for_status()
        return response.text

    async def _store_tender(self, item: dict) -> bool:
        source_id = item.get("source_id", "")
        if not source_id:
            return False

        existing = await self.session.execute(
            select(Tender).where(Tender.source_id == source_id)
        )
        if existing.scalar_one_or_none():
            self.stats["skipped"] += 1
            return False

        import contextlib
        import datetime as dt

        deadline = None
        if item.get("deadline"):
            with contextlib.suppress(ValueError):
                deadline = dt.datetime.strptime(item["deadline"], "%d.%m.%Y").date()

        is_fhk = "friedrichshain" in (
            item.get("contracting_authority", "") + item.get("location", "")
        ).lower()

        tender = Tender(
            source="berlin_vergabeplattform",
            source_id=source_id,
            title=item.get("title", ""),
            contracting_authority=item.get("contracting_authority"),
            tender_type=item.get("contract_type"),
            procedure_type=item.get("procedure_type"),
            deadline_date=deadline,
            publication_date=dt.date.today(),
            url=item.get("url"),
            data={
                "location": item.get("location"),
                "reference": item.get("reference"),
                "is_fhk": is_fhk,
            },
        )
        self.session.add(tender)
        self.stats["new"] += 1
        return True

    async def scrape(self, max_pages: int = 33) -> dict[str, int]:
        """Scrape all pages of the Vergabeplattform listing."""
        for page in range(max_pages):
            start = page * 10
            try:
                html = await self._fetch_page(start)
                items = _parse_listing_page(html)

                if not items:
                    logger.info("No more items at page %d, stopping", page + 1)
                    break

                for item in items:
                    self.stats["scraped"] += 1
                    await self._store_tender(item)

                if (page + 1) % 5 == 0:
                    await self.session.commit()
                    logger.info(
                        "Progress: page %d, %d scraped, %d new",
                        page + 1, self.stats["scraped"], self.stats["new"],
                    )

            except Exception as e:
                logger.warning("Page %d failed: %s", page + 1, e)
                self.stats["errors"] += 1

        await self.session.commit()
        logger.info(
            "Scrape done: %d scraped, %d new, %d skipped, %d errors",
            self.stats["scraped"],
            self.stats["new"],
            self.stats["skipped"],
            self.stats["errors"],
        )
        return self.stats
