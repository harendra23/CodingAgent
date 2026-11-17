import pytest

from ai_dev_agent.application.dtos.requirements_validation import AlignmentAnalysis
from ai_dev_agent.application.services import requirements_validation_service as validation_module
from ai_dev_agent.application.services.requirements_validation_service import (
    _classification,
    _confluence_text,
    _jira_text,
    _weighted_alignment_score,
)


def test_jira_adf_content_is_normalized() -> None:
    issue = {
        "fields": {
            "summary": "Export report",
            "description": {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": "CSV downloads must include headers."}
                        ],
                    }
                ],
            },
        }
    }

    text = _jira_text(issue)

    assert "Export report" in text
    assert "CSV downloads must include headers." in text


def test_confluence_storage_markup_is_normalized() -> None:
    page = {
        "title": "Export requirements",
        "body": {"storage": {"value": "<p>CSV includes headers.</p>"}},
    }

    assert _confluence_text(page) == "Export requirements\nCSV includes headers."


def test_weighted_score_and_classification_use_defined_bands() -> None:
    category_scores = {
        "business_intent": {"score": 80, "rationale": "Partial match."},
        "acceptance_criteria": {"score": 70, "rationale": "One criterion is missing."},
        "api_contract": {"score": 100, "rationale": "Not applicable."},
        "technology_stack": {"score": 100, "rationale": "Not applicable."},
        "security_controls": {"score": 100, "rationale": "Not applicable."},
        "dependencies": {"score": 100, "rationale": "Not applicable."},
    }
    from ai_dev_agent.application.dtos.requirements_validation import AlignmentCategoryScores

    weighted = _weighted_alignment_score(AlignmentCategoryScores.model_validate(category_scores))

    assert weighted == 85
    assert _classification(95) == "Fully Aligned"
    assert _classification(80) == "Mostly Aligned"
    assert _classification(60) == "Partially Aligned"
    assert _classification(59) == "Misaligned"


@pytest.mark.asyncio
async def test_validation_uses_packaged_skill_and_scores_mocked_sources(monkeypatch) -> None:
    class FakeJira:
        def get_item(self, issue_key: str) -> dict[str, object]:
            return {"fields": {"summary": "Create a CSV export", "description": "Include headers."}}

    class FakeConfluence:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def get_page(self, page_id: str) -> dict[str, object]:
            return {
                "title": "Export behavior",
                "body": {"storage": {"value": "<p>CSV downloads include headers.</p>"}},
            }

    class FakeModel:
        def with_structured_output(self, schema):
            self.schema = schema
            return self

        async def ainvoke(self, messages):
            self.messages = messages
            categories = {
                name: {"score": score, "rationale": "Compared source evidence."}
                for name, score in {
                    "business_intent": 90,
                    "acceptance_criteria": 80,
                    "api_contract": 100,
                    "technology_stack": 100,
                    "security_controls": 100,
                    "dependencies": 100,
                }.items()
            }
            return AlignmentAnalysis(
                summary="The ticket and page describe the same export behavior.",
                category_scores=categories,
                matched_areas=["CSV export includes headers"],
                material_gaps=[],
                ignored_differences=["Different wording for the export action"],
            )

    monkeypatch.setattr(
        validation_module.JiraClient,
        "from_settings",
        staticmethod(lambda settings: FakeJira()),
    )
    monkeypatch.setattr(
        validation_module.ConfluenceClient,
        "from_settings",
        staticmethod(lambda settings: FakeConfluence()),
    )
    model = FakeModel()
    settings = validation_module.Settings(
        jira_url="https://jira.example",
        jira_email="agent@example.com",
        jira_api_token="test-token",
        confluence_url="https://wiki.example",
        confluence_email="agent@example.com",
        confluence_api_token="test-token",
    )

    result = await validation_module.RequirementsValidationService(settings, model).validate(
        "PROJ-7", "701"
    )

    assert model.schema is AlignmentAnalysis
    assert "Semantic Requirements Alignment Analyzer" in model.messages[0].content
    assert "<jira_issue>" in model.messages[1].content
    assert result.overall_alignment_score == 91
    assert result.classification == "Mostly Aligned"