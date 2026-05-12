# M3 Development Plan

Last updated: 2026-05-12

## Summary

M3 replaces the M2 mock pipeline one stage at a time while keeping the demo loop
usable after each merge. The first completed slice is GitHub issue `#9`: real
image preprocessing. The current active slice is issue `#10`: deterministic,
category-constrained base mesh generation.

Paperability optimization, unfolding/layout, and final PDF export remain later
M3 work under issues `#11` through `#13`.

## GitHub Alignment

- Issues `#7` and `#8` are M2 work and should be closed after the M2 demo loop
  merge.
- Tracking issue `#16` should mark `#7` and `#8` complete.
- Issue `#9` is complete after PR `#24`.
- Issue `#10` is the active M3 entry point after preprocessing.
- Issues `#11`, `#12`, and `#13` remain open for later M3 sequencing.

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

## Active Slice: `#10` Base Mesh Generation

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

## Failure Contract

- If no usable subject can be detected, fail the task with
  `PREPROCESS_SUBJECT_NOT_FOUND`.
- If image decoding or deterministic preprocessing fails unexpectedly, fail with
  `PREPROCESS_FAILED`.
- If model generation lacks preprocessing metadata or cannot produce a
  category-constrained mesh, fail with `MODEL_GEN_FAILED`.
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
- Run:
  - `uv run --extra dev pytest`
  - `pnpm --filter @papercraft/web typecheck`
