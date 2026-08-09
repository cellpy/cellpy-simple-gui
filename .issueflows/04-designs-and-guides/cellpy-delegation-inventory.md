# cellpy delegation inventory (issue #52)

Against **cellpy 2.1.2** (post7 → 2.1.2a2 → a3 → a4 → 2.1.2). Goal: prefer cellpy
APIs; keep only app chrome that cellpy still does not own.

As of 2.1.2 every issue from the first four rounds is closed. One workaround
remains, and it is newer than the upgrade: the `film` layout translation
([#874](https://github.com/jepegit/cellpy/issues/874)).

## Release-gating note (resolved for #816/#818/#819)

`#816`, `#818`, `#819` shipped in **cellpy 2.1.2a2** (PyPI, 2026-08-08) and
their app workarounds were **removed** in the 2.1.2a2 cleanup pass:

- **#816** — cellpy now averages multi-member groups even when a singleton
  group is present, returning both in **one** collection (verified
  empirically). The app's partition/merge (`summary_collections`,
  `figures_json`, `combined_summary_frame`, `partition_by_group_size`) and the
  `#47` `_apply_share_y` / `_want_share_y` re-link are **gone**; summary
  plotting/export now go straight through `summary_collection` + `figure_json`
  / `export_bytes`. share_y / match_axes are honoured natively on both the
  grouped and grouped+spread paths.
- **#818** — `cellpy.plotting.figures.write_image(fig, fmt, scale=) -> bytes`
  (in-process `to_image`, no temp files/subprocess) plus `image_media_type()`.
  `export.figure_bytes` now delegates to these instead of `fig.write_image`.
- **#819** — a set `instrument=` wins over `.h5`/`.hdf5` suffix auto-pick, so
  `load_raw` no longer forces `auto_pick_cellpy_format=False`.

`#817`, `#820`, `#821` landed earlier (post7). Still open/deferred: the `#821`
ICA `direction` delegation (drop `_filter_ica_by_direction`) is a **follow-up**
— it changes export semantics and wants a "Both" UI option, so it was kept out
of the 2.1.2a2 cleanup.

| Area | Upstream | In 2.1.2a2? | Decision |
|------|----------|-------------|----------|
| `list_instruments` WARNING spam | #786 (post3) | yes | **Delegated** — no root-log silencing |
| Collected figure theme / labels / height | #801 (post4) | yes | **Delegated (partial)** — `_inject_app_chrome`; `_restyle` keeps legend truncation, colorway, grids |
| Unit-bearing y-labels | #801 defaults names-only | yes | **Keep forwarding** `y_label_mapper` (#38 / §18 open) |
| `read_meta(path)` | #799 (post4) | yes | **Wrapper** `read_file_meta` (UI wiring deferred) |
| `instrument_meta_schema` | #800 (post4) | yes | **Wrapper** (ingest form follow-up) |
| `spread_plot` share_y | #817 | yes | **Delegated** — cellpy honours share_y/match_axes on grouped + grouped+spread; `_apply_share_y` removed |
| Cycles facet strip labels | #820 | yes | **Delegated** — clean strips for free, no app code |
| Group-avg all-or-nothing + merge | #816 | **yes (2.1.2a2)** | **Removed** — one collection averages groups + keeps singletons; partition/merge deleted |
| Static figure bytes (kaleido) | #818 | **yes (2.1.2a2)** | **Delegated** — `figure_bytes` → `figures.write_image` + `image_media_type` |
| `.h5` `auto_pick_cellpy_format` | #819 | **yes (2.1.2a2)** | **Removed** — set `instrument=` wins over suffix; no forced `auto_pick=False` |
| ICA `direction` (line + both) | #821 | yes | **Delegated** — `ica_plotter` selects the half-cycle (charge/discharge/both); app `_filter_ica_by_direction` removed. Export mirrors the chart via `select_ica_direction`; UI has a "Both" option |
| Summary facet `category_orders` | §20 open, unfiled | n/a | **Keep forwarding** (#81) |
| Cycles plot `x_unit` vs collect mode | §17 open, unfiled | n/a | **Keep forwarding** (#72) |
| Non-atomic `.cellpy` writes | #845 ✅ 2.1.2a4 | yes | **Delegated** — cellpy writes atomically (`cellpy_file/atomic.py`). App keeps project-folder staging: that covers a wider unit (many cells + manifest) |
| Selective summary rebuild | #846 ✅ 2.1.2a4 | yes | **Delegated** — `apply_physical_meta` calls `CellpyCell.refresh_after(fields=…)` instead of a full `make_summary()` |

## Removed in the 2.1.2a2 cleanup

- **#816** — deleted `partition_by_group_size`, `summary_collections`,
  `figures_json`, `combined_summary_frame`, `_remap_trace_axes`; `summary_figure`
  / `summary_export` now use `summary_collection` + `figure_json` / `export_bytes`.
- **#817/#47** — deleted `_apply_share_y` / `_want_share_y`; `figure_json` now
  applies per-facet `y_ranges` directly and lets cellpy own axis matching.
- **#818** — `export.figure_bytes` delegates to `cellpy.plotting.figures`.
- **#819** — `load_raw` drops the forced `auto_pick_cellpy_format=False`.
- **#821 ICA** — deleted `_filter_ica_by_direction`; `ica_collection` returns
  both half-cycles and `ica_figure` passes `direction` to cellpy's `ica_plotter`
  (charge / discharge / **both** overlay). Export uses `select_ica_direction` so
  the exported rows match the chart. UI gained a "Both" option.

## Configuration (`cellpy.config`, new in 2.1.2)

cellpy 2.1.2 replaced `parameters.prms` with a layered pydantic-settings stack:
**defaults → user `cellpy.toml` → project `cellpy.toml` → env (`CELLPY_<SECTION>__<FIELD>`)
→ runtime**, with per-key provenance via `config.sources()`.

| Area | Decision |
|------|----------|
| Reading resolved settings | **Delegated** — `core/cellpy_config.diagnostics()` wraps `get_config()` + `sources()` |
| Which file actually won | **Delegated** — `config.loader.active_config_file()` (#851/#852), incl. a legacy `.conf` shadowed by a `cellpy.toml` |
| Showing where a value came from | **Delegated** — provenance layer badges in the config panel |
| Writing cellpy's **user** config | **Never** — that file is shared with the user's notebooks/CLI; only `cellpy setup` writes it |
| Reading a **project** `cellpy.toml` | **Delegated** — `activate_project_config()` pins it via `LoadOptions(project_config_file=…)` on project open |
| Writing a **project** `cellpy.toml` | **Done** — `pin_project_config()` writes `reader`/`units`/`defaults` only |
| Credentials | **Never surfaced** — `secrets` skipped; credential-ish instrument keys masked. **Kept even though #857 landed**: that fix cleans up *dumps*, but a legacy `SQL_PWD` can still sit in the in-memory config, and masking in a UI is right regardless |
| Per-job overrides | **Available but unused** — `override()` is thread-safe as of #858. The app still switches config on the request thread, because a *project* switch should be process-global, not per-thread |

### Resolved in 2.1.2a3

Three config fixes we depend on shipped in **2.1.2a3**, each verified against the
installed package rather than taken on trust (the #816/#818/#819 pass taught us
that closed ≠ released):

| Issue | Fix | Verified in 2.1.2a3 |
|-------|-----|---------------------|
| [#849](https://github.com/jepegit/cellpy/issues/849) `model_dump_for_file()` wrote a legacy `instruments.Arbin.SQL_PWD` in plaintext | `1977e64e` (#857) | ✅ dump no longer carries `SQL_PWD`/`SQL_UID` |
| [#850](https://github.com/jepegit/cellpy/issues/850) `config.override()` was process-global | `da9ccc8d` (#858, contextvars) | ✅ two pool workers each see their own value |
| [#851](https://github.com/jepegit/cellpy/issues/851) reporting disagreed with the loader about which file wins | `7d432004` (#852) | ✅ `active_config_file()` present and adopted |

**Pinning settings to a project** writes only `reader` / `units` / `defaults`
(`PINNED_SECTIONS`). That allow-list is the point: `paths` would bake this
machine's layout into a portable project, and omitting `instruments`/`db` means
the written file *structurally* cannot contain a credential — independent of
cellpy's own dump scrubbing.

## Incremental analysis (ICA / DVA)

| Area | Decision |
|------|----------|
| ICA collection + `direction` | **Delegated** — `collect_ica` + `ica_plotter` (#821) |
| DVA collection | **Delegated** — `collect_dva` (#863, new in 2.1.2a4). Before that DVA was single-cell only and the app drove `dva_plot` directly |
| DVA `both` half-cycle marking | **Delegated** — cellpy labels `"<cycle>, charge/discharge"` and dashes them (#862, 2.1.2a4). App-side marking **removed** |
| Export direction | **App-owned** — `select_ica_direction` slices exported rows to match the chart; shared by ICA and DVA |

Both were filed while building the DVA view and shipped in **2.1.2a4**, verified
against the installed package:

- **[#862](https://github.com/jepegit/cellpy/issues/862)** — `dva_plot(direction="both")`
  drew both half-cycles identically (same colour, same name, no dash), so a static
  export read as one doubled-back curve. Now solid/dot.
- **[#863](https://github.com/jepegit/cellpy/issues/863)** — there was no `collect_dva`,
  making DVA the only family that could not span cells. `collect_dva(batch, options)`
  now returns a `Collection` like its siblings, so the app's DVA view moved onto the
  shared path: multi-cell capable, polars export, app chrome via `figure_json`, and
  the pandas→polars conversion is gone.

## Raw data views (developer mode)

| Area | Decision |
|------|----------|
| Raw traces | **Delegated** — `plotutils.raw_plot(cell, plot_type=…)` |
| Step/cycle annotations | **Delegated** — `plotutils.cycle_info_plot(cell, cycle=…)`; needs `get_axes=True` to return a *figure* on the plotly backend, otherwise it returns `None` |
| Raw payload size | **Delegated** — `raw_plot(cell, max_points=…, cycles=…)` (#867, 2.1.2). `_thin_traces` and its striding are **removed** |
| Raw downsampling notice | **App-owned** — `raw_plot` downsamples silently, so the app reads the drawn point count off the figure and annotates *"showing N of M points"* |
| Cycle-info payload size | **Not needed** — bounded by the cycle selection (one ~1.5k-point trace per cycle), so `CycleInfoPlotSpec.max_points` was dropped rather than reimplemented |
| Raw data export | **Not added** — the figure is downsampled, so exporting from it would mislead; `Export cells → csv` is the real raw source |

`raw_plot` used to be the only family cellpy did not bound: `prepare_raw` copied
the whole frame, giving **7.35 MiB** of figure JSON for one 155k-row demo cell.
2.1.2 added `max_points` (and `cycles`), taking that to **0.18 MiB**. The app
computes its annotation from the actual trace length rather than assuming a
stride, so the label stays correct whatever downsampling cellpy uses.

## Cycles pane curve kinds (#95)

| Area | Decision |
|------|----------|
| Voltage curves | **Delegated** — `collect_cycles` + `family_kind="cycles"` |
| dQ/dV, dV/dQ across many cells | **Delegated** — `collect_ica` / `collect_dva` take the whole record list, so the Cycles pane reuses the Cell-explorer collectors unchanged |
| Film (density) rendering | **Delegated** — cellpy's `kind="film"` (`histogram2d`) |
| `film` as a *layout* | **App-owned (translation)** — `curve_layout_kwargs()` maps the app's `layout="film"` to `kind="film", layout="per_cell"`. cellpy accepts an unknown `layout` silently and draws lines ([#874](https://github.com/jepegit/cellpy/issues/874)); remove this when it validates or aliases |
| Differential export | **App-owned (routing)** — `cycles_export` picks the collector matching `curve_kind` so the CSV matches the chart, then reuses `select_ica_direction` |

## Summary plot families

| Area | Decision |
|------|----------|
| Which families belong in the summary menu | **Delegated** — `registry.families(entry_point="summary_plot")` (2.1.2). Previously the app listed all 25, including `raw`/`ica`/`dva`/`cycle_info`/`cycles`, which have their own tabs |
| Collect options per family | **Delegated** — `family.summary_options(hdr)` (#868, 2.1.2) carries `partition_by_cv` and the transforms. The app layers only `group_it` / `max_cycle` on top |
| Availability check | **Delegated inputs** — compares `summary_options().columns` (what the family asks the summary for) against the loaded data, *not* `family.columns()` (what it draws, including collect-built `*_cv` and `mod_01_*`) |

This is the fix for [cellpy-simple-gui#106](https://github.com/cellpy/cellpy-simple-gui/issues/106):
judging availability on the drawn names made every CV-split and full-cell family
report "your data is missing columns" when the app had simply never asked for
them. Measured on the demo cells: **8 of 25 selectable → 15 of 20**, all
rendering real traces. The app no longer holds any table of which family needs
which option.

## Still app-owned (no upstream yet / by design)

- Discrete colorways + session figure-theme preference (#32)
- Legend truncation / right margin for long cell names
- Unit-bearing summary `y_label_mapper` (§18), cycles `x_unit` (§17),
  facet `category_orders` (§20) — all unfiled friction
- Desktop Save As + zip packaging (encode itself now delegated to cellpy #818)
- Ingest form layout (until a follow-up consumes `instrument_meta_schema`)
