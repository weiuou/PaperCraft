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
issue `#3`:

- SQLAlchemy models for the core MVP entities
- Alembic migration `20260505_0001_core_schema`
- task state-machine helpers
- object storage key helpers
- API error response schema and error code enum

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
