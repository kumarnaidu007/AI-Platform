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

## Quick start — Database

```bash
cd infra
docker compose up -d
```

Verify:

```bash
docker exec ai-dev-platform-db psql -U aidev -d ai_dev_platform -c "\dt"
```

Connection string:

```
postgresql://aidev:aidev_local@localhost:5432/ai_dev_platform
```

Copy environment file from repo root:

```bash
cp .env.example .env
```

## Run API service

```bash
cd apps/api
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health check: http://localhost:8000/health

## Run web app

```bash
cd apps/web
npm install
npm run dev
```

## Database tables

**Tenancy:** `users`, `plans`, `companies`, `company_members`, `company_settings`, `integration_configs`

**Automation:** `projects`, `pipeline_runs`, `pipeline_steps`, `agent_logs`

**Artifacts:** `prd_documents`, `architecture_docs`, `external_tasks`, `pull_requests`, `deployments`, `validation_reports`

**Ops:** `audit_events`, `usage_ledger`
