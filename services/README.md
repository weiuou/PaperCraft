# Services

Runtime services live here.

- `api/`: HTTP API and persistence layer
- `worker/`: async task execution and pipeline orchestration; current worker
  code is imported from the API Python package and run as a separate Celery
  process
