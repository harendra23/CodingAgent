import base64

import httpx
import pytest

from ai_dev_agent.infrastructure.confluence import ConfluenceClient


@pytest.mark.asyncio
async def test_search_authenticates_with_email_and_api_token() -> None:
    expected_auth = base64.b64encode(b"agent@example.com:api-secret").decode()

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/wiki/rest/api/content/search"
        assert request.url.params["cql"] == "type=page"
        assert request.headers["Authorization"] == f"Basic {expected_auth}"
        return httpx.Response(200, json={"results": [{"id": "42"}]})

    client = ConfluenceClient(
        url="https://example.atlassian.net",
        email="agent@example.com",
        api_token="api-secret",
        transport=httpx.MockTransport(handler),
    )
    try:
        results = await client.search("type=page")
    finally:
        await client.aclose()

    assert results == [{"id": "42"}]