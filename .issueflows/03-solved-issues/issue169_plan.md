# Plan — Issue #169: Compare selected cells

Source: https://github.com/cellpy/cellpy-simple-gui/issues/169

## Goal

Give the **Cell explorer** a *Compare* mode: pick several cells, each with its
own cycle selection, and draw them **in one panel** — e.g. cycle 3 of cell A
over cycle 7 of cell B — for voltage curves, dQ/dV and dV/dQ, with the same
mode/method/direction/axis-range controls and the same data/figure exports the
single-cell explorer already has.

## What exists today, and the gap

| Tab | Cells | Cycles | Panels |
|---|---|---|---|
| **Cycles** (collector) | all *selected* | **one** cycle list for every cell | facets: `per_cell` (panel = cell, colour = cycle) or `per_cycle` (panel = cycle, colour = cell) |
| **Cell explorer** | exactly one | from/to/max | one panel, colour = cycle |

Two things are missing for #169, and neither is a UI-only change:

1. **Per-cell cycle selection.** cellpy's `collect_cycles` / `collect_ica` /
   `collect_dva` take one `cycles` list for the whole batch. "Cycle 3 of A and
   cycle 7 of B" has no expression in the collect step.
2. **An overlay across cells.** cellpy's collected layouts are only `per_cell`
   and `per_cycle` (`resolve_collected_layout_kind`, `_VALID_LAYOUTS`) — both
   facet. With picks (A: 3) and (B: 7), `per_cell` gives two panels with one
   curve each and `per_cycle` the same; neither puts the two curves on one axis.

Verified against the installed cellpy (probe, not assumption): the collected
curves frame is long with columns `potential, capacity, cell, group, sub_group,
cycle_num`; the ICA/DVA frame has `cycle, direction, voltage, capacity, dqdv,
cell, …` (note **`cycle_num` vs `cycle`**). `cell` holds the batch key `_batch`
builds from `rec.label or rec.name or rec.id` (de-duplicated with ` (n)`). A
`per_cell` figure has one `xaxis`/`yaxis` pair per cell, traces named by cycle,
and one facet annotation per cell — `collect._facet_traces` already maps them.

## Constraints

- **cellpy boundary:** only `core/cellpy_adapter.py` and `core/collect.py`
  import cellpy; routers/UI never do. **No hand-rolled figures from raw
  dataframes** (`plotting.py` docstring): the figure must still come out of
  `Collection.plot`, with the app applying a *light restyle* afterwards — the
  overlay is a post-plot restyle of cellpy's own traces, not a new renderer.
- **Export parity** (`plot-sidepane.md`): what the chart shows is what
  `Export → Data` writes and what kaleido renders, so ranges/picks live in the
  spec, not in client-side Plotly state.
- Compare applies to the three *collected* curve kinds (`curves`, `dqdv`,
  `dvdq`). Developer-mode `raw` / `cycleinfo` stay single-cell (their payloads
  are per-cell time series, not collections).
- Guard payload size: max **8 picks**, cycles per pick capped by the existing
  `maxCurves` logic client-side and by a server-side cap (`≤ 40` cycles per
  pick, `≤ 80` curves total) — mirrors the sidepane limits.
- `uv run pytest` must stay green; API tests use the cached example cells
  (`cellpy` + `rate`, two distinct cells with different cycle counts — exactly
  what the feature needs). No Playwright additions required (e2e suite is
  optional/skipped by default) — manual browser check instead.
- Record the missing cellpy capability (overlay layout for collected curves)
  in `CELLPY_PAINPOINTS.md` per the project's motivation section.
- Branch note: `cursor/169-compare-cells-2654` (cloud-agent naming), created
  from `origin/main` after #170 merged; first commit archives the stray #168
  status file.

### Prior art

- `collect.select_ica_direction(collection, direction)` — **mirror**: filters
  `collection.data` (polars) in place for export parity. The new
  `restrict_to_cycle_pairs(collection, pairs)` is the same move on
  `(cell, cycle_num|cycle)`.
