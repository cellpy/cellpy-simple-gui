# Status — Issue #169: Compare selected cells

- [ ] Done

## 2026-10-02 — picked, captured, planned

- Picked via `iflow pick` (only open, non-wontfix issue); branch
  `cursor/169-compare-cells-2654` off `origin/main` (post-#170). First commit
  archived the stray `issue168_status.md` left in `01-current-issues/`.
- Captured `issue169_original.md` (no comments).
- Probed cellpy: collected layouts are `per_cell` / `per_cycle` only (no
  cross-cell overlay); collect takes one cycle list per batch; frames keyed by
  `cell` + `cycle_num` (curves) / `cycle` (ICA/DVA). Hence the plan: filter the
  collection to `(cell, cycle)` pairs, plot via cellpy `per_cell`, overlay as a
  post-plot restyle.
- Wrote `issue169_plan.md`.

## Waiting on

- Plan confirmation (Accept / Revise / Abort) and the three open questions
  (overlay colouring, mode-in-explorer vs new tab, upstream pain-point filing).

## Remaining

- Everything in the plan's *Files to touch* — no code written yet.
