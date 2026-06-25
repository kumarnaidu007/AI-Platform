# API Service

Python backend for the AI Development Automation Platform.

## Responsibilities

- REST API for admin and company portals
- Multi-tenant auth and authorization
- LangGraph agent orchestration
- Celery workers for pipeline execution
- External integrations (GitHub, Jira, Teams, etc.)

## Run locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Requires PostgreSQL and Redis — start via `infra/docker-compose.yml`.
