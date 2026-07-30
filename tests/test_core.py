"""Unit tests for the core layer (no web server involved)."""

from __future__ import annotations

import json

import pytest

from cellpy_simple_gui.core import collect, export, plotting
from cellpy_simple_gui.core.models import CyclesPlotSpec, SummaryPlotSpec


@pytest.mark.essential
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

@pytest.mark.essential
def test_list_instruments_dynamic():
    from cellpy_simple_gui.core import cellpy_adapter

    ids = cellpy_adapter.instrument_ids()
    assert {"arbin_res", "maccor_txt", "neware_txt", "pec_csv"} <= ids
    maccor = next(i for i in cellpy_adapter.list_instruments() if i["id"] == "maccor_txt")
    assert maccor["models"]  # discovered from cellpy, not hard-coded


# ---- column mapping ------------------------------------------------------ #

@pytest.mark.essential
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


@pytest.mark.essential
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


@pytest.mark.essential
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


def _yaxis_matches(fig: dict) -> dict[str, str | None]:
    return {
        key: (fig["layout"].get(key) or {}).get("matches")
        for key in fig["layout"]
        if key.startswith("yaxis")
    }


def _numeric_y_values(y) -> list[float]:
    """Unpack Plotly figure-json ``y`` (plain list or binary ``bdata`` dict)."""
    import base64
    import struct

    if y is None:
        return []
    if isinstance(y, dict) and "bdata" in y:
        raw = base64.b64decode(y["bdata"])
        dtype = y.get("dtype") or "f8"
        fmt = {"f8": "d", "f4": "f", "i4": "i", "i8": "q"}.get(dtype)
        if not fmt:
            return []
        n = len(raw) // struct.calcsize(fmt)
        return [abs(v) for v in struct.unpack(f"<{n}{fmt}", raw)]
    vals = []
    for v in y:
        try:
            vals.append(abs(float(v)))
        except (TypeError, ValueError):
            continue
    return vals


def _yaxis_to_variable(fig: dict) -> dict[str, str]:
    """Map Plotly yaxis id (``y`` / ``y2`` / …) to facet strip variable name."""
    annotations = fig["layout"].get("annotations") or []
    yaxes = sorted(
        (k for k in fig["layout"] if k.startswith("yaxis")),
        key=lambda k: (fig["layout"][k].get("domain") or [0, 0])[0],
    )
    # Restyle tidies ``variable=…`` strips to the bare column id; keep only those.
    labels = [
        a.get("text")
        for a in annotations
        if isinstance(a.get("text"), str) and a.get("text")
    ]
    # Facet strips are ordered bottom→top matching yaxis domains.
    out: dict[str, str] = {}
    for ax_key, label in zip(yaxes, labels):
        # layout key ``yaxis`` → trace ``yaxis`` ``y``; ``yaxis2`` → ``y2``.
        trace_id = "y" if ax_key == "yaxis" else ax_key.replace("yaxis", "y")
        out[trace_id] = label
    return out


def test_summary_figure_independent_y_by_default(loaded_library):
    """Multi-panel summary defaults to unmatched y-axes (#2)."""
    fig = json.loads(
        plotting.summary_figure(
            loaded_library.selected(), SummaryPlotSpec(plot_type="capacity_ce")
        )
    )
    assert fig["data"]
    matches = _yaxis_matches(fig)
    assert len(matches) >= 2
    assert all(v in (None, "") for v in matches.values())


def test_summary_figure_share_y_matches_axes(loaded_library):
    """share_y=True restores cellpy's shared y-scale (#2)."""
    fig = json.loads(
        plotting.summary_figure(
            loaded_library.selected(),
            SummaryPlotSpec(plot_type="capacity_ce", share_y=True),
        )
    )
    matches = _yaxis_matches(fig)
    # Primary axis has no matches; secondary rows link to "y".
    assert any(v == "y" for v in matches.values())


def test_summary_figure_ce_outlier_does_not_crush_capacity(loaded_library):
    """Extreme CE must not force capacity panels onto a million-scale (#2)."""
    import polars as pl

    cols = collect.summary_columns_for("capacity_ce", "gravimetric")
    coll = collect.summary_collection(loaded_library.selected(), columns=cols)
    assert "coulombic_efficiency" in coll.data.columns
    coll.data = coll.data.with_columns(pl.lit(1e6).alias("coulombic_efficiency"))

    fig = json.loads(collect.figure_json(coll, match_axes=False))
    assert fig["data"]
    matches = _yaxis_matches(fig)
    assert all(v in (None, "") for v in matches.values())

    var_by_axis = _yaxis_to_variable(fig)
    capacity_max = 0.0
    ce_max = 0.0
    for tr in fig["data"]:
        vals = _numeric_y_values(tr.get("y"))
        if not vals:
            continue
        ymax = max(vals)
        var = var_by_axis.get(tr.get("yaxis") or "y", "")
        if var == "coulombic_efficiency":
            ce_max = max(ce_max, ymax)
        elif "capacity" in var:
            capacity_max = max(capacity_max, ymax)

    assert ce_max >= 1e5
    assert capacity_max > 0
    assert capacity_max < 1e5


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
