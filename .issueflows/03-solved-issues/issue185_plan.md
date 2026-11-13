# Plan — #185 cell mode does not reach ICA

## Goal

Changing a cell from anode to full cell in Manage cells must change which
half-cycle ICA (and DVA) call **charge** and which they call **discharge**,
including the Cycles and Cell explorer plots that filter on Direction.

## Root cause

The edit already lands. `Library.update` → `apply_physical_meta` sets
`cell.cycle_mode = "full_cell"`, refreshes the summary, and
`_touch` drops the plot cache. The screenshot (Cycles, dQ/dV, per cycle) is
what you get after that.

cellpy disagrees with itself about the spelling:

- `cellpy.get` and this app store `full_cell` (`CycleMode` in
  `core/models.py`, the Manage cells `<select>`).
- `get_cap` treats every mode except the exact string `anode` as
  charge-first. The first half-cycle is always direction code `-1`, the
  second `+1`. So for `full_cell`, code `-1` is the charge series.
- `cellpy.ica._DIRECTION_BY_CYCLE_MODE` only knows `anode`, `cathode`, and
  `full-cell` (hyphen). Anything else, including `full_cell`, is labeled as
  **anode** (`-1` discharge, `+1` charge).

Direction = Charge (the Cycles and Cell explorer default) then keeps code
`+1`, which on a `full_cell` is the **discharge** series. The plot stays a
single lobe, so the edit looks like it never reached ICA. `full-cell` (the
spelling ICA already accepts) labels `-1` as charge and lines up with
`get_cap`. That is the likely split behind the green cells in the screenshot
showing both lobes while the edited cells show one: same filter, opposite
half-cycle, and only some cells were stored with a spelling ICA understands.
Direction = Both still draws every half-cycle that exists; this fix does not
invent a charge or discharge step the file does not have.

Voltage curves are already on the charge-first path for any non-`anode`
mode, which matches the report that Cycles voltage looks fine.

## Constraints

- Keep the app's stored value `full_cell`. `read_meta` and the dropdown
  whitelist that spelling; rewriting the cell to `full-cell` would blank the
  control and the saved project.
- Do not change cellpy. Translate at the app boundary.
- Anode and cathode already match ICA's table. Leave them alone.
- Voltage / summary plots keep today's `get_cap` behaviour.
- Plot-cache invalidation on `Library.update` stays as it is.

### Prior art

- `cellpy.ica._direction_labels` — unknown `cycle_mode` falls back to anode.
  Mirror its `full-cell` labels; do not reimplement half-cycle extraction.
- `cellpy.readers.capacity_curves.get_cap` — order follows `== "anode"`;
  coexist, do not wrap voltage collection.
- `collect.ica_collection` / `collect.dva_collection` — both call cellpy
  collectors that read `cell.cycle_mode` inside `dqdv` / `dvdq`. Translate
  for the duration of that call, then put the original string back so the
  library and the on-disk cell stay `full_cell`.
- `plotting.cycles_figure` / `ica_figure` — already pass `spec.direction`
  through to cellpy (#821). No direction-filter change.
- `collect.select_ica_direction` — export filter uses the same `direction`
  strings. A correctly labeled frame fixes the export too.
- `Library.update` + `plot_cache.invalidate` — mode edits already miss the
  cache via `cache_revision`. Not the bug.
- `.issueflows/04-designs-and-guides/manage-cells-modal.md` — documents the
  edit path this plan relies on.
- Toolbox: `.issueflows/00-tools/` has no helper for this.
- Graph: `graphify-out/GRAPH_REPORT.md` is absent.

## Approach

1. Add a tiny translator, next to the ICA collect path: `full_cell` (any
   common separator, case-insensitive) → `full-cell` for the cellpy call
   only. Anode, cathode, empty, and an already-hyphenated `full-cell` pass
   through.
2. `ica_collection` and `dva_collection` apply it on each record's cell
   around the `collect_ica` / `collect_dva` call and restore the previous
   value in a `finally`. The cached collection then holds the corrected
   `direction` column.
3. `read_meta` maps a stored `full-cell` back to `full_cell` so a file
   written by cellpy still shows **full_cell** in the dropdown. The cell
   object is not rewritten until the user edits it.

No UI change. Direction stays default **Charge**.

## Files to touch

- `src/cellpy_simple_gui/core/collect.py` — translator and the two
  collection wrappers.
- `src/cellpy_simple_gui/core/cellpy_adapter.py` — `read_meta` accepts
  `full-cell` as `full_cell`.
- `tests/test_core.py` — labeling regression on the example cell.

## Test strategy

`uv run pytest` (project check). New test, skipped only if the example cell
cannot be loaded:

- Set `cycle_mode` to `full_cell`, collect ICA for one cycle with both step
  types, and assert both `charge` and `discharge` rows exist.
- The voltages labeled `charge` match `get_ccap` for that cycle, not
  `get_dcap`. The same cell left as `anode` still labels `get_ccap` as
  charge (the translator must not swap anode).
- `read_meta` on a cell whose attribute is `full-cell` returns `full_cell`,
  and the attribute itself is unchanged.
- After the collect call, `cell.cycle_mode` is still the app spelling.

## Open questions

- None that block the labeling fix. If the edited cells' raw files truly
  contain only one step type, Direction = Both will still show one lobe
  after this; say so if the screenshot should instead force Both for full
  cells (that would be a separate UI default, not this bug).
