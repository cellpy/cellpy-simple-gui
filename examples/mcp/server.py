# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "cellpy>=2.1.3",
#     "mcp>=2.0",
#     "plotly>=5.22",
# ]
# ///
"""A prototype MCP server for cellpy — enough to prove or disprove the design.

    CELLPY_MCP_ROOT=/path/to/your/data uv run --script examples/mcp/server.py

**This is a prototype, not a product.** It exists to answer questions by
building the thing rather than reasoning about it: first the two in
cellpy-simple-gui#128 — what happens to cellpy's process-global state when the
caller is long-lived and multi-client, and what happens to file access when the
caller is an agent — and then the four audiences raised in jepegit/cellpy#840,
which added the API and templating families and the prompts. See
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
import re
import sys
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
        "Battery cell data via cellpy.\n"
        "- Cells and figures: load cells, collect them into frames, then render "
        "or export. Tools return handles and summaries, never frames — use "
        "preview_collection to see rows, and render/export to produce files.\n"
        "- The API: use search_api and describe_api to answer questions about "
        "how a cellpy call works. Prefer them over recalling a signature; they "
        "read the version that is installed. cellpy leaves many arguments "
        "undocumented, so check undocumented_parameters and read the source "
        "rather than guessing.\n"
        "- Batch projects: list_templates and new_project set up the notebook "
        "template that `cellpy new` produces."
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
    #: Built on first use by `_index()` and then kept: it imports ten modules
    #: and cellpy is not a cheap import.
    api_index: list[dict] | None = None

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


# --------------------------------------------------------------------------- #
# The API surface: answering "how does this work" from the installed package
# --------------------------------------------------------------------------- #
#
# The observation this family exists for: people do not read API documentation.
# Nobody disputes it and no amount of rewriting fixes it, because the cost is
# not the reading — it is knowing a page exists, finding it, and trusting that
# it describes the version installed. An MCP tool removes all three: the
# assistant asks at the moment the question arises, and introspects the package
# actually on the machine.
#
# What it cannot do is invent documentation that was never written. Measured
# over the 44 calls in `docs/api-reference.md` against cellpy 2.1.3:
#
#     no docstring at all                                3
#     one-line docstring                                13
#     has an Args:/Parameters: section            14 of 44
#     parameters named anywhere in their own docstring   100 of 195  (51%)
#
# `CellpyCell.get_cap` takes 23 arguments and documents none of them. So a tool
# that returned the docstring and stopped would answer half the questions put
# to it with a sentence and a shrug. Three things follow, and they are the
# design of this family:
#
#   1. The *signature* is always there. Names, annotations and especially
#      defaults survive when prose does not, so they are returned structured
#      rather than rendered into one string.
#   2. `undocumented_parameters` is returned explicitly. Same principle as
#      `render`'s `trace_types`: the result carries the trap, so a model that
#      would otherwise guess at `categorical_column=` can see that the package
#      never said, and ask for source instead of inventing an answer.
#   3. `include_source` exists because a model reads Python well. It is the
#      honest fallback for the thin half, and it is the one thing a chat user
#      cannot do for themselves — they will not be grepping site-packages.

#: Import is execution, and the caller is a language model acting on text it may
#: have read in a file. `describe_api("os.system")` must not become a way to
#: import arbitrary modules, so resolution is confined to these roots.
API_ROOTS = ("cellpy", "cellpycore")

#: Modules `search_api` indexes. Walking a package imports every submodule it
#: finds — including optional loaders whose third-party dependencies are not
#: installed — so the list is written down instead of discovered.
API_MODULES = (
    "cellpy",
    "cellpy.collect",
    "cellpy.config",
    "cellpy.plotting",
    "cellpy.plotting.registry",
    "cellpy.readers.cellreader",
    "cellpy.utils.batch",
    "cellpy.utils.example_data",
    "cellpy.utils.helpers",
    "cellpy.utils.ica",
)

#: Docstrings can be long (`Collection.plot` is 24 lines) and a tool result is
#: context. Long enough for an Args: section, short enough not to be the reply.
MAX_DOC_CHARS = 4000
MAX_SOURCE_LINES = 200


def _resolve_dotted(path: str):
    """Import as far as the path allows, then getattr the rest — inside API_ROOTS."""
    import importlib

    if path.split(".")[0] not in API_ROOTS:
        joined = " and ".join(API_ROOTS)
        raise Refused(f"{path!r} is not part of cellpy. This tool only describes {joined}.")

    parts = path.split(".")
    for split in range(len(parts), 0, -1):
        try:
            obj = importlib.import_module(".".join(parts[:split]))
        except ImportError:
            continue
        try:
            for attr in parts[split:]:
                obj = getattr(obj, attr)
        except AttributeError:
            continue
        return obj
    raise Refused(f"Nothing called {path!r} in cellpy.")


def _index() -> list[dict]:
    """Every public callable in API_MODULES, built once and kept."""
    import importlib
    import inspect

    if _STATE.api_index is not None:
        return _STATE.api_index

    # Re-exports are the norm in cellpy: `get` is reachable as `cellpy.get` and
    # `cellpy.readers.cellreader.get`, and `CellpyCell` is re-exported by
    # `utils.helpers`, which is how the first version of this answered
    # "get_cap" with `cellpy.utils.helpers.CellpyCell.get_cap` — a true path
    # that sends the reader to the wrong file. So index by object identity and
    # keep one path each: the shortest, because that is the one people type,
    # and on a tie the one under the module that actually defines it.
    best: dict[int, tuple[tuple[int, int], str, Any]] = {}

    def offer(path: str, entity: Any) -> None:
        home = getattr(entity, "__module__", "") or ""
        rank = (len(path.split(".")), 0 if path.startswith(home) else 1)
        current = best.get(id(entity))
        if current is None or rank < current[0]:
            best[id(entity)] = (rank, path, entity)

    for module_name in API_MODULES:
        try:
            module = importlib.import_module(module_name)
        except Exception:  # noqa: BLE001 - a module that will not import is not an error here
            continue
        for name, obj in vars(module).items():
            if name.startswith("_") or not callable(obj):
                continue
            # Anything that merely passed through from outside cellpy (pandas,
            # pathlib) is not ours to describe.
            if not (getattr(obj, "__module__", "") or "").startswith(API_ROOTS):
                continue

            offer(f"{module_name}.{name}", obj)
            if isinstance(obj, type):
                for attr in vars(obj):
                    member = getattr(obj, attr, None)
                    if not attr.startswith("_") and callable(member):
                        offer(f"{module_name}.{name}.{attr}", member)

    entries = [
        {
            "path": path,
            "name": path.rsplit(".", 1)[-1],
            "summary": _summarise(inspect.getdoc(entity) or ""),
        }
        for _rank, path, entity in best.values()
    ]
    entries.sort(key=lambda e: e["path"])
    _STATE.api_index = entries
    return entries


#: ``See :func:`cellpy.readers.capacity_curves.get_cap` `` and friends.
_REFERENCE = re.compile(r":(?:func|meth|obj|class):`~?([\w.]+)`")


def _follow_reference(doc: str) -> tuple[str | None, str]:
    """Resolve a Sphinx cross-reference in `doc` to the docstring it points at.

    This is the single biggest win in the family, and it is worth saying why.
    `CellpyCell.get_cap` takes 23 arguments, documents none of them, and its
    whole docstring is "Gets the capacity for the run. See
    :func:`cellpy.readers.capacity_curves.get_cap`." The delegate documents 22
    of its 24 in a full ``Args:`` block.

    So the documentation is not missing — it is one hop away, behind a marker
    that only a docs *site* resolves. Anyone reading the docstring where it is
    actually met — an IDE tooltip, `help()`, a chat window — sees the pointer
    and not the text. Following it here is what turns the worst-documented call
    in cellpy into a fully documented one.
    """
    import inspect

    match = _REFERENCE.search(doc)
    if not match:
        return None, ""
    target = match.group(1)
    if target.split(".")[0] not in API_ROOTS:
        return None, ""
    try:
        referenced = _resolve_dotted(target)
    except Exception:  # noqa: BLE001 - a dead reference is not an error
        return None, ""
    referenced_doc = inspect.getdoc(referenced) or ""
    # A reference that resolves back to the same docstring says nothing.
    if not referenced_doc or referenced_doc == doc:
        return None, ""
    return target, referenced_doc


def _summarise(doc: str) -> str:
    """The first line of a docstring that says something.

    `CellpyCell.set_mass` opens with a bare ``Warning:``, so taking line one
    verbatim produces an index in which several unrelated calls are described
    as "Warning:". A heading is carried into the line below it instead.
    """
    lines = [line.strip() for line in doc.strip().splitlines() if line.strip()]
    if not lines:
        return ""
    first = lines[0]
    if first.endswith(":") and len(first) < 24 and len(lines) > 1:
        return f"{first} {lines[1]}"
    return first


@server.tool()
def search_api(query: str, limit: int = 15) -> dict:
    """Find cellpy calls by name, or by what their first docstring line says.

    Use this when you know the task but not the call — "average cycles",
    "loading", "mass". `describe_api` then gives the arguments.
    """
    if not query.strip():
        raise Refused("Give something to search for.")
    needle = query.strip().lower()
    limit = max(1, min(int(limit), 50))

    scored: list[tuple[int, dict]] = []
    for entry in _index():
        name = entry["name"].lower()
        if needle == name:
            score = 0
        elif needle in name:
            score = 1
        elif needle in entry["path"].lower():
            score = 2
        elif needle in entry["summary"].lower():
            score = 3
        else:
            continue
        scored.append((score, entry))

    scored.sort(key=lambda pair: (pair[0], len(pair[1]["path"])))
    return {
        "query": query,
        "indexed": len(_index()),
        "matches": [entry for _score, entry in scored[:limit]],
        "truncated": len(scored) > limit,
    }


@server.tool()
def describe_api(name: str, include_source: bool = False) -> dict:
    """What a cellpy call takes and what it does, from the installed package.

    `name` is a dotted path (`cellpy.get`, `cellpy.collect.collect_summary`) or
    a bare name (`get_cap`) looked up in the index.

    Read `undocumented_parameters` before answering a question about one of
    them. cellpy documents roughly half its arguments, so an argument missing
    from `doc` means the package never said what it does — not that it does not
    matter. Ask again with `include_source=True` rather than guessing.

    When `delegates_to` is set, the docstring pointed at another call with a
    Sphinx reference and `delegate_doc` is where the arguments are actually
    described — read it, it is usually the real documentation.
    """
    import inspect
    import re

    if "." in name:
        # A dotted path is a request to import. `_resolve_dotted` is the guard,
        # so send every dotted name through it rather than quietly falling back
        # to the index and reporting "no such cellpy call" for `os.system` —
        # true, but the wrong reason, and the wrong reason teaches the caller
        # that a different spelling might work.
        path = name
        obj = _resolve_dotted(path)
    else:
        matches = [e for e in _index() if e["name"] == name]
        if not matches:
            hits = search_api(name, limit=5)["matches"]
            suffix = ""
            if hits:
                suffix = " Did you mean: " + ", ".join(h["path"] for h in hits) + "?"
            raise Refused(f"No cellpy call called {name!r}.{suffix}")
        matches.sort(key=lambda e: len(e["path"]))
        path = matches[0]["path"]
        obj = _resolve_dotted(path)

    doc = inspect.getdoc(obj) or ""
    delegate_path, delegate_doc = _follow_reference(doc)
    # A parameter counts as documented if *either* docstring names it.
    searchable = doc + "\n" + delegate_doc

    if isinstance(obj, type):
        kind = "class"
    elif isinstance(obj, property):
        kind = "property"
    else:
        kind = "function"

    target = obj.fget if isinstance(obj, property) else obj
    parameters: list[dict] = []
    signature_text = None
    try:
        signature = inspect.signature(target)
    except (TypeError, ValueError):
        signature = None

    if signature is not None:
        # Methods are shown as you would call them. Leaving `self` in the
        # rendered signature invites a model to pass it as an argument.
        rendered = str(signature)
        if rendered.startswith("(self, "):
            rendered = "(" + rendered[len("(self, ") :]
        elif rendered == "(self)":
            rendered = "()"
        signature_text = f"{path.rsplit('.', 1)[-1]}{rendered}"
        for pname, parameter in signature.parameters.items():
            if pname in ("self", "cls"):
                continue
            empty = inspect.Parameter.empty
            variadic = (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD)
            parameters.append(
                {
                    "name": pname,
                    "annotation": (
                        None if parameter.annotation is empty else str(parameter.annotation)
                    ),
                    "default": (
                        None if parameter.default is empty else repr(parameter.default)
                    ),
                    "required": parameter.default is empty and parameter.kind not in variadic,
                    "documented": bool(re.search(rf"\b{re.escape(pname)}\b", searchable)),
                }
            )

    result: dict[str, Any] = {
        "path": path,
        "kind": kind,
        "module": getattr(obj, "__module__", None),
        "signature": signature_text,
        "parameters": parameters,
        "doc": doc[:MAX_DOC_CHARS] + ("…" if len(doc) > MAX_DOC_CHARS else ""),
        # The trap, carried in the result rather than left to be discovered.
        "undocumented_parameters": [p["name"] for p in parameters if not p["documented"]],
    }
    if delegate_path:
        result["delegates_to"] = delegate_path
        result["delegate_doc"] = delegate_doc[:MAX_DOC_CHARS] + (
            "…" if len(delegate_doc) > MAX_DOC_CHARS else ""
        )

    if include_source:
        try:
            source = inspect.getsource(target)
        except (OSError, TypeError) as exc:
            result["source_error"] = str(exc)
        else:
            lines = source.splitlines()
            result["source"] = "\n".join(lines[:MAX_SOURCE_LINES])
            result["source_truncated"] = len(lines) > MAX_SOURCE_LINES

    return result


# --------------------------------------------------------------------------- #
# Batch templating: `cellpy new` for people who will not open a terminal
# --------------------------------------------------------------------------- #
#
# `cellpy new` is the front door to the batch workflow and it is a CLI command,
# which puts it behind a terminal for exactly the users who most need a
# template. Wrapping it is therefore worth more than it looks — but it is a
# *write* primitive that creates a directory tree and downloads a cookiecutter,
# so it gets the same sandbox as `render` and `export_collection`.
#
# Measured against cellpy 2.1.3: `create_project(..., no_input=True)` is *not*
# non-interactive. When the project directory does not exist,
# `cli_api.py:1601` calls `cookiecutter.prompt.read_user_yes_no("… Create?")`
# unconditionally — outside the `no_input` guard — and an MCP server has no
# stdin to answer with. Under stdio it does not even hang usefully: it raises
# `ValueError: I/O operation on closed file`.
#
# So `new_project` creates the directory itself and then calls in, which skips
# that branch and completes with no prompt at all (verified: six notebooks and
# a data/ tree). The upstream fix is one line — honour `no_input` at 1601 — and
# until it lands this workaround is the whole reason the tool works.


@server.tool()
def list_templates() -> dict:
    """Batch templates available for `new_project`, registered and local.

    `cellpy new --list` prints this; there is no library form that returns it,
    so this reads the registry directly.
    """
    from cellpy import cli_api
    from cellpy.utils.template_registry import REGISTERED_TEMPLATES

    try:
        default = str(cli_api._get_default_template())
    except Exception as exc:  # noqa: BLE001 - report it, do not fail the call
        default = f"unknown ({exc})"

    try:
        local = {name: str(link) for name, link in (cli_api._read_local_templates() or {}).items()}
    except Exception:  # noqa: BLE001
        local = {}

    return {
        "default": default,
        "registered": sorted(REGISTERED_TEMPLATES),
        "local": sorted(local),
    }


@server.tool()
def new_project(
    project: str,
    experiment: str,
    template: str | None = None,
    directory: str | None = None,
) -> dict:
    """Create a batch project from a template — the `cellpy new` workflow.

    `project` is the folder, `experiment` the lookup value; the template dates
    the experiment folder itself, so `experiment="exp001"` becomes something
    like `2026_09_05_exp001`. Writes inside the data directory only.

    Downloads the cookiecutter from GitHub on first use.
    """
    from cellpy import cli_api

    if not project.strip() or not experiment.strip():
        raise Refused("Both a project name and an experiment name are needed.")
    for value in (project, experiment):
        if "/" in value or "\\" in value or value.strip() in (".", ".."):
            raise Refused(f"{value!r} is not a folder name.")

    base = _resolve(directory, must_exist=True) if directory else ROOT
    target = _resolve(str(base / project), must_exist=False)
    existed = target.is_dir()
    # See the note above: creating it here is what keeps `cellpy new` from
    # asking a question the server cannot answer.
    target.mkdir(parents=True, exist_ok=True)

    before = {p.name for p in target.iterdir()}
    try:
        cli_api.create_project(
            template,
            directory=str(base),
            project=project,
            experiment=experiment,
            no_input=True,
        )
    except Exception as exc:  # noqa: BLE001 - the model should read the reason
        if not existed and not any(target.iterdir()):
            target.rmdir()
        raise Refused(f"Could not create the project: {type(exc).__name__}: {exc}")

    created = sorted({p.name for p in target.iterdir()} - before)
    notebooks = sorted(str(p.relative_to(target)) for p in target.rglob("*.ipynb"))
    return {
        "project_dir": str(target),
        "created": created,
        "notebooks": notebooks,
        "template": template or "default",
        # A chat user cannot be left with a folder and no next step.
        "next_step": f"cellpy serve --directory {target}",
    }


# --------------------------------------------------------------------------- #
# Prompts: the chat user's entry point
# --------------------------------------------------------------------------- #
#
# Tools serve someone who already knows what they want. The user who opens a
# chat window and asks it to "do the cell processing" does not, and the gap is
# not knowledge of cellpy — it is not knowing that any of this is here.
#
# Prompts are the part of MCP that addresses that: a client renders them as
# named, pickable starting points, so the capability advertises itself instead
# of waiting to be asked for. Cheap to add and the only piece of the protocol
# aimed squarely at the non-technical group.


@server.prompt(title="Analyse a cell file")
def analyse_cell(path: str, mass_mg: str = "") -> str:
    """Load one cell and produce the standard set of plots."""
    mass = (
        f"Its active-material mass is {mass_mg} mg — pass it to load_cell."
        if mass_mg.strip()
        else (
            "No mass was given. Ask for it before reporting any gravimetric "
            "number: without it cellpy computes against a default of 1.0 mg and "
            "the capacities look plausible and are wrong."
        )
    )
    return (
        f"Analyse the battery cell at {path!r}.\n\n{mass}\n\n"
        "Work in this order:\n"
        "1. load_cell, and tell me the cycle count and the mass you used.\n"
        "2. describe_plot_families, and say which are unavailable and why.\n"
        "3. collect the summary and render capacity-vs-cycle and coulombic "
        "efficiency to html files next to the data.\n"
        "4. Report what the curves do — capacity fade, any outlying cycles — "
        "in plain language, and name the files you wrote."
    )


@server.prompt(title="Start a batch project")
def start_batch_project(project: str = "", experiment: str = "") -> str:
    """Set up the notebook template for a new set of experiments."""
    named = (
        f"Call it {project!r}, experiment {experiment!r}."
        if project.strip() and experiment.strip()
        else "Ask me for a project name and an experiment name first."
    )
    return (
        f"Set up a new cellpy batch project. {named}\n\n"
        "Use list_templates to show me the options and say which is the "
        "default, then new_project. Afterwards, list the notebooks it made, "
        "say in one line each what they are for, and give me the single "
        "command that opens them."
    )


@server.prompt(title="How does a cellpy call work?")
def explain_call(name: str) -> str:
    """Explain a cellpy function: arguments, defaults, and the traps."""
    return (
        f"Explain how {name!r} works in cellpy.\n\n"
        "Use describe_api. Give me the arguments that matter with their "
        "defaults, and a short worked example. If the call has "
        "undocumented_parameters that bear on my question, read the source "
        "with include_source=True rather than guessing — and say which parts "
        "of your answer came from the source rather than the documentation."
    )


# --------------------------------------------------------------------------- #
# Launching it
# --------------------------------------------------------------------------- #
#
# The deployment constraint is that there is no deployment: no Azure, no AWS,
# no budget for either. That is less of a limitation than it sounds, because
# stdio needs no server at all — the client spawns the process. What it does
# need is for someone to write a JSON block into a config file, which is a
# worse ask than the terminal we were trying to avoid.
#
# `--install` writes the block. In a shipped cellpy it belongs behind a
# subcommand (see the design doc for the `cellpy mcp` proposal); here it is
# argparse, to prove the ergonomics are one command rather than a paragraph of
# instructions.


def _client_config_path() -> Path:
    """Where Claude Desktop keeps its MCP server list, per platform."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
        return base / "Claude" / "claude_desktop_config.json"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def _install(root: Path, dry_run: bool = False) -> int:
    """Merge a `cellpy` entry into the client config, leaving the rest alone."""
    import json

    target = _client_config_path()
    config: dict[str, Any] = {}
    if target.exists():
        try:
            config = json.loads(target.read_text(encoding="utf-8")) or {}
        except json.JSONDecodeError as exc:
            print(f"refusing to overwrite unparseable {target}: {exc}", file=sys.stderr)
            return 1

    entry = {
        "command": sys.executable,
        "args": [str(Path(__file__).resolve())],
        "env": {"CELLPY_MCP_ROOT": str(root)},
    }
    servers = config.setdefault("mcpServers", {})
    replaced = "cellpy" in servers
    servers["cellpy"] = entry

    rendered = json.dumps(config, indent=2)
    if dry_run:
        # Only the block being added. The file also holds the rest of someone's
        # client settings, and printing all of it to prove one entry is both
        # noise and a small privacy leak into whatever captured the output.
        print(f"# would {'replace' if replaced else 'add'} 'cellpy' in {target}")
        print(json.dumps({"mcpServers": {"cellpy": entry}}, indent=2))
        return 0

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered + "\n", encoding="utf-8")
    print(f"{'updated' if replaced else 'added'} 'cellpy' in {target}")
    print(f"data directory: {root}")
    print("restart the client to pick it up.")
    return 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="cellpy MCP server (prototype).")
    parser.add_argument(
        "--install",
        action="store_true",
        help="register this server with Claude Desktop instead of running it",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="with --install, print the config instead of writing it",
    )
    args = parser.parse_args()

    if args.install:
        raise SystemExit(_install(ROOT, dry_run=args.dry_run))

    server.run(transport="stdio")
