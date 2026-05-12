# M3 Development Plan

Last updated: 2026-05-12

## Summary

M3 replaces the M2 mock pipeline one stage at a time while keeping the demo loop
usable after each merge. Completed slices include issue `#9`: real image
preprocessing, and issue `#10`: deterministic, category-constrained base mesh
generation, and issue `#11`: paperability optimization and constrained
decimation. The current active slice is issue `#12`: unfolding and page layout.

Final PDF export remains later M3 work under issue `#13`.

## GitHub Alignment

- Issues `#7` and `#8` are M2 work and should be closed after the M2 demo loop
  merge.
- Tracking issue `#16` should mark `#7` and `#8` complete.
- Issue `#9` is complete after PR `#24`.
- Issue `#10` is complete after PR `#25`.
- Issue `#11` is complete after PR `#26`.
- Issue `#12` is the active M3 entry point after decimation.
- Issue `#13` remains open for later M3 sequencing.

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

## Active Slice: `#12` Unfolding And Layout

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
- Run:
  - `uv run --extra dev pytest`
  - `pnpm --filter @papercraft/web typecheck`
