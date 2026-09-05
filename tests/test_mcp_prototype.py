"""Drive the MCP prototype over the real protocol (#128).

A prototype exists to answer questions, and an unrun prototype answers none. So
this loads `examples/mcp/server.py`, connects an in-process MCP client to it,
and calls the tools the way a client would — rather than calling the functions,
which would skip the schema generation, the argument validation and the error
wrapping that are most of what the SDK does.

Skips when `mcp` is absent (`uv sync --extra mcp`). It is an optional extra
because this is a prototype, not something the app depends on.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp", reason="prototype only: uv sync --extra mcp")

pytestmark = pytest.mark.essential

SERVER = Path(__file__).resolve().parents[1] / "examples" / "mcp" / "server.py"


@pytest.fixture()
def prototype(tmp_path, monkeypatch, example_cell):
    """The server module, with its sandbox pointed at a temp directory.

    `ROOT` is read at import time, so the environment has to be set first and the
    module imported fresh — the same import-time-resolution shape that made
    cellpy's `examplesdir` such a nuisance (§33).
    """
    from cellpy.utils import example_data

    root = tmp_path / "sandbox"
    root.mkdir()
    shutil.copy(example_data.cellpy_file_path(), root / "demo.cellpy")
    monkeypatch.setenv("CELLPY_MCP_ROOT", str(root))

    spec = importlib.util.spec_from_file_location("mcp_prototype", SERVER)
    module = importlib.util.module_from_spec(spec)
    sys.modules["mcp_prototype"] = module
    spec.loader.exec_module(module)
    module._STATE.cells.clear()
    module._STATE.collections.clear()
    return module, root


def drive(prototype, steps):
    """Run `steps(call)` against a connected client; return whatever it returns."""
    module, _root = prototype
    from mcp import Client

    async def main():
        async with Client(module.server) as client:
            # `tool`, not `name`: `describe_api` takes an argument called
            # `name`, and a positional parameter of the same name here makes
            # `call("describe_api", name=...)` a TypeError rather than a call.
            async def call(tool, **arguments):
                result = await client.call_tool(tool, arguments)
                text = "".join(getattr(b, "text", "") for b in (result.content or []))
                if getattr(result, "is_error", False):
                    return {"refused": text}
                return result.structured_content or json.loads(text)

            return await steps(call)

    return asyncio.run(main())


def test_the_whole_arc_over_the_protocol(prototype):
    """Load -> collect -> render -> export, as a client actually does it."""
    _module, root = prototype

    async def steps(call):
        cell = await call("load_cell", path="demo.cellpy", mass_mg=0.29)
        ica = await call("collect", kind="ica", cycles=[1, 5, 10])
        figure = await call(
            "render", handle=ica["handle"], path="out/film.json",
            kind="film", direction="both",
        )
        data = await call("export_collection", handle=ica["handle"], path="out/ica.csv")
        return cell, ica, figure, data

    cell, ica, figure, data = drive(prototype, steps)

    assert cell["cycles"] == 304
    assert cell["mass_was_supplied"] is True
    # Names only — the frame must not travel.
    assert "summary_columns" in cell and "rows" not in cell

    # The direction counts are reported so an agent can notice a partial plot.
    assert set(ica["directions"]) == {"charge", "discharge"}

    # A film is a *kind*; the result says which it got rather than hoping.
    assert figure["trace_types"] == ["histogram2d"]
    assert figure["points_plotted"] == ica["rows"], "direction='both' should draw everything"
    assert (root / "out" / "film.json").is_file()
    assert (root / "out" / "ica.csv").is_file()
    assert data["rows"] == ica["rows"]


def test_a_default_direction_plot_says_it_drew_less(prototype):
    """The trap made visible: fewer points than rows, reported rather than hidden."""

    async def steps(call):
        await call("load_cell", path="demo.cellpy")
        ica = await call("collect", kind="ica", cycles=[1, 5, 10])
        return ica, await call("render", handle=ica["handle"], path="out/f.json", kind="film")

    ica, figure = drive(prototype, steps)
    assert figure["points_plotted"] < figure["rows_collected"] == ica["rows"]


def test_no_tool_returns_a_frame(prototype):
    """Only preview returns rows, and it caps whatever it is asked for."""

    async def steps(call):
        await call("load_cell", path="demo.cellpy")
        collected = await call(
            "collect", kind="summary", columns=["discharge_capacity_gravimetric"]
        )
        return collected, await call(
            "preview_collection", handle=collected["handle"], rows=10_000
        )

    collected, preview = drive(prototype, steps)
    assert collected["rows"] == 304
    assert preview["rows_shown"] == 20  # MAX_PREVIEW_ROWS, not 10_000
    assert preview["rows_total"] == 304
    assert len(preview["records"]) == 20


def test_availability_is_answered_rather_than_discovered_by_drawing(prototype):
    async def steps(call):
        blind = await call("describe_plot_families")
        await call("load_cell", path="demo.cellpy")
        return blind, await call("describe_plot_families")

    blind, described = drive(prototype, steps)
    assert "refused" in blind, "availability depends on data; say so"

    families = described["families"]
    assert len(families) == 20
    unavailable = [f for f in families if not f["available"]]
    assert unavailable, "the demo cell genuinely lacks the *_absolute columns"
    assert all("missing_columns" in f for f in unavailable), "name what is missing"


@pytest.mark.parametrize(
    "hostile",
    [
        "../escape.cellpy",
        "C:/Windows/win.ini",
        r"\\somehost\share\x.cellpy",
        "/etc/passwd",
        "~/secrets.cellpy",
    ],
)
def test_paths_outside_the_sandbox_are_refused(prototype, hostile):
    """The caller is a model acting on text it may have read somewhere."""

    async def steps(call):
        return await call("load_cell", path=hostile)

    result = drive(prototype, steps)
    assert "refused" in result, f"{hostile!r} was not refused"
    assert "outside the data directory" in result["refused"] or "does not exist" in result["refused"]


def test_writes_are_sandboxed_too(prototype):
    """A write primitive outside the boundary would make the read check decor."""

    async def steps(call):
        await call("load_cell", path="demo.cellpy")
        collected = await call(
            "collect", kind="summary", columns=["discharge_capacity_gravimetric"]
        )
        return (
            await call("export_collection", handle=collected["handle"], path="../loot.csv"),
            await call("export_collection", handle=collected["handle"], path="out/x.exe"),
        )

    outside, wrong_kind = drive(prototype, steps)
    assert "outside the data directory" in outside["refused"]
    assert ".csv" in wrong_kind["refused"]


def test_unknown_handles_and_kinds_are_told_what_to_do(prototype):
    """Error text is read by a model, so it has to name the next call."""

    async def steps(call):
        return (
            await call("preview_collection", handle="collection-99"),
            await call("collect", kind="nope"),
        )

    handle, kind = drive(prototype, steps)
    assert "collect" in handle["refused"]
    assert "summary" in kind["refused"] and "ica" in kind["refused"]


def test_the_tool_surface_is_small_and_named_as_documented(prototype):
    """The design doc lists these; drift makes the doc wrong, not the code."""
    module, _root = prototype
    from mcp import Client

    async def main():
        async with Client(module.server) as client:
            return (
                {t.name for t in (await client.list_tools()).tools},
                {p.name for p in (await client.list_prompts()).prompts},
            )

    tools, prompts = asyncio.run(main())
    assert tools == {
        # cells and figures
        "list_instruments",
        "load_cell",
        "list_cells",
        "describe_plot_families",
        "collect",
        "preview_collection",
        "render",
        "export_collection",
        # the API surface, for "how does this call work"
        "search_api",
        "describe_api",
        # batch templating, for people who will not open a terminal
        "list_templates",
        "new_project",
    }
    assert prompts == {"analyse_cell", "start_batch_project", "explain_call"}


def test_describe_api_follows_the_reference_the_docstring_points_at(prototype):
    """The finding this family turns on.

    `CellpyCell.get_cap` takes 23 arguments, documents none of them, and spends
    its one-line docstring on ``See :func:`cellpy.readers.capacity_curves.get_cap```.
    The delegate documents 22 of 24 in a full ``Args:`` block. Following the
    reference is the difference between an unanswerable call and a documented
    one, so it is asserted rather than left to be noticed.
    """

    async def steps(call):
        return await call("describe_api", name="get_cap")

    result = drive(prototype, steps)
    assert result["path"] == "cellpy.readers.cellreader.CellpyCell.get_cap"
    assert result["delegates_to"] == "cellpy.readers.capacity_curves.get_cap"
    assert "Args:" in result["delegate_doc"]
    assert len(result["parameters"]) > 20
    # One stray argument is fine; twenty-three would mean the hop was not made.
    assert len(result["undocumented_parameters"]) <= 2


def test_describe_api_renders_a_method_the_way_you_would_call_it(prototype):
    """`self` in a rendered signature invites a model to pass it."""

    async def steps(call):
        return await call("describe_api", name="get_cap")

    signature = drive(prototype, steps)["signature"]
    assert signature.startswith("get_cap(cycle=")
    assert "self" not in signature
    assert not any(p["name"] in ("self", "cls") for p in drive(prototype, steps)["parameters"])


def test_describe_api_will_not_import_outside_cellpy(prototype):
    """Resolving a dotted path is importing it, and the caller is a model.

    The refusal has to name the actual reason. Falling through to "no such
    cellpy call" would be true of `os.system` and would teach the caller that
    some other spelling might work.
    """

    async def steps(call):
        return (
            await call("describe_api", name="os.system"),
            await call("describe_api", name="subprocess.run"),
            await call("describe_api", name="nonsense_call"),
        )

    system, subprocess_run, missing = drive(prototype, steps)
    assert "not part of cellpy" in system["refused"]
    assert "not part of cellpy" in subprocess_run["refused"]
    assert "No cellpy call" in missing["refused"]


def test_search_api_points_at_the_module_that_defines_the_call(prototype):
    """`utils.helpers` re-exports `CellpyCell`; a path through it sends the
    reader to the wrong file. Identity-deduping the index is what fixes it."""

    async def steps(call):
        return await call("search_api", query="get_mass")

    result = drive(prototype, steps)
    paths = [m["path"] for m in result["matches"]]
    assert "cellpy.readers.cellreader.CellpyCell.get_mass" in paths
    assert not any("utils.helpers" in p for p in paths)
    assert result["indexed"] > 100


def test_new_project_refuses_before_it_writes_anything(prototype):
    """The happy path downloads a cookiecutter from GitHub, so CI tests the
    boundary — which is reached before any network call — and the design doc
    records the verified happy path."""
    _module, root = prototype

    async def steps(call):
        return (
            await call("new_project", project="../escape", experiment="e1"),
            await call("new_project", project="ok", experiment=""),
            # `..`, not `C:/Windows`: on posix a drive-lettered path is
            # *relative*, so it lands inside the sandbox and is refused for
            # not existing — which passes for the wrong reason and only on
            # Windows. `..` is outside the root on both platforms.
            await call("new_project", project="ok", experiment="e1", directory=".."),
        )

    escape, empty, outside = drive(prototype, steps)
    assert "not a folder name" in escape["refused"]
    assert "needed" in empty["refused"]
    assert "outside the data directory" in outside["refused"]
    # Nothing was created on the way to refusing.
    assert not (root / "ok").exists()
    assert not (root / "escape").exists()
