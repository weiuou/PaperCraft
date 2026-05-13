# AI PaperCraft Studio

This repository hosts the MVP implementation for `AI PaperCraft Studio`, a web platform that turns user-uploaded images into printable papercraft outputs.

## Repository Layout

```text
apps/
  web/                # Next.js frontend
services/
  api/                # FastAPI API service
  worker/             # Async worker and pipeline orchestration
packages/
  shared-types/       # Shared DTOs and schemas
  geometry-core/      # Mesh repair and geometry utilities
  unfold-core/        # Unfolding and pagination logic
  export-core/        # PDF/SVG export helpers
docs/
  prd/                # PRD references
  architecture/       # Architecture references
infra/
  docker/             # Local infrastructure definitions
  scripts/            # Local bootstrap scripts
```

## Package Management Conventions

- JavaScript and TypeScript workspace packages use `pnpm`.
- Python services will use service-local virtual environments. When implementation starts, prefer `uv` or standard `venv` per service instead of a single shared Python environment.
- Cross-service configuration keys live in `.env.example`.

## Environment Variables

Copy `.env.example` to `.env` before running local services.

Core variables:

- `DATABASE_URL`
- `REDIS_URL`
- `S3_ENDPOINT`
- `S3_ACCESS_KEY`
- `S3_SECRET_KEY`
- `S3_BUCKET_UPLOADS`
- `S3_BUCKET_ARTIFACTS`
- `MAX_UPLOAD_MB`
- `TASK_TIMEOUT_SECONDS`

## Local Infrastructure

The local stack uses Docker Compose and provides:

- `web` on `localhost:3000`
- `api` on `localhost:8000`
- `postgres` on `localhost:5432`
- `redis` on `localhost:6379`
- `minio` on `localhost:9000` with console on `localhost:9001`

### Start

```bash
docker compose -f infra/docker/docker-compose.yml up -d
```

or:

```powershell
./infra/scripts/local-up.ps1
```

To rebuild application images while starting the full stack:

```powershell
pnpm dev:docker
```

### Check Health

```bash
docker compose -f infra/docker/docker-compose.yml ps
```

or:

```powershell
./infra/scripts/local-health.ps1
```

### Stop

```bash
docker compose -f infra/docker/docker-compose.yml down
```

or:

```powershell
./infra/scripts/local-down.ps1
```

## First-Time Setup

1. Copy `.env.example` to `.env`.
2. Start the local infrastructure stack.
3. Confirm `postgres`, `redis`, and `minio` are healthy.
4. Open the MinIO console at `http://localhost:9001`.
5. Verify the local buckets exist:
   - `papercraft-local-uploads`
   - `papercraft-local-artifacts`

## Current Status

The project has completed M1, M2, and M3. The current M4 branch adds
stabilization behavior on top of the real pipeline: paperability scoring,
automatic complexity fallback, conservative unfolding retry, stage-level retry
selection, and user-facing next actions.

The current real pipeline runs
preprocessing, base mesh generation, paperability repair, constrained
decimation, unfolding/layout, PDF export, and assembly metadata generation.

Completed work:

- repository structure, local infra, and onboarding docs
- frozen MVP scope and acceptance contract
- core SQLAlchemy models and Alembic schema for projects, tasks, artifacts, and
  assembly metadata
- project, upload, task creation, and task status APIs
- Celery/Redis worker backbone with stage progression, retry, and cancellation
- object storage-backed source image uploads and artifact downloads through the
  local MinIO stack
- Docker Compose services for web, API, worker, database, Redis, and MinIO
- frontend demo flow with project creation, image upload, task polling, mock
  workbench previews, paper-net page switching, task history, regeneration,
  cancellation, retry, controlled mock failures, and PDF download
- real M3 artifacts for `preprocess_mask`, `preprocess_crop`, `base_mesh`,
  `preview_model`, `repaired_mesh`, `low_poly_mesh`, `net_json`, `net_svg`,
  and `export_pdf`
- real assembly metadata derived from the exported net
- M4 paperability scoring and automatic fallback metadata on mesh/net artifacts
- task status `next_actions` for clear recovery guidance
- frontend retry-stage selection for failed or canceled tasks

Next development focus:

- finish issue `#14` by merging the M4 fallback branch
- continue M4 with observability, regression samples, and beta QA
