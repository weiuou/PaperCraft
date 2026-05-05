# services/api

FastAPI backend service for project, upload, task, artifact, and export APIs.

Planned responsibilities:

- project and task APIs
- upload handling
- auth and authorization
- artifact lookup
- task dispatch to the worker queue

## Current implementation

The first implementation slice defines the core data and task contracts for
issues `#3` and `#4`:

- SQLAlchemy models for the core MVP entities
- Alembic migration `20260505_0001_core_schema`
- task state-machine helpers
- object storage key helpers
- API error response schema and error code enum
- FastAPI app entrypoint with health check and `/api` routes
- project create/list/detail endpoints
- source image upload endpoint with MIME, size, count, and decode validation
- task creation endpoint with immutable parameter snapshot persistence
- task status endpoint with stable stage, progress, and error fields

Implemented endpoints:

- `GET /health`
- `POST /api/projects`
- `GET /api/projects`
- `GET /api/projects/{project_id}`
- `POST /api/projects/{project_id}/images`
- `POST /api/projects/{project_id}/tasks`
- `GET /api/tasks/{task_id}`

## Local commands

Install and run tests:

```bash
uv run --extra dev pytest
```

Generate SQL for the current migration:

```bash
uv run alembic upgrade head --sql
```

Apply migrations to the configured database:

```bash
uv run alembic upgrade head
```
