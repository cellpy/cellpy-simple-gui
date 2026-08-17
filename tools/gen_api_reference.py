"""Generate `docs/api-reference.md` from the installed cellpy (#127).

The list of calls that matter is a judgement and is written down here. Their
*signatures* are not: those are introspected from whatever cellpy is installed,
so the reference cannot quietly describe a version nobody is running.

    uv run tools/gen_api_reference.py            # rewrite the file
    uv run tools/gen_api_reference.py --check    # exit 1 if it is out of date

`tests/test_api_reference.py` runs the check, so a cellpy upgrade that changes a
signature fails CI until the reference is regenerated.
"""

from __future__ import annotations

import argparse
import dataclasses
import inspect
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "docs" / "api-reference.md"

#: The Claude Skill carries its own copy so it still works once someone has
#: installed it somewhere else, with no network and no clone. Same bytes,
#: generated from the same run, so the two cannot disagree.
SKILL_COPY = ROOT / "skills" / "cellpy-app" / "reference" / "api-reference.md"

#: (dotted path, one-line semantics). The path is resolved and introspected; the
#: sentence is the part a signature cannot tell you. Grouped by task, in the same
#: order as `docs/guides/`.
SECTIONS: list[tuple[str, str, list[tuple[str, str]]]] = [
    (
        "Loading",
        "Getting cells into memory — [guide 1](guides/01-loading-cells.md).",
        [
            ("cellpy.get", "The one entry point. Only `filename` is required; `mass` / `area` / `nominal_capacity` accept unit strings such as `\"0.47 mg\"`."),
            ("cellpy.list_instruments", "Loaders registered at runtime: `{id, label, models, suffixes}`. Registered is not the same as usable on this machine."),
            ("cellpy.read_meta", "Metadata without loading the data — **cellpy files only**; a raw file gives an HDF5 traceback."),
            ("cellpy.instrument_meta_schema", "Fields an instrument wants (`name`, `required`, `type`, `unit`, `maps_to`, `help`) — enough to generate an ingestion form."),
            ("cellpy.utils.example_data.cellpy_file", "A loaded demo cell (304 cycles). Downloads once, then caches."),
            ("cellpy.utils.example_data.cellpy_file_path", "Path to the same file, for when you want to call `cellpy.get` yourself."),
            ("cellpy.utils.example_data.rate_file", "**A path, not a cell** — unlike `cellpy_file()`. Passing it where a cell is expected fails silently."),
            ("cellpy.utils.example_data.neware_file_path", "A raw Neware export (`.csv`) that loads with no external tooling."),
            ("cellpy.utils.example_data.arbin_file_path", "A raw Arbin `.res` — needs mdbtools or the Access driver to load."),
        ],
    ),
    (
        "One cell",
        "`CellpyCell` — what you get back from `cellpy.get`.",
        [
            ("cellpy.readers.cellreader.CellpyCell.get_cycle_numbers", "The cycle numbers present, optionally filtered by rate."),
            ("cellpy.readers.cellreader.CellpyCell.get_cap", "Capacity/voltage curve for one cycle or several, as **pandas**."),
            ("cellpy.readers.cellreader.CellpyCell.save", "Write a `.cellpy` file. Atomic since 2.1.2a4 — staged write plus `os.replace`."),
            ("cellpy.readers.cellreader.CellpyCell.to_csv", "Write raw / steps / summary as separate CSVs into a directory."),
            ("cellpy.readers.cellreader.CellpyCell.to_excel", "Write one workbook."),
            ("cellpy.readers.cellreader.CellpyCell.refresh_after", "Rebuild only what a metadata edit invalidated, instead of a full `make_summary()`."),
        ],
    ),
    (
        "Cells into a Collection",
        "The bridge and the four collectors — [guide 2](guides/02-collections.md).",
        [
            ("cellpy.collect.from_cells", "**The call that matters.** Turns `{label: CellpyCell}` into a real `Batch` with no journal on disk. Values that are not cells are dropped silently — validate first."),
            ("cellpy.collect.collect_summaries", "Per-cycle summary values across cells. `group_it=True` averages within groups **and changes the frame's schema**."),
            ("cellpy.collect.collect_cycles", "Voltage/capacity curves for chosen cycles, isolated per cell."),
            ("cellpy.collect.collect_ica", "dQ/dV. Keeps both half-cycles in a `direction` column."),
            ("cellpy.collect.collect_dva", "dV/dQ. Same shape as `collect_ica` (2.1.2a4)."),
            ("cellpy.collect.load_collection", "Read a saved collection back."),
        ],
    ),
    (
        "Collect options",
        "Dataclasses passed as `options=`; `.replace(...)` returns a modified copy.",
        [
            ("cellpy.collect.options.SummaryOptions", "For `collect_summaries`. Usually obtained from `family.summary_options(hdr)` rather than built by hand."),
            ("cellpy.collect.options.CurveOptions", "For `collect_cycles` — `cycles`, plus `mode` and `method` so you need not slice afterwards."),
            ("cellpy.collect.options.IcaOptions", "For `collect_ica` / `collect_dva` — `cycles` and the resolutions."),
        ],
    ),
    (
        "The Collection",
        "A polars frame that knows how to draw itself — [guides 3](guides/03-plotting.md) and [4](guides/04-exporting.md).",
        [
            ("cellpy.collect.collection.Collection.plot", "Returns a real plotly `Figure`. Takes `layout_updates`, `height_per_panel`, `spread`, `layout` **and `kind`**."),
            ("cellpy.collect.collection.Collection.save", "Write the frame; defaults to parquet + csv, and adds a `.meta.json` sidecar."),
            ("cellpy.collect.collection.Collection.to_image", "Collection straight to image bytes."),
            ("cellpy.collect.collection.Collection.to_wide", "One column per cell, for a spreadsheet."),
            ("cellpy.collect.collection.Collection.is_grouped", "Whether these are averaged series. Decides which schema `.data` has, and whether `spread=True` means anything."),
        ],
    ),
    (
        "The plot registry",
        "Build a menu instead of maintaining one — [guide 3](guides/03-plotting.md).",
        [
            ("cellpy.plotting.registry.families", "`[(name, description)]`. **Pass `entry_point=\"summary_plot\"`** or you list families that can never work in a summary menu."),
            ("cellpy.plotting.registry.get", "One `PlotFamily` by name."),
            ("cellpy.plotting.registry.PlotFamily.summary_options", "**The accessor that matters.** A ready `SummaryOptions` — columns, CV flag, transforms. Judge availability on `.columns` of *this*."),
            ("cellpy.plotting.registry.PlotFamily.columns", "The columns the family *draws*, including ones collect manufactures. Not an availability check."),
        ],
    ),
    (
        "Single-cell plots",
        "Outside the collect path; these take a cell.",
        [
            ("cellpy.utils.plotutils.raw_plot", "Raw traces. **Set `max_points`** — one demo cell is 7.35 MiB of figure JSON without it, 0.18 MiB with."),
            ("cellpy.utils.plotutils.cycle_info_plot", "Raw traces annotated with step/cycle info. **Needs `get_axes=True`** or it returns `None` on the plotly backend."),
            ("cellpy.utils.plotutils.dva_plot", "Single-cell dV/dQ. Prefer `collect_dva` unless you specifically want one cell."),
        ],
    ),
    (
        "Figures to bytes",
        "In-process encoding, no temp file — [guide 4](guides/04-exporting.md).",
        [
            ("cellpy.plotting.figures.write_image", "plotly figure to image bytes. Raises if kaleido is missing **or** if kaleido cannot find a browser — different problems, different advice."),
            ("cellpy.plotting.figures.image_media_type", "MIME type for a format, for an HTTP response."),
        ],
    ),
    (
        "Configuration",
        "The 2.1.2 layered stack — [guide 5](guides/05-configuration.md).",
        [
            ("cellpy.config.get_config", "The resolved settings: `paths`, `reader`, `units`, `instruments`, `db`, `secrets`, …"),
            ("cellpy.config.sources", "`{\"section.field\": layer}` — per-key provenance. This is how you answer \"where did this value come from?\""),
            ("cellpy.config.active_config_file", "Which file the loader actually used, including a legacy `.conf` shadowed by a `cellpy.toml`."),
            ("cellpy.config.override", "Scoped overrides, isolated **per thread and per asyncio task** (contextvars), stacking LIFO."),
            ("cellpy.config.reload", "Re-resolve everything. **Process-global** — use it when you mean process-wide."),
            ("cellpy.config.LoadOptions", "Where to load config from; `project_config_file` is how you pin a project's settings."),
        ],
    ),
]

