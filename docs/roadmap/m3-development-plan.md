# M3 Development Plan

Last updated: 2026-05-13

## Summary

M3 replaces the M2 mock pipeline one stage at a time while keeping the demo loop
usable after each merge. Completed code slices include issue `#9`: real image
preprocessing, issue `#10`: deterministic category-constrained base mesh
generation, issue `#11`: paperability optimization and constrained decimation,
issue `#12`: unfolding and page layout, and issue `#13`: PDF export,
instruction sheet generation, and assembly metadata.

M3 is code-complete on this branch. The next sequencing step is GitHub
bookkeeping for `#12`, `#13`, and tracking issue `#16`, followed by M4
stabilization.

## GitHub Alignment

- Issues `#7` and `#8` are closed M2 work.
- Tracking issue `#16` already marks `#7` and `#8` complete.
- Issue `#9` is complete after PR `#24`.
- Issue `#10` is complete after PR `#25`.
- Issue `#11` is complete after PR `#26`.
- Issue `#12` is code-complete after PR `#27`, but the GitHub issue and
  tracking checkbox still need to be closed/updated.
- Issue `#13` is implemented on the `codex/issue-13-pdf-export` branch and
  should be closed after merge.

## Completed Slice: `#9` Image Preprocessing

- Use Pillow only; do not add OpenCV, rembg, or ML model dependencies.
- Read the first project source image from the uploads bucket during the
  `preprocessing` worker stage.
- Generate two artifacts in the artifacts bucket:
  - `preprocess_mask`: PNG mask of the detected subject.
  - `preprocess_crop`: PNG crop of the detected subject with mask alpha applied.
- Record metadata on each preprocessing artifact:
  - `real_stage: "preprocessing"`
  - source image id and storage key
  - original image size
  - crop box and crop size
  - mask coverage
  - background strategy and transparency/plain-background hints
  - lightweight view hints
  - processing duration in milliseconds
- Continue to run M2 mock stages after preprocessing succeeds so the full demo
  loop still reaches mock preview, net, PDF, and assembly metadata.

## Completed Slice: `#10` Base Mesh Generation

- Use deterministic Python mesh generation; do not add external 3D or ML
  dependencies for this first pass.
- Read `preprocess_crop` metadata from the current task.
- Use project category and task parameter snapshot to select a simple,
  controllable strategy:
  - `pet`: low-poly body and head ellipsoids.
  - `bust`: low-poly head and shoulders.
  - `simple_object`: low-poly rectangular prism.
- Generate a `base_mesh` OBJ artifact in the meshes object-storage group.
- Generate a lightweight `preview_model` glTF metadata artifact in the previews
  group.
- Continue to run M2 mock paperability, unfolding, and export stages after base
  mesh generation succeeds.

## Completed Slice: `#11` Paperability And Decimation

- Use deterministic Python OBJ processing; do not add external mesh libraries
  for this first pass.
- Read the `base_mesh` OBJ artifact and metadata from the current task.
- Repair the base mesh into a `repaired_mesh` OBJ artifact by validating
  faces, deduplicating vertices, removing degenerate or duplicate faces, and
  recording fragile-structure diagnostics.
- Read the `repaired_mesh` artifact and task parameter snapshot.
- Produce a `low_poly_mesh` OBJ artifact through constrained decimation using
  `target_poly_count` and `max_pages` as the first budget controls.
- Continue to run M2 mock unfolding and export stages after low-poly mesh
  generation succeeds.

## Completed Code Slice: `#12` Unfolding And Layout

- Use deterministic Python OBJ processing; do not add external unfolding
  libraries for this first pass.
- Read the `low_poly_mesh` OBJ artifact and metadata from the current task.
- Generate a structured `net_json` artifact with pages, parts, cut/fold line
  counts, glue flap counts, pair numbering, and layout positions.
- Generate a `net_svg` intermediate artifact for visual inspection and future
  export work.
- Apply a first fallback simplification path by increasing parts per page when
  the calculated layout would exceed `max_pages`.
- Continue to run M2 mock export after unfolding succeeds.

## Completed Code Slice: `#13` PDF Export And Assembly Metadata

- Reads the latest `net_json` and `net_svg` artifacts from the current task.
- Generates a downloadable `export_pdf` artifact in the exports object-storage
  group.
- Includes printable A4/A3 pages, page numbers, cut lines, fold lines, glue
  flaps, pair numbering, and a first-page instruction sheet or equivalent
  assembly guidance.
