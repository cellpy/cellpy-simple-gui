# 7. What cellpy will and will not do for you

*You are about to write some code. Should you?*

This is the guide that saves the most time, because the expensive mistakes in
this project were never hard bugs — they were weeks spent maintaining something
cellpy already owned, or would own two releases later.

It is distilled from
[`cellpy-delegation-inventory.md`](../../.issueflows/04-designs-and-guides/cellpy-delegation-inventory.md),
which is the same document kept live for one specific app. Written against
**cellpy 2.1.3**.

## cellpy owns these — do not reimplement them

| You might write | cellpy already has |
|---|---|
| a batch shim around in-memory cells | `collect.from_cells(cells, groups=…, selected=…)` |
| per-cycle summaries across cells | `collect_summaries(batch, columns=…)` |
| group averaging with mean ± std | `group_it=True`, then `plot(spread=True)` |
| a "was this averaged?" flag | `Collection.is_grouped` |
| voltage-curve extraction per cycle | `collect_cycles` + `CurveOptions(cycles=…, mode=…, method=…)` |
| dQ/dV and dV/dQ, across cells | `collect_ica` / `collect_dva` + `IcaOptions` |
| a table of which plot needs which options | `family.summary_options(hdr)` |
| a hard-coded plot menu | `registry.families(entry_point="summary_plot")` |
| figure theming, panel heights, facet labels | `plot(layout_updates=…, height_per_panel=…)` |
| PNG/SVG/PDF encoding via a temp file | `figures.write_image(fig, fmt, scale=) -> bytes` |
| csv / parquet / json / xlsx writers | `collection.data.write_*`, `collection.save(...)` |
| an instrument list | `cellpy.list_instruments()` |
| an ingestion form per instrument | `cellpy.instrument_meta_schema(instrument)` |
| a cheap metadata peek | `cellpy.read_meta(path)` — cellpy files only |
| a staged-write wrapper for `.cellpy` | atomic since 2.1.2a4 |
| a full `make_summary()` after a metadata edit | `cell.refresh_after(fields=…)` |
| point-limiting for raw plots | `raw_plot(cell, max_points=…, cycles=…)` |

Two of those are worth their own sentence.

**`from_cells` replaced a hand-rolled batch shim** and was the largest single
deletion in this project ([cellpy#787](https://github.com/jepegit/cellpy/issues/787)).

**`family.summary_options(hdr)` replaced the app's out-of-band knowledge** of
which families need `partition_by_cv` ([cellpy#868](https://github.com/jepegit/cellpy/issues/868)).
It arrived better than requested: the ask was one accessor, and the fix added
capability flags and `entry_point` tagging as well. Measured on the demo cells,
that took the app from 8 of 25 plot families working to 15 of 20.

## cellpy does not do these, and probably should not

Not gaps — different jobs:

- **Chrome.** Colorways, a figure-theme preference, legend truncation for long
  cell names, the right-hand margin that stops a legend squashing the plot.
- **A cell library.** Which cells are loaded, what they are called, which are
  selected, which have unsaved changes. cellpy has no "has this cell changed?"
  signal, so if you want to skip rewriting an unchanged file you track it
  yourself. `(size, mtime_ns)` is a reasonable freshness check — it catches a file
  rewritten behind your back without re-reading megabytes on every save, and it
  will not catch a tamper that preserves both. That is the honest limit, and it
  is fine for a single-user desktop app.
- **Projects.** Saving a set of cells plus a manifest as a portable folder.
- **Jobs, progress and cancellation.** See [guide 6](06-state-and-threading.md).
- **Sandboxing.** If your app takes paths over a network, deciding what may be
  read is yours. cellpy will open whatever you hand it, correctly.

## Currently worth working around

Two open issues, both narrow, both with a workaround that should be deleted when
upstream lands. Keeping that list short — and *actually deleting* the entries —
is the difference between a thin app and a thick one.

| # | What | Workaround |
|---|---|---|
| [#875](https://github.com/jepegit/cellpy/issues/875) | `spread_plot` traces carry no `hovertemplate` at all | rebuild hover from the figure; `hoverinfo="skip"` on the band edges |

One came off this list in the writing of it: [#874](https://github.com/jepegit/cellpy/issues/874)
(an unknown `layout=` accepted silently) closed in 2.1.3, and the app's
translation shim went with it. What did *not* change was the test — it asserted
the resulting trace type rather than the shim's return value, so it kept meaning
something when the responsibility moved upstream. That is the whole of habit 3
below, and it is worth copying.

Plus three unfiled frictions where the app simply forwards a knob rather than
working around anything: summary y-labels omit units, the cycles plotter ignores
the collect `mode` for `x_unit`, and summary facet order ignores collect column
order under group-averaging.

## How to keep the list shrinking

Four habits, in the order they pay off.

**1. File it, with a reproduction.** 29 issues came out of this project and 25
are closed. Nearly every one was a five-line script showing the surprising
output. The two that came back *better than asked* were the two that explained
what the app was trying to do, rather than only what was wrong.

**2. Closed is not released.** This caught us twice. Verify against the installed
package before deleting a workaround:

```python
import warnings

from cellpy.plotting import registry
from cellpy.utils import example_data

warnings.simplefilter("ignore")

hdr = example_data.cellpy_file().schema.summary
family = registry.get("capacities_gravimetric_split_constant_voltage")

# The #868 fix, verified rather than assumed: options carry the CV flag,
# and transforms are callables rather than a nested mapping.
options = family.summary_options(hdr)
print("partition_by_cv:", options.partition_by_cv)
print("transforms are callable:", all(callable(t) for t in (options.transforms or ())))
```

```text
partition_by_cv: True
transforms are callable: True
```

**3. Test the delegation, not the workaround.** When a workaround goes, the test
that guarded it should become a test that the delegation *works* — otherwise the
next regression is silent. The film translation is the clearest example: the test
asserts `histogram2d` traces, so it keeps meaning something whether the fix is
ours or upstream's.

**4. Watch for silent success.** The worst failures in this whole project looked
like passes:

- an import job reported `status: "done"` and imported **zero** cells, because
  the failure lived in the result payload rather than the status;
- instrument discovery returned **11 of 13** loaders and logged nothing a user
  would see;
- `layout="film"` drew a perfectly plausible *line* plot;
- a `customdata` array serialised to base64 and rendered `± NaN` in a tooltip
  while a test asserting "customdata is truthy" passed.

In every case the code was wrong in a way that produced *plausible* output, and
in every case the fix was at the level of the check rather than the code: assert
on `added`/`errors` rather than job status, assert the trace type rather than
that a figure exists, look at the thing in a browser. Green meaning working is
not free; it is a property you have to design for.

## The shape that turned out right

For anyone starting: build a `Collection` and let cellpy plot it.

Grouping, spread, per-cell cycle isolation and multi-format export then stay
consistent with cellpy instead of drifting away from it, and every upstream fix
arrives as a deletion in your code rather than a migration. `core/collect.py` in
this app is substantially *shorter* than it was at 2.1.1, and nearly all the
difference is logic cellpy now owns.

---

*Sources:
[`cellpy-delegation-inventory.md`](../../.issueflows/04-designs-and-guides/cellpy-delegation-inventory.md)
and [`CELLPY_PAINPOINTS.md`](../../CELLPY_PAINPOINTS.md) (29 filed, 25 closed).*
