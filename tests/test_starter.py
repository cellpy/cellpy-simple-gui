"""The starter app in ``examples/starter/`` (#125).

The starter is documentation that runs, which is the only kind worth writing —
but it also means it rots exactly like documentation unless something exercises
it. Nothing in the package imports it, so without these tests a cellpy API
change would break the first thing a newcomer runs and pass CI while doing it.

Two of these tests are about the *promises the README makes* rather than about
behaviour: that adding a plot is one line, and that the dependency header is
complete enough for ``uv run --script`` to work outside this repository.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import re
import sys
import tomllib
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

pytestmark = pytest.mark.essential

STARTER = Path(__file__).resolve().parents[1] / "examples" / "starter" / "app.py"


@pytest.fixture()
def starter():
    """The starter imported as a module, with no cells loaded."""
    spec = importlib.util.spec_from_file_location("starter_app", STARTER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.CELLS.clear()
    return module


@pytest.fixture()
def with_cell(starter, example_cell):
    starter.CELLS["demo"] = example_cell
    return starter


# --- the four calls the README promises ------------------------------------- #


def test_the_whole_arc(with_cell):
    """Load -> collect -> plot -> export, which is the entire point of the file."""
    collection = with_cell.collection_for("Capacity")

    # A Collection is a polars frame that knows how to draw itself.
    assert collection.data.height > 0
    assert "cycle_num" in collection.data.columns
    assert "charge_capacity_gravimetric" in collection.data.columns

    figure = json.loads(with_cell.figure_json("Capacity"))
    assert len(figure["data"]) == 2  # charge and discharge

    csv = with_cell.export_csv("Capacity").decode()
    # The download matches the chart because both come from the same Collection.
    assert csv.count("\n") == collection.data.height + 1


def test_voltage_curves_are_a_different_collector(with_cell):
    """Curves come from ``collect_cycles``, not from another column list."""
    collection = with_cell.collection_for(with_cell.CYCLE_CURVES, cycles=(1, 5))
    assert {"potential", "capacity"} <= set(collection.data.columns)
    assert sorted(collection.data["cycle_num"].unique().to_list()) == [1, 5]


# --- the promises the README makes ------------------------------------------ #


def test_adding_a_plot_is_one_line(with_cell):
    """The README's worked example, run.

    If this ever needs a second edit somewhere else, the walkthrough in
    ``examples/starter/README.md`` has become a lie and both need fixing.
    """
    with_cell.SUMMARY_PLOTS["C-rate"] = ("charge_c_rate", "discharge_c_rate")

    assert "C-rate" in with_cell.state()["plots"]
    figure = json.loads(with_cell.figure_json("C-rate"))
    assert len(figure["data"]) == 2
    assert with_cell.export_csv("C-rate")


def test_the_dependency_header_covers_every_import(starter):
    """``uv run --script app.py`` has to work outside this repository.

    The PEP 723 header is the only thing standing between "one file you can copy
    anywhere" and "one file that only runs in the repo it came from", and it is
    the sort of thing that silently falls behind an added import.

    Names are compared bare, which holds only while every dependency's import
    name equals its distribution name. If that stops being true, add a mapping
    here rather than deleting the test.
    """
    source = STARTER.read_text(encoding="utf-8")
    block, _, _ = source.split("# /// script\n", 1)[1].partition("# ///")
    metadata = tomllib.loads("".join(line[2:] for line in block.splitlines(True)))
    declared = {
        re.match(r"[A-Za-z0-9._-]+", requirement).group().lower()
        for requirement in metadata["dependencies"]
    }

    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported.add(node.module.split(".")[0])

    third_party = {name for name in imported if name not in sys.stdlib_module_names}
    assert third_party <= declared, f"undeclared: {sorted(third_party - declared)}"


def test_it_stays_small_enough_to_read(starter):
    """Size is the feature. The reference implementation is the other artifact.

    A generous ceiling — the point is to catch the starter quietly growing into
    a second application, not to police a diff.
    """
    assert len(STARTER.read_text(encoding="utf-8").splitlines()) < 400


# --- the things that go wrong ------------------------------------------------ #


def test_a_column_the_cells_lack_is_refused_not_drawn_empty(with_cell):
    """cellpy draws an empty chart for a missing column rather than raising."""
    with_cell.SUMMARY_PLOTS["Invented"] = ("no_such_column",)
    with pytest.raises(HTTPException) as raised:
        with_cell.collection_for("Invented")
    assert "no_such_column" in raised.value.detail


def test_no_cells_and_no_such_plot_are_different_answers(starter):
    with pytest.raises(HTTPException) as empty:
        starter.collection_for("Capacity")
    assert empty.value.status_code == 400

    starter.CELLS["pretend"] = object()
    with pytest.raises(HTTPException) as unknown:
        starter.collection_for("Not a plot")
    assert unknown.value.status_code == 404


def test_a_file_that_will_not_load_says_which_one(starter):
    with TestClient(starter.app) as client:
        res = client.post("/api/cells", json={"paths": ["/nowhere/ghost.res"]})
    assert res.status_code == 400
    assert "ghost.res" in res.json()["detail"]
    assert not starter.CELLS


def test_two_cells_of_one_name_are_two_cells(starter, example_cell):
    for _ in range(2):
        starter._remember("same", example_cell)
    assert list(starter.CELLS) == ["same", "same (2)"]


# --- the served surface ------------------------------------------------------ #


def test_the_page_and_the_api_agree_on_what_can_be_plotted(with_cell):
    with TestClient(with_cell.app) as client:
        plots = client.get("/api/state").json()["plots"]
        assert plots[-1] == with_cell.CYCLE_CURVES

        figure = client.get("/api/figure", params={"plot": plots[0]})
        assert figure.status_code == 200
        assert figure.json()["data"]

        csv = client.get("/api/export.csv", params={"plot": plots[0]})
        assert csv.status_code == 200
        assert "attachment" in csv.headers["content-disposition"]
