# 2. Cells into a Collection

*You have `CellpyCell` objects. You want one frame you can plot and export.*

The bridge is `from_cells`, and it is the most important call in this whole set
of guides:

```python
import warnings

import cellpy
from cellpy.collect import collect_summaries, from_cells
from cellpy.utils import example_data

warnings.simplefilter("ignore")

cells = {
    "sf033": example_data.cellpy_file(),
    "rate": cellpy.get(filename=example_data.rate_file()),
}
batch = from_cells(cells)
print(type(batch).__name__)
```

```text
Batch
```

That is a **real** cellpy `Batch`, built from cells already in memory, with no
journal written to disk. It matters because everything downstream — grouping,
group averaging, spread bands, per-cell cycle isolation, multi-format export —
is written against `Batch`, so you get all of it by handing over a dict.

The alternative, assembling summary frames yourself, is the single most expensive
mistake available in this library. It looks like less work for about a day.

> Before `from_cells` ([cellpy#787](https://github.com/jepegit/cellpy/issues/787),
> 2.1.1) this app maintained a hand-rolled batch shim. Deleting it was the
> largest single simplification in the project.

## Collecting

Four collectors, one shape. Each takes the batch and an options object, and each
returns a `Collection`:

| Call | Gives you |
|---|---|
| `collect_summaries(batch, columns=…)` | per-cycle summary values — capacity, CE, IR, voltages |
| `collect_cycles(batch, options=CurveOptions(…))` | voltage/capacity curves for chosen cycles |
| `collect_ica(batch, options=IcaOptions(…))` | dQ/dV |
| `collect_dva(batch, options=IcaOptions(…))` | dV/dQ |

```python
summary = collect_summaries(
    batch,
    columns=("charge_capacity_gravimetric", "discharge_capacity_gravimetric"),
)
print(summary.data.height, "rows")
print(summary.data.columns)
```

```text
325 rows
['cell', 'group', 'sub_group', 'group_label', 'label', 'cycle_num',
 'charge_capacity_gravimetric', 'discharge_capacity_gravimetric']
```

325 = 304 cycles from one cell plus 21 from the other. The frame is **long over
cells** and wide over the columns you asked for, and it carries the identity
columns (`cell`, `group`, `label`) that the plotters use to split traces.

```python
from cellpy.collect import collect_cycles
from cellpy.collect.options import CurveOptions

curves = collect_cycles(batch, options=CurveOptions(cycles=(1, 5, 10)))
print(curves.data.columns, "·", curves.data.height, "points")
```

```text
['potential', 'capacity', 'cell', 'group', 'sub_group', 'cycle_num'] · 6916 points
```

`CurveOptions` also carries `mode` (charge / discharge) and `method`, so you do
not have to slice the frame afterwards. `IcaOptions` carries `voltage_resolution`
and `capacity_resolution` instead.

**The differential collectors use a different column vocabulary.** Worth printing
once rather than assuming:

```python
from cellpy.collect import collect_ica
from cellpy.collect.options import IcaOptions

ica = collect_ica(batch, options=IcaOptions(cycles=(1, 5)))
print(ica.data.columns)
```

```text
['cycle', 'direction', 'voltage', 'capacity', 'dqdv', 'cell', 'group', 'sub_group']
```

Note **`cycle`, not `cycle_num`** — `collect_summaries` and `collect_cycles` use
`cycle_num`, and `collect_ica` / `collect_dva` do not. Code that filters an ICA
frame by `cycle_num` after reading the section above will not find the column.
The extra `direction` column carries both half-cycles.

> **`collect_*` fixes a bug you would otherwise write.** The collectors isolate
> cycles per cell, so asking for "cycles 1, 5, 10" across cells with different
> cycle counts does not narrow every cell to the intersection. That is exactly
> the kind of correctness an app cannot cheaply get right on its own.

## What a Collection is

A small object, and that is the point:

```python
print([n for n in dir(summary) if not n.startswith("_")])
```

```text
['data', 'is_grouped', 'kind', 'meta', 'name', 'plot', 'save', 'to_image', 'to_wide']
```

- **`.data`** — a [polars](https://pola.rs) DataFrame. This is the numbers.
- **`.plot()`** — returns a plotly `Figure`. See [guide 3](03-plotting.md).
- **`.save()` / `.to_image()`** — files. See [guide 4](04-exporting.md).
- **`.is_grouped`** — whether these are averaged series or per-cell ones.
- **`.to_wide()`** — one column per cell, for people who want a spreadsheet:

```python
wide = summary.to_wide(values="discharge_capacity_gravimetric")
print(wide.shape, wide.columns)
```

```text
(304, 3) ['cycle_num', 'sf033', 'rate']
```

## Grouping and averaging

Groups are assigned when you build the batch, not when you collect:

```python
batch = from_cells(
    cells,
    groups={"sf033": 1, "rate": 1},
    group_labels={1: "silicon"},
)
```

Then `group_it=True` averages within each group:

```python
grouped = collect_summaries(
    batch, columns=("discharge_capacity_gravimetric",), group_it=True
)
print("is_grouped:", grouped.is_grouped)
print(grouped.data.columns)
```

```text
is_grouped: True
['group', 'cycle_num', 'variable', 'mean', 'std', 'group_label']
```

**Read those columns again.** Grouping does not merely change the values, it
changes the *schema*: `cell` is gone, the column you asked for has moved into a
`variable` column, and the value is now `mean` with a companion `std`. Any code
downstream that indexes `collection.data` by column name has two cases to handle,
which is what `is_grouped` is for.

`std` is also what makes a spread band possible — `collection.plot(spread=True)`
draws mean ± 1σ, and only means anything when `is_grouped` is true. Check first:

```python
def draw(collection, spread=False):
    return collection.plot(spread=spread and collection.is_grouped)


print(type(draw(grouped, spread=True)).__name__)
```

```text
Figure
```

> Singleton groups used to make this all-or-nothing: one group of one cell and
> `group_it=True` returned nothing averaged at all
> ([cellpy#816](https://github.com/jepegit/cellpy/issues/816), fixed in 2.1.2a2).
> Since then one collection averages multi-member groups *and* keeps singletons as
> per-cell rows, so the app-side partition-and-merge that used to be needed here
> is gone. If you find code doing that, delete it.

## polars here, pandas there

The boundary is not arbitrary, but it is easy to trip on:

| | Type |
|---|---|
| `collection.data` | polars |
| `collection.to_wide(...)` | polars |
| `cell.data.summary`, `cell.data.raw`, `cell.data.steps` | pandas |
| `cell.get_cap(...)` | pandas |

```python
print(type(summary.data).__module__, "vs", type(cells["sf033"].data.summary).__module__)
```

```text
polars.dataframe.frame vs pandas
```

Crossing it is explicit and cheap — `collection.data.to_pandas()` — but do it at
the edge of your code rather than in the middle of it. The failure mode is a
`.iloc` on a polars frame twenty minutes into a debugging session.

## Two things that fail quietly

**A value that is not a cell is silently dropped.** `from_cells` accepts the
mapping without validating it, and the non-cell simply does not appear
downstream — no exception, no warning, a plot with one fewer line than you have
cells:

```python
oops = from_cells({"good": cells["sf033"], "oops": example_data.rate_file()})
collected = collect_summaries(oops, columns=("discharge_capacity_gravimetric",))
print(collected.data["cell"].unique().to_list())
```

```text
['good']
```

`example_data.rate_file()` returns a *path*, not a cell — an easy mistake, since
its sibling `example_data.cellpy_file()` returns a cell. A plain `42` is dropped
just as quietly, so what you get is a chart with fewer lines than you have cells,
which reads as a data problem rather than a type error. If you build the mapping
from anything dynamic, check it yourself:

```python
from cellpy.readers.cellreader import CellpyCell   # note: not cellpy.cellreader

def checked(mapping: dict) -> dict:
    bad = [k for k, v in mapping.items() if not isinstance(v, CellpyCell)]
    if bad:
        raise TypeError(f"not cells: {bad}")
    return mapping


print(len(checked({"sf033": cells["sf033"]})), "cell(s)")
```

**A column your cells do not have collects to nothing**, rather than raising —
you get an empty chart with correct-looking axes. Check before you collect:

```python
def missing(cells: dict, columns) -> list[str]:
    """Union across cells: one odd cell should not veto the rest."""
    have = set()
    for cell in cells.values():
        have |= set(cell.data.summary.columns)
    return [c for c in columns if c not in have]


print(missing(cells, ("discharge_capacity_gravimetric", "no_such_column")))
```

```text
['no_such_column']
```

Union rather than intersection is a deliberate choice: a collected plot spans the
whole selection, so a single cell lacking a column should not make the plot
unavailable for the others. Whether that is right depends on your app — but it
should be a decision, not an accident.

## Where to go next

You have a `Collection`. [Guide 3](03-plotting.md) draws it — including how to
build a plot menu from cellpy's own registry instead of a hard-coded list.

---

*Sources: `cellpy.collect.from_cells`, `collect_summaries`, `collect_cycles`,
`collect_ica`, `collect_dva`, `cellpy.collect.options`, `Collection`.*
