# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "cellpy>=2.1.3",
#     "fastapi>=0.115",
#     "uvicorn>=0.30",
#     "plotly>=5.22",
# ]
# ///
"""A cellpy app in one file: load cells, plot them, export the numbers.

    uv run examples/starter/app.py        # then open http://127.0.0.1:8000

This is a **starting point**, not a small version of cellpy-simple-gui. It is
deliberately the shortest path from "I have cell files" to "I have a chart and a
CSV", so that everything you add on top is yours rather than ours.

The whole cellpy story is four calls, and they are the four sections below:

    cellpy.get(...)          one file  -> one CellpyCell
    from_cells({...})        many cells -> a Batch
    collect_summaries(batch) a Batch    -> a Collection (a tidy polars frame)
    collection.plot()        a Collection -> a plotly Figure

The single thing worth knowing before you read on: **you do not build the
Batch.** ``from_cells`` takes cells you already hold in memory and hands back a
real cellpy Batch, so grouping, cycle selection, group averaging, spread bands
and multi-format export all come from cellpy rather than from you. Reaching past
it and assembling frames by hand is the most common way to end up maintaining a
worse copy of cellpy.

What this file leaves out on purpose: saved projects, background jobs, upload,
authentication, themes. Those are most of why the full app is twenty times the
size. Add them when you need them, not before.

The server binds to 127.0.0.1 and has no authentication. That is fine for a tool
on your own machine and *only* there — the moment it is reachable from a
network, ``/api/cells`` is arbitrary file read on the host.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import plotly.io as pio
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response

# --------------------------------------------------------------------------- #
# 1. What you can plot — this table is the thing you edit first
# --------------------------------------------------------------------------- #

#: Plot name -> the ``cell.data.summary`` columns behind it. Adding a plot is
#: adding a line here; nothing else in this file knows the names.
#:
#: The ``_gravimetric`` suffix is the capacity *basis*. cellpy also computes
#: ``_areal``, and unsuffixed columns are absolute — so "discharge capacity per
#: gram" and "discharge capacity per cm²" are different columns, not a setting.
SUMMARY_PLOTS: dict[str, tuple[str, ...]] = {
    "Capacity": ("charge_capacity_gravimetric", "discharge_capacity_gravimetric"),
    "Coulombic efficiency": ("coulombic_efficiency",),
    "End voltages": ("potential_end_charge", "potential_end_discharge"),
    "Internal resistance": ("ir_charge", "ir_discharge"),
}

#: Voltage curves are a different *collector*, not a different column set, so
#: they get a name of their own rather than an entry above.
CYCLE_CURVES = "Voltage curves"

#: Loaded cells, by display name. A module global because this app serves one
#: person on one machine — which is a decision, not an oversight. Two browsers
#: pointed at one process share this dict, and cellpy's own configuration is
#: process-global too, so anything multi-user starts by fixing both.
CELLS: dict[str, Any] = {}


# --------------------------------------------------------------------------- #
# 2. Getting cells into memory
# --------------------------------------------------------------------------- #


def load_example() -> str:
    """Load cellpy's bundled demo cell. Downloads once, then caches."""
    from cellpy.utils import example_data

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cell = example_data.cellpy_file()
    return _remember("demo cell", cell)


def load_file(path: str, instrument: str | None = None, mass: float | None = None) -> str:
    """Load one file. ``instrument=None`` lets cellpy decide from the suffix.

    ``mass`` is the active-material mass in mg. Without it the gravimetric
    columns are computed against whatever mass the file carries (often 1.0),
    so the numbers are still *there* — just not per gram of your material.
    """
    import cellpy

    kwargs: dict[str, Any] = {"filename": path}
    if instrument:
        kwargs["instrument"] = instrument
    if mass is not None:
        kwargs["mass"] = mass
    return _remember(Path(path).stem, cellpy.get(**kwargs))


def _remember(name: str, cell: Any) -> str:
    """Store a cell under a name that is not already taken."""
    unique, n = name, 1
    while unique in CELLS:
        n += 1
        unique = f"{name} ({n})"
    CELLS[unique] = cell
    return unique


def instruments() -> list[str]:
    """Every loader cellpy can offer on this machine.

    Discovered at runtime, so the list depends on the installed cellpy — and a
    loader being listed does not promise it will work here: Arbin ``.res`` is an
    Access database and needs a system reader (mdbtools, or Microsoft's Access
    Database Engine on Windows) that most machines do not have.
    """
    import cellpy

    return sorted(entry["id"] for entry in cellpy.list_instruments())


# --------------------------------------------------------------------------- #
# 3. Cells -> Collection -> figure -> bytes
# --------------------------------------------------------------------------- #


def collection_for(plot: str, *, cycles: tuple[int, ...] = (1, 5, 10, 20)):
    """The cellpy ``Collection`` behind one plot name.

    A Collection is a tidy `polars` frame (``.data``) plus enough context to
    draw itself (``.plot()``). Both plots and exports below come from here, so
    the CSV you download always matches the chart you are looking at.
    """
    from cellpy.collect import collect_cycles, collect_summaries, from_cells
    from cellpy.collect.options import CurveOptions

    if not CELLS:
        raise HTTPException(400, "Load a cell first.")

    batch = from_cells(CELLS)

    if plot == CYCLE_CURVES:
        return collect_cycles(batch, options=CurveOptions(cycles=cycles))

    columns = SUMMARY_PLOTS.get(plot)
    if columns is None:
        raise HTTPException(404, f"No plot called {plot!r}.")
    missing = _missing(columns)
    if missing:
        # Collecting a column the summary does not carry draws an empty chart
        # rather than raising, so say it here instead.
        raise HTTPException(400, "These cells have no " + ", ".join(missing) + ".")
    return collect_summaries(batch, columns=columns)