#: Attributes rather than calls, and the ones people look for most.
ATTRIBUTES = [
    ("cell.data.summary", "pandas", "per-cycle values — the source of every summary column name"),
    ("cell.data.raw", "pandas", "the raw measurement frame"),
    ("cell.data.steps", "pandas", "the step table"),
    ("cell.schema.summary", "`CycleCols`", "the summary column vocabulary — this is the `hdr` argument the registry wants"),
    ("cell.cell_name / .mass / .nominal_capacity / .active_electrode_area", "", "cell metadata"),
    ("collection.data", "polars", "the numbers behind the figure"),
]


def resolve(path: str):
    """Import as far as possible, then getattr the rest."""
    import importlib

    parts = path.split(".")
    for split in range(len(parts) - 1, 0, -1):
        try:
            obj = importlib.import_module(".".join(parts[:split]))
        except ImportError:
            continue
        for attr in parts[split:]:
            obj = getattr(obj, attr)
        return obj
    raise ImportError(path)


#: Renderings that differ between Python versions rather than between cellpy
#: versions. Left alone, they make the file interpreter-dependent: CI runs the
#: tests on two Pythons, and the same cellpy would produce two different
#: references — a diff that says nothing about cellpy and fails anyway.
#: Normalising to the modern spelling also removes `pathlib._local`, which is
#: private and has no business in a reference.
_NORMALISE = (
    (re.compile(r"\bpathlib\._local\."), "pathlib."),
    (re.compile(r"\bOptional\[([^\[\]]+)\]"), r"\1 | None"),
    (re.compile(r"\bUnion\[([^\[\]]+?), ([^\[\]]+?)\]"), r"\1 | \2"),
)


