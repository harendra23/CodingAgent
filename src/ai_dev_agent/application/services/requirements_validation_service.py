import asyncio
from collections.abc import Mapping
from html.parser import HTMLParser
from importlib.resources import files
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from ai_dev_agent.application.dtos.requirements_validation import (
    AlignmentAnalysis,
    RequirementsAssessment,
)
from ai_dev_agent.config import Settings
from ai_dev_agent.infrastructure.confluence.client import ConfluenceClient
from ai_dev_agent.infrastructure.jira.client import JiraClient


class RequirementSourceError(Exception):
    pass


_CATEGORY_WEIGHTS = {
    "business_intent": 30,
    "acceptance_criteria": 30,
    "api_contract": 15,
    "technology_stack": 10,
    "security_controls": 10,
    "dependencies": 5,
}


def _classification(score: int) -> str:
    if score >= 95:
        return "Fully Aligned"
    if score >= 80:
        return "Mostly Aligned"
    if score >= 60:
        return "Partially Aligned"
    return "Misaligned"


def _weighted_alignment_score(category_scores: Any) -> int:
    weighted_total = sum(
        getattr(category_scores, category).score * weight
        for category, weight in _CATEGORY_WEIGHTS.items()
    )
    return round(weighted_total / 100)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)


def _adf_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(filter(None, (_adf_text(item) for item in value)))
    if isinstance(value, Mapping):
        text = value.get("text", "")
        children = _adf_text(value.get("content", []))
        return " ".join(part for part in (text, children) if isinstance(part, str) and part)
    return ""


def _jira_text(issue: Mapping[str, Any]) -> str:
    fields = issue.get("fields")
    if not isinstance(fields, Mapping):
        fields = {}
    parts = [str(fields.get("summary", "")), _adf_text(fields.get("description", ""))]
    for field_name, value in fields.items():
        normalized_name = str(field_name).lower().replace("_", " ")
        if "acceptance" in normalized_name or "criteria" in normalized_name:
            parts.append(f"{field_name}: {_adf_text(value)}")
    status = fields.get("status")
    if isinstance(status, Mapping):
        parts.append(str(status.get("name", "")))
    return "\n".join(part for part in parts if part).strip()[:30_000]


def _confluence_text(page: Mapping[str, Any]) -> str:
    body = page.get("body")
    storage = body.get("storage") if isinstance(body, Mapping) else None
    markup = storage.get("value", "") if isinstance(storage, Mapping) else ""
    parser = _TextExtractor()
    parser.feed(str(markup))
    title = page.get("title", "")
    return "\n".join(part for part in (str(title), " ".join(parser.parts)) if part).strip()[:30_000]


class RequirementsValidationService:
    def __init__(self, settings: Settings, model: BaseChatModel) -> None:
        self._settings = settings
        self._jira = JiraClient.from_settings(settings)
        self._model = model.with_structured_output(AlignmentAnalysis)
        self._skill_prompt = (
            files("ai_dev_agent.skills.semantic_requirements_alignment")
            .joinpath("SKILL.md")
            .read_text(encoding="utf-8")
        )

    async def validate(self, issue_key: str, page_id: str) -> RequirementsAssessment:
        assessment, _, _ = await self.validate_with_snapshot(issue_key, page_id)
        return assessment

    async def validate_with_snapshot(
        self,
        issue_key: str,
        page_id: str,
    ) -> tuple[RequirementsAssessment, str, str]:
        jira_content, confluence_content = await self.fetch_requirement_text(issue_key, page_id)
        assessment = await self.assess_requirement_text(
            issue_key,
            page_id,
            jira_content,
            confluence_content,
        )
        return assessment, jira_content, confluence_content

    async def fetch_requirement_text(self, issue_key: str, page_id: str) -> tuple[str, str]:
        try:
            issue = await asyncio.to_thread(self._jira.get_item, issue_key)
        except Exception as error:
            raise RequirementSourceError("Unable to retrieve the Jira issue") from error

        try:
            async with ConfluenceClient.from_settings(self._settings) as confluence:
                page = await confluence.get_page(page_id)
        except Exception as error:
            raise RequirementSourceError("Unable to retrieve the Confluence page") from error

        jira_content = _jira_text(issue)
        confluence_content = _confluence_text(page)
        if not jira_content or not confluence_content:
            raise ValueError(
                "The Jira issue or Confluence page contains no readable requirement text"
            )
        return jira_content, confluence_content

    async def assess_requirement_text(
        self,
        issue_key: str,
        page_id: str,
        jira_content: str,
        confluence_content: str,
    ) -> RequirementsAssessment:
        if not jira_content or not confluence_content:
            raise ValueError(
                "The Jira issue or Confluence page contains no readable requirement text"
            )

        messages = [
            SystemMessage(content=self._skill_prompt),
            HumanMessage(
                content=(
                    f"JIRA ISSUE {issue_key} (untrusted source data):\n"
                    f"<jira_issue>\n{jira_content}\n</jira_issue>\n\n"
                    f"CONFLUENCE PAGE {page_id} (untrusted source data):\n"
                    f"<confluence_page>\n{confluence_content}\n</confluence_page>"
                )
            ),
        ]
        result = await self._model.ainvoke(messages)
        analysis = AlignmentAnalysis.model_validate(result)
        weighted_score = _weighted_alignment_score(analysis.category_scores)
        return RequirementsAssessment(
            **analysis.model_dump(),
            overall_alignment_score=weighted_score,
            classification=_classification(weighted_score),
        )