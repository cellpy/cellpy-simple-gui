"""Unit tests for the core layer (no web server involved)."""

from __future__ import annotations

import json

from cellpy_simple_gui.core import collect, export, plotting
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


# ---- dynamic instrument discovery ---------------------------------------- #

def test_list_instruments_dynamic():
    from cellpy_simple_gui.core import cellpy_adapter

    ids = cellpy_adapter.instrument_ids()
    assert {"arbin_res", "maccor_txt", "neware_txt", "pec_csv"} <= ids
    maccor = next(i for i in cellpy_adapter.list_instruments() if i["id"] == "maccor_txt")
    assert maccor["models"]  # discovered from cellpy, not hard-coded


# ---- column mapping ------------------------------------------------------ #

def test_summary_columns_mapping():
    assert collect.summary_columns("gravimetric", True, True, True) == (
        "charge_capacity_gravimetric",
        "discharge_capacity_gravimetric",
        "coulombic_efficiency",
    )
    assert collect.summary_columns("absolute", True, False, False) == ("charge_capacity",)
    assert collect.summary_columns("areal", False, True, False) == ("discharge_capacity_areal",)
    # nothing selected -> falls back to charge
    assert collect.summary_columns("gravimetric", False, False, False) == (
        "charge_capacity_gravimetric",
    )


# ---- collect-based plotting ---------------------------------------------- #

def test_summary_collection_and_figure(loaded_library):
    recs = loaded_library.selected()
    cols = collect.summary_columns("gravimetric", True, True, False)
    coll = collect.summary_collection(recs, columns=cols)
    assert coll.data.height > 0
    fig = json.loads(collect.figure_json(coll))
    assert fig["data"]  # at least one trace
    assert "layout" in fig


def test_summary_figure_via_plotting(loaded_library):
    spec = SummaryPlotSpec(basis="gravimetric", show_charge=True, show_discharge=True)
    fig = json.loads(plotting.summary_figure(loaded_library.selected(), spec))
    assert len(fig["data"]) >= 1


def test_summary_figure_empty():
    fig = json.loads(plotting.summary_figure([], SummaryPlotSpec()))
    assert "layout" in fig  # placeholder figure, no crash


def test_cycles_figure(loaded_library):
    rec = loaded_library.all()[0]
    spec = CyclesPlotSpec(cell_id=rec.id, cycles=[1, 5, 10])
    fig = json.loads(plotting.cycles_figure(rec, spec))
    assert len(fig["data"]) >= 1


# ---- multi-format export ------------------------------------------------- #

def test_summary_export_all_formats(loaded_library):
    recs = loaded_library.selected()
    spec = SummaryPlotSpec()
    for fmt in collect.EXPORT_FORMATS:
        data, media = export.summary_export(recs, spec, fmt)
        assert isinstance(data, bytes) and len(data) > 0
        assert media


def test_cycles_export_csv(loaded_library):
    rec = loaded_library.all()[0]
    spec = CyclesPlotSpec(cell_id=rec.id, cycles=[1, 2])
    data, media = export.cycles_export(rec, spec, "csv")
    assert data.startswith(b"cycle") or b"capacity" in data[:200]
    assert media == "text/csv"
