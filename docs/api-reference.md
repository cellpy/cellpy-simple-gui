# cellpy API surface

The calls that matter when building on cellpy, with real signatures and
one line each of what a signature cannot tell you — so you do not have to
grep `site-packages` to find out that `family.summary_options(hdr)` exists.

Generated from the installed **cellpy 2.1.2** by
[`tools/gen_api_reference.py`](../tools/gen_api_reference.py); do not edit by
hand. The prose is curated, the signatures are introspected, and
`tests/test_api_reference.py` fails if this file drifts from the installed
package.

For worked examples see [`docs/guides/`](guides/README.md); for a running
app in one file see [`examples/starter/`](../examples/starter/).

## Loading

Getting cells into memory — [guide 1](guides/01-loading-cells.md).

```python
cellpy.get(filename=None, instrument=None, instrument_file=None, cellpy_file=None, cycle_mode=None, mass: Union[str, numbers.Number] = None, nominal_capacity: Union[str, numbers.Number] = None, nom_cap_specifics=None, loading=None, area: Union[str, numbers.Number] = None, estimate_area=True, logging_mode=None, custom_log_dir=None, custom_log_config_path=None, auto_pick_cellpy_format=True, auto_summary=True, units=None, step_kwargs=None, summary_kwargs=None, selector=None, testing=False, refuse_copying=False, initialize=False, debug=False, **kwargs)
```
The one entry point. Only `filename` is required; `mass` / `area` / `nominal_capacity` accept unit strings such as `"0.47 mg"`.

```python
cellpy.list_instruments() -> List[Dict[str, Any]]
```
Loaders registered at runtime: `{id, label, models, suffixes}`. Registered is not the same as usable on this machine.

```python
cellpy.read_meta(path)
```
Metadata without loading the data — **cellpy files only**; a raw file gives an HDF5 traceback.

```python
cellpy.instrument_meta_schema(instrument: Optional[str] = None) -> Dict[str, Any]
```
Fields an instrument wants (`name`, `required`, `type`, `unit`, `maps_to`, `help`) — enough to generate an ingestion form.

```python
cellpy.utils.example_data.cellpy_file(testing: bool = False) -> cellpy.readers.cellreader.CellpyCell
```
A loaded demo cell (304 cycles). Downloads once, then caches.

```python
cellpy.utils.example_data.cellpy_file_path() -> pathlib._local.Path
```
Path to the same file, for when you want to call `cellpy.get` yourself.

```python
cellpy.utils.example_data.rate_file()
```
**A path, not a cell** — unlike `cellpy_file()`. Passing it where a cell is expected fails silently.

```python
cellpy.utils.example_data.neware_file_path() -> pathlib._local.Path
```
A raw Neware export (`.csv`) that loads with no external tooling.

```python
cellpy.utils.example_data.arbin_file_path() -> pathlib._local.Path
```
A raw Arbin `.res` — needs mdbtools or the Access driver to load.

## One cell

`CellpyCell` — what you get back from `cellpy.get`.

```python
CellpyCell.get_cycle_numbers(steptable=None, rate=None, rate_on=None, rate_std=None, rate_agg='first', inverse=False)
```
The cycle numbers present, optionally filtered by rate.

```python
CellpyCell.get_cap(cycle=None, cycles=None, method='back-and-forth', insert_nan=None, shift=0.0, categorical_column=False, label_cycle_number=False, split=False, interpolated=False, dx=0.1, number_of_points=None, ignore_errors=True, inter_cycle_shift=True, interpolate_along_cap=False, capacity_then_voltage=False, mode='gravimetric', mass=None, area=None, volume=None, cycle_mode=None, usteps=None, dynamic=False, **kwargs)
```
Capacity/voltage curve for one cycle or several, as **pandas**.

```python
CellpyCell.save(filename, force=False, overwrite=None, extension='cellpy', ensure_step_table=None, ensure_summary_table=None, cellpy_file_format=None)
```
Write a `.cellpy` file. Atomic since 2.1.2a4 — staged write plus `os.replace`.

```python
CellpyCell.to_csv(datadir=None, sep=None, cycles=False, raw=True, summary=True, shifted=False, method=None, shift=0.0, last_cycle=None)
```
Write raw / steps / summary as separate CSVs into a directory.

