# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "cellpy>=2.1.2",
#     "mcp>=2.0",
#     "plotly>=5.22",
# ]
# ///
"""A prototype MCP server for cellpy — enough to prove or disprove the design.

    CELLPY_MCP_ROOT=/path/to/your/data uv run --script examples/mcp/server.py

**This is a prototype, not a product.** It exists to answer the two questions in
cellpy-simple-gui#128 — what happens to cellpy's process-global state when the
caller is long-lived and multi-client, and what happens to file access when the
caller is an agent — by building the thing rather than reasoning about it. See
`.issueflows/04-designs-and-guides/mcp-server-design.md` for what it found.

Three rules shape every tool here, and they are the design:

1. **Tools return handles and facts, never data.** A tool result goes into a
   model's context window. One collected summary is ~58 kB of JSON and a raw
   figure can be 7 MB; returning either is how you burn a context window and pay
   for the privilege. Frames stay server-side behind an id.

2. **One client per process, and cellpy's global config is never written.**
   The intended design was per-session state; the SDK does not give a tool a
   stable session identity, so this is honest about being single-client instead
   (see `_STATE`). `config.reload()` is process-global anyway (deliberately —
   see guide 6), so a tool that called it would reconfigure cellpy for anyone
   else sharing the process. `override()` is contextvar-scoped and is the only
   safe way to vary settings per call.

3. **Every path is checked, in and out.** The caller is a language model acting
   on text it may have read somewhere. That is a less trustworthy caller than a
   human typing into a desktop app, so the sandbox is not optional here the way
   it is on loopback.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# NOTE: `mcp.server.mcpserver.Context` — *not* `mcp.server.context.Context`.
# Both exist in mcp 2.0 and only this one is recognised by `@server.tool()`. The
# other registers without complaint and then fails schema generation with a
# pydantic error naming neither the import nor the fix.
from mcp.server import MCPServer
from mcp.server.mcpserver import Context

server = MCPServer(
    name="cellpy",
    instructions=(
        "Battery cell data via cellpy. Load cells, collect them into frames, "
        "then render or export. Tools return handles and summaries — use "
        "preview_collection to see rows, and render/export to produce files."
    ),
)

#: Everything readable and writable. No default of "/" — a server that starts
#: wide open and relies on being configured is a server that ships wide open.
ROOT = Path(os.environ.get("CELLPY_MCP_ROOT", Path.home() / "cellpy_mcp")).expanduser().resolve()

#: Hard cap on rows a tool will put in front of a model, whatever it asks for.
MAX_PREVIEW_ROWS = 20


class Refused(ValueError):
    """The request is not allowed. The message is meant for the model to read."""


# --------------------------------------------------------------------------- #
# Paths: the agent is the untrusted caller
# --------------------------------------------------------------------------- #


def _resolve(raw: str, *, must_exist: bool = True) -> Path:
    """Resolve a caller-supplied path inside ROOT, or refuse it.

    The volume is settled from the string before any filesystem call. On Windows
    that keeps a UNC path off the network — ``Path.resolve()`` on
    ``\\\\host\\share`` asks Windows to go and find *host* — and a boundary that
    waits on a name server is one a name server could answer differently.
    """
    text = str(raw).strip().strip('"')
    if not text:
        raise Refused("No path given.")

    candidate = Path(text).expanduser()
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    elif os.path.normcase(candidate.drive) != os.path.normcase(ROOT.drive):
        raise Refused(f"“{text}” is outside the data directory.")

    resolved = candidate.resolve()
    if resolved != ROOT and not resolved.is_relative_to(ROOT):
        raise Refused(f"“{text}” is outside the data directory.")
    if must_exist and not resolved.exists():
        raise Refused(f"“{text}” does not exist.")
    return resolved


# --------------------------------------------------------------------------- #
# State: what the prototype learned about sessions
# --------------------------------------------------------------------------- #


@dataclass
class Session:
    cells: dict[str, Any] = field(default_factory=dict)
    collections: dict[str, Any] = field(default_factory=dict)
    counter: int = 0

    def handle(self, prefix: str) -> str:
        self.counter += 1
        return f"{prefix}-{self.counter}"


#: **One client per process.** Not laziness — measured.
#:
#: The obvious design is a per-session store, and mcp 2.0 appears to offer the
#: key for it: the tool `Context` has a `session`. It is a *different*
#: `ServerSession` object on every call (three distinct objects across three
#: calls on one connection), so a `WeakKeyDictionary` keyed on it hands every
#: call a fresh, empty state and the server silently forgets what you loaded.
#: The other `Context` class — the one tools do *not* receive — has a
#: `session_id`, which is the sort of asymmetry you only find by trying it.
#:
#: So state is process-wide and honest about it. Under stdio, which is how MCP
#: servers are normally launched, each client spawns its own process and that
#: *is* the isolation. A shared streamable-http deployment would need a session
#: token the client passes in its tool arguments, or one process per client
#: anyway. See the design doc — this is one of the two questions #128 asked.
_STATE = Session()


def _session(ctx: Context) -> Session:
    return _STATE


def _cell(state: Session, handle: str):
    if handle not in state.cells:
        raise Refused(f"No cell {handle!r}. Call list_cells to see what is loaded.")
    return state.cells[handle]


def _collection(state: Session, handle: str):
    if handle not in state.collections:
        raise Refused(f"No collection {handle!r}. Call collect first.")
    return state.collections[handle]


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #


@server.tool()
def list_instruments() -> dict:
    """Which cellpy loaders exist, and which can actually run on this machine."""
    import shutil
    import sys

    import cellpy

    def arbin_res_readable() -> bool:
        try:
            if sys.platform != "win32":
                return shutil.which("mdb-export") is not None
            import pyodbc

            return any("microsoft access driver" in d.lower() for d in pyodbc.drivers())
        except Exception:  # noqa: BLE001 - no opinion means "assume it works"
            return True

    usable = arbin_res_readable()
    out = []
    for entry in cellpy.list_instruments():
        item = {"id": entry["id"], "suffixes": entry.get("suffixes", []), "usable": True}
        if entry["id"] == "arbin_res" and not usable:
            item["usable"] = False
            item["reason"] = "needs mdbtools (posix) or the Access Database Engine (Windows)"
        out.append(item)
    return {"instruments": out, "root": str(ROOT)}


@server.tool()
def load_cell(
    ctx: Context,
    path: str,
    instrument: str | None = None,
    mass_mg: float | None = None,
) -> dict:
    """Load one cell file and return a handle plus what the data can support.

    `mass_mg` is the active-material mass. Without it every `*_gravimetric`
    column is computed against a default of 1.0 mg — the numbers still appear,
    they are simply wrong, so supply it when you know it.
    """
    import cellpy

    state = _session(ctx)
    target = _resolve(path)

    kwargs: dict[str, Any] = {"filename": str(target)}
    if instrument:
        kwargs["instrument"] = instrument
    if mass_mg is not None:
        kwargs["mass"] = mass_mg

    cell = cellpy.get(**kwargs)
    handle = state.handle("cell")
    state.cells[handle] = cell

    cycles = list(cell.get_cycle_numbers())
    return {
        "handle": handle,
        "name": cell.cell_name,
        "cycles": len(cycles),
        "first_cycle": cycles[0] if cycles else None,
        "last_cycle": cycles[-1] if cycles else None,
        "mass_mg": cell.mass,
        "mass_was_supplied": mass_mg is not None,
        # Names only. The frame itself stays here.
        "summary_columns": sorted(cell.data.summary.columns),
    }


@server.tool()
def list_cells(ctx: Context) -> dict:
    """The cells loaded in this session."""
    state = _session(ctx)
    return {
        "cells": [
            {"handle": h, "name": c.cell_name, "cycles": len(c.get_cycle_numbers())}
            for h, c in state.cells.items()
        ]
    }


@server.tool()
def describe_plot_families(ctx: Context) -> dict:
    """Summary plot families cellpy offers, and whether the loaded cells support them.

    Availability is judged on what a family *asks the summary for*
    (`summary_options().columns`), not on the columns it draws — the drawn list
    includes columns the collector manufactures, and checking those reports
    "missing columns" for families that work perfectly well.
    """
    from cellpy.plotting import registry

    state = _session(ctx)
    if not state.cells:
        raise Refused("Load a cell first — availability depends on the data.")

    have: set[str] = set()
    hdr = None
    for cell in state.cells.values():
        have |= set(cell.data.summary.columns)
        hdr = hdr if hdr is not None else cell.schema.summary

    families = []
    for name, description in registry.families(entry_point="summary_plot"):
        try:
            needs = registry.get(name).summary_options(hdr).columns
        except Exception as exc:  # noqa: BLE001 - a broken family is data, not a crash
            families.append({"name": name, "available": False, "reason": str(exc)})
            continue
        missing = [c for c in needs if c not in have]
        entry = {"name": name, "description": description, "available": not missing}
        if missing:
            entry["missing_columns"] = missing
        families.append(entry)
    return {"families": families}


@server.tool()
def collect(
    ctx: Context,
    kind: str,
    cells: list[str] | None = None,
    columns: list[str] | None = None,
    family: str | None = None,
    cycles: list[int] | None = None,
    group_it: bool = False,
    max_cycle: int | None = None,
) -> dict:
    """Build a collection. `kind` is one of: summary, cycles, ica, dva.

    Returns a handle and the frame's shape — never the frame. Use
    preview_collection for rows, export_collection for the numbers.

    For `summary`, give either `columns` or `family` (a name from
    describe_plot_families; the family supplies its own collect options).
    For `cycles` / `ica` / `dva`, give `cycles`.
    """
    from cellpy.collect import (
        collect_cycles,
        collect_dva,
        collect_ica,
        collect_summaries,
        from_cells,
    )
    from cellpy.collect.options import CurveOptions, IcaOptions
    from cellpy.plotting import registry

    # Check the argument before the state: telling an agent "no cells loaded"
    # when it also misspelled `kind` costs it a round trip to find that out.
    if kind not in ("summary", "cycles", "ica", "dva"):
        raise Refused(f"Unknown kind {kind!r}. Use summary, cycles, ica or dva.")

    state = _session(ctx)
    handles = cells or list(state.cells)
    if not handles:
        raise Refused("No cells loaded.")

    # from_cells accepts anything and silently drops what is not a cell, so the
    # mapping is built from checked lookups only (cellpy#939).
    chosen = {h: _cell(state, h) for h in handles}
    batch = from_cells({state.cells[h].cell_name or h: c for h, c in chosen.items()})

    if kind == "summary":
        if family:
            hdr = next(iter(chosen.values())).schema.summary
            options = registry.get(family).summary_options(hdr).replace(
                only_selected=False, group_it=group_it, max_cycle=max_cycle
            )
            collection = collect_summaries(batch, options=options)
        else:
            if not columns:
                raise Refused("Give either `columns` or `family` for kind='summary'.")
            missing = [c for c in columns if not any(
                c in cell.data.summary.columns for cell in chosen.values())]
            if missing:
                # Collecting these would draw an empty chart rather than fail.
                raise Refused("These cells have no " + ", ".join(missing) + ".")
            collection = collect_summaries(
                batch, columns=tuple(columns), only_selected=False,
                group_it=group_it, max_cycle=max_cycle,
            )
    elif kind == "cycles":
        collection = collect_cycles(batch, options=CurveOptions(cycles=tuple(cycles or ())))
    elif kind in ("ica", "dva"):
        collector = collect_ica if kind == "ica" else collect_dva
        collection = collector(batch, options=IcaOptions(cycles=tuple(cycles or ())))
    else:  # unreachable: kind was validated above
        raise Refused(f"Unknown kind {kind!r}.")

    handle = state.handle("collection")
    state.collections[handle] = collection
    data = collection.data
    result = {
        "handle": handle,
        "kind": kind,
        "rows": data.height,
        "columns": data.columns,
        "is_grouped": bool(collection.is_grouped),
    }
    if "direction" in data.columns:
        # Plotting defaults to charge; say so here rather than let it surprise.
        result["directions"] = dict(
            data.group_by("direction").len().sort("direction").iter_rows()
        )
        result["note"] = (
            "Plots draw direction='charge' by default; pass direction='both' to render."
        )
    return result


@server.tool()
def preview_collection(ctx: Context, handle: str, rows: int = 5) -> dict:
    """A few rows, capped. This is the only tool that returns data, on purpose."""
    collection = _collection(_session(ctx), handle)
    n = max(1, min(int(rows), MAX_PREVIEW_ROWS))
    return {
        "rows_shown": n,
        "rows_total": collection.data.height,
        "records": collection.data.head(n).to_dicts(),
    }


@server.tool()
def render(
    ctx: Context,
    handle: str,
    path: str,
    kind: str | None = None,
    layout: str = "per_cell",
    direction: str | None = None,
    spread: bool = False,
) -> dict:
    """Draw a collection and write the figure to `path` (.json or .html).

    `kind="film"` gives a 2-D density rendering. Note it is a **kind**, not a
    layout: on cellpy 2.1.2 `layout="film"` silently drew lines instead (fixed
    in 2.1.3). The returned `trace_types` is how you check what you actually got.
    """
    import plotly.io as pio

    collection = _collection(_session(ctx), handle)
    target = _resolve(path, must_exist=False)
    if target.suffix.lower() not in (".json", ".html"):
        raise Refused("Write a .json or .html figure.")

    kwargs: dict[str, Any] = {"layout": layout}
    if kind:
        kwargs["kind"] = kind
    if direction:
        kwargs["direction"] = direction
    if spread and collection.is_grouped:
        kwargs["spread"] = True

    figure = collection.plot(**kwargs)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.suffix.lower() == ".json":
        target.write_text(pio.to_json(figure), encoding="utf-8")
    else:
        target.write_text(pio.to_html(figure, include_plotlyjs="cdn"), encoding="utf-8")

    points = sum(len(t.x) for t in figure.data if getattr(t, "x", None) is not None)
    return {
        "path": str(target),
        "bytes": target.stat().st_size,
        "traces": len(figure.data),
        "trace_types": sorted({t.type for t in figure.data}),
        "points_plotted": points,
        "rows_collected": collection.data.height,
    }


@server.tool()
def export_collection(ctx: Context, handle: str, path: str) -> dict:
    """Write the collected frame to `path` (.csv, .parquet or .json)."""
    collection = _collection(_session(ctx), handle)
    target = _resolve(path, must_exist=False)
    suffix = target.suffix.lower()
    target.parent.mkdir(parents=True, exist_ok=True)

    if suffix == ".csv":
        target.write_text(collection.data.write_csv(), encoding="utf-8")
    elif suffix == ".parquet":
        collection.data.write_parquet(target)
    elif suffix == ".json":
        target.write_text(collection.data.write_json(), encoding="utf-8")
    else:
        raise Refused("Write a .csv, .parquet or .json file.")

    return {"path": str(target), "bytes": target.stat().st_size, "rows": collection.data.height}


if __name__ == "__main__":
    server.run(transport="stdio")
