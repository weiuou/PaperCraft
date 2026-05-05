# Core Platform Contracts

This document defines the first stable backend contracts for MVP implementation.
It is intended to be mirrored by the API service models and migrations.

## Core Entities

### users

Represents an account that owns projects.

- `id`: UUID primary key
- `email`: unique login identifier
- `display_name`: nullable display name
- `plan_type`: account tier, defaults to `free`
- `created_at`, `updated_at`: audit timestamps

### projects

Represents one papercraft generation workspace.

- `id`: UUID primary key
- `user_id`: owner
- `title`: user-visible project name
- `category`: `pet`, `bust`, or `simple_object`
- `status`: `draft`, `active`, `archived`, or `deleted`
- `cover_image_url`: optional cover image
- `latest_task_id`: optional pointer to the newest generation task
- `created_at`, `updated_at`: audit timestamps

### source_images

Represents uploaded images attached to a project.

- `id`: UUID primary key
- `project_id`: parent project
- `storage_key`: object storage key
- `mime_type`: validated MIME type
- `width`, `height`: pixel dimensions
- `file_size`: bytes
- `sort_order`: input order, limited by `MAX_UPLOAD_IMAGES`
- `created_at`: upload timestamp

### generation_tasks

Represents one generation attempt with a parameter snapshot.

- `id`: UUID primary key
- `project_id`: parent project
- `status`: `draft`, `queued`, `in_progress`, `completed`, `failed`, or `canceled`
- `stage`: current pipeline stage
- `progress`: integer `0..100`
- `retry_from_stage`: optional stage requested for retry
- `error_code`, `error_message`: populated on failure
- `started_at`, `finished_at`: task-level timing
- `created_at`, `updated_at`: audit timestamps

### param_configs

Represents immutable task parameters.

- `id`: UUID primary key
- `task_id`: owning generation task
- `category`: input category snapshot
- `complexity_level`: `simple`, `balanced`, or `detailed`
- `target_poly_count`: desired low-poly target
- `paper_size`: `a4` or `a3`
- `texture_mode`: `plain`, `source_texture`, or `print_friendly`
- `flap_size`: glue flap size in millimeters
- `max_pages`: page budget
- `build_difficulty_mode`: `easy`, `standard`, or `advanced`
- `created_at`: snapshot timestamp

### artifacts

Represents files generated or consumed by the pipeline.

- `id`: UUID primary key
- `task_id`: owning generation task
- `kind`: artifact kind
- `storage_key`: object storage key
- `mime_type`: content type
- `file_size`: bytes, when known
- `metadata`: JSON metadata
- `created_at`: timestamp

### assembly_metadata

Represents user-facing build metadata for a completed task.

- `id`: UUID primary key
- `task_id`: owning generation task
- `page_count`: exported page count
- `part_count`: assembled part count
- `difficulty_score`: integer `1..10`
- `estimated_build_minutes`: estimated assembly time
- `metadata`: JSON details
- `created_at`, `updated_at`: audit timestamps

### task_events

Represents append-only task timeline events for debugging and progress display.

- `id`: UUID primary key
- `task_id`: owning generation task
- `stage`: related pipeline stage, when applicable
- `event_type`: `created`, `queued`, `stage_started`, `stage_completed`,
  `progress_updated`, `failed`, `retry_requested`, `canceled`, or `completed`
- `message`: optional human-readable note
- `metadata`: JSON details
- `created_at`: event timestamp

## Object Storage Keys

Object keys must be deterministic, debuggable, and grouped by project and task:

```text
projects/{project_id}/source-images/{image_id}/{filename}
projects/{project_id}/tasks/{task_id}/preprocess/{artifact_id}/{filename}
projects/{project_id}/tasks/{task_id}/meshes/{artifact_id}/{filename}
projects/{project_id}/tasks/{task_id}/nets/{artifact_id}/{filename}
projects/{project_id}/tasks/{task_id}/previews/{artifact_id}/{filename}
projects/{project_id}/tasks/{task_id}/exports/{artifact_id}/{filename}
```

Rules:

- Keys use lowercase path segments and UUID identifiers.
- User-provided filenames are sanitized before use.
- Source uploads go to `S3_BUCKET_UPLOADS`.
- Intermediate and final artifacts go to `S3_BUCKET_ARTIFACTS`.

## Task State Machine

Task statuses:

- `draft`: local task data exists but is not queued
- `queued`: task is ready for worker pickup
- `in_progress`: worker owns the task
- `completed`: final export and metadata are available
- `failed`: execution stopped with an error
- `canceled`: user or system canceled execution

Pipeline stages:

- `upload_validation`
- `preprocessing`
- `model_generating`
- `paperability_optimizing`
- `decimating`
- `unfolding`
- `exporting`
- `completed`

Allowed status transitions:

```text
draft -> queued
queued -> in_progress
queued -> canceled
in_progress -> completed
in_progress -> failed
in_progress -> canceled
failed -> queued
canceled -> queued
```

Stages advance in the listed order. Retry may resume from one of the pipeline
stages before `completed`, but a retry must create a task event and keep prior
artifacts traceable.

## Error Response Shape

All API errors should use this shape:

```json
{
  "error": {
    "code": "UPLOAD_FILE_TOO_LARGE",
    "message": "Uploaded image exceeds the configured size limit.",
    "details": {
      "max_upload_mb": 20
    }
  }
}
```

## Initial Error Code Catalog

Upload and validation:

- `UPLOAD_UNSUPPORTED_TYPE`
- `UPLOAD_FILE_TOO_LARGE`
- `UPLOAD_TOO_MANY_IMAGES`
- `UPLOAD_IMAGE_INVALID`

Project and task:

- `PROJECT_NOT_FOUND`
- `TASK_NOT_FOUND`
- `TASK_INVALID_STATE`
- `TASK_RETRY_NOT_ALLOWED`

Pipeline stages:

- `PREPROCESS_SUBJECT_NOT_FOUND`
- `PREPROCESS_FAILED`
- `MODEL_GEN_FAILED`
- `PAPERABILITY_OPT_FAILED`
- `DECIMATE_FAILED`
- `UNFOLD_FAILED`
- `EXPORT_FAILED`

System:

- `STORAGE_WRITE_FAILED`
- `STORAGE_READ_FAILED`
- `INTERNAL_ERROR`
