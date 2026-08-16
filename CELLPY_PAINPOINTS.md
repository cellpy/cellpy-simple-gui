# cellpy pain-points & wishlist (from building cellpy-simple-gui)

Notes gathered while building a small desktop GUI on **cellpy 2.1.0.post1**. The
goal here is constructive: these are the places where the library made an app
harder to build than it needed to be, each with a concrete suggestion. Ordered
roughly by impact.

Legend: 🔴 blocker / had to work around · 🟠 friction · 🟢 nice-to-have.

> **Update — everything from the first four rounds is fixed upstream** 🎉
>
> The notes below were written against **cellpy 2.1.0.post1**; the app now runs
> on **≥2.1.2** (released). #867 and #868 both closed in 2.1.2, clearing the
> backlog; §29 and §30 were found afterwards, while building on it, and §31–§33
> came out of deploying it headless. Each fix was verified against the installed
> package before the corresponding app workaround was removed — closed upstream
> is not the same as released, and that caught us twice (see the release-gating
> note in `.issueflows/04-designs-and-guides/cellpy-delegation-inventory.md`).
>
> **29 issues filed from this project · 25 closed · 4 open** (§29 /
> [#874](https://github.com/jepegit/cellpy/issues/874), §30 /
> [#875](https://github.com/jepegit/cellpy/issues/875), §31 + §33 /
> [#938](https://github.com/jepegit/cellpy/issues/938), §32 /
> [#937](https://github.com/jepegit/cellpy/issues/937)). Plus
> [#851](https://github.com/jepegit/cellpy/issues/851), which cellpy raised
> itself and whose fix the app adopted.
>
> Workarounds deleted as the fixes landed: the group-average partition and
> facet-remap path, the `share_y` axis re-link, the `fig.write_image` export
> plumbing, the forced `auto_pick_cellpy_format=False`, the ICA direction
> frame-filter, the DVA single-cell path with its pandas→polars conversion, the
> DVA half-cycle marking, and the raw-trace striding.
>
> ### Round 1 — the first build (2.1.1.x)
>
> | # | Item | Upstream | Landed |
> |---|---|---|---|
> | 1 | Collection from in-memory cells | [#787](https://github.com/jepegit/cellpy/issues/787) | `collect.from_cells` — replaced a hand-rolled batch shim |
> | 2 | Group-averaged summary can't plot | [#785](https://github.com/jepegit/cellpy/issues/785) | fixed |
> | 3 | No "was it averaged?" signal | [#790](https://github.com/jepegit/cellpy/issues/790) | `Collection.is_grouped` / `meta.grouped` |
> | 4 | `CurveOptions` mode/method | [#788](https://github.com/jepegit/cellpy/issues/788) | added |
> | 5 | Quiet, app-facing instrument list | [#786](https://github.com/jepegit/cellpy/issues/786) | quiet by contract (2.1.1.post3) |
> | 6 | `Collection.save` xlsx/json | [#789](https://github.com/jepegit/cellpy/issues/789) | supported |
> | 7–8 | polars/pandas boundary + quiet startup docs | [#791](https://github.com/jepegit/cellpy/issues/791) / [#798](https://github.com/jepegit/cellpy/pull/798) | docs |
> | 9 | Lightweight `read_meta(path)` | [#799](https://github.com/jepegit/cellpy/issues/799) | 2.1.1.post4 |
> | 10 | Per-instrument metadata schema | [#800](https://github.com/jepegit/cellpy/issues/800) | 2.1.1.post4 |
> | 11 | App-friendly collected figures | [#801](https://github.com/jepegit/cellpy/issues/801) | 2.1.1.post4 hooks |
> | 12 | Per-panel y-limits / `share_y` | [#804](https://github.com/jepegit/cellpy/issues/804) | 2.1.1.post2 |
>
> ### Round 2 — plotting and loading (2.1.2a2 / a3)
>
> | # | Item | Upstream | Landed | App code removed |
> |---|---|---|---|---|
> | 3b | All-or-nothing `group_it` + long/wide facet merge | [#816](https://github.com/jepegit/cellpy/issues/816) | 2.1.2a2 | partition + merge + facet remap |
> | 12b | `spread_plot` ignores `share_y` | [#817](https://github.com/jepegit/cellpy/issues/817) | 2.1.2a2 | the `#47` axis re-link |
> | 13 | In-memory figure export (PNG/SVG/PDF bytes) | [#818](https://github.com/jepegit/cellpy/issues/818) | 2.1.2a2 | `fig.write_image` plumbing |
> | 14 | `.h5` auto-pick vs raw `instrument=` | [#819](https://github.com/jepegit/cellpy/issues/819) | 2.1.2a2 | forced `auto_pick=False` |
> | 15 | Cycles facet strip pretty labels | [#820](https://github.com/jepegit/cellpy/issues/820) | post7 | (nothing — free) |
> | 16 | ICA `direction` for line plots + `both` | [#821](https://github.com/jepegit/cellpy/issues/821) | post7 | `_filter_ica_by_direction` |
>
> ### Round 3 — configuration (2.1.2a3)
>
> Found while wiring the config panel. cellpy 2.1.2 replaced `parameters.prms`
> with a layered pydantic-settings stack, which is a large improvement for apps —
> these were the rough edges in it.
>
> | # | Item | Upstream | Landed |
> |---|---|---|---|
> | 22 | `model_dump_for_file()` wrote legacy Arbin SQL credentials in plaintext | [#849](https://github.com/jepegit/cellpy/issues/849) | 2.1.2a3 |
> | 23 | `config.override()` process-global, cross-talks between threads | [#850](https://github.com/jepegit/cellpy/issues/850) | 2.1.2a3 (contextvars) |
> | 24 | Reporting disagreed with the loader about which config file wins | [#851](https://github.com/jepegit/cellpy/issues/851) | 2.1.2a3 — `active_config_file()`, now used by the app's config panel |
>
> ### Round 4 — data integrity, DVA, raw (2.1.2a4)
>
> | # | Item | Upstream | Landed |
> |---|---|---|---|
> | 19 | Non-atomic v9 `.cellpy` writes could destroy the file | [#845](https://github.com/jepegit/cellpy/issues/845) | 2.1.2a4 — `readers/cellpy_file/atomic.py`, staged write + `os.replace` |
> | 21 | No selective summary rebuild after metadata edits | [#846](https://github.com/jepegit/cellpy/issues/846) | 2.1.2a4 — `CellpyCell.refresh_after(fields=…)`, now used instead of a full `make_summary()` |
> | 25 | `dva_plot(direction="both")` drew both half-cycles identically | [#862](https://github.com/jepegit/cellpy/issues/862) | 2.1.2a4 — solid/dot |
> | 26 | No `collect_dva` — DVA was the only single-cell family | [#863](https://github.com/jepegit/cellpy/issues/863) | 2.1.2a4 — DVA moved onto the shared collection path |
>
> ### Round 5 — the plot registry becomes self-describing (2.1.2)
>
> | # | Item | Upstream | Landed | App code removed |
> |---|---|---|---|---|
> | 27 | `raw_plot` had no point/cycle limit — 7.35 MiB of figure JSON for one demo cell | [#867](https://github.com/jepegit/cellpy/issues/867) | 2.1.2 — `max_points` / `cycles`; 7.35 MiB → 0.18 MiB | `_thin_traces` + its striding |
> | 28 | `fullcell_standard_*` couldn't be collected: `family.transforms()` shape ≠ `SummaryOptions.transforms` | [#868](https://github.com/jepegit/cellpy/issues/868) | 2.1.2 — transforms are a tuple of callables, **plus** the `family.summary_options(hdr)` this asked for | the app's out-of-band knowledge of which families need `partition_by_cv` |
>
> #28 came back better than filed. The wish was for a registry that describes
> its own collect options instead of making every app rediscover them;
> `PlotFamily` now answers with `summary_options(hdr)`, `supports_cv_split` and
> `supports_formation`, and `families(entry_point=…)` says which public plot
> entry a family belongs to. That turned a five-line app fix into a deletion:
> availability is now judged on what a family *asks the summary for* rather than
> on the columns it draws, which is exactly the distinction the app had been
> getting wrong ([cellpy-simple-gui#106](https://github.com/cellpy/cellpy-simple-gui/issues/106)).
> Measured on the demo cells: **8 of 25 families selectable → 15 of 20**, every
> one rendering real traces.
>
> ### Still open
>
> | # | Item | Upstream | App workaround |
> |---|---|---|---|
> | 29 | An unknown `layout=` is accepted silently — `layout="film"` draws a line plot that looks fine | [#874](https://github.com/jepegit/cellpy/issues/874) | `curve_layout_kwargs()` translates `film` → `kind="film"` |
> | 30 | `spread_plot` traces have no hovertemplate — ticking Spread drops all hover detail | [#875](https://github.com/jepegit/cellpy/issues/875) | `_add_spread_hover()` rebuilds it from the figure |
>
> ### Open but unfiled (app forwards a knob instead)
>
> | # | Item | App workaround |
> |---|---|---|
> | 17 | Cycles plotter ignores collect `mode` for `x_unit` | forwards `x_unit` |
> | 18 | Summary y-labels omit units; CE / C-rate have no unit hooks | passes `y_label_mapper` |
> | 20 | Summary facet order ignores collect column order on group-avg | passes `category_orders` |
>
> The notes below are kept as originally written (against 2.1.0) for context.

---

## 1. 🔴 No public "collection from in-memory cells"

`collect_summaries` / `collect_cycles` are exactly the right tools, but they only
accept a `batch` object that exposes `.cells` (`{label: CellpyCell}`) **and**
`.journal.pages` (a **polars** frame with `filename` / `group` / `sub_group` /
`group_label` / `label` / `selected`). There is no public way to get such an
object from a set of already-loaded `CellpyCell`s.

I had to reverse-engineer the contract and duck-type a shim
(`core/collect.py::_BatchShim`). It also turned out `collect_summaries` reads
`batch.journal.name` — an undocumented required attribute that only surfaced as
an `AttributeError` at runtime.

**Wish:** a supported constructor, e.g.

```python
collection = cellpy.collect.from_cells(
    cells,                       # list/dict of CellpyCell
    groups={label: 1, ...},      # optional
    selected={label: True, ...}, # optional
)
```

or `Batch.from_cells(...)`. This is the single biggest enabler for GUIs/notebooks
that manage cells in memory rather than from a journal on disk.

## 2. 🔴 Group-averaged summaries can be collected but not plotted

```python
col = collect_summaries(batch, columns=("charge_capacity_gravimetric",), group_it=True)
col.plot()            # KeyError: 'cell'
col.plot(spread=True) # KeyError: 'mean'  (when 1 cell/group) or 'cell'
```

Traceback bottoms out in `cellpy/plotting/collected.py::spread_plot`, which does
`curves.groupby("cell")` — but a group-averaged frame is keyed by `group`
(columns `group, cycle_num, variable, mean, std`), so there is no `cell` column.
The **data** side (averaging) works; only the **plot** side breaks. I ended up
degrading gracefully (`figure_json` falls back to a plain render / empty figure)
and exposing group-averaging as a data/export feature only.

**Wish:** make the collected summary renderer accept group-averaged frames
(`groupby("group")` when there is no `cell` column), so `group_it=True` is
plottable end-to-end.

## 3. 🟠 Silent all-or-nothing group-averaging when any group is a singleton

`group_it=True` silently returns a *wide, non-averaged* frame when **any** group
has < 2 cells (the "std needs ≥ 2 cells" guard in `collect/summary.py`). One
singleton in the selection disables averaging for *every* group — including
those with plenty of members. GUIs that default each cell to its own group (or
mix multi-cell and single-cell groups) see "Group average" appear to do nothing.
The returned `Collection` also carries no flag saying whether averaging actually
happened, so callers sniff for a `mean` column (`collect.is_grouped`).

Workaround in this app (#27): partition selected cells into multi-member vs
singleton groups, `group_it=True` only the multi set, keep singletons as plain
per-cell series (no spread), then merge Plotly traces / export frames.

**Follow-up (#39):** merging those two Plotly figures with bare `add_trace` puts
singleton series on the wrong facet — averaged (long) and per-cell (wide)
collections assign different subplot ids (`x`/`y`/`x2`/…) to the same
`variable`. App remaps secondary traces onto the base figure's
variable→axis map before merge. Ideal upstream: stable facet axis ids (or a
merge helper) so long and wide summary plots share subplot identity by
`variable`.

**Wish:**
1. Average groups that have ≥ 2 cells and leave singletons as ordinary (non-spread)
   series in the same collection — not all-or-nothing.
2. `Collection.meta.grouped: bool` (or `collection.is_grouped`) so callers can
   adapt UI/labels without inspecting columns.
3. Stable facet subplot ids across long (averaged) vs wide (per-cell) summary
   plots for the same column set.

**Upstream:** wish 2 ✅ [#790](https://github.com/jepegit/cellpy/issues/790);
wishes 1+3 → [#816](https://github.com/jepegit/cellpy/issues/816).

**Resolved in 2.1.2a2:** `group_it=True` averages multi-member groups while
keeping singletons as their own group in **one** collection with stable facet
ids. App `partition_by_group_size` / `summary_collections` / `figures_json` /
`combined_summary_frame` **removed**.

## 4. 🟠 `CurveOptions` can't set capacity mode / method

`CellpyCell.get_cap()` takes `mode` (`gravimetric`/`areal`/`absolute`) and
`method` (`forth-and-forth`/…), but `collect_cycles` / `CurveOptions` expose only
`cycles` / `rate`. So a multi-cell cycle-curve collection can't offer the
areal/absolute toggle a single cell can. I had to drop that control from the cell
explorer when moving to `collect_cycles`.

**Wish:** add `mode` / `method` to `CurveOptions` (and pass through to `get_cap`).

## 5. 🟠 Instrument discovery logs a WARNING per non-loader module

`instrument_configurations()` is the right API for "what can cellpy load" — but
it emits a `logging.warning(...)` for every non-loader module it skips
(`config_declarations`, `contract`, `hooks`, `declarations`, `registry`,
`testing`, and `custom` which "needs a definition file") **on every call**. An
app calling it at startup has to bracket it with a log-level bump
(`core/cellpy_adapter.py::list_instruments`).

**Wish:** a quiet, app-facing `list_instruments()` returning
`[{id, label, models, suffixes}]` with human labels and raw extensions. I keep my
own label/extension map today because the ids (`maccor_txt`, `pec_csv`) aren't
display-ready and the raw suffix isn't exposed alongside the models.

## 6. 🟠 `Collection.save()` only supports parquet/csv

`Collection.save(dir, formats=...)` raises `ValueError("unsupported collection
format")` for anything but `parquet`/`csv`, even though "save in different formats
for free" is a selling point of the collection design. I export `xlsx`/`json`
myself via `data.to_pandas().to_excel(...)` / `data.write_json()`.

**Wish:** support `xlsx` and `json` in `SaveOptions.formats` / `Collection.save`.

## 7. 🟠 polars vs pandas boundary is easy to trip on

`Collection.data` is **polars**; `cell.data.summary` is **pandas**;
`Collection.plot` internally does `.to_pandas()`. Apps end up juggling both and
guessing which a given function wants. `collect_summaries` also returns different
shapes (wide vs long) depending on `group_it`, which the plot layer then has to
reconcile (it renames `cycle_num`→`cycle` for the summary family).

**Wish:** document the dataframe boundary explicitly, and/or offer
`Collection.to_pandas()` plus a stable column contract per `kind`.

## 8. 🟠 `get_summary()` deprecation warning is noisy

`CellpyCell.get_summary()` is deprecated in favour of `cell.data.summary` (good),
but the `DeprecationWarning` fires readily and apps must blanket-suppress warnings
to keep logs/console clean. A one-line "how to silence cellpy warnings in an app"
in the docs would help.

## 9. 🟢 No lightweight metadata read

Listing many `.cellpy` files (e.g. a project browser) means a full
`cellpy.get(...)` per file just to show mass / area / #cycles. A cheap
`read_meta(path)` that reads header metadata without materialising raw/steps
would make file browsers snappy.

## 10. 🟢 No per-instrument metadata schema

When importing raw files, an app has to guess which metadata an instrument needs
(mass? area? nominal capacity? default units?). A declared schema per instrument
would let apps generate the right ingestion form automatically instead of showing
every field for every instrument.

## 11. 🟢 Collected figures aren't app-friendly by default

`collected_plot` returns faceted figures with default plotly styling: mirror axis
boxes, right-side facet titles spelled `variable=charge_capacity_gravimetric`, and
an auto height that grows with facet count. I re-style every figure
(`core/collect.py::_restyle`) to fit the app shell.

cellpy-simple-gui #32 layered **light/dark theme tokens** and curated **colorways**
onto that restyle, and registers cellpy's collector templates via
`make_collector_templates` (already done inside cellpy's plot path). Those
templates still don't cover app needs for: compact right-hand legend + long-name
truncation, facet-strip shortening, per-theme paper/plot colors, or a discrete
colorway switch independent of the science plot family.

**Wish:** a first-class theme/label/height/colorway hook (or a `FigureSpec` the
caller can pass) so the returned figure drops cleanly into an app without
post-processing. `make_plotly_template` / collector templates help axes, not the
full app chrome contract.

## 12. 🟢 Per-panel y-limits on collected summary facets

`match_axes=False` already gives independent auto-scale (cellpy-simple-gui #2
forwards it as `share_y`). Fixed **per-facet-row** ranges ship via cellpy
`y_ranges={variable: [lo, hi]}` (#804, 2.1.1.post2+); the app exposes them as
`SummaryPlotSpec.y_ranges` + summary UI widgets (#54). Older notes about
`AxisSpec` / `ce_range` / global `range_y` remain historical background.

### 12b. 🟠 `spread_plot` ignores `share_y` / `match_axes`

`summary_plotter` resolves `share_y` / `match_axes` and passes `match_axes=` into
`_cycles_plotter`, but the **spread** path (`spread_plot` / mean±std bands used
when a group-averaged frame is plotted with `spread=True`) never links facet
y-axes — `matches` stays unset even when `match_axes=True`. Apps that offer
“Share y-scale” together with “Group avg + Spread” must re-apply
`yaxisN.matches = "y"` after `collection.plot` (cellpy-simple-gui #47).

**Wish:** honour `share_y` / `match_axes` in `spread_plot` the same way the
non-spread summary path does.

**Upstream:** non-spread path ✅ [#804](https://github.com/jepegit/cellpy/issues/804);
spread follow-up → [#817](https://github.com/jepegit/cellpy/issues/817).

**Resolved in 2.1.2a2:** both grouped and grouped+spread paths honour
`share_y` / `match_axes` on the collection, so the app `#47` re-apply
(`_apply_share_y` / `_want_share_y`) was **removed**.

## 13. 🟠 No app-friendly static figure export on the collect path

`collection.plot()` is the right way for an app to get a Plotly figure, but there
is no matching collect-level API to turn that figure into PNG / SVG / PDF bytes.
`Collection.save(...)` is **data-only** (parquet/csv/json/xlsx). The kaleido-based
helper that does exist — `cellpy.utils.plotutils.save_image_files` — lives outside
collect, writes to **disk**, spawns a **subprocess** around `fig.write_image`, and
prints status to stdout. That fits notebooks/scripts; it does not fit a desktop
or FastAPI app that wants `(bytes, media_type)` for a download response (and a
clear error when kaleido is missing).

This is exactly the kind of gap this app is meant to surface: the science path
(`from_cells` → `collect_summaries` → `.plot()`) is great, then static export
falls off the paved road and each app reinvents Plotly/kaleido wiring.

**Wish:** something on the collect / plotting surface, e.g.

```python
collection.to_image("svg")           # -> bytes
# or
fig = collection.plot(...)
cellpy.plotting.write_image(fig, "pdf")  # -> bytes, raises if kaleido missing
```

Same formats users expect from kaleido (`png` / `svg` / `pdf`), in-memory, no
subprocess or cwd side effects. Optional: `Collection.save(..., formats=("svg",))`
that saves the *plot* next to the data — but bytes-first matters more for apps.

*(cellpy-simple-gui #27 — will call `fig.write_image` directly until this exists.)*

**Resolved in 2.1.2a2:** `cellpy.plotting.figures.write_image(fig, fmt, scale=)
-> bytes` (in-process `to_image`, no subprocess/temp files) plus
`image_media_type(fmt)`; `Collection.to_image(...)` too. App `export.figure_bytes`
now delegates to these.

**Upstream:** [#818](https://github.com/jepegit/cellpy/issues/818).

## 14. 🟠 `.h5` auto-picks cellpy format over raw instrument loaders

`cellpy.get(..., auto_pick_cellpy_format=True)` (the default) treats `.h5` /
`.hdf5` as native cellpy files whenever `instrument` is not exactly
`arbin_sql_h5`. Other Arbin SQL variants (or a missing instrument) then hit the
native reader and fail with `No object named data_df in the file` — easy to
misread as a corrupt file. cellpy already special-cases `arbin_sql_h5`, but apps
that always pass an explicit instrument still need
`auto_pick_cellpy_format=False` for defense in depth.

**Workaround (cellpy-simple-gui #41):** `load_raw` always sets
`auto_pick_cellpy_format=False`; Load cells stays on the native path and the UI
hints that Arbin SQL HDF5 belongs under Import raw.

**Wish:** when `instrument=` is set, never auto-pick cellpy format from suffix
(or document that callers must disable it for every raw `.h5` loader).

**Resolved in 2.1.2a2:** `.h5` / `.hdf5` auto-pick only fires when `not
instrument`, so a set `instrument=` wins. App `load_raw` no longer forces
`auto_pick_cellpy_format=False` (the `data_df` error hint is kept as UX).

**Upstream:** [#819](https://github.com/jepegit/cellpy/issues/819).

## 15. 🟢 Cycles collector facet strips still use raw `cycle_num=` / `cell=`

#801 / post4 pretty-prints **summary** facet labels (no more
`variable=charge_capacity_gravimetric` on strips; axis titles are human-readable).
The **cycles** family (`layout="per_cell"` / `"per_cycle"`, legacy
`fig_pr_cell` / `fig_pr_cycle`) still annotates facets as `cycle_num=1`,
`cell=demo`, etc. Axis titles for capacity/voltage are already fine; only the
facet strips look unfinished next to summary plots.

Surfaced while adding the multi-cell Cycles tab in cellpy-simple-gui #55 —
same `collection.plot(family_kind="cycles", layout=…)` path, no app restyle for
those annotations yet.

**Wish:** apply the same pretty-label pass to cycles (and other non-summary)
collected layouts — e.g. `Cycle 1` / cell label only — so apps get consistent
chrome without per-family string scrubbing. Optionally document that `layout=`
is preferred over legacy `method="fig_pr_*"` in `cycles_plotter` docs.

**Upstream:** [#820](https://github.com/jepegit/cellpy/issues/820).

## 16. 🟢 ICA plotter direction gaps (line plots + `both`)

`cellpy.utils.ica.dqdv(..., direction="both")` (and therefore `collect_ica`,
which calls `dqdv` with the default) returns a tidy frame with both half-cycles
(`direction` column = `charge` / `discharge`). The collected **plot** path has
two gaps:

1. **`both` unsupported.** `ica_plotter` only accepts `direction="charge"` or
   `"discharge"` and silently coerces anything else to `"charge"` (with a
   `print`). Apps that want a single figure with both directions must merge two
   plot calls themselves. cellpy-simple-gui #56 therefore exposes only
   Charge | Discharge in the Cell explorer dQ/dV UI.

2. **Line / `fig_pr_cell` ignores `direction`.** `ica_plotter` →
   `_cycles_plotter` → `sequence_plotter` only calls `_select_direction` when
   `method=="film"`. For the default ICA line layout (`fig_pr_cell` /
   `layout="per_cell"`), the `direction` kwarg is a no-op: both lobes stay in
   each cycle’s trace and Plotly can draw a spurious join between half-cycles.
   Surfaced in cellpy-simple-gui #67 after #56.

**App workaround (#67):** filter the collected ICA polars frame to
`direction == charge|discharge` in `core/collect.ica_collection` before
`Collection.plot`, so Charge/Discharge (and figure/data export) actually differ
without depending on cellpy’s film-only filter.

**Wish:** call `_select_direction` for ICA line layouts as well as `film`;
honour `direction="both"` (e.g. two series or grouped legend entries per cycle,
with a break so half-cycles do not join); prefer a logger warning over `print`
when coercing invalid values.

**Resolved in 2.1.2a2:** `ica_plotter` normalizes `direction` and applies
`_select_direction` on the line path too; `direction="both"` overlays both
half-cycles with `line_dash` (charge=dot, discharge=solid) and logs a warning
on invalid values. App `_filter_ica_by_direction` **removed** — `ica_figure`
passes `direction` to cellpy; the UI gained a "Both" option and exports use
`select_ica_direction` to keep the exported rows matching the chart.

---

## 17. 🟢 Cycles plotter ignores collect `mode` for `x_unit`

`collect_cycles(..., options=CurveOptions(mode=…))` correctly scales the
capacity column (gravimetric / areal / absolute), and the mode is recorded on
`Collection.meta.options`. The cycles plot path still defaults
`x_unit="mAh/g"` in `cycles_plotter` / `sequence_plotter`, so axis titles stay
gravimetric after a Mode change.

cellpy-simple-gui #72 forwards `x_unit` from the app's `CAPACITY_UNITS` map into
`collection.plot(...)`.

**Wish:** derive default `x_unit` (or full capacity axis label) from the
collection's recorded mode — e.g. via `units_quantity_label` — so apps need not
re-pass units they already set on `CurveOptions`.

## 18. 🟢 Summary default y-labels omit units (CE / C-rate unit hooks)

#801 / post4 pretty-prints summary facet / y-axis titles
(`Charge Capacity`, `Coulombic Efficiency`) via `_pretty_variable_label`, so
apps are no longer stuck with `variable=charge_capacity_gravimetric`. Units are
only appended when a Batch-style `units=` dict is passed into the summary
plotter; the `Collection.plot` path does not supply that bag, so collected
figures stay unit-less and basis-blind (areal still reads “Charge Capacity”).

Separately, `units_quantity_label` cannot label every summary column:

- **Coulombic efficiency** — no `CellpyUnits` physical property (apps fall back
  to `quantity_label(..., "%")`).
- **C-rate** — not a physical property; mapping through `current` yields
  Amperes, which is wrong (apps use `quantity_label(..., "C")`).

cellpy-simple-gui #38 builds a `y_label_mapper` with
`units_quantity_label` / `quantity_label` and passes it into `collection.plot`.

**Wish:** default summary mapper (or documented helpers) should produce
unit-bearing, mode-aware labels from the column id alone — without requiring a
Batch `units=` payload. Add efficiency / C-rate to the unit spec (or a small
registry of canonical summary labels) so apps need not maintain per-column
fallbacks.

## 19. 🟠 Non-atomic v9 `.cellpy` writes leave corrupt archives

`cellpy.readers.cellpy_file.v9` saves with
`zipfile.ZipFile(path, mode="w")` directly on the destination path. Mode `"w"`
truncates the file immediately, then members are appended in order
(`meta.json` → `raw.parquet` → `steps` / `summary` / `fid`). An interrupt,
kill, or exception mid-write (common when parquet-serializing large raw
tables) leaves a zip that still opens as a zip but is missing members —

```
cellpy.exceptions.CorruptCellpyFile: missing zip member 'raw.parquet'
```

Surfaced in cellpy-simple-gui when a project save was interrupted: one cell
file contained only `meta.json` (~1 KB); later cells were never written. The
app now stages project folders atomically, but each individual
`cell.save(..., overwrite=True)` can still truncate a previously good
`.cellpy` in place.

**Wish:** write to a same-directory tempfile (or `path.with_suffix(".cellpy.tmp")`),
close the zip, then `os.replace` onto the final path so readers never see a
half-written archive. Optionally validate required members before replace.

**Resolved in 2.1.2a4:** `readers/cellpy_file/atomic.py` stages the write beside
the target and finishes with `os.replace`, so an interrupted save can no longer
destroy the previous file. The app keeps its own project-level staging — that
protects the whole folder commit (many cells + manifest), which is a wider unit
than a single file.

## 20. 🟠 Summary facet order ignores collect column order on group-avg

`collect_summaries(..., columns=(…))` records the requested variable set, but
the summary plot path facets on the long `variable` column without setting
Plotly `category_orders`. On **per-cell (wide)** figures, facet order roughly
follows the collect column tuple. On **group-averaged (long)** figures,
`variable.unique()` / Plotly’s default order wins — typically alphabetical —
so *Capacity + CE* becomes Charge → CE → Discharge instead of the collect
order (or a stable CE-on-top layout).

Surfaced in cellpy-simple-gui #81: toggling Group avg reshuffled the CE panel.

**App workaround (#81):** pass
`category_orders={"variable": list(columns)}` into `collection.plot` / PX, and
put CE first in the app’s `capacity_ce` column tuple.

**Wish:** honour collect column order (or an explicit
`category_orders` / categorical dtype) by default for summary `facet_row="variable"`,
so averaged and per-cell figures stay consistent without every app re-passing
Plotly category orders.

## 21. 🟠 No selective summary rebuild after meta edits

Editing physical metadata (mass, active electrode area, nominal capacity,
cycle mode) requires a **full** `cell.make_summary()` — there is no public API
to rebuild only the dependent summary columns (e.g. gravimetric capacities
after mass, C-rates after nominal capacity).

Surfaced in cellpy-simple-gui #69: Manage Cells lets users change these knobs
post-load. The app assigns attributes (`cell.mass`, `cell.active_electrode_area`,
`cell.nominal_capacity`, `cell.cycle_mode`) and always remakes the whole
summary. That is correct but opaque and potentially expensive for large cells.

There is also no documented **meta → summary-column dependency graph**
(which parameters invalidate which columns), so app builders cannot do
targeted updates or warn users precisely.

**Wish:** either (a) cheap selective refresh helpers keyed by meta field, or
(b) a small dependency map / docs (“`nominal_capacity` affects …”) so GUIs can
scope rebuilds and UX messaging. Dedicated setters (vs bare attribute assign)
would also help discoverability.

**Resolved in 2.1.2a4:** `CellpyCell.refresh_after(fields=[...])` recomputes only
the meta-dependent (scaled / equivalent-cycle) columns and falls back to a full
`make_summary()` when there is no summary yet. `apply_physical_meta` uses it.

---

## Round 3 — configuration (all resolved in 2.1.2a3)

cellpy 2.1.2 replaced `parameters.prms` with a layered pydantic-settings stack —
defaults → user `cellpy.toml` → project `cellpy.toml` → env → runtime, with
per-key provenance via `config.sources()`. That is a large improvement for app
builders: it is the first time an app could *show* a user where a setting came
from. These were the rough edges found while wiring that into a settings panel.

### 22. 🔴 `model_dump_for_file()` wrote credentials in plaintext

The dump documented as "secrets excluded" dropped the `[secrets]` section but
let a legacy `instruments.Arbin.SQL_PWD` through, because the instrument models
are `extra="allow"`. Worse, the asymmetry: a hand-written `[secrets]` block was
correctly *rejected* on load, while the same credential under `[instruments]`
was written **and** silently accepted. A "Save settings" button would have
written a migrating user's database password into `%LOCALAPPDATA%`.

**Upstream:** [#849](https://github.com/jepegit/cellpy/issues/849) — fixed in 2.1.2a3.

### 23. 🔴 `config.override()` was process-global

It reads as a scoped context manager but mutated a module-level stack, so in a
thread pool two workers saw each other's values *inside their own blocks*. For a
GUI running work off the request thread that is silent wrong-numbers, not a
crash — the worse failure mode.

**Upstream:** [#850](https://github.com/jepegit/cellpy/issues/850) — fixed in
2.1.2a3 with `contextvars`. The app still switches config on the request thread,
because a *project* switch should be process-global by design.

### 24. 🟠 Reporting disagreed with the loader about the active config

`cellpy info` / `edit config` re-derived `~/.cellpy_prms_<user>.conf` instead of
asking the loader, so after `cellpy setup migrate` they named and validated a
file that no longer had any effect.

**Upstream:** [#851](https://github.com/jepegit/cellpy/issues/851) — fixed in
2.1.2a3 by `config.loader.active_config_file()`, which also reports a legacy
`.conf` *shadowed* by a `cellpy.toml`. The app's config panel uses it, and shows
the shadowed file as ignored — a real source of "I edited the config and nothing
happened".

---

## Round 4 — DVA and raw data

### 25. 🟠 `dva_plot(direction="both")` drew both half-cycles identically

Same colour, same trace name, no dash — only the hover told them apart, so on a
static export (PNG/SVG/PDF for a report) the information was simply gone.
`ica_plotter` had already gained `line_dash` for exactly this in #821.

**Upstream:** [#862](https://github.com/jepegit/cellpy/issues/862) — fixed in 2.1.2a4.

### 26. 🟠 No `collect_dva`

`collect_summaries`, `collect_cycles` and `collect_ica` all existed; DVA had no
collector, so it was the one analysis family that could not be compared across
cells. Apps had to special-case it onto the single-cell `dva_plot`, with its own
pandas (not polars) export path.

**Upstream:** [#863](https://github.com/jepegit/cellpy/issues/863) — fixed in
2.1.2a4. The app's DVA view moved onto the shared collection path and the
special case disappeared.

### 27. 🟠 `raw_plot` has no way to limit points *(fixed in 2.1.2)*

`prepare_raw` copies the whole raw frame — no cycle filter, no thinning — so a
single 155k-row demo cell produces **7 MiB** (`voltage-current`) to **18 MiB**
(`full`) of figure JSON. Every other family is bounded, by cycle or by cycle
selection; raw is unbounded by construction. Not something a browser canvas can
take.

**Workaround (app):** thin the traces after the fact — every Nth point, ~4000 per
trace, which takes `full` from 18.5 MiB to 482 KiB (2.6%) with the curve shape
intact — and annotate the chart so a thinned plot is never passed off as
complete.

**Wish:** `max_points=` (ideally min/max per bucket, which preserves spikes that
striding drops) or the `cycles=` bound the other families already have, applied
before the frame is copied.

**Upstream:** [#867](https://github.com/jepegit/cellpy/issues/867) — fixed in
2.1.2. `raw_plot` gained **both** `max_points` and `cycles`. Measured on the
demo cell: 7.35 MiB → 0.18 MiB at `max_points=4000`. `_thin_traces` and its
striding are gone.

One thing the app kept: `raw_plot` downsamples silently, so the app still reads
the drawn point count off the figure and labels the chart *"showing 1,882 of
155,754 points"*. Reading it back rather than assuming a stride means the note
stays true whatever algorithm cellpy picks. A `fig` annotation upstream would
retire that too.

---

### 28. 🔴 Seven registered families cannot be collected at all *(fixed in 2.1.2)*

Building a plot menu from `registry.families()` gives 25 entries. On the demo
cell only **8** have all their columns with default collect options. Digging in:

| collect options | families satisfied |
|---|---|
| defaults | 8 / 25 |
| `SummaryOptions(partition_by_cv=True)` | 12 / 25 |
| + the family's own `transforms` | **`TypeError`** |

Two separate problems.

**The CV families are reachable but undiscoverable.** `*_cv` / `*_non_cv` are
produced by the *collector* (`partition_by_cv=True`), not by the cell summary.
Nothing on the family says so, so a caller enumerating the registry has to know
out of band which families need which options. (This half was our bug — the app
now knows to ask; tracked as cellpy-simple-gui#106.)

**The full-cell families are unreachable, full stop.** `PlotFamily.transforms()`
returns a nested mapping `{output: {(cycle, source): fn}}`, while
`SummaryOptions.transforms` is applied as `frame = transform(frame)` — callables.
Feeding one to the other raises `TypeError: 'dict' object is not callable`, so
the `mod_01_*` column the family needs can never be produced, and all seven
`fullcell_standard_*` entries are dead.

For an app this is the worst of the failure modes in this document, because it
surfaces to the *user* as "your data is missing columns" when the truth is the
app was never able to ask for them.

**Wish:** make the registry self-describing — `family.summary_options(hdr)`
returning a ready `SummaryOptions` (CV flag set where needed, transforms in the
shape the collector accepts), so `collect_summaries(batch,
options=family.summary_options(hdr))` just works.

**Upstream:** [#868](https://github.com/jepegit/cellpy/issues/868) — fixed in
2.1.2, and the wish was granted literally. `PlotFamily` now carries:

| API | What it gives an app |
|---|---|
| `family.summary_options(hdr)` | a ready `SummaryOptions` — CV flag, transforms, column list |
| `family.supports_cv_split` / `.supports_formation` | declarative capability flags |
| `families(entry_point="summary_plot")` | which families belong in *this* menu |

`SummaryOptions.transforms` is now a tuple of callables, matching how collect
applies them, so the `mod_01_*` columns get built and all seven
`fullcell_standard_*` families collect.

**What the app deleted.** The whole idea of the app knowing which families need
which options. Availability now compares `summary_options().columns` — what a
family *asks the summary for* — against the loaded data, instead of
`family.columns()`, which names the derived columns collect has not built yet.
That distinction was the entire bug: **8 of 25 families selectable → 15 of 20**,
each verified to render real traces rather than merely be selectable.

The `entry_point` filter fixed a second thing quietly: `raw`, `ica`, `dva`,
`cycle_info` and `cycles` were being listed in the *summary* menu, where they
could never work — they have their own tabs.

Five `*_absolute` families are still unavailable on the demo cells, and that
report is now truthful: `charge_capacity_absolute` is written by
`make_summary()` on current cellpy, and those saved files predate it. "Your data
lacks these columns" is the right message, which it was not before.

---

### 29. 🟠 An unknown `layout=` is accepted silently *(open)*

Found while adding dQ/dV and dV/dQ to the multi-cell Cycles pane (#95).

`film` reads like a layout — it sits in `_METHOD_TO_LAYOUT` next to
`fig_pr_cell` / `fig_pr_cycle`, and `Collection.plot`'s docstring mentions only
`layout=` for the cycles/ICA path. It is actually a **kind**. Passing it as a
layout falls through `_LAYOUT_TO_METHOD.get(layout, "fig_pr_cell")` to the line
renderer:

```python
>>> resolve_collected_layout_kind(layout="film")
('film', 'line', 'fig_pr_cell')      # kind='line' — draws lines
>>> resolve_collected_layout_kind(layout="totally_bogus")
('totally_bogus', 'line', 'fig_pr_cell')   # no error, no warning
>>> resolve_collected_layout_kind(kind="film")
('per_cell', 'film', 'film')         # the intended histogram2d
```

The trap is that the wrong call **produces a perfectly plausible figure** —
identical `scattergl` traces to `per_cell`. Nothing suggests it is wrong, so it
ships. That is worse than a traceback.

**Workaround (app):** `collect.curve_layout_kwargs()` translates the app's
`film` layout into `kind="film", layout="per_cell"`, with a test asserting the
result is `histogram2d` and not lines.

**Wish:** validate unknown `layout` / `kind` (`totally_bogus` reaching the
renderer is a bug on its own), or accept `layout="film"` as an alias — and
document `kind=` in `Collection.plot`, where it is currently absent.

**Upstream:** [#874](https://github.com/jepegit/cellpy/issues/874) — open.

---

### 30. 🟠 `spread_plot` traces carry no hover at all *(open)*

Found while chasing [cellpy-simple-gui#40](https://github.com/cellpy/cellpy-simple-gui/issues/40).

Same collection, same columns, three renderings:

| mode | `hovertemplate` on the first trace |
|---|---|
| per-cell | `cellpy<br>group=1<br>sub_group=1<br>variable=…<br>Cycle (n.)=%{x}<br>value=%{y}` |
| `group_it=True` | `group=1<br>variable=…<br>Cycle (n.)=%{x}<br>mean=%{y}` |
| `group_it=True, spread=True` | **`None`** — on all 18 traces, mean lines included |

`summary_plotter` goes through plotly.express, which attaches hover from the
frame. `spread_plot` builds traces directly with `go.Scatter` and never sets
one.

Spread is exactly where hover matters most: the band hides the individual
cells, so the tooltip is the only way to read a value. A user ticking one
checkbox loses group, variable, cycle and value at the moment they most need
them. The **Upper Bound / Lower Bound** traces are also hoverable, and they are
construction artefacts — a tooltip on one reads like a measurement nobody took.

**Workaround (app):** `_add_spread_hover()` rebuilds it after the fact — group
from the mean trace's name, variable from the y-axis title the user is already
reading, `± std` derived from the upper-bound trace, and `hoverinfo="skip"` on
the bounds. It works, but it leans on trace naming (`"Upper Bound <group>"`) and
emission order (mean, upper, lower), which are internal details.

**Upstream:** [#875](https://github.com/jepegit/cellpy/issues/875) — open.

---

## Round 6 — deploying cellpy headless

Found while building the server container
([#121](https://github.com/cellpy/cellpy-simple-gui/issues/121)). These are not
API problems; they are what shows up the first time cellpy has to run somewhere
that is not a workstation.

### 31. 🟠 Missing external tools fail quietly enough to look like success *(open)*

Two of them, and the second is the reason this section exists at all.

**`mdb-export`.** On posix, `arbin_res` shells out to mdbtools. Without it:

```
[Errno 2] No such file or directory: 'mdb-export'
```

Our smoke test asserted the import job reached `status: "done"`. It did. It also
imported **zero cells** — the failure lives in the result payload, not the
status. The test passed for a whole build cycle while the feature was broken:

```json
{"added": [], "errors": ["Arbin demo (.res): [Errno 2] No such file or directory: 'mdb-export'"]}
```

That is our test's fault, not cellpy's. But a bare `FileNotFoundError` naming a
binary nobody has heard of is what made it easy to skim past.

**`libodbc.so.2`.** `arbin_sql` and `arbin_sql_7` raise `ImportError` during
discovery, so the app enumerated **11 instruments instead of 13** with nothing
logged that a user would see. The picker simply did not offer them.

**Workaround (app):** `apt install mdbtools unixodbc` in the image, and the
smoke test now asserts on `added` / `errors` rather than on job status.

**Wish:** a named, actionable error for a missing external tool
(`shutil.which` before the call would do it), and discovery that reports
*unavailable* loaders with a reason instead of omitting them — the shape
`registry.families()` already uses so well for plots (§ round 5) would suit
instruments too. Then an app can grey an entry out with a tooltip instead of
silently narrowing the list.

**Upstream:** [#938](https://github.com/jepegit/cellpy/issues/938) — open.

### 32. 🟢 Notebook tooling is a hard runtime dependency *(open)*

Traced with `importlib.metadata`, not guessed:

```
matplotlib   <- cellpy
ipykernel    <- cellpy
ipython      <- ipykernel        jedi <- ipython        debugpy <- ipykernel
```

In a headless server image that is ~90 MB of `matplotlib` + `jedi` + `debugpy`
(plus `ipython`, `pyzmq`, `tornado`, `fontTools` behind them) that no code path
reaches. The app plots with plotly and never opens a notebook. `debugpy` in a
server image is also not something a deployer would pick.

**Wish:** `cellpy[notebook]` and `cellpy[plotting-mpl]` extras, with local
imports where they are used. Notebook users — surely the majority — would notice
nothing.

**Upstream:** [#937](https://github.com/jepegit/cellpy/issues/937) — open.

### 33. 🟢 `examplesdir` is resolved at import time, and falls back into site-packages

`example_data.DATA_PATH` is computed when the module is imported: if
`config.paths.examplesdir` is not an existing directory, it falls back to
`site-packages/cellpy/utils/data`. In a container that path is root-owned and
the app runs as uid 10001, so the zero-setup demo fails on a permission error at
the moment a new user clicks the friendliest button in the product.

Setting `CELLPY_PATHS__EXAMPLESDIR` is not enough on its own — the directory has
to **exist** before cellpy is imported, or the override is silently discarded
with a `warnings.warn`.

**Workaround (app):** the image creates the directory at build time and
pre-downloads the demo cells into it, which also makes the demo work offline.

**Wish:** create the directory rather than falling back, or at least keep the
override and fail at *use* time with a message naming it. A config value that is
accepted and then ignored is hard to debug from the outside.

Not filed separately — folded into the discussion on
[#938](https://github.com/jepegit/cellpy/issues/938).

---

## What already works well (thank-you notes)

- `cellpy.get(...)` as a single entry point, with unit-string args
  (`mass="1.14 mg"`) — lovely.
- `collect_summaries` / `collect_cycles` fixing the cross-cell cycle-narrowing bug
  by per-cell isolation (`collect/cells.py`) — exactly the kind of correctness win
  an app can't easily do itself.
- `cellpy.utils.example_data` — made a zero-setup demo trivial.
- Arbin `.res` loading working on Windows via the Access ODBC driver with no
  mdbtools — pleasant surprise.
- The curated plot `families` registry — a great vocabulary for a plot-type menu.
- `instrument_configurations()` exists at all — discovery was possible; it just
  needs a quieter, app-facing wrapper (see #5).

Added after the later rounds:

- The **2.1.2 config stack** is the single biggest app-facing improvement here.
  Layered sources with per-key provenance (`config.sources()`) let an app *show*
  a user which file a setting came from — most libraries make that unknowable.
  `active_config_file()` reporting a shadowed legacy `.conf` is a small touch
  that removes a whole category of confusion.
- **`from_cells` / `collect_*` / the family registry together** turned out to be
  the right shape: the app builds a Collection and lets cellpy plot it, so
  grouping, spread, per-cell cycle isolation and multi-format export all stay
  consistent with cellpy instead of drifting.
- **Fix turnaround.** Every issue in rounds 2–5 was closed quickly, which is what
  made it possible to keep *deleting* workarounds rather than accumulating them.
  `core/collect.py` is substantially shorter than at 2.1.1, and nearly all of the
  difference is logic upstream now owns.
- **The self-describing registry** (2.1.2, #868) is the best example of a fix
  landing *better* than the request. Asking for one accessor produced
  `summary_options()`, capability flags and `entry_point` tagging — and the app
  answered a question it had previously been guessing at. A registry that only
  names things makes every consumer reimplement the same lookup table; one that
  describes how to satisfy itself makes that table unnecessary.

*Started while building [cellpy-simple-gui](./README.md) on cellpy 2.1.0.post1;
kept up to date through 2.1.2. 29 issues filed from this project, 25 closed.*
