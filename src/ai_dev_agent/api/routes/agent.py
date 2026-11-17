from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from ai_dev_agent.application.dtos.agent import AgentInvokeRequest, AgentInvokeResponse
from ai_dev_agent.application.services.agent_service import AgentService
from ai_dev_agent.config import get_settings
from ai_dev_agent.infrastructure.llm.provider_factory import create_chat_model

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


def get_agent_service() -> AgentService:
    try:
        model = create_chat_model(get_settings())
    except ValueError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return AgentService(model)


@router.post("/invoke", response_model=AgentInvokeResponse)
async def invoke_agent(
    request: AgentInvokeRequest,
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> AgentInvokeResponse:
    response = await service.invoke(request.prompt)
    return AgentInvokeResponse(response=response)
