from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage

from ai_dev_agent.application.agent_graph import build_agent_graph


class AgentService:
    def __init__(self, model: BaseChatModel) -> None:
        self._graph = build_agent_graph(model)

    async def invoke(self, prompt: str) -> str:
        result = await self._graph.ainvoke({"messages": [HumanMessage(content=prompt)]})
        return str(result["messages"][-1].content)
