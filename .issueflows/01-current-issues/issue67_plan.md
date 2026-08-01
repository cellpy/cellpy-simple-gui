# Issue #67 — Plan: filter ICA by Charge/Discharge direction

## Goal

Make Cell explorer dQ/dV **Charge** vs **Discharge** produce different figures
(and matching figure export) by filtering the ICA collection before plot —
cellpy’s `direction` plot kwarg is a no-op for default line layouts.

## Constraints

- cellpy boundary: only `core/collect.py` (+ adapter) import/mutate cellpy types.
- Prefer app-side filter on collected ICA data; do **not** rely on cellpy’s
  film-only `_select_direction`.
- Out of scope: true `both` overlay, dV/dQ, multi-cell ICA collector.
- No UI changes (direction control already exists from #56).

### Prior art

- [`plotting.ica_figure`](../../../src/cellpy_simple_gui/core/plotting.py) →
  `ica_collection` + `figure_json(..., direction=spec.direction)` (kwarg ignored
  by cellpy for `fig_pr_cell`).
- [`collect.ica_collection`](../../../src/cellpy_simple_gui/core/collect.py) /
  `IcaOptions(cycles=, voltage_resolution=)` — collect keeps both half-cycles
  (`direction` column on the tidy frame; see `CELLPY_PAINPOINTS` §16).
- [`export.ica_figure_export`](../../../src/cellpy_simple_gui/core/export.py)
  already goes through `ica_figure` (gets fix for free once figure path filters).
- [`export.ica_export`](../../../src/cellpy_simple_gui/core/export.py) (CSV/…)
  uses `ica_collection` without direction today — filter there too for
  consistency with the selected UI direction.
- Tests: `test_ica_figure` / `test_ica_figure_discharge` only assert
  `len(data) >= 1` — need a charge ≠ discharge assertion.
- Design: [`plot-sidepane.md`](../04-designs-and-guides/plot-sidepane.md)
  (explorer dQ/dV knobs; no structural change).
- Toolbox: none. Graph: export community mentions `ica_figure_export`; no
  dedicated filter helper.

## Approach

1. **Confirm cause (doc only in pain points)** — `ica_plotter` →
   `_cycles_plotter` / `sequence_plotter` applies `_select_direction` only when
   `method=="film"`, not default line/`fig_pr_cell`. Extend §16 accordingly.

2. **Filter helper in `collect.py`** — after `collect_ica`, if the frame has a
   `direction` column, keep rows matching `charge` or `discharge` (normalize
   case). Prefer an immutable-ish pattern: assign filtered frame back onto the
   collection (same pattern as other app collection tweaks). If the column is
   missing, leave data alone and log a warning (older cellpy).

3. **Wire `direction` into `ica_collection(...)`** — new kwarg
   `direction: Literal["charge","discharge"]`. Call sites:
   - `plotting.ica_figure` → pass `spec.direction`
   - `export.ica_export` → pass `spec.direction`
   - Keep passing `direction=` into `collection.plot` for forward-compat (still
     harmless if cellpy starts honouring it).

4. **CELLPY_PAINPOINTS §16** — add: documented `direction` on `ica_plotter` is
   ignored for line/`fig_pr_cell`; only `film` filters. Wish: call
   `_select_direction` for ICA line layouts; optional separate-series `both`.
   Note app workaround (filter collected frame) + link #67.

5. **Tests** — same demo cell / cycles / resolution:
   - charge and discharge figures both non-empty;
   - y-values differ (e.g. concatenated trace `y` not equal, or mean sign /
     polarity differs as appropriate for the example cell);
   - optional: API smoke still passes with both directions.
   No new e2e required.

6. **Optional follow-up (not in this PR unless trivial)** — file upstream
   cellpy issue pointing at §16.

## Files to touch

| Path | Change |
|------|--------|
| `src/cellpy_simple_gui/core/collect.py` | `direction` on `ica_collection` + filter helper |
| `src/cellpy_simple_gui/core/plotting.py` | pass `spec.direction` into `ica_collection` |
| `src/cellpy_simple_gui/core/export.py` | pass `spec.direction` into `ica_collection` for data export |
| `CELLPY_PAINPOINTS.md` | extend §16 (film-only / line no-op + app workaround) |
| `tests/test_core.py` | charge ≠ discharge assertion |
| `.issueflows/04-designs-and-guides/` | short note only if a durable decision needs recording (likely skip — pain point covers it) |

## Test strategy

```bash
uv run pytest
```

Focus: `tests/test_core.py` ICA cases (+ existing `tests/test_api.py` ICA smoke).

## Open questions

1. **Data export filtering** — Recommended **yes**: `ica_export` uses the same
   filtered `ica_collection` so CSV matches the selected direction. Alternative:
   filter figures only (CSV keeps both half-cycles). Prefer recommended unless
   you want raw both-directions tables.
