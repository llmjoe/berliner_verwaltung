"""Tests for OParl client – uses httpx mock transport."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from berliner_verwaltung.ingestion.oparl.client import OparlClient


def _mock_transport(responses: dict[str, Any]) -> httpx.MockTransport:
    """Create a mock transport that returns predefined responses by URL path."""

    async def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        for pattern, response_data in responses.items():
            if pattern in url:
                return httpx.Response(200, json=response_data)
        return httpx.Response(404, json={"error": "not found"})

    return httpx.MockTransport(handler)


@pytest.fixture
def mock_system_response() -> dict[str, Any]:
    return {
        "id": "https://example.org/oparl/1.0/system",
        "type": "https://schema.oparl.org/1.0/System",
        "name": "BVV Friedrichshain-Kreuzberg",
        "body": "https://example.org/oparl/1.0/bodies",
    }


@pytest.fixture
def mock_body_response() -> dict[str, Any]:
    return {
        "data": [
            {
                "id": "https://example.org/oparl/1.0/body/22",
                "type": "https://schema.oparl.org/1.0/Body",
                "name": "BVV Friedrichshain-Kreuzberg",
                "organization": "https://example.org/oparl/1.0/organizations",
                "person": "https://example.org/oparl/1.0/persons",
                "meeting": "https://example.org/oparl/1.0/meetings",
                "paper": "https://example.org/oparl/1.0/papers",
            }
        ],
        "links": {},
        "pagination": {},
    }


@pytest.mark.asyncio
async def test_get_body(
    mock_system_response: dict[str, Any], mock_body_response: dict[str, Any]
) -> None:
    transport = _mock_transport({
        "system": mock_system_response,
        "bodies": mock_body_response,
    })
    client = OparlClient(base_url="https://example.org/oparl/1.0/system")
    client._client = httpx.AsyncClient(transport=transport)

    body = await client.get_body()
    assert body["name"] == "BVV Friedrichshain-Kreuzberg"
    await client.close()


@pytest.mark.asyncio
async def test_pagination() -> None:
    page1 = {
        "data": [{"id": "https://example.org/1"}, {"id": "https://example.org/2"}],
        "links": {"next": "https://example.org/list?page=2"},
        "pagination": {},
    }
    page2 = {
        "data": [{"id": "https://example.org/3"}],
        "links": {},
        "pagination": {},
    }
    transport = _mock_transport({"page=2": page2, "list": page1})
    client = OparlClient(base_url="https://example.org/oparl/v1.1")
    client._client = httpx.AsyncClient(transport=transport)

    items = []
    async for item in client.paginate("https://example.org/list"):
        items.append(item)

    assert len(items) == 3
    assert items[2]["id"] == "https://example.org/3"
    await client.close()
