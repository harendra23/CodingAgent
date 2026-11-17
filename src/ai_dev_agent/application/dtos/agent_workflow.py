import re
from typing import Literal
from uuid import UUID
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator

from ai_dev_agent.application.dtos.requirements_validation import RequirementsAssessment


class AgentWorkflowRequest(BaseModel):
    validation_id: UUID
    repository_url: str = Field(min_length=1, max_length=500)

    @field_validator("repository_url")
    @classmethod
    def validate_repository_url(cls, value: str) -> str:
        parsed = urlsplit(value.strip())
        parts = parsed.path.strip("/").split("/")
        if (
            parsed.scheme != "https"
            or parsed.hostname != "github.com"
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or len(parts) != 2
            or parts[0] in {".", ".."}
            or parts[1].removesuffix(".git") in {".", ".."}
            or not re.fullmatch(r"[A-Za-z0-9_.-]+", parts[0])
            or not re.fullmatch(r"[A-Za-z0-9_.-]+(?:\.git)?", parts[1])
        ):
            raise ValueError("Repository URL must be an HTTPS GitHub owner/repository URL")
        return value.strip().rstrip("/")


class CodeGenerationDraft(BaseModel):
    summary: str
    unified_diff: str = ""


class WorkflowArtifactSection(BaseModel):
    heading: str
    summary: str | None = None
    items: list[str] = Field(default_factory=list)


class TraceabilityRow(BaseModel):
    requirement: str
    implementation: str
    verification: str
    status: str


class WorkflowArtifact(BaseModel):
    summary: str
    sections: list[WorkflowArtifactSection] = Field(default_factory=list)
    mermaid_diagram: str | None = None
    traceability_rows: list[TraceabilityRow] = Field(default_factory=list)


class WorkflowStage(BaseModel):
    id: str
    name: str
    status: Literal["completed", "blocked", "skipped"]
    output: str | None = None
    artifact: WorkflowArtifact | None = None
    code_diff: str | None = None


class AgentWorkflowResponse(BaseModel):
    validation_id: UUID
    jira_issue_key: str
    confluence_page_id: str
    status: Literal["completed", "blocked"]
    assessment: RequirementsAssessment
    stages: list[WorkflowStage]