def normalise(text: str) -> str:
    for pattern, replacement in _NORMALISE:
        text = pattern.sub(replacement, text)
    return text


def display_name(path: str) -> str:
    """How you would write the call: `cellpy.get`, `CellpyCell.get_cap`.

    A reference that renders a bare `get(...)` makes the reader go and find out
    where it lives, which is the exact cost this file exists to remove.
    """
    parts = path.split(".")
    if len(parts) > 1 and parts[-2][:1].isupper():
        return ".".join(parts[-2:])
    return path


def describe(path: str) -> str:
    """A one-line rendering of what this thing is, from the live object."""
    obj = resolve(path)
    name = display_name(path)

    if isinstance(obj, property):
        return f"{name}  ->  property"
    if dataclasses.is_dataclass(obj) and isinstance(obj, type):
        fields = ", ".join(f.name for f in dataclasses.fields(obj))
        return f"{name}({fields})"
    if callable(obj):
        try:
            signature = str(inspect.signature(obj))
        except (TypeError, ValueError):
            return name
        # Methods are shown as you would call them, without `self`.
        if signature.startswith("(self, "):
            signature = "(" + signature[len("(self, ") :]
        elif signature == "(self)":
            signature = "()"
        return normalise(f"{name}{signature}")
    return normalise(f"{name}  ->  {type(obj).__name__}")


def render() -> str:
    import cellpy

    version = getattr(cellpy, "__version__", None) or _version()
    lines = [
        "# cellpy API surface",
        "",
        "The calls that matter when building on cellpy, with real signatures and",
        "one line each of what a signature cannot tell you — so you do not have to",
        "grep `site-packages` to find out that `family.summary_options(hdr)` exists.",
        "",
        f"Generated from the installed **cellpy {version}** by",
        "[`tools/gen_api_reference.py`](../tools/gen_api_reference.py); do not edit by",
        "hand. The prose is curated, the signatures are introspected, and",
        "`tests/test_api_reference.py` fails if this file drifts from the installed",
        "package.",
        "",
        "For worked examples see [`docs/guides/`](guides/README.md); for a running",
        "app in one file see [`examples/starter/`](../examples/starter/).",
        "",
    ]

    for title, blurb, entries in SECTIONS:
        lines += [f"## {title}", "", blurb, ""]
        for path, semantics in entries:
            lines += ["```python", describe(path), "```", semantics, ""]

    lines += ["## Attributes worth knowing", "", "| | Type | |", "|---|---|---|"]
    for name, kind, meaning in ATTRIBUTES:
        lines.append(f"| `{name}` | {kind} | {meaning} |")
    lines += [
        "",
        "The frames on a **cell** are pandas; the frame on a **collection** is",
        "polars. Cross the boundary explicitly with `.to_pandas()`, at the edge of",
        "your code rather than in the middle of it.",
        "",
    ]
    return "\n".join(lines)


def _version() -> str:
    from importlib.metadata import version

    return version("cellpy")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 if out of date")
    args = parser.parse_args()

    generated = render()
    targets = (REFERENCE, SKILL_COPY)

    if args.check:
        stale = [
            t.relative_to(ROOT).as_posix()
            for t in targets
            if not t.exists()
            or t.read_text(encoding="utf-8").replace("\r\n", "\n") != generated
        ]
        if stale:
            print(
                f"out of date: {', '.join(stale)} — "
                "run: uv run tools/gen_api_reference.py"
            )
            return 1
        print("api-reference.md is up to date")
        return 0

    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(generated, encoding="utf-8", newline="\n")
        print(f"wrote {target.relative_to(ROOT).as_posix()} ({len(generated.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
