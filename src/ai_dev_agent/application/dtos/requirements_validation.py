from uuid import UUID
from typing import Literal

from pydantic import BaseModel, Field


class RequirementsValidationRequest(BaseModel):
    jira_issue_key: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]*-\d+$")
    confluence_page_id: str = Field(pattern=r"^\d+$")


class AlignmentCategoryScore(BaseModel):
    score: int = Field(ge=0, le=100)
    rationale: str


class AlignmentCategoryScores(BaseModel):
    business_intent: AlignmentCategoryScore
    acceptance_criteria: AlignmentCategoryScore
    api_contract: AlignmentCategoryScore
    technology_stack: AlignmentCategoryScore
    security_controls: AlignmentCategoryScore
    dependencies: AlignmentCategoryScore


class MaterialGap(BaseModel):
    missing: str
    why_it_matters: str
    severity: Literal["High", "Medium", "Low"]


class AlignmentAnalysis(BaseModel):
    summary: str
    category_scores: AlignmentCategoryScores
    matched_areas: list[str]
    material_gaps: list[MaterialGap]
    ignored_differences: list[str]


class RequirementsAssessment(AlignmentAnalysis):
    overall_alignment_score: int = Field(ge=0, le=100)
    classification: Literal[
        "Fully Aligned",
        "Mostly Aligned",
        "Partially Aligned",
        "Misaligned",
    ]


class RequirementsValidationResponse(BaseModel):
    validation_id: UUID
    jira_issue_key: str
    confluence_page_id: str
    assessment: RequirementsAssessment


class StoredRequirementValidation(BaseModel):
    validation_id: UUID
    jira_issue_key: str
    confluence_page_id: str
    assessment: RequirementsAssessment
    jira_content: str
    confluence_content: str