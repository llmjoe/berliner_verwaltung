"""Async HTTP client for OParl 1.1 APIs with pagination and retry."""

from __future__ import annotations

import logging
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

OPARL_TYPE_MAP = {
    "https://schema.oparl.org/1.1/Body": "body",
    "https://schema.oparl.org/1.1/Organization": "organization",
    "https://schema.oparl.org/1.1/Person": "person",
    "https://schema.oparl.org/1.1/Membership": "membership",
    "https://schema.oparl.org/1.1/Meeting": "meeting",
    "https://schema.oparl.org/1.1/AgendaItem": "agendaItem",
    "https://schema.oparl.org/1.1/Paper": "paper",
    "https://schema.oparl.org/1.1/File": "file",
    "https://schema.oparl.org/1.1/Consultation": "consultation",
}


class OparlClient:
    def __init__(self, base_url: str | None = None, timeout: float = 30.0) -> None:
        self.base_url = (base_url or settings.oparl_base_url).rstrip("/")
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={"Accept": "application/json"},
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
        return response.json()

    async def get_body(self) -> dict[str, Any]:
        data = await self._get(self.base_url)
        bodies = data.get("data", [data]) if "data" in data else [data]
        if not bodies:
            raise ValueError("No body found at OParl endpoint")
        return bodies[0]

    async def paginate(self, url: str) -> AsyncGenerator[dict[str, Any], None]:
        current_url: str | None = url
        while current_url:
            data = await self._get(current_url)

            items = data.get("data", [])
            for item in items:
                yield item

            links = data.get("links", {})
            pagination = data.get("pagination", {})
            current_url = links.get("next") or pagination.get("next")

            if current_url:
                logger.debug("Next page: %s", current_url)

    async def get_all_of_type(self, list_url: str) -> AsyncGenerator[dict[str, Any], None]:
        async for item in self.paginate(list_url):
            yield item
