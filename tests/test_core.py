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


def test_instrument_meta_schema_wrapper():
    """Adapter exposes cellpy #800 schema for ingest-form follow-ups (#52)."""
    from cellpy_simple_gui.core import cellpy_adapter

    schema = cellpy_adapter.instrument_meta_schema("arbin_res")
    assert schema.get("instrument") == "arbin_res"
    names = {f["name"] for f in schema.get("fields", [])}
    assert {"mass", "area", "nominal_capacity"} <= names


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


def test_group_average_keeps_singleton_traces(example_cell):
    """Group avg must still average multi-member groups when a singleton exists.

    cellpy's ``group_it=True`` otherwise silently disables averaging for the
    whole selection if any group has < 2 cells (#27).
    """
    from cellpy_simple_gui.core import cellpy_adapter
    from cellpy_simple_gui.core.library import Library

    lib = Library()
    lib.add_cell(example_cell, source="ex")
    lib.add_cell(cellpy_adapter.load_example("rate"), source="ex")
    lib.add_cell(cellpy_adapter.load_example("cellpy"), source="ex")
    recs = lib.all()
    lib.update(recs[0].id, group=1, label="g1a")
    lib.update(recs[1].id, group=1, label="g1b")
    lib.update(recs[2].id, group=2, label="solo")

    # Naive path: cellpy drops averaging entirely.
    cols = collect.summary_columns_for("capacity_ce", "gravimetric")
    naive = collect.summary_collection(lib.selected(), columns=cols, group_it=True)
    assert not collect.is_grouped(naive)

    parts = collect.summary_collections(lib.selected(), columns=cols, group_it=True)
    assert len(parts) == 2
    assert parts[0][1] is True and collect.is_grouped(parts[0][0])
    assert parts[1][1] is False and not collect.is_grouped(parts[1][0])

    spec = SummaryPlotSpec(plot_type="capacity_ce", group_average=True, spread=True)
    fig = json.loads(plotting.summary_figure(lib.selected(), spec))
    names = {tr.get("name") for tr in fig["data"]}
    assert "solo" in names
    # Averaged group legend uses the group id; spread adds Upper/Lower Bound traces.
    assert any(n == "1" or (isinstance(n, str) and n.startswith("Upper Bound")) for n in names)
    assert len(fig["data"]) > len(json.loads(collect.figure_json(parts[1][0]))["data"])


def test_group_average_singleton_traces_on_correct_facet(example_cell):
    """Mixed avg+singleton merge must put each series on its variable's row (#39)."""
    from cellpy_simple_gui.core import cellpy_adapter
    from cellpy_simple_gui.core.library import Library

    lib = Library()
    lib.add_cell(example_cell, source="ex")
    lib.add_cell(cellpy_adapter.load_example("rate"), source="ex")
    lib.add_cell(cellpy_adapter.load_example("cellpy"), source="ex")
    recs = lib.all()
    lib.update(recs[0].id, group=1, label="g1a")
    lib.update(recs[1].id, group=1, label="g1b")
    lib.update(recs[2].id, group=2, label="solo")

    fig = json.loads(
        plotting.summary_figure(
            lib.selected(),
            SummaryPlotSpec(plot_type="capacity_ce", group_average=True, spread=True),
        )
    )

    def _hover_var(tr) -> str | None:
        ht = tr.get("hovertemplate") or ""
        return next(
            (p.split("=", 1)[1] for p in ht.split("<br>") if p.startswith("variable=")),
            None,
        )

    # Each column id must live on a single y-axis (avg + singleton share the panel).
    axes_by_var: dict[str, set[str]] = {}
    for tr in fig["data"]:
        var = _hover_var(tr)
        if not var:
            continue
        axes_by_var.setdefault(var, set()).add(tr.get("yaxis") or "y")
    assert axes_by_var
    for var, axes in axes_by_var.items():
        assert len(axes) == 1, (var, axes)

    solo = [tr for tr in fig["data"] if tr.get("name") == "solo"]
    assert len(solo) >= 3
    for tr in solo:
        assert _hover_var(tr)


def test_summary_figure_pretty_axis_labels(loaded_library):
    """cellpy #801 pretty-prints y-axis titles (not bare snake_case) (#52 / #38)."""
    fig = json.loads(
        plotting.summary_figure(
            loaded_library.selected(),
            SummaryPlotSpec(plot_type="capacity_ce"),
        )
    )
    titles = []
    for key, axis in fig["layout"].items():
        if not key.startswith("yaxis"):
            continue
        title = axis.get("title")
        if isinstance(title, dict):
            title = title.get("text")
        if isinstance(title, str) and title:
            titles.append(title)
    assert titles
    assert any(" " in t or "(" in t for t in titles)
    assert not any(t.startswith("charge_capacity_") for t in titles)


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


