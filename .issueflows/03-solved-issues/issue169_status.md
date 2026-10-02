# Status — Issue #169: Compare selected cells

- [x] Done

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
- Wrote `issue169_plan.md`; accepted with all defaults (sequential colouring in
  overlay, mode inside the Cell explorer, pain-point recorded but not filed).

## 2026-10-02 — built

- **Core:** `models.ComparePick` / `ComparePlotSpec` (≤8 picks, ≤40 cycles per
  pick, ≤80 curves, duplicate cells merge, `pairs()`); `collect.batch_keys`
  (factored from `_batch`), `collect.restrict_to_cycle_pairs` (polars semi-join
  on `(cell, cycle_num|cycle)`), `collect._overlay_facets` + `figure_json(...,
  overlay=)`; `plotting.compare_collection` / `compare_figure`;
  `export.compare_export` / `compare_figure_export`.
- **API:** `POST /api/plots/compare`, `POST /api/export/compare?fmt=`
  (`compare_<n>_cells.<ext>`; 404 names the missing cell; 422 on limits; empty
  picks → prompt figure / 400 on export).
- **UI:** `Compare cells` checkbox in the explorer sidepane (hidden for raw /
  cycle-info and with one cell), `Layout` select (Overlay / Side by side),
  two-line pick rows (cell select; cycles text `3` / `7, 12` / `5-9` + ✕),
  `+ Add cell`; top Cell select stays pick #1; export menu routes to the
  compare endpoint. Alpine select/x-for ordering quirk fixed with
  `x-init="$nextTick(...)"`.
- **Tests:** `tests/test_compare.py` (24: spec, batch keys, pair filter on both
  frames, overlay structure / hover / colours, side by side, dqdv/dvdq, both
  directions, ranges, empty, exports, API incl. 404/422 and PNG-or-503).
  `test_index_alpine_state_is_defined` now ignores `x-for` loop variables.
  Suite: **337 passed, 7 skipped**.
- **Manual (browser, server mode):** compare on → overlay of two cells; picks
  `3` and `7, 12` → three curves, legend `Cell · cycle`; Side by side → two
  facets; add/remove row; dQ/dV; top Cell select sync; Export CSV downloaded
  `compare_2_cells.csv` with exactly the three picked pairs; compare off
  restores the single-cell controls. Recording and screenshots under
  `/opt/cursor/artifacts/` (attached to the PR).
- **Docs:** `docs/guides/03-plotting.md` (new section), `README.md` bullet,
  `CELLPY_PAINPOINTS.md` §36, `.issueflows/04-designs-and-guides/compare-cells.md`,
  `llms-full.txt` regenerated.

## Remaining

- Nothing for #169. Possible follow-ups (not in scope): "Colour by cell" with
  line-dash by cycle; filing the §36 wish upstream is the maintainer's call.
