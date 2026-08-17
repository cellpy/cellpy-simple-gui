# 3. Plotting a collection

*You have a `Collection`. You want a figure — and a plot menu you do not have to
maintain by hand.*

The easy half first:

```python
import warnings

from cellpy.collect import collect_summaries, from_cells
from cellpy.utils import example_data

warnings.simplefilter("ignore")

cell = example_data.cellpy_file()
batch = from_cells({"sf033": cell})
collection = collect_summaries(
    batch, columns=("charge_capacity_gravimetric", "discharge_capacity_gravimetric")
)

figure = collection.plot()
print(type(figure).__module__ + "." + type(figure).__name__, "·", len(figure.data), "traces")
```

```text
plotly.graph_objs._figure.Figure · 2 traces
```

It is a real plotly figure. Everything you know about plotly applies — restyle
it, add traces, serialise it with `plotly.io.to_json` and hand it to the browser.
cellpy does not wrap it.

## Making it look like your app

`Collection.plot` takes the hooks you would otherwise reach in and set yourself
([cellpy#801](https://github.com/jepegit/cellpy/issues/801)):

```python
figure = collection.plot(
    layout_updates={
        "paper_bgcolor": "white",
        "plot_bgcolor": "white",
        "font": {"family": "Inter, system-ui, sans-serif", "size": 12},
    },
    height_per_panel=250,
    figure_border_height=120,   # room for axis labels; without it the last facet clips
)
print(figure.layout.paper_bgcolor)
```

Prefer these over post-processing the figure: they are applied while the figure
is built, so they survive facet layout instead of fighting it. Keep your own pass
for the things cellpy does not own — legend truncation for long cell names,
a discrete colorway, grid styling.

## The plot menu you should not hard-code

There are 25 registered plot families, and the registry describes them well
enough that a menu is a projection rather than a list you maintain:

```python
from cellpy.plotting import registry

print(len(registry.families()), "families total")
print(len(registry.families(entry_point="summary_plot")), "belong in a summary menu")
for name, description in registry.families(entry_point="summary_plot")[:3]:
    print(f"  {name:<24} {description}")
```

```text
25 families total
20 belong in a summary menu
  voltages                 End-of-charge and end-of-discharge voltages vs cycle
  capacities               Raw charge/discharge capacity vs cycle
  capacities_gravimetric   Gravimetric charge/discharge capacity vs cycle
```

**`entry_point` is the filter that keeps a menu honest.** The other five entry
points — `cycles_plot`, `raw_plot`, `ica_plot`, `dva_plot`, `cycle_info_plot` —
have one family each and their own call sites. Listing all 25 in a summary menu
puts entries there that can never work; we did exactly that until 2.1.2 offered
this filter.

## `summary_options` — the accessor that matters

Given a family name, this is how you collect it:

```python
from cellpy.plotting import registry

hdr = cell.schema.summary                     # the summary column vocabulary
family = registry.get("capacities_gravimetric")

options = family.summary_options(hdr)
print(type(options).__name__, "·", options.columns)

collection = collect_summaries(batch, options=options)
print(len(collection.plot().data), "traces")
```

```text
SummaryOptions · ('charge_capacity_gravimetric', 'discharge_capacity_gravimetric')
2 traces
```

`family.summary_options(hdr)` returns a **ready** `SummaryOptions` — the columns,
the CV-split flag, and any transforms, in the shape the collector accepts. You
layer only your own concerns on top:

```python
options = family.summary_options(hdr).replace(group_it=False, max_cycle=100)
print(collect_summaries(batch, options=options).data.height, "rows")
```

```text
100 rows
```

That one accessor took a measured investigation to find, and it is the difference
between a menu where 8 of 25 entries work and one where 15 of 20 do. Before it
existed, an app had to know out of band which families needed
`partition_by_cv=True` — knowledge that lives nowhere in the family and goes
stale silently.

## Asked-for columns are not drawn columns

This is the subtlest thing on the page, and getting it wrong tells users their
data is broken when it is not.

```python
family = registry.get("capacities_gravimetric_split_constant_voltage")

asks_for = family.summary_options(hdr).columns
draws = family.columns(hdr)
print("asks the summary for:", len(asks_for), asks_for)
print("draws:              ", len(draws))
print("manufactured by collect:", [c for c in draws if c not in asks_for])
```

```text
asks the summary for: 2 ('charge_capacity_gravimetric', 'discharge_capacity_gravimetric')
draws:               6
manufactured by collect: ['charge_capacity_gravimetric_cv', 'discharge_capacity_gravimetric_cv',
                          'charge_capacity_gravimetric_non_cv', 'discharge_capacity_gravimetric_non_cv']
```

The `*_cv` / `*_non_cv` columns are built by the collector from
`partition_by_cv=True`; the `mod_01_*` columns of the full-cell families come
from transforms. Neither is in anybody's summary.

**So judge availability on `summary_options().columns`, never on
`columns()`.** Checking the drawn names made every CV-split and full-cell family
report "your data is missing columns" when the truth was that we had never asked
for them:

```python
def is_available(family_name: str, cells: dict) -> tuple[bool, str]:
    family = registry.get(family_name)
    have = set()
    for c in cells.values():
        have |= set(c.data.summary.columns)
    needs = family.summary_options(hdr).columns
    missing = [c for c in needs if c not in have]
    return (not missing), ("missing " + ", ".join(missing) if missing else "ok")


for name in ("capacities_gravimetric_split_constant_voltage", "capacities_absolute"):
    print(name, "->", is_available(name, {"sf033": cell}))
```

```text
capacities_gravimetric_split_constant_voltage -> (True, 'ok')
capacities_absolute -> (False, 'missing charge_capacity_absolute, discharge_capacity_absolute')
```

The second answer is *correct* and now truthful: `*_absolute` columns are written
by current `make_summary()`, and this saved file predates them. "Your data lacks
these columns" is the right message — it just has to be true.

Families also declare capabilities directly, which is worth surfacing rather than
inferring:

```python
family = registry.get("capacities_gravimetric")
print(family.supports_cv_split, family.supports_formation, "·", family.mode)
```

```text
False True · gravimetric
```

`mode` is the capacity **basis** (`gravimetric` / `areal` / `absolute` / `raw` /
`None`), not the entry point. The basis is baked into the family name, so a
family and a "which basis?" control are the same choice made twice.

## Films: `kind=`, and what version you are on

A density film is a **kind**, not a layout — and which of those sentences is true
depends on your cellpy version, so check before copying anything:

```python
from importlib.metadata import version

from cellpy.plotting.collected import resolve_collected_layout_kind as resolve

installed = version("cellpy")
print("cellpy", installed)
print("kind='film'  ->", resolve(kind="film"))
```

```text
cellpy 2.1.3
kind='film'  -> ('per_cell', 'film', 'film')
```

**`kind="film"` is correct on every version**, so write that and you never have
to care. What changed is what happens when you get it wrong.

**On 2.1.2 and earlier**, `layout="film"` silently drew lines — and so did
`layout="totally_bogus"`:

```pycon
>>> resolve(layout="film")                 # cellpy 2.1.2
('film', 'line', 'fig_pr_cell')            # kind='line' — it draws lines
>>> resolve(layout="totally_bogus")        # cellpy 2.1.2
('totally_bogus', 'line', 'fig_pr_cell')   # no error, no warning
```

That is the worst kind of bug: the wrong call produced a perfectly plausible
figure, identical `scattergl` traces to `per_cell`, with nothing to suggest
anything was wrong. So it shipped.

**On 2.1.3 and later** ([cellpy#874](https://github.com/jepegit/cellpy/issues/874),
closed) `layout="film"` is accepted as an alias, and an unknown layout raises
with the fix in the message:

```pycon
>>> resolve(layout="film")                 # cellpy 2.1.3
('per_cell', 'film', 'film')
>>> resolve(layout="totally_bogus")        # cellpy 2.1.3
ValueError: Unknown layout='totally_bogus'; expected one of: per_cell, per_cycle,
summary (note: 'film' is a kind=, not a layout= — use kind='film' or layout='film')
```

If you carry a `film` → `kind="film"` translation shim for older cellpy, it is
dead code on 2.1.3 — delete it. This app did
([#154](https://github.com/cellpy/cellpy-simple-gui/issues/154)); the test that
guarded the shim survived unchanged, because it asserted the *trace type* rather
than the shim's return value.

There is also a **legacy third spelling**, `method="film"`, which still works.
Prefer `kind=`: `ica_plotter`'s own docstring advertises the legacy `method`
form, so a reader who lands there first writes the old call.

Whichever version you are on, **assert on the trace type** — "it drew something"
is not a test:

```python
from cellpy.collect import collect_cycles
from cellpy.collect.options import CurveOptions

curves = collect_cycles(batch, options=CurveOptions(cycles=(1, 5, 10)))
film = curves.plot(kind="film", layout="per_cell")
lines = curves.plot(layout="per_cell")
print("film:", {t.type for t in film.data}, "· per_cell:", {t.type for t in lines.data})
```

```text
film: {'histogram2d'} · per_cell: {'scattergl'}
```

### `direction` is a plot argument, and it defaults to charge

Films work on an ICA collection too — the axes are then voltage × cycle with
dQ/dV as the density weight. But **a dQ/dV plot shows one half-cycle by
default**, and the knob that changes it is not where you would look for it:

```python
from cellpy.collect import collect_ica
from cellpy.collect.options import IcaOptions

ica = collect_ica(batch, options=IcaOptions(cycles=(1, 5, 10)))
print("collected:", dict(ica.data.group_by("direction").len().sort("direction").iter_rows()))

def points(**kwargs):
    figure = ica.plot(**kwargs)
    return sum(len(t.x) for t in figure.data if t.x is not None)


for direction in (None, "both", "discharge"):
    kwargs = {"kind": "film", "layout": "per_cell"}
    if direction:
        kwargs["direction"] = direction
    print(f"  direction={direction!s:<9} -> {points(**kwargs)} points")
```

```text
collected: {'charge': 891, 'discharge': 1437}
  direction=None      -> 891 points
  direction=both      -> 2328 points
  direction=discharge -> 1437 points
```

`collect_ica` keeps both half-cycles; the plotters draw `charge` unless told
otherwise, and that holds for the line renderer as much as the film. So a chart
of "the dQ/dV collection" is showing 38% of the rows you collected, and nothing
on the figure says so.

The reason this is easy to miss is that **`direction` is not on `IcaOptions`** —
it is an argument to `plot()`. Reading the options dataclass to find out how to
control direction turns up nothing, which reads like "there is no control"
rather than "look one layer up". Pass `direction="both"` when you mean both.

One more knob, findable only by reading the source: `histscale` (`"abs"`,
`"abs-log"`, `"norm"`, `"hist-eq"`) sets the film's colour scaling. dQ/dV is
signed and heavy-tailed, so the unscaled default is rarely what you want.

## Spread plots lose their hover

Same collection, same columns, three renderings — and one of them has no
`hovertemplate` on any trace:

| mode | hover on the first trace |
|---|---|
| per-cell | `cellpy<br>group=1<br>variable=…<br>Cycle (n.)=%{x}<br>value=%{y}` |
| `group_it=True` | `group=1<br>variable=…<br>Cycle (n.)=%{x}<br>mean=%{y}` |
| `group_it=True, spread=True` | **`None`** — on all traces, mean lines included |

`summary_plotter` goes through plotly express, which attaches hover from the
frame; `spread_plot` builds traces with bare `go.Scatter` and never sets one.
Spread is where hover matters most — the band hides the individual cells, so the
tooltip is the only way to read a value.

Until [cellpy#875](https://github.com/jepegit/cellpy/issues/875) closes, rebuild
it after the fact: the group is the mean trace's name, the variable is the y-axis
title, and `± std` is the distance to the upper-bound trace. Also set
`hoverinfo="skip"` on the Upper/Lower Bound traces — they are construction
artefacts, and a tooltip on one reads like a measurement nobody took.

One detail that will cost you an afternoon otherwise: hand `customdata` over as a
**plain list**, not a numpy array. `plotly.io` serialises arrays as a base64
`{dtype, bdata}` blob that plotly.js does not decode for `customdata`, so the
tooltip renders `± NaN`. A test asserting "customdata is truthy" passes either
way — this was caught in a browser.

## Single-cell plots

Two useful ones live outside the collect path, taking a cell directly:

```python
from cellpy.utils.plotutils import raw_plot

figure = raw_plot(cell, plot_type="voltage-current", backend="plotly", max_points=4000)
print(len(figure.data), "traces")
```

`max_points` matters more than it looks. Without it, one 155k-row demo cell
produced **7.35 MiB** of figure JSON; with it, 0.18 MiB. It also downsamples
silently, so if the number of points is scientifically relevant, say so — read
the drawn count off the figure and annotate it rather than assuming a stride:

```python
shown = max((len(t.x) for t in figure.data if t.x is not None), default=0)
total = len(cell.data.raw)
print(f"showing {shown:,} of {total:,} points")
```

The sibling, `cycle_info_plot`, has one sharp edge:

```python
from cellpy.utils.plotutils import cycle_info_plot

figure = cycle_info_plot(cell, cycle=[1, 2], backend="plotly", get_axes=True)
print(type(figure).__name__ if figure is not None else "None")
```

**`get_axes=True` is what returns the figure.** Without it, `cycle_info_plot`
returns `None` on the plotly backend and your chart is blank for no visible
reason.

## Where to go next

[Guide 4](04-exporting.md) turns the same collection into files — and the figure
above into PNG bytes without a temp file.

---

*Sources: `Collection.plot`, `cellpy.plotting.registry`,
`cellpy.plotting.collected`, `cellpy.utils.plotutils`. Traps from
[CELLPY_PAINPOINTS.md](../../CELLPY_PAINPOINTS.md) §28–§30 and
[cellpy-simple-gui#106](https://github.com/cellpy/cellpy-simple-gui/issues/106).*
