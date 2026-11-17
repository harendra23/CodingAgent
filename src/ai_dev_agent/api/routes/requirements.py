from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from mypy.state import state
from sqlalchemy.exc import SQLAlchemyError

from ai_dev_agent.application.dtos.requirements_validation import (
    RequirementsValidationRequest,
    RequirementsValidationResponse,
)
from ai_dev_agent.application.services.requirements_validation_service import (
    RequirementSourceError,
    RequirementsValidationService,
)
from ai_dev_agent.config import get_settings
from ai_dev_agent.infrastructure.llm.provider_factory import create_chat_model
from ai_dev_agent.infrastructure.persistence.database import get_session_factory
from ai_dev_agent.infrastructure.persistence.validation_repository import (
    RequirementValidationRepository,
)

from ai_dev_agent.infrastructure.logging.workflow_trace import WorkflowTrace

router = APIRouter(prefix="/api/v1/requirements", tags=["requirements"])


def get_requirements_service() -> RequirementsValidationService:
    settings = get_settings()
    try:
        return RequirementsValidationService(settings, create_chat_model(settings))
    except ValueError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


def get_validation_repository() -> RequirementValidationRepository:
    settings = get_settings()
    return RequirementValidationRepository(get_session_factory(settings.database_url))


@router.post("/validate", response_model=RequirementsValidationResponse)
async def validate_requirements(
    request: RequirementsValidationRequest,
    service: Annotated[RequirementsValidationService, Depends(get_requirements_service)],
    repository: Annotated[
        RequirementValidationRepository,
        Depends(get_validation_repository),
    ],
) -> RequirementsValidationResponse:
    try:
        assessment, jira_content, confluence_content = await service.validate_with_snapshot(
            request.jira_issue_key,
            request.confluence_page_id,
        )
        trace = WorkflowTrace(state["run_id"])
        trace.record(
                                step_order=-1,
                                step_id="requirement_validation",
                                step_name="store Requirement Validation",
                                status="completed",
                                error=None,
                            )
    except RequirementSourceError as error:
        trace = WorkflowTrace(state["run_id"])
        trace.record(
                                        step_order=-2,
                                        step_id="requirement_validation_error",
                                        step_name="Requirement Validation error",
                                        status="completed",
                                        error=error,
                                    )
        raise HTTPException(status_code=502, detail=str(error)) from error
    except ValueError as error:
        trace = WorkflowTrace(state["run_id"])
        trace.record(
                                               step_order=-3,
                                                step_id="requirement_validation_error",
                                                step_name="Requirement Validation error",
                                                status="completed",
                                                error=error,
                                            )
        raise HTTPException(status_code=422, detail=str(error)) from error
    try:
        print(f"Storing validation result for Jira issue {request.jira_issue_key} and Confluence page {request.confluence_page_id} and repository {repository}" )
        cached = await repository.create(
            request.jira_issue_key,
            request.confluence_page_id,
            assessment,
            jira_content,
            confluence_content,
        )
    except SQLAlchemyError as error:
        trace = WorkflowTrace(state["run_id"])
        trace.record(
                        step_order=-4,
                        step_id="requirement_validation",
                        step_name="store Requirement Validation",
                        status="failure",
                        error=error,
                    )
        raise HTTPException(
            status_code=503,
            detail="Unable to store validation. Apply the requirement validations migration and check DATABASE_URL.",
        ) from error
    except Exception as error:
        trace = WorkflowTrace(state["run_id"])
        trace.record(
                                step_order=-5,
                                step_id="requirement_validation",
                                step_name="store Requirement Validation",
                                status="failure",
                                error=error,
                            )   
        raise HTTPException(status_code=503, detail="Unable to store validation result") from error
    return RequirementsValidationResponse(
        validation_id=cached.validation_id,
        jira_issue_key=request.jira_issue_key,
        confluence_page_id=request.confluence_page_id,
        assessment=assessment,
    )