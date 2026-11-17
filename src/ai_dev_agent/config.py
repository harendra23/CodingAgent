from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    llm_provider: Literal["openai", "anthropic", "google"] = "openai"
    llm_model: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    google_api_key: str | None = None
    database_url: str = "postgresql+asyncpg://agent:agent@localhost:5432/aidevagent"
    github_token: str | None = None
    jira_url: str | None = None
    jira_email: str | None = None
    jira_api_token: str | None = None
    confluence_url: str | None = None
    confluence_email: str | None = None
    confluence_api_token: str | None = None

    @property
    def effective_llm_model(self) -> str:
        if self.llm_model:
            return self.llm_model
        return {
            "openai": "gpt-4.1",
            "anthropic": "claude-sonnet-4-5",
            "google": "gemini-2.5-pro",
        }[self.llm_provider]


@lru_cache
def get_settings() -> Settings:
    return Settings()
