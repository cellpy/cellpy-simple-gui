# Plan — Issue #72: Cycles Mode ↔ x-axis capacity units

## Goal

When Cycles **Mode** changes (gravimetric / areal / absolute), the plot x-axis
title/units match that mode — including after an existing plot is already shown.

## Constraints

- Prefer cellpy label/unit helpers; stay consistent with the current
  `collect_cycles` → `collection.plot` path.
- Out of scope: full #38 summary/cell-explorer label mapper work.
- Do not change which modes/methods the UI offers (Absolute already present).
- UI already calls `plotCycles()` on Mode `@change`; fix is backend figure chrome.

### Prior art

- Confirmed: capacity **data** scales with mode; x-axis stays
  `Capacity (mAh/g)` because cellpy `cycles_plotter` / `sequence_plotter`
  default `x_unit="mAh/g"` and do not read collection meta mode.
- Passing `x_unit=…` into `collection.plot(...)` updates the title (verified).
- [`CAPACITY_UNITS`](../../src/cellpy_simple_gui/core/models.py) already maps
  mode → pretty units (`mAh/g`, `mAh/cm²`, `mAh`).
- [`cellpy.plotting.units_quantity_label`](../../.issueflows/04-designs-and-guides/cellpy-delegation-inventory.md)
  → e.g. `Capacity (mAh/cm**2)`; usable, but `**2` is uglier than `CAPACITY_UNITS`.
- [`plotting.cycles_figure`](../../src/cellpy_simple_gui/core/plotting.py) →
  [`collect.figure_json`](../../src/cellpy_simple_gui/core/collect.py).
- [`test_cycles_figure_areal_mode`](../../tests/test_core.py) exists but only
  asserts `len(data) >= 1` — strengthen per acceptance.
- Toolbox: none.

## Approach

1. In `cycles_figure`, derive `x_unit` from `spec.mode` via `CAPACITY_UNITS`
   (primary) — optionally cross-check / fallback with
   `units_quantity_label("Capacity", "capacity", mode=…)` if we want cellpy as
   source of truth with a small `**2` → `²` tidy.
2. Forward `x_unit=…` into `collect.figure_json` / `collection.plot` kwargs
   (same path Cell explorer uses).
3. Strengthen tests: gravimetric → `mAh/g`; areal → `mAh/cm` (accept `²` or
   `**2`); absolute → bare `mAh` without `/g` or `/cm`.
4. Note upstream gap briefly in `CELLPY_PAINPOINTS.md` and/or
   `cellpy-delegation-inventory.md` (cycles plotter ignores collection mode for
   `x_unit`).

## Files to touch

| Path | Change |
| --- | --- |
| `src/cellpy_simple_gui/core/plotting.py` | Pass mode-derived `x_unit` into `figure_json` |
| `tests/test_core.py` | Assert x-axis unit substrings per mode |
| `.issueflows/04-designs-and-guides/cellpy-delegation-inventory.md` | Record keep-forwarding `x_unit` until upstream |
| `CELLPY_PAINPOINTS.md` | Optional short painpoint bullet |
| `.issueflows/01-current-issues/issue72_status.md` | Track during build |

## Test strategy

- `uv run pytest` (focus `tests/test_core.py` cycles figure tests).
- Manual: Cycles tab → Mode Areal / Gravimetric / Absolute; axis updates without reload.

## Open questions

None blocking — recommended: use existing `CAPACITY_UNITS` for `x_unit` (pretty
`cm²`) rather than raw `units_quantity_label` (`cm**2`). Say if you prefer
cellpy-string-only.
