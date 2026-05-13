# Regression Runbook

Last updated: 2026-05-13

This runbook defines the repeatable MVP regression process for the sample suite
in `docs/qa/regression-sample-suite.json`.

## Preconditions

- Work from a clean checkout of the target release commit.
- Copy `.env.example` to `.env` and use local-only credentials.
- Start the full Docker Compose stack with `pnpm dev:docker`.
- Confirm `web`, `api`, `worker`, `postgres`, `redis`, and `minio` are healthy.
- Confirm the uploads and artifacts buckets exist in MinIO.

## Required Commands

```bash
uv run --directory services/api --extra dev pytest
pnpm --filter @papercraft/web typecheck
docker compose -f infra/docker/docker-compose.yml ps
```

## Sample Execution Procedure

1. Open the web app at `http://localhost:3000`.
2. For each positive sample, create a new project using the manifest category.
3. Upload the listed source image or image set.
4. Use the manifest paper size and max page budget.
5. Start generation and wait for terminal status.
6. Download `export_pdf`, `net_json`, and task metrics evidence.
7. Record the result in the run record table below.
8. For failure samples, verify the expected error code, failing stage, and next
   action guidance.

## Run Record Template

| Field | Value |
| --- | --- |
| Release commit |  |
| Runner |  |
| Run started at |  |
| Run completed at |  |
| Environment | local Docker Compose |
| API metrics snapshot | `/api/metrics/tasks` response saved |

| Sample ID | Status | Task ID | Error code | Page count | Part count | PDF opened | Manual QA needed | Notes |
| --- | --- | --- | --- | ---: | ---: | --- | --- | --- |
| pet-001 |  |  |  |  |  |  |  |  |
| pet-002 |  |  |  |  |  |  |  |  |
| pet-003 |  |  |  |  |  |  |  |  |
| pet-004 |  |  |  |  |  |  |  |  |
| pet-005 |  |  |  |  |  |  |  |  |
| bust-001 |  |  |  |  |  |  |  |  |
| bust-002 |  |  |  |  |  |  |  |  |
| bust-003 |  |  |  |  |  |  |  |  |
| bust-004 |  |  |  |  |  |  |  |  |
| bust-005 |  |  |  |  |  |  |  |  |
| object-001 |  |  |  |  |  |  |  |  |
| object-002 |  |  |  |  |  |  |  |  |
| object-003 |  |  |  |  |  |  |  |  |
| object-004 |  |  |  |  |  |  |  |  |
| object-005 |  |  |  |  |  |  |  |  |
| background-001 |  |  |  |  |  |  |  |  |
| background-002 |  |  |  |  |  |  |  |  |
| background-003 |  |  |  |  |  |  |  |  |
| upload-001 |  |  |  |  |  |  |  |  |
| upload-002 |  |  |  |  |  |  |  |  |
| upload-003 |  |  |  |  |  |  |  |  |

## Pass Criteria

- At least 60% of positive samples complete with downloadable PDFs.
- Every accepted PDF opens locally and contains page numbers, cut lines, fold
  lines, glue flaps, and pair numbering.
- Page count is within the manifest budget or has explicit fallback metadata.
- Failure samples return the expected error code or a documented recovery path.
- `/api/metrics/tasks` can report completion rate, failure rate, export rate,
  stage durations, and average page/part counts.

