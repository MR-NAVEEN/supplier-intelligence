# Supplier Intelligence Backend

Django 5 + DRF backend for the Supplier Intelligence Platform (Backend PRD v2).

## Quick start

```powershell
cd "C:\Users\LENOVO T495\Desktop\Tatkal Backend\supplier-intelligence"
copy .env.example .env
..\env\Scripts\python.exe -m pip install -r requirements.txt
..\env\Scripts\python.exe manage.py migrate
..\env\Scripts\python.exe manage.py runserver
```

API base: `http://127.0.0.1:8000/api/`  
Swagger: `http://127.0.0.1:8000/api/docs/`

## Environment

| Variable | Default | Notes |
|----------|---------|-------|
| `DATABASE_URL` | `sqlite:///db.sqlite3` | Switch to Postgres in production |
| `CELERY_TASK_ALWAYS_EAGER` | `True` | Set `False` when Redis/Celery worker running |
| `AI_PROVIDER_MODE` | `stub` | Stub OCR/AI until real services connected |

## Auth

```
POST /api/auth/signup/
{
  "email": "naveen@example.com",
  "password": "YourPassword123!",
  "first_name": "Naveen",
  "last_name": "Kumar",
  "phone": "+91-9000000000",
  "workspace_name": "Pezala"
}
```

No role field. Signup creates a workspace and adds the user as `admin`.

## Workspace header

All workspace-scoped endpoints require:

```
Authorization: Bearer <access_token>
X-Workspace-Id: <workspace_id>
```

## Smoke test

```powershell
..\env\Scripts\python.exe scripts/smoke_test.py
```

## GitHub push

```powershell
cd "C:\Users\LENOVO T495\Desktop\Tatkal Backend\supplier-intelligence"
git init
git add .
git commit -m "Initial supplier-intelligence backend (PRD v2)"
git branch -M main
git remote add origin https://github.com/YOUR_ORG/supplier-intelligence.git
git push -u origin main
```

Replace `YOUR_ORG/supplier-intelligence` with your repository URL.

## PostgreSQL (production)

Update `.env`:

```
DATABASE_URL=postgres://user:pass@host:5432/supplier_intelligence
CELERY_TASK_ALWAYS_EAGER=False
```

Then run `manage.py migrate` on the server.

## Frontend integration

See `C:\Users\LENOVO T495\Documents\Supplier-Intelligence-Frontend-API-Integration.txt`

## Project structure

```
api/
  accounts/      JWT auth, /auth/me
  workspaces/    Workspace + membership (admin|member)
  suppliers/     Supplier CRUD + nested resources
  products/      Product CRUD + bulk/archive
  categories/    Category tree + stats
  catalogues/    Upload sessions, OCR, extractions
  business_cards/ Extract + commit
  jobs/          Unified async job tracking
  search/        Global, quick, saved, history, AI
  notifications/ In-app notifications (camelCase)
  dashboard/     Widget endpoints (camelCase)
  settings_app/  Profile + notification prefs
  activity/      Audit timeline
  analytics/     Product/search analytics
  common/        Envelope, middleware, pagination
config/
  settings/      base, local, test
  celery.py      Celery app
```
