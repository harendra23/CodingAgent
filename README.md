# AiDevAgent

A modular AI coding-agent backend built for Python 3.12, FastAPI, and LangGraph. It is organized into API, application, domain, and infrastructure layers, with provider adapters for OpenAI, Anthropic, Gemini, GitHub, Jira, Confluence, PostgreSQL, and pgvector.

## Requirements

- Python 3.12
- Docker and Docker Compose for the local PostgreSQL/pgvector service
- API credentials for the LLM and external services you choose to use

## Setup

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Set the selected provider's credentials in `.env`. Also configure `JIRA_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `CONFLUENCE_URL`, `CONFLUENCE_EMAIL`, and `CONFLUENCE_API_TOKEN` to enable requirement reviews. Keep credentials out of source control; rotate any token that has been committed or otherwise exposed.
Provider defaults are `gpt-4.1`, `claude-sonnet-4-5`, and `gemini-2.5-pro`; set `LLM_MODEL` to another supported model ID, such as `gpt-5`, when needed.

Use the Confluence adapter asynchronously; configure `CONFLUENCE_URL`, `CONFLUENCE_EMAIL`, and `CONFLUENCE_API_TOKEN` in `.env`:

```python
from ai_dev_agent.config import get_settings
from ai_dev_agent.infrastructure.confluence import ConfluenceClient


async def find_pages() -> list[dict[str, object]]:
	async with ConfluenceClient.from_settings(get_settings()) as confluence:
		return await confluence.search('type = "page" AND text ~ "release"')
```

## Run

```powershell
uvicorn ai_dev_agent.api.main:app --reload --app-dir src
```

Open `http://localhost:8000/` for the requirement review UI. Compare requirements with `POST /api/v1/requirements/validate`, or use **Run delivery workflow** to execute the staged workflow through `POST /api/v1/workflows/run`. The workflow form also requires an HTTPS GitHub repository URL. Source text and a bounded snapshot of tracked repository files are sent to the configured LLM provider for analysis; obvious environment and credential files are excluded.

## Delivery workflow

The LangGraph workflow follows these stages in order:

1. Confluence Requirement
2. Requirement Validation
3. Repository Impact Analysis
4. Technical Specification
5. Architecture Design
6. Task Breakdown
7. Code Generation
8. Unit Tests
9. Traceability Matrix
10. Pull Request

If semantic alignment is below 80%, the workflow stops after validation and marks later stages skipped for human review. Otherwise, the service clones the GitHub repository under the ignored `repos/cloned-projects/` directory, analyzes a bounded snapshot, and applies a validated Code Generation diff only to that local clone. It does not execute generated code or tests, create branches, push changes, or publish a PR. Review the changed files locally before committing or sharing them. Workflow instructions are in `src/ai_dev_agent/skills/agent_workflow/SKILL.md`.

Workflow results are presented as readable summaries and headed sections. Architecture Design includes a rendered Mermaid diagram (with source fallback if the renderer is unavailable), Traceability Matrix uses a table, and Code Generation shows changed files with the patch available on demand.

## Workflow trace logs

Each workflow writes ordered JSON Lines events to `logs/workflow-trace.jsonl` by default. Records include a UTC timestamp, run ID, step order/name, status (`started`, `success`, `failure`, or `skipped`), and a sanitized error type/description when applicable. Source text, repository contents, and credentials are not logged. Rotated files are kept beside the active log. Set `WORKFLOW_TRACE_LOG_PATH` to choose another path. The local Compose setup persists `./logs` on the host; container filesystem logs in Cloud Run are ephemeral.

The existing `GET /health` and `POST /api/v1/agent/invoke` routes remain available. Interactive API docs are at `/docs`.

The API does not include application-level user authentication yet. Keep deployments behind an authenticated gateway until an authorization model is implemented.

## Database

Start the local pgvector-enabled PostgreSQL instance with:

```powershell
docker compose up -d db
```

Set `DATABASE_URL` for the application. Schema migrations are intentionally not run at startup; add and apply migrations before persisting application data in shared environments.

## Checks

```powershell
python -m pytest
ruff check .
```

## Project map

- `src/ai_dev_agent/api`: FastAPI application and HTTP routes
- `src/ai_dev_agent/application`: agent graph and use-case contracts
- `src/ai_dev_agent/domain`: core entities and enums
- `src/ai_dev_agent/infrastructure`: LLM, source-control, requirements, and persistence adapters
- `prompts`: versioned prompt templates
- `tests`: unit and API integration tests
- `repos/cloned-projects`: local checkout location; contents are ignored by Git

See `docs/architecture.md` for dependency boundaries and integration notes.
