# Plan — #197 filtering for cycle summary plots

## Goal

On the Cycle summary tab, a side-pane filter keeps only cycles run at a chosen
C-rate. The chart and the data export show the same cycles.

## Constraints

- Cycle summary only. Cycles and Cell explorer stay as they are.
- Filter before collect, so group average, spread, y-ranges, and CSV/Parquet
  export all see the reduced cycle set. Do not hide points in Plotly after the
  fact.
- Blank C-rate means no filter (today's behaviour).
- Out of scope: summary-column range filters (CE, capacity, IR, …), and
  cellpy's `rate_inverse` / `rate_inverted` ("keep the other cycles").
- Update `.issueflows/04-designs-and-guides/plot-sidepane.md` when this lands:
  the summary pane is no longer y-ranges only.

### Prior art

- `cellpy.collect.SummaryOptions.rate` / `rate_on` / `rate_std` — step-table
  C-rate selection (`rate_cycles` in `cellpy/collect/_summary_ops.py`). Keep
  cycles whose charge and/or discharge step is within tolerance of the rate.
  Default step is charge; default tolerance is 10% of the rate. **Use this.**
- `summary_collection` (`core/collect.py`) already forwards `max_cycle` and
  `group_it` into `collect_summaries`, on both the curated-column path and the
  registry-family `options.replace(...)` path. Mirror that for the rate fields,
  and put them in the plot-cache key next to `max_cycle`.
- `SummaryPlotSpec.max_cycle` plus the summary side pane (`index.html`,
  `app.js` `summarySpec()`) is the existing "optional number, blank = off"
  pattern. Coexist: C-rate sits in that pane; Max cycle stays in the top bar.
- Summary `charge_c_rate` / `discharge_c_rate` columns are a plot type, not a
  cycle selector. Do not filter the summary frame on those columns.
- Toolbox: none. Graph: `graphify-out/` is absent.

## Approach

1. Add optional fields on `SummaryPlotSpec`:
   - `rate: float | None` — C-rate to keep (for example `0.05` for C/20).
   - `rate_on: tuple` of `"charge"` and/or `"discharge"`, or `None` (cellpy
     default: charge) .
   - `rate_std: float | None` — absolute tolerance; `None` keeps cellpy's
     10% of `rate`.
   Reject negative `rate` or `rate_std`.
2. `summary_collection(..., rate, rate_on, rate_std)` passes those into
   `collect_summaries` (kwargs on the plain path, `options.replace` on the
   family path). Include them in the cache payload.
3. `plotting.summary_figure` and `export.summary_export` pass the three fields
   from the spec. Figure export already goes through `summary_figure`.
4. If `rate` is set and the collected frame has no rows, return the existing
   empty-figure helper: "No cycles match C-rate {rate}." Export of that case
   raises `ValueError` with the same sentence (same idea as compare export
   when nothing is selected).
5. Side pane (same `<aside>` as Y ranges, 200px):
   - **Filter** — C-rate (blank = all), step (`Charge` / `Discharge` /
     `Charge and discharge`), tolerance (blank = 10%).
   - **Y ranges** — unchanged, under the filter.
   `@change` calls `plotSummary()`, same as Max cycle. `summarySpec()` sends
   `rate` / `rate_on` / `rate_std` only when a rate is set (`_num`, null when
   blank). Step "both" is `["charge", "discharge"]`.

## Files to touch

- `src/cellpy_simple_gui/core/models.py` — spec fields and validators.
- `src/cellpy_simple_gui/core/collect.py` — `summary_collection` kwargs and
  cache key.
- `src/cellpy_simple_gui/core/plotting.py` — pass the fields; empty-frame
  message when a rate is set.
- `src/cellpy_simple_gui/core/export.py` — pass the fields; empty export error.
- `src/cellpy_simple_gui/web/templates/index.html` — Filter section.
- `src/cellpy_simple_gui/web/static/js/app.js` — `summary` state and
  `summarySpec()`.
- `src/cellpy_simple_gui/web/static/css/app.css` — spacing for the second
  pane heading, only if the existing gap is not enough.
- `tests/test_core.py` — rate keeps matching cycles; a rate present in no
  step yields the empty message; export raises.
- `.issueflows/04-designs-and-guides/plot-sidepane.md` — summary pane now
  holds the C-rate filter and the y-ranges.

## Test strategy

`uv run pytest` (full suite). New tests use the existing `loaded_library`
example cell: read a C-rate that its step table actually contains, assert the
filtered collection's cycle set is smaller than the unfiltered one and that
every kept cycle had a matching step, then assert an unused rate (for example
`99`) produces the empty-figure message and a `ValueError` from
`summary_export`. A spec test rejects a negative rate without loading cells.

## Open questions

None. Summary-column filters and "keep the other cycles" are deferred on
purpose. **Revise** if the pane should filter on something other than C-rate.
