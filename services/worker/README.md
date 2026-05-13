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
- calculate paperability scoring and page-budget fallback metadata
- retry unfolding with conservative decimation when the first layout attempt
  fails
- write task events, progress updates, completion, and failure details
- provide retry and cancellation hooks for API endpoints

The real image, geometry, unfolding, export, and assembly metadata stages are
integrated through the API project's worker orchestrator. M4 stabilization now
adds scoring, fallback, and recovery guidance on top of that pipeline.
