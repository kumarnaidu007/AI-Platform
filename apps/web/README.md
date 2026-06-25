# Web Application

React TypeScript frontend for the AI Development Automation Platform.

## Super Admin UI

| Route | Page |
|-------|------|
| `/admin` | Dashboard (platform setup + tenants) |
| `/admin/integrations` | Integrations catalog (16 types) |
| `/admin/integrations/:key` | Configure platform OAuth connection |
| `/admin/platform-services` | AI services (Claude, E2B, LangSmith, etc.) |
| `/admin/platform-settings` | Global platform settings |
| `/admin/companies` | Companies list |
| `/admin/plans` | Plans with included integrations |
| `/admin/audit-log` | Audit log |
| `/admin/system-health` | System health |

UI loads live data from the FastAPI backend (`/api/admin/*`). Start the API via Docker before running the dev server.

## Database — platform layer tables

- `platform_integrations` — catalog (no secrets)
- `platform_connections` — your OAuth apps (`encrypted_config_ref` → vault)
- `platform_services` — AI/runtime keys (Anthropic, E2B, etc.)
- `platform_settings` — global key-value config
- `plan_platform_integrations` — which integrations each plan includes

## Run locally

```bash
npm install
npm run dev
```

App runs on **http://localhost:5180** (dedicated port — do not use 5173 if another project is running there).

| Portal | URL |
|--------|-----|
| Super Admin login | http://localhost:5180/login |
| Super Admin | http://localhost:5180/admin |
| Company login | http://localhost:5180/c/{slug}/login |
| Company portal | http://localhost:5180/c/{slug} |

Example company: http://localhost:5180/c/acme-corp/login