def test_summary_figure_dark_theme(loaded_library):
    """Dark theme tokens land on layout (#32)."""
    fig = json.loads(
        plotting.summary_figure(
            loaded_library.selected(),
            SummaryPlotSpec(figure_theme="dark"),
        )
    )
    layout = fig["layout"]
    assert layout.get("paper_bgcolor") == collect._THEME_TOKENS["dark"]["paper_bgcolor"]
    assert (layout.get("font") or {}).get("color") == collect._THEME_TOKENS["dark"]["font_color"]


def test_summary_figure_safe_color_scheme(loaded_library):
    """safe colorway paints at least one trace from library.PALETTE (#32)."""
    fig = json.loads(
        plotting.summary_figure(
            loaded_library.selected(),
            SummaryPlotSpec(color_scheme="safe"),
        )
    )
    palette = set(collect.COLOR_SCHEMES["safe"] or [])
    colors = []
    for tr in fig["data"]:
        line = tr.get("line") or {}
        if line.get("color"):
            colors.append(line["color"])
        marker = tr.get("marker") or {}
        if marker.get("color") and isinstance(marker["color"], str):
            colors.append(marker["color"])
    assert colors
    assert any(c in palette for c in colors)


@pytest.mark.parametrize("scheme", ["safe", "muted"])
def test_spread_fillcolor_has_alpha(example_cell, scheme):
    """safe/muted spread bands use translucent rgba fill, solid mean lines (#37)."""
    from cellpy_simple_gui.core import cellpy_adapter
    from cellpy_simple_gui.core.library import Library

    lib = Library()
    lib.add_cell(example_cell, source="ex")
    lib.add_cell(cellpy_adapter.load_example("rate"), source="ex")
    for r in lib.all():
        lib.update(r.id, group=1)

    fig = json.loads(
        plotting.summary_figure(
            lib.selected(),
            SummaryPlotSpec(group_average=True, spread=True, color_scheme=scheme),
        )
    )
    filled = [
        tr for tr in fig["data"]
        if tr.get("fill") and tr.get("fill") != "none"
    ]
    assert filled, "expected at least one spread fill trace"
    for tr in filled:
        fc = tr.get("fillcolor") or ""
        assert fc.startswith("rgba("), fc
        alpha = float(fc.rsplit(",", 1)[-1].rstrip(")"))
        assert 0.15 <= alpha <= 0.4
    # Mean / series lines stay opaque hex from the colorway.
    palette = set(collect.COLOR_SCHEMES[scheme] or [])
    line_colors = [
        (tr.get("line") or {}).get("color")
        for tr in fig["data"]
        if (tr.get("line") or {}).get("color")
    ]
    assert any(c in palette for c in line_colors)


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


def _hover_variable(tr: dict) -> str | None:
    """Column id from a PX ``variable=…`` hovertemplate fragment."""
    ht = tr.get("hovertemplate") or ""
    return next(
        (p.split("=", 1)[1] for p in ht.split("<br>") if p.startswith("variable=")),
        None,
    )


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


def _yaxis_for_variable(fig: dict, variable: str) -> str | None:
    """Plotly layout key (``yaxis`` / ``yaxis2`` / …) for a facet variable."""
    for tr in fig["data"]:
        if _hover_variable(tr) != variable:
            continue
        axis = tr.get("yaxis") or "y"
        return "yaxis" if axis == "y" else f"yaxis{axis[1:]}"
    return None


def test_summary_figure_y_ranges_sets_panel_limits(loaded_library):
    """Per-panel y_ranges land on the matching facet axis (#54 / cellpy #804)."""
    fig = json.loads(
        plotting.summary_figure(
            loaded_library.selected(),
            SummaryPlotSpec(
                plot_type="capacity_ce",
                y_ranges={"coulombic_efficiency": [0.9, 1.05]},
            ),
        )
    )
    axis = _yaxis_for_variable(fig, "coulombic_efficiency")
    assert axis is not None
    layout_axis = fig["layout"][axis]
    assert layout_axis.get("range") == [0.9, 1.05]
    assert layout_axis.get("autorange") is False