def _missing(columns: tuple[str, ...]) -> list[str]:
    """Which of ``columns`` none of the loaded cells actually has."""
    have: set[str] = set()
    for cell in CELLS.values():
        have |= set(cell.data.summary.columns)
    return [c for c in columns if c not in have]


def figure_json(plot: str, **kwargs) -> str:
    """Plotly figure JSON for a plot name.

    ``Collection.plot()`` returns a real ``plotly.graph_objects.Figure``, so
    anything you know about plotly applies — restyle it, add traces, whatever.
    Two knobs worth knowing: ``group_it=True`` on the collect call averages
    cells that share a group, and ``spread=True`` here draws the ±1σ band.
    """
    figure = collection_for(plot, **kwargs).plot()
    return pio.to_json(figure)


def export_csv(plot: str, **kwargs) -> bytes:
    """The collected frame as CSV — the numbers behind the chart.

    ``collection.data`` is polars, so ``write_parquet`` / ``write_json`` are
    right there too, and ``.to_pandas()`` if you would rather have pandas.
    """
    return collection_for(plot, **kwargs).data.write_csv().encode("utf-8")


# --------------------------------------------------------------------------- #
# 4. The web bit
# --------------------------------------------------------------------------- #

app = FastAPI(title="cellpy starter")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return PAGE


@app.get("/api/state")
def state() -> dict:
    return {
        "cells": list(CELLS),
        "plots": [*SUMMARY_PLOTS, CYCLE_CURVES],
        "instruments": instruments(),
    }


@app.post("/api/cells")
def add_cells(body: dict) -> dict:
    """Load the demo cell (``{"example": true}``) or files (``{"paths": [...]}``)."""
    if body.get("example"):
        load_example()
    for path in body.get("paths") or []:
        try:
            load_file(path, body.get("instrument"), body.get("mass"))
        except Exception as exc:  # noqa: BLE001 - the reason belongs on screen
            raise HTTPException(400, f"{Path(path).name}: {exc}") from exc
    return {"cells": list(CELLS)}


@app.delete("/api/cells")
def clear_cells() -> dict:
    CELLS.clear()
    return {"cells": []}


@app.get("/api/figure")
def figure(plot: str) -> Response:
    return Response(figure_json(plot), media_type="application/json")


@app.get("/api/export.csv")
def export(plot: str) -> Response:
    return Response(
        export_csv(plot),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{plot}.csv"'},
    )


# --------------------------------------------------------------------------- #
# 5. One page, no build step
# --------------------------------------------------------------------------- #

PAGE = """<!doctype html>
<meta charset="utf-8"><title>cellpy starter</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<style>
  body { font: 15px/1.5 system-ui, sans-serif; margin: 2rem; max-width: 60rem; }
  header { display: flex; gap: .5rem; align-items: center; flex-wrap: wrap; }
  #chart { height: 30rem; margin-top: 1rem; }
  #cells { color: #667; margin-top: .5rem; }
  input { flex: 1; min-width: 14rem; }
</style>

<h1>cellpy starter</h1>
<header>
  <button onclick="load({example: true})">Load demo cell</button>
  <input id="path" placeholder="…or a path to a cell file on this machine">
  <button onclick="load({paths: [path.value]})">Load</button>
  <button onclick="send('DELETE')">Clear</button>
</header>
<div id="cells"></div>

<header style="margin-top:1rem">
  <select id="plot" onchange="draw()"></select>
  <a id="csv" href="#">Download CSV</a>
</header>
<div id="chart"></div>

<script>
// What is loaded lives here, not in the text on screen: a status line you also
// read state back out of drifts the moment anything writes to it twice.
let loaded = [];

const api = async (url, opts) => {
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
  return r.json();
};
const send = (method, body) =>
  api('/api/cells', {method, headers: {'Content-Type': 'application/json'},
                     body: body && JSON.stringify(body)}).then(refresh);
const load = (body) => send('POST', body).catch(e => say(e.message));

function say(problem) {
  cells.textContent =
    (loaded.length ? 'Loaded: ' + loaded.join(', ') : 'No cells loaded.') +
    (problem ? ' — ' + problem : '');
}

async function refresh() {
  const s = await api('/api/state');
  loaded = s.cells;
  if (!plot.options.length)
    plot.append(...s.plots.map(p => new Option(p, p)));
  draw();
}

let drawing = 0;

async function draw() {
  const mine = ++drawing;
  csv.href = '/api/export.csv?plot=' + encodeURIComponent(plot.value);
  if (!loaded.length) { say(); return Plotly.purge(chart); }
  // Collecting a few hundred cycles takes a moment, and a chart that has not
  // caught up yet is the previous plot wearing the new plot's name.
  say('drawing…');
  try {
    const fig = await api('/api/figure?plot=' + encodeURIComponent(plot.value));
    if (mine !== drawing) return;  // someone changed the menu while we waited
    Plotly.react(chart, fig.data, fig.layout, {responsive: true});
    say();
  } catch (e) {
    if (mine !== drawing) return;
    Plotly.purge(chart);
    say(e.message);
  }
}

refresh();
</script>
"""


if __name__ == "__main__":
    # 127.0.0.1 on purpose: see the module docstring.
    uvicorn.run(app, host="127.0.0.1", port=8000)
