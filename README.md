# AI Development Automation Platform

Enterprise multi-tenant platform for automated software development using AI agents.

## Monorepo structure

```
AI-Platform/
├── apps/
│   ├── api/                    # Backend — Python FastAPI service
│   │   ├── app/                # FastAPI application (routes, middleware)
│   │   ├── agents/             # LangGraph AI agents
│   │   ├── db/                 # Database session & utilities
│   │   ├── models/             # SQLAlchemy ORM models
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   ├── services/           # Business logic & external integrations
│   │   ├── workers/            # Celery background workers
│   │   ├── templates/          # Stack scaffolding templates
│   │   ├── config.py
│   │   └── requirements.txt
│   │
│   └── web/                    # Frontend — React TypeScript admin portal
│       ├── Dockerfile          # Production image (nginx)
│       ├── nginx.conf          # SPA + /api proxy for Docker
│       ├── src/
│       │   ├── pages/          # Route pages (admin, company, auth)
│       │   ├── components/     # Shared UI components
│       │   └── services/       # API client (axios)
│       └── package.json
│
├── packages/
│   └── shared/                 # Shared types, constants, contracts (future)
│
├── infra/                      # Infrastructure & deployment
│   ├── docker-compose.yml
│   └── db/init/                # PostgreSQL schema migrations
│
├── docs/
│   └── architecture/           # Architecture & design docs
│
├── .env.example
└── README.md
```

## Stack

| Layer | Location | Technology |
|-------|----------|------------|
| API service | `apps/api` | Python, FastAPI, SQLAlchemy, LangGraph |
| Web app | `apps/web` | React 18, TypeScript, Vite |
| Database | `infra` | PostgreSQL 16 |
| Queue | `infra` | Redis (Celery — phase 2+) |

## Quick start — Full stack (Docker)

Clone the repo, then start **PostgreSQL, Redis, API, Celery worker, and web UI** with one command:

```bash
cp .env.example .env
cd infra
docker compose up -d --build
```

| Service | URL |
|---------|-----|
| Web UI | http://localhost:5180 |
| API | http://localhost:8000 |
| API health | http://localhost:8000/health |

Default logins are seeded on first API start (see `apps/api/services/seed.py`).

The web container serves the React build and proxies `/api` to the API service. OAuth redirect URIs use `http://localhost:8000/api/oauth/...` — configure GitHub/Jira in **Admin → Integrations**.

Verify database:

```bash
docker exec ai-dev-platform-db psql -U aidev -d ai_dev_platform -c "\dt"
```

To stop:

```bash
cd infra
docker compose down
```

## Quick start — Database only

```bash
cd infra
docker compose up -d postgres redis
```

Connection string:

```
postgresql://aidev:aidev_local@localhost:5432/ai_dev_platform
```

Copy environment file from repo root:

```bash
cp .env.example .env
```

## Run API service (local dev, without Docker)

```bash
cd apps/api
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health check: http://localhost:8000/health

## Run web app (local dev, without Docker)

```bash
cd apps/web
npm install
npm run dev
```

Opens http://localhost:5180 with Vite proxy to the API on port 8000.

## Database tables

**Tenancy:** `users`, `plans`, `companies`, `company_members`, `company_settings`, `integration_configs`

**Automation:** `projects`, `pipeline_runs`, `pipeline_steps`, `agent_logs`

**Artifacts:** `prd_documents`, `architecture_docs`, `external_tasks`, `pull_requests`, `deployments`, `validation_reports`

**Ops:** `audit_events`, `usage_ledger`