def test_summary_figure_y_ranges_wins_over_share_y(loaded_library):
    """Fixed ranges must not be defeated by app share_y re-link (#54)."""
    fig = json.loads(
        plotting.summary_figure(
            loaded_library.selected(),
            SummaryPlotSpec(
                plot_type="capacity_ce",
                share_y=True,
                y_ranges={"coulombic_efficiency": [0.95, 1.02]},
            ),
        )
    )
    matches = _yaxis_matches(fig)
    assert all(v in (None, "") for v in matches.values())
    axis = _yaxis_for_variable(fig, "coulombic_efficiency")
    assert fig["layout"][axis].get("range") == [0.95, 1.02]


def test_summary_panels_for_capacity_ce():
    panels = collect.summary_panels_for("capacity_ce", "gravimetric")
    ids = [p["id"] for p in panels]
    assert ids == [
        "charge_capacity_gravimetric",
        "discharge_capacity_gravimetric",
        "coulombic_efficiency",
    ]
    assert panels[-1]["label"] == "CE"


def test_summary_figure_share_y_with_group_avg_and_spread(loaded_library):
    """Group avg + Spread must still honour share_y (#47; cellpy spread_plot gap)."""
    from cellpy_simple_gui.core import cellpy_adapter

    # Need ≥2 cells in one group so averaging + spread actually engage.
    lib = loaded_library
    lib.add_cell(cellpy_adapter.load_example("rate"), source="example:rate")
    for rec in lib.all():
        rec.group = 1
        rec.selected = True

    fig = json.loads(
        plotting.summary_figure(
            lib.selected(),
            SummaryPlotSpec(
                plot_type="capacity_ce",
                group_average=True,
                spread=True,
                share_y=True,
            ),
        )
    )
    matches = _yaxis_matches(fig)
    assert len(matches) >= 2
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

    capacity_max = 0.0
    ce_max = 0.0
    for tr in fig["data"]:
        vals = _numeric_y_values(tr.get("y"))
        if not vals:
            continue
        ymax = max(vals)
        var = _hover_variable(tr) or ""
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


def _kaleido_available() -> bool:
    try:
        import kaleido  # noqa: F401
    except ImportError:
        return False
    return True


@pytest.mark.skipif(not _kaleido_available(), reason="kaleido not installed (uv sync --extra export)")
def test_summary_figure_export_svg(loaded_library):
    recs = loaded_library.selected()
    spec = SummaryPlotSpec(plot_type="capacity_ce")
    data, media = export.summary_figure_export(recs, spec, "svg")
    assert media == "image/svg+xml"
    assert data.lstrip().startswith(b"<svg") or b"<svg" in data[:200]


def test_figure_export_unknown_format_raises():
    with pytest.raises(export.FigureExportError, match="Unsupported figure format"):
        export.figure_bytes("{}", "gif")


def _rate_library():
    from cellpy_simple_gui.core import cellpy_adapter
    from cellpy_simple_gui.core.library import Library

    try:
        cell = cellpy_adapter.load_example("rate")
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"example data unavailable: {exc}")
    lib = Library()
    lib.add_cell(cell, source="example:rate")
    return lib


def test_cells_export_cellpy_and_xlsx():
    rec = _rate_library().selected()[0]
    data, media, name = export.cells_export([rec], "cellpy")
    assert media == "application/octet-stream"
    assert name.endswith(".cellpy")
    assert len(data) > 1000

    data, media, name = export.cells_export([rec], "xlsx")
    assert name.endswith(".xlsx")
    assert data[:2] == b"PK"  # zip-based xlsx


def test_cells_export_two_cells_zip():
    from cellpy_simple_gui.core import cellpy_adapter

    lib = _rate_library()
    lib.add_cell(cellpy_adapter.load_example("rate"), source="ex2")
    recs = lib.selected()
    assert len(recs) >= 2
    data, media, name = export.cells_export(recs, "cellpy")
    assert media == "application/zip"
    assert name.endswith(".zip")
    import io
    import zipfile

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = zf.namelist()
    assert len(names) >= 2
    assert all(n.endswith(".cellpy") for n in names)


def test_cells_export_csv_is_zip():
    rec = _rate_library().selected()[0]
    data, media, name = export.cells_export([rec], "csv")
    assert media == "application/zip"
    assert name.endswith(".zip")
    import io
    import zipfile

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = zf.namelist()
    assert names
    assert any(n.endswith(".csv") for n in names)