- `collect._facet_traces(fig)`, `_tidy_facet_annotations`, `_apply_colorway`,
  `_shorten_legend`, `_apply_xy_ranges` — **reuse** inside the new
  `_overlay_facets(fig)` post-plot step (trace → facet → cell label).
- `plotting.cycles_figure` — **mirror** its dispatch on `curve_kind`
  (`_CURVE_FAMILIES`, ica/dva vs cycles collection, `x_unit` from mode (#72),
  `direction` passed to the plotter (#821)).
- `routers/plots._cycles_records`, `_cell` — **reuse** for 404 handling.
- `routers/export.export_cycles` + `core/export.cycles_export` /
  `cycles_figure_export` — **mirror** for `/api/export/compare`.
- `models.CyclesPlotSpec` / `IcaPlotSpec` (`_clean_axis_range` validators) —
  **extend by composition**: `ComparePlotSpec` carries the union of their
  curve-kind fields plus `picks`.
- `app.js`: `buildCycleListFrom`, `axisRangeFields`, `appearanceFields`,
  `_withPlotBusy("cell", …)`, `exportCycles` — **reuse**; Compare lives in the
  existing `cell` state and `cellChart`, no new tab (the issue asks for a
  *mode* in the explorer, and `plot-sidepane.md` already rejected folding the
  collector into the explorer — the reverse holds too).
- Toolbox `.issueflows/00-tools/`: empty. Graph: community 52 "CyclesPlotSpec"
  (cycles_plot/_cycles_records/ica_figure…) is exactly the touched area.

## Approach

### 1. Spec — `core/models.py`

```python
class ComparePick(BaseModel):
    cell_id: str
    cycles: list[int] = Field(default_factory=list, max_length=40)

class ComparePlotSpec(BaseModel):
    """Several cells, each with its own cycles, in one figure (#169)."""
    picks: list[ComparePick] = Field(min_length=1, max_length=8)
    curve_kind: CurveKind = "voltage"          # voltage | dqdv | dvdq
    mode: CapacityMode = "gravimetric"; method: CycleMethod = "forth-and-forth"
    direction: IcaDirection = "charge"; voltage_resolution: float = 0.005
    layout: CompareLayout = "overlay"          # overlay | per_cell
    x_range / y_range / figure_theme / color_scheme / title  (as CyclesPlotSpec)
```

Validator: total cycles across picks ≤ 80; a pick with no cycles is dropped
(an empty-after-cleaning spec renders the "pick cycles" empty-figure prompt,
like `cycles_figure`). Duplicate `(cell, cycle)` pairs collapse.

### 2. Core — `core/collect.py`

- `restrict_to_cycle_pairs(collection, pairs: set[tuple[str, int]])` — filter
  `collection.data` to rows whose `(cell, cycle_num)` (curves) or
  `(cell, cycle)` (ica/dva) is in `pairs`; column picked by presence. Best-effort
  with a warning like `select_ica_direction`. Keys are the **batch labels**, so
  the caller maps records → labels the same way `_batch` does (factor the key
  derivation out of `_batch` into `batch_keys(records) -> list[str]` and reuse
  it in both places so they cannot drift).
- `_overlay_facets(fig, cell_labels: dict[axis_pair → label])` — post-plot:
  for every trace, rename to `"<cell> · cycle <n>"` (hover keeps the full name
  via `_preserve_full_name_on_hover`), point `xaxis`/`yaxis` at `x`/`y`, give
  each trace its own `legendgroup` (so `group_legend_muting` semantics don't
  mute both cells), drop facet annotations and the extra axes, keep the first
  axes' titles, and recolour traces sequentially from the figure's colorway —
  mandatory, because cellpy colours by *cycle number*, so cycle 3 of A and
  cycle 3 of B would otherwise be the same colour. The Plotly template
  colorway is used when `color_scheme == "cellpy"`, else `_apply_colorway`'s
  palette.
- `figure_json(...)` gains `overlay: bool = False`, applied right after
  `collection.plot` and before `_restyle` (so legend truncation and theme see
  the final names).

### 3. Core — `core/plotting.py`

`compare_figure(records: list[tuple[CellRecord, list[int]]], spec)`:
unique records in pick order → union of cycles → the right collection
(`cycles_collection` with mode/method, or `ica_collection` / `dva_collection`
with resolution) → `restrict_to_cycle_pairs` → `figure_json(collection,
family_kind=…, layout="per_cell", overlay=(spec.layout == "overlay"),
direction=…, x_unit=…, x_range/y_range, theme/colours)`. Empty picks → the
existing `_CURVE_PROMPTS` empty figure.

### 4. API — `api/routers/plots.py`, `api/routers/export.py`, `core/export.py`

- `POST /api/plots/compare` → `ComparePlotSpec` → resolve each pick's cell
  (404 "No such cell: <id>" on a miss) → `plotting.compare_figure`.
- `POST /api/export/compare?fmt=` → data via `collect.export_bytes` on the
  *restricted* collection (ICA direction filter applied as `export_ica` does);
  figure formats via the kaleido path (`compare_figure_export`, mirroring
  `cycles_figure_export`). Filename `compare_<n>_cells.<ext>`.

### 5. UI — `web/templates/index.html`, `web/static/js/app.js`, `app.css`

In the Cell explorer sidepane, under *Plot*:

- A **Compare cells** toggle (checkbox). Hidden for `raw` / `cycleinfo`.
- When on, a **Picks** list replaces the single from/to/max-curves block:
  pick #1 is the explorer's current cell (its from/to/max carry over); each
  pick row = cell `<select>` + `cycles` text input accepting `3` / `3, 7` /
  `5-9` (parsed client-side with a small `parseCycleList(text, min, max)`,
  clamped to that cell's cycle bounds fetched from the existing
  `GET /api/cells/{id}/cycles`) + ✕. **+ Add cell** appends a row (default:
  first cell not yet picked, same cycles as the last row). Max 8.
- A **Layout** select: *Overlay* (default) / *Side by side* (`per_cell`).
- Mode / method / direction / V-resolution / axis ranges stay where they are
  and apply to all picks; `cellAxisLabels` unchanged.
- `compareSpec()` builds the payload; `_plotCellFigure` routes to
  `/api/plots/compare` when compare is on; `exportCycles` routes to
  `/api/export/compare`. The Export button label/menu is unchanged.
- The top-row **Cell** select still drives pick #1 (changing it updates row 1
  and re-plots), so the mental model stays "the explorer, plus more cells".
- Cell-metrics strip: shown for pick #1 only (unchanged).
- Persist `cell.compare` state in memory only (no localStorage).

### 6. Docs

- `docs/guides/` — if a cell-explorer guide exists, add a short *Compare cells*
  subsection; else a paragraph in `README.md`'s screenshot tour where the
  explorer is described. `tools/gen_llms_txt.py` regenerate if docs change.
- `CELLPY_PAINPOINTS.md` — new entry (Round 7): *collected curve layouts have
  no `overlay`; per-cell cycle selection needs post-collect filtering*. Mark
  🟢 (workaround in app) and offer to file upstream.
- `.issueflows/04-designs-and-guides/compare-cells.md` — decision note
  (filter-on-collection + overlay-as-restyle vs. the alternatives below).

## Files to touch

| Path | Change |
|---|---|
| `src/cellpy_simple_gui/core/models.py` | `ComparePick`, `CompareLayout`, `ComparePlotSpec` (+ validators) |
| `src/cellpy_simple_gui/core/collect.py` | `batch_keys()` (factored from `_batch`), `restrict_to_cycle_pairs()`, `_overlay_facets()`, `overlay=` on `figure_json` |
| `src/cellpy_simple_gui/core/plotting.py` | `compare_figure()` |
| `src/cellpy_simple_gui/core/export.py` | `compare_export()`, `compare_figure_export()` |
| `src/cellpy_simple_gui/api/routers/plots.py` | `POST /plots/compare` (+ `_compare_records`) |
| `src/cellpy_simple_gui/api/routers/export.py` | `POST /export/compare` |
| `src/cellpy_simple_gui/web/templates/index.html` | Compare toggle, picks list, layout select in the explorer sidepane |
| `src/cellpy_simple_gui/web/static/js/app.js` | `cell.compare` state, `parseCycleList`, pick CRUD, `compareSpec`, routing in `_plotCellFigure` / `exportCycles` |
| `src/cellpy_simple_gui/web/static/css/app.css` | `.pick-row` styling (compact, matches `.ctl`) |
| `tests/test_api.py` (or new `tests/test_compare.py`) | see below |
| `tests/test_core.py` | `restrict_to_cycle_pairs` + overlay unit tests |
| `docs/…`, `README.md`, `llms-full.txt` | per §6 |
| `CELLPY_PAINPOINTS.md`, `.issueflows/04-designs-and-guides/compare-cells.md` | per §6 |
| `.issueflows/01-current-issues/issue169_status.md` | status |

## Test strategy

`uv run pytest` (example cells are cached in this VM, so the `example_cell`
fixture runs rather than skips). New tests:

- **Core** — `restrict_to_cycle_pairs` keeps exactly the requested
  `(cell, cycle)` rows for both the curves frame (`cycle_num`) and the ICA
  frame (`cycle`); unknown column → unchanged + warning. `_overlay_facets` on a
  real two-cell `per_cell` figure: one axis pair left, N traces named
  `"<cell> · cycle <n>"`, N distinct colours, no facet annotations,
  `legendgroup`s unique.
- **API** — `/api/plots/compare` with `[(cellpy-cell, [1,3]), (rate-cell, [2])]`
  returns 3 traces in one panel; `layout="per_cell"` returns two axis pairs;
  `dqdv` and `dvdq` kinds work; unknown `cell_id` → 404; 9 picks → 422;
  empty cycles everywhere → the empty-figure prompt (not 500);
  `/api/export/compare?fmt=csv` rows cover only the picked pairs, PNG export
  returns bytes or a clean 503 (same contract as the smoke test).
- **Essential marker:** the API tests carry `@pytest.mark.essential` like the
  neighbouring plot tests.
- **Manual (browser):** `uv run cellpy-simple-gui --server --no-open --port 8577`
  with `CSG_TOKEN`, load demo cells, Cell explorer → Compare → two picks with
  different cycles → overlay renders, legend shows cell · cycle, switching to
  Side by side facets, Export CSV downloads; recorded as a walkthrough video.

## Open questions

1. **Overlay colouring when `color_scheme = "cellpy"`.** *Recommended:*
   sequential colours from the Plotly template colorway per trace (cellpy's
   per-cycle colours cannot be kept — they collide across cells). Alternative:
   colour by **cell** with line-dash by cycle — reads well for ≤3 cycles per
   cell, badly beyond; could be a later "Colour by" option.
2. **Where picks live.** *Recommended:* inside the Cell explorer as a mode
   (the issue's wording; keeps one chart and one export menu). Alternative: a
   fourth tab "Compare" — cleaner state, but a fourth tab for a variant of the
   explorer felt like the thing `plot-sidepane.md` already declined.
3. **Pain-point upstream.** *Recommended:* record it in `CELLPY_PAINPOINTS.md`
   now; filing the cellpy issue (`layout="overlay"` + per-cell cycle selection
   in `CurveOptions`) is your call — I will not create it from here.

Reply **Accept** (defaults = recommendations), **Revise**, or **Abort**.
`auto_build = true` chains into `/iflow-build` on Accept.
