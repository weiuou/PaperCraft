# AI PaperCraft Studio Current Development Plan

Last updated: 2026-05-13

## Current Position

The repository has completed the M1 foundation and the M2 mock closed loop.
M3 is implemented in code through real preprocessing, base mesh generation,
paperability repair, constrained decimation, unfolding/layout, PDF export, and
assembly metadata generation.

M4 has started with issue `#14`: paperability scoring, automatic fallback,
conservative unfolding retry, stage-level retry selection, and user-facing next
actions.

## Near-Term Execution Plan

### M1.1 Product and Acceptance Contract

Owner focus: product, QA, engineering lead

Status: completed.

- Freeze MVP scope for inputs, categories, outputs, and explicit non-goals.
- Define acceptance samples for happy paths and known failure paths.
- Define buildability metrics: completion rate, page count, part count,
  difficulty score, and manual assembly bar.

Exit criteria:

- Issue `#1` can be closed.
- Frontend, backend, and algorithm work share the same acceptance target.

### M1.2 Core Data and Task Contract

Owner focus: backend, worker

Status: completed.

- Implement the first database schema for users, projects, source images,
  generation tasks, parameter snapshots, artifacts, assembly metadata, and task
  events.
- Define object storage key conventions.
- Define task status/stage transitions and prohibited transitions.
- Define the first error code catalog and API error response shape.

Exit criteria:

- Issue `#3` can be closed.
- Migrations run against the local Postgres service.
- Later API and worker work can rely on stable field names and enum values.

### M1.3 Minimal API Surface

Owner focus: backend

Status: completed.

- Build project create/list/detail endpoints.
- Build image upload validation and metadata persistence.
- Build task creation and task status endpoints.
- Return stable validation and missing-resource errors.

Exit criteria:

- Issue `#4` can be closed.
- Frontend can create a project, upload images, start a task, and poll status.

### M1.4 Async Worker Backbone

Owner focus: backend, worker

Status: completed.

- Integrate Celery with Redis.
- Add task enqueueing from API to worker.
- Add a mock stage executor for queue and state-machine validation.
- Persist progress, stage timestamps, and failure details.

Exit criteria:

- Issue `#5` can be closed.
- Long-running pipeline behavior can be validated before real algorithms land.

### M2 Demo Loop

Owner focus: frontend, backend, worker

Status: completed.

Completed:

- Build create-project, upload, parameter, and progress frontend flows.
- Connect frontend task polling to backend status, artifacts, and assembly
  metadata.
- Run the full stack through Docker Compose for local internal demos.
- Write source uploads and mock preview/net/PDF artifacts through the local
  S3-compatible object storage path.

Current backend support:

- completed tasks record a 3D preview placeholder, real or mock net artifacts,
  PDF export placeholder, and assembly metadata.
- task status responses include available artifacts and assembly metadata for
  frontend polling and workbench rendering.
- artifact downloads are exposed through the API and read from MinIO in the
  Docker demo stack, while tests use in-memory storage substitutes.
- Docker Compose can run the web, API, worker, database, Redis, and MinIO stack.
- the workbench renders mock net JSON with page switching and part lists for the
  internal demo flow.
- the demo flow supports task history, regeneration, cancellation, retry, and
  controlled mock failures.

Exit criteria:

- Issues `#6`, `#7`, and `#8` are closed.
- The product can be demonstrated from upload through fake export, including
  failure, cancellation, retry, and repeat generation paths.

### M3 Real Pipeline

Owner focus: worker, backend, algorithm

Status: completed.

Completed in code:

- Issue `#9`: real image preprocessing writes `preprocess_mask` and
  `preprocess_crop` artifacts.
- Issue `#10`: deterministic category-constrained base mesh generation writes
  `base_mesh` and `preview_model` artifacts.
- Issue `#11`: paperability repair and constrained decimation write
  `repaired_mesh` and `low_poly_mesh` artifacts.
- Issue `#12`: unfolding/layout writes structured `net_json` and `net_svg`
  artifacts.
- Issue `#13`: PDF export writes `export_pdf` artifacts and real assembly
  metadata.

Exit criteria:

- Issues `#9` through `#13` are closed.
- M3 milestone is closed.

### M4 Stabilization

Owner focus: worker, backend, frontend, QA

Status: in progress.

Current issue:

- Issue `#14`: paperability scoring, automatic fallback, and stage-level retry.

Implemented on the active branch:

- Rule-based `paperability_score` and buildability warnings on repaired meshes.
- Automatic complexity reduction when requested poly count exceeds page budget.
- Conservative decimation and unfolding retry when the first unfolding attempt
  fails.
- `next_actions` in task status responses for failure recovery and fallback
  guidance.
- Frontend retry-stage selection for failed or canceled tasks.

Remaining M4 work:

- Issue `#15`: task-level observability, metrics, logging, and alerting.
- Issue `#17`: regression sample suite, manual assembly QA, and beta release
  checklist.

## Next Implementation Focus

Finish issue `#14` through PR review and merge, then move to issue `#15` for
observability.
