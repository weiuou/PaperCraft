# Manual Assembly QA Checklist

Last updated: 2026-05-13

Use this checklist for any sample selected for physical or close visual
assembly review.

## Print Review

- PDF opens without repair warnings in a standard PDF viewer.
- Paper size matches the selected task parameter.
- Pages print at 100% scale without clipped margins.
- Page numbers are visible on every page.

## Net Review

- Cut lines are visually distinguishable from fold lines.
- Mountain/valley or dashed fold styling is visible.
- Glue flaps are present where parts need attachment.
- Pair numbers are readable and not placed outside printable bounds.
- No tiny isolated parts are below a practical cutting threshold.

## Assembly Review

- Instruction sheet or assembly guidance is present.
- Estimated build time is plausible for the page and part count.
- First three parts can be matched using visible pair numbers.
- Fallback warnings are understandable when simplification was applied.
- The result is rejected if it lacks numbering, fold lines, glue flaps, or a
  downloadable PDF.

## Evidence To Save

- Source sample ID.
- Task ID.
- Downloaded PDF.
- `net_json` artifact.
- Screenshot of workbench task status and next actions.
- Notes for each failed checklist item.

