# Compare cells (#169)

## Context

The Cell explorer plotted one cell; the Cycles collector plotted every selected
cell with *one* cycle list for all of them. The request: pick several cells,
each with its own cycles ("cycle 3 of A against cycle 7 of B"), and draw them
together. cellpy has neither piece — `CurveOptions.cycles` is per batch and
the collected layouts (`per_cell` / `per_cycle`) both facet, colouring by
cycle number (CELLPY_PAINPOINTS §36).

## Decision

- **A mode inside the Cell explorer**, not a fourth tab: a `Compare cells`
  checkbox in the sidepane; pick #1 is the explorer's current cell and the top
  Cell select keeps driving it. Picks are rows of cell select + free-text
  cycles (`3`, `3, 7`, `5-9`, parsed and clamped client-side with that cell's
  bounds from `GET /api/cells/{id}/cycles`), max 8 picks. A `Layout` select
  offers `Overlay` (default) or `Side by side` (cellpy's `per_cell`).
- **Filter the collection, don't collect per cell.** `plotting.compare_collection`
  collects the union of cycles across the picked cells (same `cycles_collection`
  / `ica_collection` / `dva_collection` as everywhere else), then
  `collect.restrict_to_cycle_pairs` semi-joins `collection.data` on
  `(cell, cycle_num | cycle)`. Keys come from `collect.batch_keys` — factored
  out of `_batch` so the filter and the batch cannot disagree on labels.
  Mirrors `select_ica_direction`; the figure and the data export share one
  narrowed collection, so what the chart shows is what `Export → Data` writes.
- **Overlay is a post-plot restyle, not a new renderer.** `figure_json(...,
  overlay=True)` draws cellpy's `per_cell` figure, then `_overlay_facets`
  rebuilds the layout with one axis pair, moves every trace to `x`/`y`, names
  it `"<cell> · cycle <n>"` (cell part truncated so the cycle survives
  `_shorten_legend`), gives it a unique `legendgroup` (so a legend click mutes
  one curve), recolours sequentially from the template colorway (curated
  schemes still win via `_apply_colorway`), and drops the facet strips. Full
  identity stays in the PX hovertemplate (`cell=…`, `cycle_num=…`).
- **Guards:** `ComparePlotSpec` — ≤8 picks, ≤40 cycles per pick, ≤80 curves
  total; duplicate cells merge; axis-range cleaning as `CyclesPlotSpec`.
  Raw / cycle-info stay single-cell (per-cell time series, no collection).
- Endpoints: `POST /api/plots/compare`, `POST /api/export/compare?fmt=`
  (filename `compare_<n>_cells.<ext>`; data formats + kaleido figures).

## Alternatives considered

- *Fourth "Compare" tab* — cleaner state, but a tab for a variant of the
  explorer is what `plot-sidepane.md` already declined.
- *Collect each pick separately and concatenate frames* — would bypass cellpy's
  batch (groups, labels, de-duplication) and still need the overlay.
- *Colour by cell with line-dash by cycle* — reads well for ≤3 cycles per cell,
  badly beyond; possible later "Colour by" option.
- *Build the overlay figure by hand from the frame* — against the project rule
  that figures come from `Collection.plot` plus a light restyle.

## Gotcha recorded

Alpine `x-model` on a `<select>` whose `<option>`s come from a nested `x-for`
applies the value before the options exist; a row created with its `cell_id`
already set displays the first option. The pick-row select re-applies the value
in `x-init="$nextTick(...)"`.

Issue: https://github.com/cellpy/cellpy-simple-gui/issues/169

## Addendum — missing / unreadable cycles are reported (#175)

**Context.** The semi-join silently drops a `(cell, cycle)` pair that matches
nothing, the client clamped picks to the cell's range before sending, and when
no requested cycle existed at all cellpy raised (`KeyError('cycle_num')`,
painpoint §37) → "nothing happened" or `Could not render this plot`.

**Decision.**

- No client-side clamping: `parseCycleList` keeps `≥ 1` and the 40-cap only,
  so an out-of-range cycle reaches the server and is reported like any other.
  The cell's range is the cycles input's placeholder instead.
- `plotting.compare_collection` → `(collection, reports)`. Pre-check against
  `cellpy_adapter.cycle_numbers` (never collect when nothing exists), post-check
  `collect.present_cycle_pairs` (mirror of `restrict_to_cycle_pairs`) for
  cycles that exist but yield no rows. `core/cycle_report.py` words it per cell:
  `…: cycles 22–24, 50 not in data (has 1–21)` / `…: cycle 7 could not be read`.
- Transport is `layout.meta.warnings` (Plotly free-form `meta`), so the figure
  endpoints keep returning a plain figure and the UI reads one place. The
  explorer shows a persistent `.plot-note` strip above `#cellChart` (a toast
  would fade); an all-missing request renders the empty figure with
  `Nothing to draw — …` so the message is inside the chart too.
- Same for the one-cell explorer views (`cycles_figure` with one record,
  `ica_figure`, `dva_figure`). The Cycles **tab** (several cells, one shared
  cycle list) only gets the all-missing guard
  (`None of the N selected cells has cycles …`): per-cell gaps there are
  expected, not warnings.
- Compare CSV: rows that exist are exported silently; all-missing → 400 with
  the same wording. Not done: figure annotation for static exports, an
  `X-CSG-Warnings` header for partial CSVs.

Issue: https://github.com/cellpy/cellpy-simple-gui/issues/175
