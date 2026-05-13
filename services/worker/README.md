# services/worker

The worker runs from the API Python project so it can share settings, database
models, task state helpers, and domain enums with the HTTP API.

Current entrypoint:

```bash
cd ../api
uv run celery -A app.worker.celery_app:celery_app worker --loglevel=INFO
```

Current responsibilities:

- consume queued generation tasks from Redis through Celery
- run the generation pipeline stage by stage
- execute real M3 preprocessing, base mesh generation, paperability repair,
  constrained decimation, unfolding/layout, and PDF export
- write task events, progress updates, completion, and failure details
- provide retry and cancellation hooks for API endpoints

The real image, geometry, unfolding, export, and assembly metadata stages are
integrated through the API project's worker orchestrator.