- Persists assembly metadata using real export inputs:
  - `page_count`
  - `part_count`
  - `difficulty_score`
  - `estimated_build_minutes`
- Fails export with `EXPORT_FAILED` when PDF generation or persistence cannot
  complete.

## Failure Contract

- If no usable subject can be detected, fail the task with
  `PREPROCESS_SUBJECT_NOT_FOUND`.
- If image decoding or deterministic preprocessing fails unexpectedly, fail with
  `PREPROCESS_FAILED`.
- If model generation lacks preprocessing metadata or cannot produce a
  category-constrained mesh, fail with `MODEL_GEN_FAILED`.
- If paperability repair cannot produce a usable mesh, fail with
  `PAPERABILITY_OPT_FAILED`.
- If constrained decimation cannot produce a low-poly mesh, fail with
  `DECIMATE_FAILED`.
- If unfolding or page layout cannot produce a net within budget, fail with
  `UNFOLD_FAILED`.
- If PDF export or final assembly metadata cannot be produced, fail with
  `EXPORT_FAILED`.
- Storage read/write errors continue to use the existing storage error codes so
  infrastructure failures stay distinguishable from algorithm failures.

## Acceptance Criteria

For `#9`:

- Positive sample images produce both `preprocess_mask` and `preprocess_crop`
  artifacts.
- Blank or low-contrast images fail at `preprocessing` with
  `PREPROCESS_SUBJECT_NOT_FOUND`.
- `GET /api/tasks/{task_id}` returns preprocessing artifacts with download URLs
  and metadata.
- Retry from `preprocessing` can regenerate preprocessing artifacts while prior
  artifacts remain traceable.
- Existing M2 mock demo behavior remains intact after preprocessing.

For `#10`:

- Positive samples produce a `base_mesh` OBJ artifact.
- Task status returns `base_mesh` and `preview_model` artifacts with download
  URLs and generation metadata.
- Model generation failures return `MODEL_GEN_FAILED`.
- The task continues into later paperability/unfold/export stages after base
  mesh generation succeeds.

For `#11`:

- Positive samples produce `repaired_mesh` and `low_poly_mesh` OBJ artifacts.
- Task status returns paperability and decimation artifacts with download URLs
  and metadata.
- Paperability failures return `PAPERABILITY_OPT_FAILED`.
- Decimation failures return `DECIMATE_FAILED`.
- The task continues into later unfolding/export stages after constrained
  decimation succeeds.

For `#12`:

- Positive samples produce `net_json` and `net_svg` artifacts.
- `net_json` includes fold lines, cut lines, glue flaps, pair numbering, and
  page layout data.
- Page overflow can trigger a fallback simplification path.
- Unfolding failures return `UNFOLD_FAILED`.
- The task continues into the later export stage after unfolding succeeds.

For `#13`:

- Positive samples produce an `export_pdf` artifact.
- The PDF can be downloaded through the existing artifact download endpoint.
- The PDF includes page numbers, cut/fold styling, flap styling, pair
  numbering, and basic assembly guidance.
- Assembly metadata is stored with real page count, part count, difficulty
  score, and estimated build time.
- Export failures return `EXPORT_FAILED`.

## Test Plan

- Unit-test Pillow preprocessing for successful mask/crop generation and
  metadata.
- Unit-test blank or low-contrast inputs for subject-not-found failure.
- Worker-test that `preprocessing` writes artifacts and later mock stages still
  complete.
- API-test that task status includes preprocessing artifacts and download URLs.
- Unit-test deterministic base mesh generation for all category strategies.
- Worker-test that `model_generating` writes `base_mesh` and continues into the
  later mock stages.
- Unit-test paperability repair metadata and constrained decimation budgets.
- Worker-test that `paperability_optimizing` writes `repaired_mesh` and
  `decimating` writes `low_poly_mesh`.
- Unit-test unfolding output for structured net JSON and SVG artifacts.
- Worker-test that `unfolding` writes `net_json` and `net_svg`.
- Unit-test PDF export generation from representative `net_json` data.
- Worker-test that `exporting` writes `export_pdf` and assembly metadata.
- API-test that completed task status returns the real PDF artifact download
  URL and real assembly metadata.
- Run:
  - `uv run --extra dev pytest`
  - `pnpm --filter @papercraft/web typecheck`