```python
CellpyCell.to_excel(filename=None, cycles=None, raw=False, steps=True, nice=True, get_cap_kwargs=None, to_excel_kwargs=None)
```
Write one workbook.

```python
CellpyCell.refresh_after(fields=None, **kwargs)
```
Rebuild only what a metadata edit invalidated, instead of a full `make_summary()`.

## Cells into a Collection

The bridge and the four collectors — [guide 2](guides/02-collections.md).

```python
cellpy.collect.from_cells(cells, **kwargs) -> 'Batch'
```
**The call that matters.** Turns `{label: CellpyCell}` into a real `Batch` with no journal on disk. Values that are not cells are dropped silently — validate first.

```python
cellpy.collect.collect_summaries(batch: 'Any', options: 'SummaryOptions | None' = None, **overrides) -> 'Collection'
```
Per-cycle summary values across cells. `group_it=True` averages within groups **and changes the frame's schema**.

```python
cellpy.collect.collect_cycles(batch: 'Any', options: 'CurveOptions | None' = None, **overrides) -> 'Collection'
```
Voltage/capacity curves for chosen cycles, isolated per cell.

```python
cellpy.collect.collect_ica(batch: 'Any', options: 'IcaOptions | None' = None, **overrides) -> 'Collection'
```
dQ/dV. Keeps both half-cycles in a `direction` column.

```python
cellpy.collect.collect_dva(batch: 'Any', options: 'IcaOptions | None' = None, **overrides) -> 'Collection'
```
dV/dQ. Same shape as `collect_ica` (2.1.2a4).

```python
cellpy.collect.load_collection(path: 'Path | str') -> 'Collection'
```
Read a saved collection back.

## Collect options

Dataclasses passed as `options=`; `.replace(...)` returns a modified copy.

```python
cellpy.collect.options.SummaryOptions(columns, max_cycle, remove_last, only_selected, rate, rate_on, rate_std, rate_column, rate_inverse, rate_inverted, partition_by_cv, normalize_cycles, group_it, average_method, custom_group_labels, replace_inf_with_nan, replace_extremes_with_nan, low_limit, high_limit, transforms)
```
For `collect_summaries`. Usually obtained from `family.summary_options(hdr)` rather than built by hand.

```python
cellpy.collect.options.CurveOptions(cycles, rate, rate_on, rate_std, inverse, mode, method, transforms)
```
For `collect_cycles` — `cycles`, plus `mode` and `method` so you need not slice afterwards.

```python
cellpy.collect.options.IcaOptions(cycles, voltage_resolution, capacity_resolution, transforms)
```
For `collect_ica` / `collect_dva` — `cycles` and the resolutions.

## The Collection

A polars frame that knows how to draw itself — [guides 3](guides/03-plotting.md) and [4](guides/04-exporting.md).

```python
Collection.plot(*, family_kind: 'str | None' = None, **kwargs)
```
Returns a real plotly `Figure`. Takes `layout_updates`, `height_per_panel`, `spread`, `layout` **and `kind`**.

```python
Collection.save(directory: 'Path | str | None' = None, formats: 'tuple[str, ...]' = ('parquet', 'csv')) -> 'list[Path]'
```
Write the frame; defaults to parquet + csv, and adds a `.meta.json` sidecar.

```python
Collection.to_image(fmt: 'str' = 'png', *, scale: 'float' = 1.0, **plot_kwargs) -> 'bytes'
```
Collection straight to image bytes.

```python
Collection.to_wide(values: 'str', index: 'str' = 'cycle_num', columns: 'str' = 'cell') -> 'pl.DataFrame'
```
One column per cell, for a spreadsheet.

```python
Collection.is_grouped  ->  property
```
Whether these are averaged series. Decides which schema `.data` has, and whether `spread=True` means anything.

## The plot registry

Build a menu instead of maintaining one — [guide 3](guides/03-plotting.md).

```python
cellpy.plotting.registry.families(*, entry_point: 'Optional[str]' = None) -> 'list[tuple[str, str]]'
```
`[(name, description)]`. **Pass `entry_point="summary_plot"`** or you list families that can never work in a summary menu.

