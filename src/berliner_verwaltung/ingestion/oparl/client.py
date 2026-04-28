"""Async HTTP client for OParl 1.0 APIs (Berlin sitzungsdienst) with pagination and retry."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncGenerator
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from berliner_verwaltung.config import settings

logger = logging.getLogger(__name__)

USER_AGENT = (
    "BerlinerVerwaltungsdaten/0.1 "
    "(+https://github.com/llmjoe/berliner_verwaltung; "
    "Mozilla/5.0 compatible)"
)

OPARL_TYPE_MAP = {
    "https://schema.oparl.org/1.0/Body": "body",
    "https://schema.oparl.org/1.0/Organization": "organization",
    "https://schema.oparl.org/1.0/Person": "person",
    "https://schema.oparl.org/1.0/Membership": "membership",
    "https://schema.oparl.org/1.0/Meeting": "meeting",
    "https://schema.oparl.org/1.0/AgendaItem": "agendaItem",
    "https://schema.oparl.org/1.0/Paper": "paper",
    "https://schema.oparl.org/1.0/File": "file",
    "https://schema.oparl.org/1.0/Consultation": "consultation",
}


class OparlClient:
    def __init__(self, base_url: str | None = None, timeout: float = 30.0) -> None:
        self.base_url = (base_url or settings.oparl_base_url).rstrip("/")
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            },
            follow_redirects=True,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> OparlClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
    )
    async def _get(self, url: str) -> dict[str, Any]:
        logger.debug("GET %s", url)
        response = await self._client.get(url)
        response.raise_for_status()
        try:
            return response.json()
        except json.JSONDecodeError:
            cleaned = re.sub(r"[\x00-\x1f\x7f](?<![\n\r\t])", "", response.text)
            return json.loads(cleaned)

    async def get_system(self) -> dict[str, Any]:
        """Fetch the OParl System object (entry point)."""
        return await self._get(self.base_url)

    async def get_body(self) -> dict[str, Any]:
        """Fetch the first Body from the system's body list."""
        system = await self.get_system()
        body_list_url = system.get("body")
        if not body_list_url:
            raise ValueError("System object has no 'body' URL")
        data = await self._get(body_list_url)
        bodies = data.get("data", [])
        if not bodies:
            raise ValueError("No bodies found at body list URL")
        return bodies[0]

    async def paginate(self, url: str) -> AsyncGenerator[dict[str, Any], None]:
        current_url: str | None = url
        page = 0
        while current_url:
            page += 1
            data = await self._get(current_url)

            items = data.get("data", [])
            for item in items:
                yield item

            links = data.get("links", {})
            pagination = data.get("pagination", {})
            current_url = links.get("next") or pagination.get("next")

            if current_url:
                logger.debug("Page %d done, next: %s", page, current_url)

    async def get_all_of_type(self, list_url: str) -> AsyncGenerator[dict[str, Any], None]:
        async for item in self.paginate(list_url):
            yield item
