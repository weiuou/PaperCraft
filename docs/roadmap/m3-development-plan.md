# M3 Development Plan: Image Preprocessing First Slice

Last updated: 2026-05-12

## Summary

M3 starts with GitHub issue `#9`: integrate the first real image
preprocessing stage while keeping later generation stages on the M2 mock path.
This slice proves that uploaded source images can be read from object storage,
processed deterministically, and written back as traceable intermediate
artifacts before mesh generation begins.

This slice does not implement issues `#10` through `#13`. Base mesh generation,
paperability optimization, unfolding/layout, and final PDF export remain later
M3 work.

## GitHub Alignment

- Issues `#7` and `#8` are M2 work and should be closed after the M2 demo loop
  merge.
- Tracking issue `#16` should mark `#7` and `#8` complete.
- Issue `#9` is the active M3 entry point for this slice.
- Issues `#10`, `#11`, `#12`, and `#13` remain open for later M3 sequencing.

## Implementation Plan

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

## Failure Contract

- If no usable subject can be detected, fail the task with
  `PREPROCESS_SUBJECT_NOT_FOUND`.
- If image decoding or deterministic preprocessing fails unexpectedly, fail with
  `PREPROCESS_FAILED`.
- Storage read/write errors continue to use the existing storage error codes so
  infrastructure failures stay distinguishable from algorithm failures.

## Acceptance Criteria

- Positive sample images produce both `preprocess_mask` and `preprocess_crop`
  artifacts.
- Blank or low-contrast images fail at `preprocessing` with
  `PREPROCESS_SUBJECT_NOT_FOUND`.
- `GET /api/tasks/{task_id}` returns preprocessing artifacts with download URLs
  and metadata.
- Retry from `preprocessing` can regenerate preprocessing artifacts while prior
  artifacts remain traceable.
- Existing M2 mock demo behavior remains intact after preprocessing.

## Test Plan

- Unit-test Pillow preprocessing for successful mask/crop generation and
  metadata.
- Unit-test blank or low-contrast inputs for subject-not-found failure.
- Worker-test that `preprocessing` writes artifacts and later mock stages still
  complete.
- API-test that task status includes preprocessing artifacts and download URLs.
- Run:
  - `uv run --extra dev pytest`
  - `pnpm --filter @papercraft/web typecheck`
