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
- run the mock pipeline executor stage by stage
- write task events, progress updates, completion, and failure details
- provide retry and cancellation hooks for later API endpoints

The real image, geometry, unfolding, and export implementations will replace
the mock stage executor in later milestone work.
