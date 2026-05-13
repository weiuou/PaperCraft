# services/api

FastAPI backend service for project, upload, task, artifact, and export APIs.

Planned responsibilities:

- project and task APIs
- upload handling
- auth and authorization
- artifact lookup
- task dispatch to the worker queue

## Current implementation

The service now covers the M1 foundation, M2 demo loop, M3 real pipeline, and
the first M4 stabilization slice:

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
- Celery app configuration backed by Redis
- task enqueueing from the task creation API
- worker pipeline orchestrator with real preprocessing, mesh generation,
  paperability repair, constrained decimation, unfolding/layout, and PDF export
- task events, progress updates, completion, failure write-back, and retry or
  cancellation hooks
- task status next-action suggestions for fallback and recovery guidance
- artifact records for preprocessing, mesh, paperability, decimation, net JSON,
  net SVG, preview, PDF export, and assembly metadata
- real PDF export and assembly metadata generation from net artifacts
- paperability scoring, automatic page-budget fallback, and conservative
  unfolding retry metadata

Implemented endpoints:

- `GET /health`
- `POST /api/projects`
- `GET /api/projects`
- `GET /api/projects/{project_id}`
- `POST /api/projects/{project_id}/images`
- `POST /api/projects/{project_id}/tasks`
- `GET /api/tasks/{task_id}` including artifacts and assembly metadata when
  available
- `GET /api/artifacts/{artifact_id}/download` for stored artifacts, with a mock
  fallback only for legacy/mock artifacts

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

Run the API:

```bash
uv run uvicorn app.main:app --reload
```

Run the worker:

```bash
uv run celery -A app.worker.celery_app:celery_app worker --loglevel=INFO
```

Run the API, worker, and dependencies through Docker Compose:

```bash
docker compose -f ../../infra/docker/docker-compose.yml up -d --build api worker
```
