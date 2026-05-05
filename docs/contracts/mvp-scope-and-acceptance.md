# MVP Scope and Acceptance Contract

Last updated: 2026-05-05

This document freezes the MVP product scope, acceptance samples, success
metrics, and minimum buildability bar for AI PaperCraft Studio. It is the
shared contract for product, frontend, backend, worker, algorithm, and QA work.

## MVP Goal

The MVP must prove a complete web-based papercraft generation loop:

```text
upload images -> create project -> create task -> run async pipeline ->
preview 3D and paper net -> export printable PDF
```

The product optimizes for a buildable papercraft result before photorealistic
3D fidelity. A result that is less realistic but printable, numbered, folded,
and assemblable is preferable to a visually stronger mesh that cannot unfold
reliably.

## Frozen Scope

### Platform

- Web application.
- Project-based workflow with task history.
- Async generation with task status polling.
- Local development stack based on PostgreSQL, Redis, and S3-compatible object
  storage.

### Input

- Users may upload 1 to 3 source images per project.
- Supported file types: JPG, PNG, and WebP.
- Server-side validation must enforce MIME type, file size, and image count.
- Single-image input must work; multi-image input is an enhancement path, not a
  hard requirement for success.

### Categories

MVP generation is limited to these project categories:

- `pet`: pets with a clear primary subject.
- `bust`: head or upper-body bust-like subjects.
- `simple_object`: simple tabletop objects or decorative items with a readable
  silhouette.

The system may expose automatic category hints later, but MVP APIs and task
contracts must not depend on auto-detection being correct.

### User Parameters

The MVP parameter set is:

- `complexity_level`: `simple`, `balanced`, or `detailed`.
- `target_poly_count`: desired low-poly target.
- `paper_size`: `a4` or `a3`.
- `texture_mode`: `plain`, `source_texture`, or `print_friendly`.
- `flap_size`: glue flap size in millimeters.
- `max_pages`: page budget.
- `build_difficulty_mode`: `easy`, `standard`, or `advanced`.

### Output

Every successful MVP task must provide:

- A 3D preview artifact or equivalent placeholder during the mock-pipeline
  phase.
- A paper-net preview artifact or equivalent placeholder during the
  mock-pipeline phase.
- An A4 or A3 PDF export.
- Assembly metadata with `page_count`, `part_count`, `difficulty_score`, and
  `estimated_build_minutes`.
- A task event trail that explains stage progress and failures.

The final export must include:

- Printable pages.
- Page numbers.
- Cut lines.
- Fold lines.
- Glue flaps.
- Pairing or assembly numbering.
- Basic assembly guidance, either as a first-page instruction sheet or linked
  metadata surfaced by the UI.

## Explicit Non-Goals

The MVP does not include:

- Native mobile apps.
- Public community sharing.
- Template marketplace.
- Commercial licensing administration.
- Advanced account billing or plan enforcement.
- Fully general image-to-3D reconstruction for arbitrary subjects.
- Real-time collaborative editing.
- Manual mesh editing tools.
- Guaranteed photo-accurate likeness.
- Production CDN, moderation, or public asset gallery.
- SVG, PNG, OBJ, or GLB export as required product output.

These may appear as later enhancements, but MVP tasks must not depend on them.

## Acceptance Sample Set

The official sample suite is versioned as a product/QA artifact. Until sample
files are committed, the required sample groups are:

| Group | Count | Purpose |
| --- | ---: | --- |
| Pet front or three-quarter subject | 5 | Validate the highest-priority consumer use case. |
| Bust subject | 5 | Validate face/head or upper-body handling. |
| Simple object | 5 | Validate silhouette-driven object workflows. |
| Complex background | 3 | Validate graceful preprocessing failure or recovery. |
| Upload validation edge cases | 3 | Validate too small, unsupported, too large, or invalid inputs. |

Each positive sample must record:

- Category.
- Source image count.
- Expected happy-path stages.
- Expected paper size.
- Maximum acceptable page count for MVP acceptance.
- Notes on known hard details, such as thin parts or occlusions.

Each failure sample must record:

- Expected error code.
- Expected failing stage.
- User-facing recovery guidance.

## Success Metrics

### Product Completion

- A user can complete one web flow from project creation to PDF download.
- The workbench can display both 3D preview and net preview for completed or
  mock-completed tasks.
- Failed tasks show stage, error code, readable message, and next action.

### Result Acceptance

- At least 60% of official positive samples produce a buildable paper-net PDF.
- Every accepted PDF includes visible numbering, fold lines, cut lines, and
  glue flaps.
- Accepted outputs stay within the configured `max_pages` budget or explain an
  automatic simplification/fallback.
- Accepted outputs include assembly metadata.

### Engineering Acceptance

- Core API request and response shapes are stable enough for frontend and
  worker implementation.
- Async task status can be queried by `task_id`.
- Logs or task events can be correlated by `task_id`.
- Project history can preserve prior tasks, parameter snapshots, and artifacts.
- Local development can run the API, database, queue, object storage, and tests.

### Operating Metrics To Capture

The MVP should be able to report or derive:

- Upload start rate.
- Upload success rate.
- Project creation success rate.
- Task completion rate.
- Stage-level failure rate.
- Average task duration.
- Average page count.
- Average part count.
- Export rate.
- Re-generation or retry rate.

## Minimum Buildability Bar

A task result is considered buildable only when all required criteria pass:

- The PDF can be opened and printed on the selected paper size.
- Page margins leave printable safe space.
- Cut lines and fold lines are visually distinguishable.
- Glue flaps are present where parts need attachment.
- Pairing or assembly numbers are present and readable.
- `page_count` is greater than 0 and not above the accepted page budget.
- `part_count` is greater than 0.
- `difficulty_score` is between 1 and 10.
- The model avoids obvious unbuildable fragments, such as tiny isolated pieces
  below the configured minimum piece threshold.
- The result has a clear user-facing failure or warning if simplification was
  required.

A result is not accepted as buildable if it only produces a 3D model, only
produces an unnumbered net, exceeds the page budget without fallback, or lacks
the fold/flap/numbering information needed for assembly.

## Failure And Fallback Contract

Known failure paths must remain user-actionable:

| Scenario | Error code | Expected behavior |
| --- | --- | --- |
| Unsupported upload type | `UPLOAD_UNSUPPORTED_TYPE` | Reject before task creation. |
| File too large | `UPLOAD_FILE_TOO_LARGE` | Reject with configured size limit. |
| Too many images | `UPLOAD_TOO_MANY_IMAGES` | Reject extra input before task creation. |
| Subject not found | `PREPROCESS_SUBJECT_NOT_FOUND` | Ask for a cleaner, centered subject image. |
| Model generation failed | `MODEL_GEN_FAILED` | Preserve task failure details and allow retry or simpler settings. |
| Paperability optimization failed | `PAPERABILITY_OPT_FAILED` | Report complexity or structure problem. |
| Decimation failed | `DECIMATE_FAILED` | Allow retry with adjusted complexity. |
| Unfolding failed | `UNFOLD_FAILED` | Prefer automatic simplification before final failure. |
| Export failed | `EXPORT_FAILED` | Preserve prior artifacts and allow export retry. |

Where possible, the worker should keep intermediate artifacts traceable even
when later stages fail.

## Exit Criteria For Issue #1

Issue #1 is complete when:

- This frozen scope document exists in `docs/contracts/`.
- The official sample groups and counts are listed.
- Completion, result, and engineering success metrics are defined.
- The minimum buildability bar is documented.
- MVP non-goals are explicit enough to prevent downstream scope drift.
