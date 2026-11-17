# AiDevAgent workspace guidance

This workspace is a Python 3.12 service using FastAPI and LangGraph. Follow the API/application/domain/infrastructure boundaries described in `docs/architecture.md`.

- Keep provider credentials in environment variables; never commit secrets.
- Use async APIs for HTTP and PostgreSQL paths.
- Keep LLM, Jira, Confluence, and GitHub SDK usage inside infrastructure adapters.
- Make changes narrowly, add focused tests, and run `python -m pytest` plus `ruff check .` when available.
- Do not claim checks passed unless they were executed.
