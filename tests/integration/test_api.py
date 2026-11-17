from uuid import UUID

from fastapi.testclient import TestClient

from ai_dev_agent.api.main import app
from ai_dev_agent.api.routes.agent import get_agent_service
from ai_dev_agent.api.routes.requirements import get_requirements_service
from ai_dev_agent.api.routes.workflow import get_validation_repository, get_workflow_service
from ai_dev_agent.application.dtos.agent_workflow import WorkflowStage
from ai_dev_agent.application.dtos.requirements_validation import (
    RequirementsAssessment,
    StoredRequirementValidation,
)
from ai_dev_agent.application.services.agent_workflow_service import WorkflowExecutionError


class StubAgentService:
    async def invoke(self, prompt: str) -> str:
        return f"Handled: {prompt}"


class StubRequirementsService:
    def __init__(self) -> None:
        self.calls = 0
        self.assessment = RequirementsAssessment(
            overall_alignment_score=85,
            classification="Mostly Aligned",
            summary="The ticket covers the main behavior but omits an edge case.",
            category_scores={
                "business_intent": {"score": 80, "rationale": "Core objective matches."},
                "acceptance_criteria": {"score": 70, "rationale": "An edge case is missing."},
                "api_contract": {"score": 100, "rationale": "No API contract applies."},
                "technology_stack": {
                    "score": 100,
                    "rationale": "No technology requirement differs.",
                },
                "security_controls": {
                    "score": 100,
                    "rationale": "No security requirement differs.",
                },
                "dependencies": {"score": 100, "rationale": "No dependency requirement differs."},
            },
            matched_areas=["User can submit the form"],
            material_gaps=[
                {
                    "missing": "Timeout behavior",
                    "why_it_matters": (
                        "The failure behavior cannot be implemented or tested consistently."
                    ),
                    "severity": "Medium",
                }
            ],
            ignored_differences=["Different wording for the same user action"],
        )

    async def validate_with_snapshot(
        self,
        issue_key: str,
        page_id: str,
    ) -> tuple[RequirementsAssessment, str, str]:
        self.calls += 1
        return self.assessment, "stored Jira source", "stored Confluence source"


class StubValidationRepository:
    def __init__(self) -> None:
        self.records: dict[UUID, StoredRequirementValidation] = {}

    async def create(
        self,
        jira_issue_key: str,
        confluence_page_id: str,
        assessment: RequirementsAssessment,
        jira_content: str,
        confluence_content: str,
    ) -> StoredRequirementValidation:
        record = StoredRequirementValidation(
            validation_id=UUID("4ed21177-4e42-4bc2-9644-643af21d69a8"),
            jira_issue_key=jira_issue_key,
            confluence_page_id=confluence_page_id,
            assessment=assessment,
            jira_content=jira_content,
            confluence_content=confluence_content,
        )
        self.records[record.validation_id] = record
        return record

    async def get(self, validation_id: UUID) -> StoredRequirementValidation | None:
        return self.records.get(validation_id)


class StubWorkflowService:
    async def run(
        self,
        validation: StoredRequirementValidation,
        repository_url: str,
    ) -> dict[str, object]:
        return {
            "status": "completed",
            "validation_id": validation.validation_id,
            "jira_issue_key": validation.jira_issue_key,
            "confluence_page_id": validation.confluence_page_id,
            "assessment": validation.assessment,
            "stages": [
                WorkflowStage(
                    id="requirement_validation",
                    name="Requirement Validation",
                    status="completed",
                    output=validation.assessment.model_dump_json(),
                )
            ],
        }


class FailingWorkflowService:
    async def run(
        self,
        validation: StoredRequirementValidation,
        repository_url: str,
    ) -> dict[str, object]:
        raise WorkflowExecutionError(
            "Repository Impact Analysis",
            "Could not clone repository. Check URL and token access.",
        )


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_agent_endpoint_uses_injected_service() -> None:
    app.dependency_overrides[get_agent_service] = StubAgentService
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/agent/invoke", json={"prompt": "Summarize this change"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"response": "Handled: Summarize this change"}


def test_requirements_ui_is_served() -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "Jira issue key" in response.text
    assert "Confluence page ID" in response.text
    assert "GitHub repository URL" in response.text


def test_requirement_validation_endpoint_returns_structured_findings() -> None:
    service = StubRequirementsService()
    repository = StubValidationRepository()
    app.dependency_overrides[get_requirements_service] = lambda: service
    app.dependency_overrides[get_validation_repository] = lambda: repository
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/requirements/validate",
                json={"jira_issue_key": "PROJ-123", "confluence_page_id": "456789"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["validation_id"] == "4ed21177-4e42-4bc2-9644-643af21d69a8"
    assert service.calls == 1
    assessment = response.json()["assessment"]
    assert assessment["overall_alignment_score"] == 85
    assert assessment["classification"] == "Mostly Aligned"
    assert assessment["material_gaps"][0]["severity"] == "Medium"
    assert assessment["ignored_differences"] == ["Different wording for the same user action"]


def test_workflow_endpoint_returns_ordered_stage_results() -> None:
    repository = StubValidationRepository()
    assessment = StubRequirementsService().assessment
    validation_id = UUID("4ed21177-4e42-4bc2-9644-643af21d69a8")
    repository.records[validation_id] = StoredRequirementValidation(
        validation_id=validation_id,
        jira_issue_key="PROJ-123",
        confluence_page_id="456789",
        assessment=assessment,
        jira_content="stored Jira source",
        confluence_content="stored Confluence source",
    )
    app.dependency_overrides[get_workflow_service] = StubWorkflowService
    app.dependency_overrides[get_validation_repository] = lambda: repository
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/workflows/run",
                json={
                    "validation_id": str(validation_id),
                    "repository_url": "https://github.com/acme/example",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["validation_id"] == str(validation_id)
    assert response.json()["status"] == "completed"
    assert response.json()["stages"][0]["id"] == "requirement_validation"


def test_workflow_endpoint_returns_safe_stage_failure_detail() -> None:
    repository = StubValidationRepository()
    validation_id = UUID("4ed21177-4e42-4bc2-9644-643af21d69a8")
    repository.records[validation_id] = StoredRequirementValidation(
        validation_id=validation_id,
        jira_issue_key="PROJ-123",
        confluence_page_id="456789",
        assessment=StubRequirementsService().assessment,
        jira_content="stored Jira source",
        confluence_content="stored Confluence source",
    )
    app.dependency_overrides[get_workflow_service] = FailingWorkflowService
    app.dependency_overrides[get_validation_repository] = lambda: repository
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/workflows/run",
                json={
                    "validation_id": str(validation_id),
                    "repository_url": "https://github.com/acme/example",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert response.json()["detail"].startswith("Repository Impact Analysis failed:")
