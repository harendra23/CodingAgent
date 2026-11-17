from atlassian import Jira

from ai_dev_agent.config import Settings


class JiraClient:
    def __init__(self, url: str, email: str, api_token: str) -> None:
        if not all((url, email, api_token)):
            raise ValueError("Jira URL, email, and API token are required")
        self._client = Jira(url=url, username=email, password=api_token, cloud=True)

    @classmethod
    def from_settings(cls, settings: Settings) -> "JiraClient":
        if not settings.jira_url or not settings.jira_email or not settings.jira_api_token:
            raise ValueError("JIRA_URL, JIRA_EMAIL, and JIRA_API_TOKEN are required")
        return cls(settings.jira_url, settings.jira_email, settings.jira_api_token)

    def get_item(self, item_key: str) -> dict[str, object]:
        return self._client.issue(item_key)

    def search(self, query: str, limit: int = 50) -> list[dict[str, object]]:
        result = self._client.jql(query, limit=limit)
        return result.get("issues", [])
