# Beta Release Checklist

Last updated: 2026-05-13

## Pre-Release Gates

- `main` is green for `uv run --directory services/api --extra dev pytest`.
- Frontend typecheck passes with `pnpm --filter @papercraft/web typecheck`.
- Docker Compose stack starts and reports healthy services.
- Regression runbook has been executed for the target release commit.
- Manual assembly QA has at least one accepted sample from each positive group:
  `pet`, `bust`, and `simple_object`.
- `/api/metrics/tasks` reports completion, failure, duration, and export
  metrics for the regression run.
- Known limitations are documented in release notes.

## Release Notes Template

| Field | Value |
| --- | --- |
| Version or commit |  |
| Release owner |  |
| Regression run record |  |
| Accepted sample count |  |
| Known failures |  |
| Rollback target |  |

## Rollback Approach

1. Keep the previous accepted commit SHA in the release notes.
2. Stop the Docker Compose stack.
3. Check out the rollback commit.
4. Rebuild the app containers with `pnpm dev:docker`.
5. Confirm `/health`, `/api/metrics/tasks`, project creation, upload, task
   polling, and artifact download still work.
6. Preserve MinIO artifacts and database records unless the rollback explicitly
   requires a clean local environment.

## Beta Exit Criteria

- No release-blocking upload, task creation, polling, export, or download bugs.
- Positive sample completion rate is at or above 60%.
- Failures show user-facing next actions.
- Metrics identify the highest-failure stage.
- Manual QA accepts at least one generated PDF per supported category.

