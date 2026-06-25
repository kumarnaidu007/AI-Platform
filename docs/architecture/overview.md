# Architecture Overview

## Monorepo layout

| Path | Purpose |
|------|---------|
| `apps/api` | Backend API service (FastAPI) |
| `apps/web` | Frontend web application (React) |
| `packages/shared` | Shared types and contracts |
| `infra` | Docker, database, deployment |
| `docs` | Architecture and design documentation |

## Multi-tenancy model

```
Platform (Super Admin)
  └── Company (tenant)
        └── Project (AI dev automation unit)
              └── Pipeline Run (agent execution)
```

All tenant data is scoped by `company_id`. Companies have members, integrations, projects, and usage limits.

## Communication

```
apps/web  ──HTTP/WS──►  apps/api  ──►  PostgreSQL
                              └──►  Redis (Celery)
                              └──►  External APIs (GitHub, Jira, LLM, E2B)
```