```python
cellpy.plotting.registry.get(name: 'str') -> 'PlotFamily'
```
One `PlotFamily` by name.

```python
PlotFamily.summary_options(hdr: 'Any', *, norm_factor: 'Optional[float]' = None) -> 'Any'
```
**The accessor that matters.** A ready `SummaryOptions` — columns, CV flag, transforms. Judge availability on `.columns` of *this*.

```python
PlotFamily.columns(hdr: 'Any') -> 'list[str]'
```
The columns the family *draws*, including ones collect manufactures. Not an availability check.

## Single-cell plots

Outside the collect path; these take a cell.

```python
cellpy.utils.plotutils.raw_plot(cell, y=None, y_label=None, x=None, x_label=None, title=None, backend: Optional[str] = None, plot_type='voltage-current', double_y=True, cycles=None, max_points: Optional[int] = None, **kwargs)
```
Raw traces. **Set `max_points`** — one demo cell is 7.35 MiB of figure JSON without it, 0.18 MiB with.

```python
cellpy.utils.plotutils.cycle_info_plot(cell, cycle=None, get_axes=False, backend: Optional[str] = None, t_unit='hours', v_unit='V', i_unit='mA', **kwargs)
```
Raw traces annotated with step/cycle info. **Needs `get_axes=True`** or it returns `None` on the plotly backend.

```python
cellpy.utils.plotutils.dva_plot(cell, cycles=None, direction='both', options=None, *, backend: Optional[str] = None, title=None, colormap='viridis', width=800, height=600, figsize=(6, 4), x_range=None, y_range=None, plotly_template=None, return_data=False, **kwargs)
```
Single-cell dV/dQ. Prefer `collect_dva` unless you specifically want one cell.

## Figures to bytes

In-process encoding, no temp file — [guide 4](guides/04-exporting.md).

```python
cellpy.plotting.figures.write_image(figure, fmt: 'str' = 'png', *, scale: 'float' = 1.0, **kwargs) -> 'bytes'
```
plotly figure to image bytes. Raises if kaleido is missing **or** if kaleido cannot find a browser — different problems, different advice.

```python
cellpy.plotting.figures.image_media_type(fmt: 'str') -> 'str'
```
MIME type for a format, for an HTTP response.

## Configuration

The 2.1.2 layered stack — [guide 5](guides/05-configuration.md).

```python
cellpy.config.get_config() -> 'CellpyConfig'
```
The resolved settings: `paths`, `reader`, `units`, `instruments`, `db`, `secrets`, …

```python
cellpy.config.sources() -> 'dict[str, str]'
```
`{"section.field": layer}` — per-key provenance. This is how you answer "where did this value come from?"

```python
cellpy.config.active_config_file(options: 'LoadOptions | None' = None) -> 'ActiveConfigFile'
```
Which file the loader actually used, including a legacy `.conf` shadowed by a `cellpy.toml`.

```python
cellpy.config.override(**sections: 'Any') -> 'Iterator[CellpyConfig]'
```
Scoped overrides, isolated **per thread and per asyncio task** (contextvars), stacking LIFO.

```python
cellpy.config.reload(overrides: 'dict[str, Any] | None' = None, *, options: 'LoadOptions | None' = None) -> 'CellpyConfig'
```
Re-resolve everything. **Process-global** — use it when you mean process-wide.

```python
cellpy.config.LoadOptions(user_config_file, project_config_file, env_file, cwd, skip_files, skip_env, legacy_yaml_file)
```
Where to load config from; `project_config_file` is how you pin a project's settings.

## Attributes worth knowing

| | Type | |
|---|---|---|
| `cell.data.summary` | pandas | per-cycle values — the source of every summary column name |
| `cell.data.raw` | pandas | the raw measurement frame |
| `cell.data.steps` | pandas | the step table |
| `cell.schema.summary` | `CycleCols` | the summary column vocabulary — this is the `hdr` argument the registry wants |
| `cell.cell_name / .mass / .nominal_capacity / .active_electrode_area` |  | cell metadata |
| `collection.data` | polars | the numbers behind the figure |

The frames on a **cell** are pandas; the frame on a **collection** is
polars. Cross the boundary explicitly with `.to_pandas()`, at the edge of
your code rather than in the middle of it.
