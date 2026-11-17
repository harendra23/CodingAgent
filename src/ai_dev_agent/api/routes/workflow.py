from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from ai_dev_agent.application.dtos.agent_workflow import (
    AgentWorkflowRequest,
    AgentWorkflowResponse,
)
from ai_dev_agent.application.services.agent_workflow_service import (
    AgentWorkflowService,
    WorkflowExecutionError,
)
from ai_dev_agent.config import get_settings
from ai_dev_agent.infrastructure.llm.provider_factory import create_chat_model
from ai_dev_agent.infrastructure.persistence.database import get_session_factory
from ai_dev_agent.infrastructure.persistence.validation_repository import (
    RequirementValidationRepository,
)

router = APIRouter(prefix="/api/v1/workflows", tags=["workflow"])


def get_workflow_service() -> AgentWorkflowService:
    settings = get_settings()
    try:
        model = create_chat_model(settings)
    except ValueError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return AgentWorkflowService(
        model,
        github_token=getattr(settings, "github_token", None),
    )


def get_validation_repository() -> RequirementValidationRepository:
    settings = get_settings()
    return RequirementValidationRepository(get_session_factory(settings.database_url))


@router.post("/run", response_model=AgentWorkflowResponse)
async def run_workflow(
    request: AgentWorkflowRequest,
    service: Annotated[AgentWorkflowService, Depends(get_workflow_service)],
    repository: Annotated[
        RequirementValidationRepository,
        Depends(get_validation_repository),
    ],
) -> AgentWorkflowResponse:
    try:
        validation = await repository.get(request.validation_id)
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=503,
            detail="Unable to load cached validation. Check the database migration and DATABASE_URL.",
        ) from error
    if validation is None:
        raise HTTPException(
            status_code=404,
            detail="Validation ID was not found. Run requirement validation again.",
        )

    try:
        result = await service.run(validation, request.repository_url)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except WorkflowExecutionError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail="Agent workflow failed") from error
    return AgentWorkflowResponse(**result)