# 4. Exporting data and figures

*You want files: the numbers behind a chart, the chart itself, or a whole cell.*

The rule that matters more than any API on this page: **export the collection you
plotted.** If the chart comes from one `Collection` and the CSV from a fresh
query, they will disagree eventually — different cycle cap, different half-cycle,
different grouping — and the person who notices will be someone comparing a
figure in a paper against its data.

## The numbers

`collection.data` is a polars DataFrame, so the formats are polars' own and there
is nothing to install:

```python
import warnings

from cellpy.collect import collect_summaries, from_cells
from cellpy.utils import example_data

warnings.simplefilter("ignore")

batch = from_cells({"sf033": example_data.cellpy_file()})
collection = collect_summaries(
    batch, columns=("charge_capacity_gravimetric", "discharge_capacity_gravimetric")
)

csv = collection.data.write_csv()
print(csv.splitlines()[0])
print(len(csv.splitlines()) - 1, "rows")
```

```text
cell,group,sub_group,group_label,label,cycle_num,charge_capacity_gravimetric,discharge_capacity_gravimetric
304 rows
```

In memory, which is what a web app wants — no temp file, no cleanup:

```python
import io

buffer = io.BytesIO()
collection.data.write_parquet(buffer)
print("parquet:", len(buffer.getvalue()), "bytes")

print("json:", len(collection.data.write_json()), "bytes")
print("xlsx: via", type(collection.data.to_pandas()).__name__ + ".to_excel")
```

Excel is the one that leaves polars: `collection.data.to_pandas().to_excel(buf,
index=False)`, which needs `openpyxl`. Everything else is native.

If you would rather cellpy wrote the files, it will:

```python
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as tmp:
    written = collection.save(Path(tmp), formats=("csv", "parquet"))
    print([p.name for p in written])
```

```text
['in_memory_summary.csv', 'in_memory_summary.parquet', 'in_memory_summary.meta.json']
```

