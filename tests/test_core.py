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

def test_summary_columns_for_types():
    assert collect.summary_columns_for("capacity_ce", "gravimetric") == (
        "charge_capacity_gravimetric",
        "discharge_capacity_gravimetric",
        "coulombic_efficiency",
    )
    assert collect.summary_columns_for("end_voltages", "gravimetric") == (
        "potential_end_charge",
        "potential_end_discharge",
    )
    assert collect.summary_columns_for("internal_resistance", "areal") == ("ir_charge", "ir_discharge")
    assert collect.summary_columns_for("capacity_loss", "areal") == (
        "charge_capacity_loss_areal",
        "discharge_capacity_loss_areal",
    )
    # unknown type falls back to capacity_ce
    assert collect.summary_columns_for("???", "gravimetric")[0] == "charge_capacity_gravimetric"


def test_plot_type_renders_end_voltages(loaded_library):
    spec = SummaryPlotSpec(plot_type="end_voltages")
    fig = json.loads(plotting.summary_figure(loaded_library.selected(), spec))
    assert len(fig["data"]) >= 1


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


def test_cycles_figure_areal_mode(loaded_library):
    rec = loaded_library.all()[0]
    spec = CyclesPlotSpec(cell_id=rec.id, cycles=[1, 5], mode="areal", method="back-and-forth")
    fig = json.loads(plotting.cycles_figure(rec, spec))
    assert len(fig["data"]) >= 1


def test_grouped_summary_renders(example_cell):
    """Regression guard for cellpy #785 (fixed in 2.1.1): group-averaged
    collected summaries must actually plot, not fall back to an empty figure."""
    from cellpy_simple_gui.core import cellpy_adapter
    from cellpy_simple_gui.core.library import Library

    lib = Library()
    lib.add_cell(example_cell, source="ex")
    lib.add_cell(cellpy_adapter.load_example("rate"), source="ex")
    for r in lib.all():
        lib.update(r.id, group=1)  # same group -> averaging valid

    cols = collect.summary_columns("gravimetric", True, False, False)
    coll = collect.summary_collection(lib.selected(), columns=cols, group_it=True)
    assert collect.is_grouped(coll)
    fig = json.loads(collect.figure_json(coll, spread=True))
    assert len(fig["data"]) >= 1  # was 0 (empty fallback) on cellpy 2.1.0


def test_summary_figure_long_cell_names_shorten_legend(loaded_library):
    """Long journal-style labels must not blow up the summary legend (#1)."""
    long = (
        "20130419_es018_02_eth_01-20130419_es018_02_eth_03-"
        "CONCAT-VERY-LONG-LABEL-FOR-LEGEND"
    )
    assert len(long) > 40
    rec = loaded_library.all()[0]
    loaded_library.update(rec.id, label=long)

    spec = SummaryPlotSpec(plot_type="capacity_ce")
    fig = json.loads(plotting.summary_figure(loaded_library.selected(), spec))
    assert fig["data"]

    limit = collect._LEGEND_NAME_LIMIT
    for tr in fig["data"]:
        name = tr.get("name") or ""
        assert len(name) <= limit
        # Full identity remains on hover (PX embeds it in hovertemplate).
        hover = tr.get("hovertemplate") or tr.get("hovertext") or ""
        assert long in hover

    legend = fig["layout"].get("legend") or {}
    assert legend.get("orientation") == "v"
    assert legend.get("xanchor") == "left"
    assert float(legend.get("x", 0)) > 1.0
    margin_r = (fig["layout"].get("margin") or {}).get("r") or 0
    assert margin_r >= 40 + limit * 7  # room for truncated legend (+ strips)


def test_summary_figure_short_names_unchanged(loaded_library):
    """Short labels stay intact; right margin stays modest (#1)."""
    rec = loaded_library.all()[0]
    short = "cell-a"
    loaded_library.update(rec.id, label=short)

    fig = json.loads(
        plotting.summary_figure(loaded_library.selected(), SummaryPlotSpec())
    )
    names = [tr.get("name") for tr in fig["data"] if tr.get("name")]
    assert names
    assert all(n == short for n in names)
    margin_r = (fig["layout"].get("margin") or {}).get("r") or 0
    # Short name + optional facet-strip pad; not the full long-name gutter.
    expected_max = (
        collect._FACET_STRIP_RIGHT_PAD + 40 + len(short) * 7 + 8
    )
    assert margin_r <= expected_max


def test_shorten_legend_runs_when_restyle_cosmetics_fail():
    """Legend shortening must not be skipped if update_layout raises (#1)."""
    import plotly.graph_objects as go

    long = "x" * 60
    fig = go.Figure(go.Scatter(x=[1, 2], y=[1, 2], name=long))

    original_update = fig.update_layout

    def boom(*args, **kwargs):
        raise RuntimeError("cosmetics broken")

    fig.update_layout = boom  # type: ignore[method-assign]
    collect._restyle(fig)
    fig.update_layout = original_update  # type: ignore[method-assign]

    assert fig.data[0].name == "x" * (collect._LEGEND_NAME_LIMIT - 1) + "…"
    assert fig.data[0].hovertext == long


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
