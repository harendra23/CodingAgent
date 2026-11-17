from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from ai_dev_agent.api.routes.agent import router as agent_router
from ai_dev_agent.api.routes.health import router as health_router
from ai_dev_agent.api.routes.requirements import router as requirements_router
from ai_dev_agent.api.routes.workflow import router as workflow_router

app = FastAPI(title="AiDevAgent API", version="0.1.0")
app.include_router(health_router)
app.include_router(agent_router)
app.include_router(requirements_router)
app.include_router(workflow_router)


@app.get("/", include_in_schema=False)
async def requirements_ui() -> FileResponse:
	return FileResponse(
		Path(__file__).parent / "static" / "index.html",
		headers={"Cache-Control": "no-store"},
	)