`save` defaults to `("parquet", "csv")`; xlsx and json are supported too
([cellpy#789](https://github.com/jepegit/cellpy/issues/789)). It also writes a
`.meta.json` sidecar you did not ask for — welcome for provenance, surprising if
you are zipping the result and counting files.

## Matching the chart, in practice

Two cases where "export the collection you plotted" needs actual work.

**Differential curves.** dQ/dV and dV/dQ come from different collectors than
voltage curves, so an export routed on "the user is on the Cycles tab" will
happily give them the wrong numbers. Route on the *curve kind*:

```python
from cellpy.collect import collect_cycles, collect_dva, collect_ica
from cellpy.collect.options import CurveOptions, IcaOptions

COLLECTORS = {
    "voltage": lambda b, cycles: collect_cycles(b, options=CurveOptions(cycles=cycles)),
    "dqdv": lambda b, cycles: collect_ica(b, options=IcaOptions(cycles=cycles)),
    "dvdq": lambda b, cycles: collect_dva(b, options=IcaOptions(cycles=cycles)),
}

for kind, collect in COLLECTORS.items():
    data = collect(batch, (1, 5)).data
    print(f"{kind:<8} {data.height:>6} rows · {data.columns}")
```

```text
voltage    1829 rows · ['potential', 'capacity', 'cell', 'group', 'sub_group', 'cycle_num']
dqdv       1825 rows · ['cycle', 'direction', 'voltage', 'capacity', 'dqdv', 'cell', 'group', 'sub_group']
dvdq       1825 rows · ['cycle', 'direction', 'capacity', 'voltage', 'dvdq', 'cell', 'group', 'sub_group']
```

Three different column vocabularies for what a user thinks of as "the same two
cycles" — which is why routing the export on the tab rather than the kind gives
you a file with plausible headers and the wrong contents.

**Half-cycle selection.** The ICA/DVA plotters take a `direction` and draw one
half-cycle; the collected frame keeps both, in a `direction` column. If the chart
shows charge only, the export has to say so too:

```python
import polars as pl

def select_direction(collection, direction: str):
    """Mirror what the plotter drew. 'both' (or anything else) keeps everything."""
    want = (direction or "").lower()
    if want not in ("charge", "discharge") or "direction" not in collection.data.columns:
        return collection
    collection.data = collection.data.filter(
        pl.col("direction").str.to_lowercase() == want
    )
    return collection


ica = COLLECTORS["dqdv"](batch, (1, 5))
print(ica.data.height, "->", select_direction(ica, "charge").data.height, "rows")
```

## The figure

cellpy will encode a plotly figure to image bytes in-process — no temp file, no
subprocess ([cellpy#818](https://github.com/jepegit/cellpy/issues/818)):

```python
from cellpy.plotting import figures

print(sorted(figures.IMAGE_FORMATS))
print(figures.image_media_type("png"), figures.image_media_type("svg"))
```

```text
['jpeg', 'jpg', 'pdf', 'png', 'svg', 'webp']
image/png image/svg+xml
```

```python
figure = collection.plot()

try:
    data = figures.write_image(figure, "png", scale=2)
    print("png:", len(data), "bytes")
except Exception as exc:  # noqa: BLE001 - see below; this is the normal path
    print("no server-side export here:", type(exc).__name__)
```

`Collection.to_image(fmt, scale=)` does the same in one step if you have not
customised the figure.

### "kaleido is installed" and "figure export works" are different facts

This is the sharp edge, and it is not cellpy's doing. **kaleido 1.x renders by
driving a separate Chrome**, so the Python package being importable proves
nothing. Three states, and your error message has to tell them apart:

| State | What the user should be told |
|---|---|
| kaleido missing | install it — `uv sync --extra export` |
| kaleido present, no browser | install Chrome or Chromium; installing kaleido again will not help |
| something else | the real error |

Telling someone to install kaleido when kaleido is already there and the browser
is what is missing sends them in exactly the wrong direction — which is what
happens by default in a slim container:

```python
MISSING_KALEIDO = ("Static figure export needs kaleido. Install with: "
                   "uv sync --extra export.")
MISSING_BROWSER = ("Static figure export needs a Chrome or Chromium binary — "
                   "kaleido is installed but renders by driving a browser.")

def explain_export_failure(exc: BaseException) -> str:
    text = str(exc).lower()
    # Browser first: a browser failure often mentions kaleido too.
    if any(k in text for k in ("chrome", "chromium", "browser")):
        return MISSING_BROWSER
    if any(k in text for k in ("kaleido", "orca", "image export")):
        return MISSING_KALEIDO
    return f"Figure export failed ({exc})."


print(explain_export_failure(RuntimeError("BrowserFailedError: chrome exited")))
```

Note the ordering — browser before kaleido — because the browser failure text
usually names kaleido as well, and matching kaleido first gives the wrong answer.
`plotly_get_chrome` exiting 0 does not mean the browser works either; the only
honest check is to render something.

**Degrade, do not block.** Plotly's own toolbar has a camera button that saves a
PNG client-side, so a web app that cannot render server-side is inconvenienced,
not broken. Say that in the error rather than presenting a dead end.

## Whole cells

Different job: not a view, the cell itself.

```python
import tempfile
from pathlib import Path

cell = example_data.cellpy_file()
with tempfile.TemporaryDirectory() as tmp:
    target = Path(tmp) / "exported.cellpy"
    cell.save(target)
    print(target.name, "·", round(target.stat().st_size / 1e6, 1), "MB")
```

`cell.to_csv(datadir=…)` writes several files (raw, steps, summary), and
`cell.to_excel(filename=…)` writes one workbook. Because csv is multi-file and
users usually want one thing, zipping at the boundary is normal.

> **`.cellpy` writes are atomic** as of 2.1.2a4
> ([cellpy#845](https://github.com/jepegit/cellpy/issues/845)) — staged write plus
> `os.replace`, so an interrupted save no longer destroys the previous file. If
> your app saves a *set* of things (several cells plus a manifest), you still want
> your own staging: atomicity per file is not atomicity per project.

## Where to go next

[Guide 5](05-configuration.md) — where cellpy is reading its settings from, and
how to change them without writing into a file your users share with their
notebooks.

---

*Sources: `Collection.save` / `.to_image`, `cellpy.plotting.figures.write_image`,
`cellpy.plotting.figures.image_media_type`, `CellpyCell.save` / `.to_csv` /
`.to_excel`. Export traps from
[cellpy-simple-gui#135](https://github.com/cellpy/cellpy-simple-gui/issues/135).*
