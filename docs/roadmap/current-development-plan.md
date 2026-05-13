# AI PaperCraft Studio Current Development Plan

Last updated: 2026-05-13

## Current Position

The repository has completed the M1 foundation and the M2 mock closed loop.
M3 is implemented in code through real preprocessing, base mesh generation,
paperability repair, constrained decimation, unfolding/layout, PDF export, and
assembly metadata generation.

GitHub bookkeeping is slightly behind the code state. PR `#27` merged the
unfolding and layout implementation for issue `#12`, but issue `#12` and the
tracking checkbox in issue `#16` are still open. Issue `#13` should be closed
after this export implementation is merged.

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

Status: code-complete pending issue/PR bookkeeping.

Completed in code:

- Issue `#9`: real image preprocessing writes `preprocess_mask` and
  `preprocess_crop` artifacts.
- Issue `#10`: deterministic category-constrained base mesh generation writes
  `base_mesh` and `preview_model` artifacts.
- Issue `#11`: paperability repair and constrained decimation write
  `repaired_mesh` and `low_poly_mesh` artifacts.
- Issue `#12`: unfolding/layout writes structured `net_json` and `net_svg`
  artifacts. GitHub issue closure is still pending.
- Issue `#13`: PDF export writes `export_pdf` artifacts and real assembly
  metadata.

Remaining:

- Run a full Docker Compose demo from upload through real PDF download.
- Close/update issues `#12`, `#13`, and tracking issue `#16`.

## Next Implementation Focus

The next implementation slice should start M4 with paperability scoring and
automatic fallback because those directly affect real-pipeline completion rate.
