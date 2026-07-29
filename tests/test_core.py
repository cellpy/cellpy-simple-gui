"""Unit tests for the core layer (no web server involved)."""

from __future__ import annotations

import json

from cellpy_simple_gui.core import export, plotting
from cellpy_simple_gui.core.models import CyclesPlotSpec, SummaryPlotSpec


def test_read_meta(example_cell):
    from cellpy_simple_gui.core import cellpy_adapter

    meta = cellpy_adapter.read_meta(example_cell)
    assert meta["name"]
    assert meta["n_cycles"] > 0
    assert meta["mass"] and meta["mass"] > 0


def test_summary_frame_has_expected_columns(example_cell):
    from cellpy_simple_gui.core import cellpy_adapter

    df = cellpy_adapter.summary_frame(example_cell)
    assert "cycle_num" in df.columns
    assert "charge_capacity_gravimetric" in df.columns
    assert "coulombic_efficiency" in df.columns
    assert len(df) > 0


def test_capacity_curve(example_cell):
    from cellpy_simple_gui.core import cellpy_adapter

    curve = cellpy_adapter.capacity_curve(example_cell, cycle=1)
    assert list(curve.columns) == ["capacity", "potential"]
    assert len(curve) > 0


def test_library_lifecycle(loaded_library):
    lib = loaded_library
    assert len(lib) == 1
    rec = lib.all()[0]
    assert rec.selected is True

    lib.update(rec.id, label="my cell", group=3, selected=False)
    rec = lib.get(rec.id)
    assert rec.label == "my cell"
    assert rec.group == 3
    assert rec.selected is False
    assert len(lib.selected()) == 0

    lib.set_selection(True)
    assert len(lib.selected()) == 1

    lib.remove(rec.id)
    assert lib.is_empty()


def test_summary_figure_json(loaded_library):
    spec = SummaryPlotSpec(mode="gravimetric", direction="charge", show_efficiency=True)
    fig = json.loads(plotting.summary_figure(loaded_library.selected(), spec))
    # one capacity trace + one efficiency trace for a single cell
    assert len(fig["data"]) == 2
    assert "layout" in fig


def test_summary_figure_empty():
    spec = SummaryPlotSpec()
    fig = json.loads(plotting.summary_figure([], spec))
    assert "layout" in fig  # annotation-only placeholder figure


def test_cycles_figure_json(loaded_library):
    rec = loaded_library.all()[0]
    spec = CyclesPlotSpec(cell_id=rec.id, cycles=[1, 5, 10])
    fig = json.loads(plotting.cycles_figure(rec, spec))
    assert len(fig["data"]) == 3


def test_summary_csv(loaded_library):
    spec = SummaryPlotSpec()
    data = export.summary_csv(loaded_library.selected(), spec)
    assert data.startswith(b"cycle")
    assert len(data.splitlines()) > 5


def test_cycles_csv(loaded_library):
    rec = loaded_library.all()[0]
    spec = CyclesPlotSpec(cell_id=rec.id, cycles=[1, 2])
    data = export.cycles_csv(rec, spec)
    assert data.splitlines()[0] == b"cycle,capacity,potential"
    assert len(data.splitlines()) > 5
