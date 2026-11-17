from types import TracebackType
from typing import Self

import httpx

from ai_dev_agent.config import Settings


class ConfluenceClient:
    def __init__(
        self,
        url: str,
        email: str,
        api_token: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not all((url, email, api_token)):
            raise ValueError("Confluence URL, email, and API token are required")
        base_url = url.rstrip("/")
        if base_url.endswith("/rest/api"):
            api_url = base_url
        elif base_url.endswith("/wiki"):
            api_url = f"{base_url}/rest/api"
        else:
            api_url = f"{base_url}/wiki/rest/api"
        self._client = httpx.AsyncClient(
            base_url=api_url,
            auth=httpx.BasicAuth(email, api_token),
            headers={"Accept": "application/json"},
            transport=transport,
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> Self:
        if not all(
            (settings.confluence_url, settings.confluence_email, settings.confluence_api_token)
        ):
            raise ValueError(
                "CONFLUENCE_URL, CONFLUENCE_EMAIL, and CONFLUENCE_API_TOKEN are required"
            )
        return cls(
            url=settings.confluence_url,
            email=settings.confluence_email,
            api_token=settings.confluence_api_token,
        )

    async def search(self, query: str, limit: int = 25) -> list[dict[str, object]]:
        response = await self._client.get("/content/search", params={"cql": query, "limit": limit})
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise ValueError("Confluence returned an invalid search response")
        return payload["results"]

    async def get_page(self, page_id: str) -> dict[str, object]:
        response = await self._client.get(
            f"/content/{page_id}",
            params={"expand": "body.storage,version"},
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Confluence returned an invalid page response")
        return payload

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()
