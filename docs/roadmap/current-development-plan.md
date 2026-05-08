# AI PaperCraft Studio Current Development Plan

Last updated: 2026-05-08

## Current Position

The repository has completed the M1 backend foundation through the worker
backbone and the first M2 frontend flow. The next priority is to finish the
remaining workbench behaviors and broaden the mock demo coverage before
replacing the mock stages with real algorithms.

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

Status: in progress.

Completed:

- Build create-project, upload, parameter, and progress frontend flows.
- Connect frontend task polling to backend status, artifacts, and assembly
  metadata.
- Run the full stack through Docker Compose for local internal demos.

Remaining:

- Add paper-net page switching and richer workbench artifact interactions.
- Add regenerate/export actions around the project detail flow.
- Demonstrate failure and cancellation flows with mock pipeline controls.
- Add project artifact history once multiple task runs are visible.

Current backend support:

- completed mock tasks now record a 3D preview placeholder, net JSON
  placeholder, PDF export placeholder, and assembly metadata.
- task status responses include available artifacts and assembly metadata for
  frontend polling and workbench rendering.
- local mock artifact downloads are exposed through the API so the frontend can
  exercise preview/export actions before object storage integration.
- Docker Compose can run the web, API, worker, database, Redis, and MinIO stack.
- the workbench renders mock net JSON as a paper page and part list for the
  internal demo flow.

Exit criteria:

- Issue `#6` can be closed.
- Issues `#7` and `#8` remain open until page switching, regenerate/history,
  and failure/cancellation demo paths are complete.
- The product can be demonstrated from upload through fake export.

## Implementation Started

M2 should start with the frontend create-project, upload, parameter, and
progress flow, then connect the workbench to the mock task artifacts.
