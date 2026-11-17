# Architecture

## Runtime

The HTTP boundary is FastAPI. Use cases and LangGraph workflows live in the application layer. Domain entities and enums are independent of web frameworks and vendors. Infrastructure implements application-facing ports for model providers, source control, requirements systems, and persistence.

## Dependency direction

`api -> application -> domain`

`infrastructure -> application + domain`

The API composition root selects concrete infrastructure adapters. Domain code must not import FastAPI, LangChain, database drivers, or vendor SDKs.

The starter API has no application-level user authentication. Deploy it only behind an authenticated gateway until authorization and per-user access controls are implemented.

## Requirement validation

The requirements endpoint reads the Jira issue and Confluence page using server-side credentials, normalizes their descriptions, and submits the source text to the configured LLM for a structured alignment assessment. Treat the response as advisory and review it against the source documents. Do not send sensitive source content to a provider unless its data-handling policy is acceptable for the workspace.

## Agent delivery workflow

`POST /api/v1/workflows/run` accepts a Jira issue key, Confluence page ID, and HTTPS GitHub repository URL. It runs the ordered workflow: Confluence requirement retrieval, requirement validation, repository impact analysis, technical specification, architecture design, task breakdown, code generation, unit tests, traceability matrix, and pull-request draft. Alignment below 80% blocks all later stages for human review.

The service clones the requested GitHub repository into the ignored `repos/cloned-projects/` workspace and sends a bounded, tracked-text snapshot to the LLM for impact analysis. Environment and obvious credential/key files are excluded. Code Generation applies a validated unified diff to that local clone; the service never executes generated code or tests, creates branches, pushes changes, or publishes a pull request. Review local changes before committing. The workflow instructions and stage boundaries live in `skills/agent_workflow/SKILL.md`.

Stage output is returned as structured artifacts with summaries and sections. Architecture artifacts may include Mermaid diagrams, rendered in the browser with a source fallback; traceability rows render as a table, and code diffs are expandable rather than shown as the primary summary.

## Workflow trace logs

The graph writes one JSONL event per step transition to `WORKFLOW_TRACE_LOG_PATH` (default `logs/workflow-trace.jsonl`) using TRACE-level rotating file logging. Each event contains run correlation, timestamp, stable step order, status, and a redacted error description where applicable. Inputs, source text, and repository contents are intentionally excluded.

## LLM providers

`LLM_PROVIDER` selects OpenAI, Anthropic, or Google Gemini. `LLM_MODEL` may override that provider's model name. API keys are read from environment settings and must not be committed. Provider calls occur only when an agent request is handled.

## Integrations

GitHub, Jira, and Confluence clients are adapters. Credentials and base URLs are configured through environment variables. Keep authorization checks and outbound request scoping in their application-facing services; do not let prompts grant additional repository or ticket permissions.

## Persistence and vectors

PostgreSQL is accessed asynchronously through SQLAlchemy. The pgvector extension is available in the local database image. Migrations should own extension, schema, and vector-index creation; the API does not mutate schema during startup. Choose embedding dimensions and distance operators together with the embedding model before adding persisted vectors.

## Local development

Use Python 3.12, install the project with its `dev` extra, and run PostgreSQL using `docker compose up -d db`. Copy `.env.example` to `.env` and add credentials only for integrations in use. Run tests with `python -m pytest`.
