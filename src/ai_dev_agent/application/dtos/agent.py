from pydantic import BaseModel, Field


class AgentInvokeRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20_000)


class AgentInvokeResponse(BaseModel):
    response: str
