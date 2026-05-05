# AI PaperCraft Studio Current Development Plan

Last updated: 2026-05-05

## Current Position

The repository has completed the initial engineering bootstrap from issue `#2`.
The next priority is to turn the architecture and MVP roadmap into stable
contracts that API, worker, frontend, and algorithm work can depend on.

## Near-Term Execution Plan

### M1.1 Product and Acceptance Contract

Owner focus: product, QA, engineering lead

- Freeze MVP scope for inputs, categories, outputs, and explicit non-goals.
- Define acceptance samples for happy paths and known failure paths.
- Define buildability metrics: completion rate, page count, part count,
  difficulty score, and manual assembly bar.

Exit criteria:

- Issue `#1` can be closed.
- Frontend, backend, and algorithm work share the same acceptance target.

### M1.2 Core Data and Task Contract

Owner focus: backend, worker

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

- Build project create/list/detail endpoints.
- Build image upload validation and metadata persistence.
- Build task creation and task status endpoints.
- Return stable validation and missing-resource errors.

Exit criteria:

- Issue `#4` can be closed.
- Frontend can create a project, upload images, start a task, and poll status.

### M1.4 Async Worker Backbone

Owner focus: backend, worker

- Integrate Celery with Redis.
- Add task enqueueing from API to worker.
- Add a mock stage executor for queue and state-machine validation.
- Persist progress, stage timestamps, and failure details.

Exit criteria:

- Issue `#5` can be closed.
- Long-running pipeline behavior can be validated before real algorithms land.

### M2 Demo Loop

Owner focus: frontend, backend, worker

- Build create-project and progress frontend flows.
- Build workbench shell with 3D preview and net preview placeholders.
- Implement mock artifacts for an end-to-end demo.

Exit criteria:

- Issues `#6`, `#7`, and `#8` can be closed.
- The product can be demonstrated from upload through fake export.

## Implementation Started

This plan starts with M1.2 because it is the highest-leverage dependency for
API, worker, and frontend work.
