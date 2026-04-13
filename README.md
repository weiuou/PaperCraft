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

This commit sets up the engineering skeleton for issue `#2`:

- repository structure
- base config templates
- local Docker dependencies
- bootstrap scripts
- onboarding documentation
