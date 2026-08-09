"""Unit tests for the core layer (no web server involved)."""

from __future__ import annotations

import json

import pytest

from cellpy_simple_gui.core import collect, export, plotting
from cellpy_simple_gui.core.models import CyclesPlotSpec, IcaPlotSpec, SummaryPlotSpec


@pytest.mark.essential
def test_read_meta(example_cell):
    from cellpy_simple_gui.core import cellpy_adapter

    meta = cellpy_adapter.read_meta(example_cell)
    assert meta["name"]
    assert meta["n_cycles"] > 0
    assert meta["mass"] and meta["mass"] > 0
    assert meta["cycle_mode"] in ("anode", "cathode", "full_cell", None)
    assert meta["nom_cap_specifics"] in ("gravimetric", "areal", "absolute", None)


def test_apply_physical_meta_updates_and_summary(example_cell):
    from cellpy_simple_gui.core import cellpy_adapter

    before = cellpy_adapter.summary_frame(example_cell)
    assert len(before) > 0
    changed = cellpy_adapter.apply_physical_meta(
        example_cell,
        mass=1.5,
        area=2.0,
        nominal_capacity=1800.0,
        nom_cap_specifics="areal",
        cycle_mode="cathode",
    )
    assert set(changed) == {
        "mass", "area", "nominal_capacity", "nom_cap_specifics", "cycle_mode",
    }
    meta = cellpy_adapter.read_meta(example_cell)
    assert abs(meta["mass"] - 1.5) < 1e-9
    assert abs(meta["area"] - 2.0) < 1e-9
    assert abs(meta["nominal_capacity"] - 1800.0) < 1e-9
    assert meta["nom_cap_specifics"] == "areal"
    assert meta["cycle_mode"] == "cathode"
    after = cellpy_adapter.summary_frame(example_cell)
    assert len(after) > 0
    assert "charge_capacity_gravimetric" in after.columns


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
        "coulombic_efficiency",
        "charge_capacity_gravimetric",
        "discharge_capacity_gravimetric",
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
    # unknown type falls back to capacity_ce (CE on top — #81)
    assert collect.summary_columns_for("???", "gravimetric")[0] == "coulombic_efficiency"


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


def test_summary_figure_forwards_group_legend_muting(loaded_library, monkeypatch):
    """#62: SummaryPlotSpec.group_legend_muting reaches collection.plot kwargs."""
    captured: dict = {}
    real = collect.figure_json

    def spy(*args, **kwargs):
        captured.clear()
        captured.update(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(collect, "figure_json", spy)
    plotting.summary_figure(
        loaded_library.selected(), SummaryPlotSpec(group_legend_muting=False)
    )
    assert captured.get("group_legend_muting") is False
    plotting.summary_figure(
        loaded_library.selected(), SummaryPlotSpec(group_legend_muting=True)
    )
    assert captured.get("group_legend_muting") is True


def test_cycles_figure_forwards_group_legend_muting(loaded_library, monkeypatch):
    """#62: CyclesPlotSpec.group_legend_muting reaches collection.plot kwargs."""
    captured: dict = {}
    real = collect.figure_json

    def spy(*args, **kwargs):
        captured.clear()
        captured.update(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(collect, "figure_json", spy)
    recs = loaded_library.selected()
    plotting.cycles_figure(
        recs, CyclesPlotSpec(cycles=[1, 2], layout="per_cycle", group_legend_muting=False)
    )
    assert captured.get("group_legend_muting") is False
    plotting.cycles_figure(
        recs, CyclesPlotSpec(cycles=[1, 2], layout="per_cycle", group_legend_muting=True)
    )
    assert captured.get("group_legend_muting") is True


def test_cycles_figure(loaded_library):
    rec = loaded_library.all()[0]
    spec = CyclesPlotSpec(cell_id=rec.id, cycles=[1, 5, 10], layout="per_cell")
    fig = json.loads(plotting.cycles_figure([rec], spec))
    assert len(fig["data"]) >= 1


def test_cycles_figure_xy_ranges(loaded_library):
    """Cell-explorer / Cycles-collector x/y range widgets pin Plotly axes."""
    rec = loaded_library.all()[0]
    fig = json.loads(
        plotting.cycles_figure(
            [rec],
            CyclesPlotSpec(
                cell_id=rec.id,
                cycles=[1, 2],
                layout="per_cell",
                x_range=[0.0, 100.0],
                y_range=[0.1, 1.5],
            ),
        )
    )
    xaxis = fig["layout"]["xaxis"]
    yaxis = fig["layout"]["yaxis"]
    assert xaxis.get("range") == [0.0, 100.0]
    assert xaxis.get("autorange") is False
    assert yaxis.get("range") == [0.1, 1.5]
    assert yaxis.get("autorange") is False


def test_cycles_collector_xy_ranges_per_cycle(loaded_library):
    """Collector layout also honours axis ranges for export parity."""
    rec = loaded_library.all()[0]
    fig = json.loads(
        plotting.cycles_figure(
            [rec],
            CyclesPlotSpec(
                cycles=[1, 2],
                layout="per_cycle",
                x_range=[0.0, 50.0],
                y_range=[0.2, 1.0],
            ),
        )
    )
    assert fig["layout"]["xaxis"].get("range") == [0.0, 50.0]
    assert fig["layout"]["yaxis"].get("range") == [0.2, 1.0]


def test_cycles_figure_xy_ranges_one_sided(loaded_library):
    """Cycles x/y accept a single end; the other is filled from data."""
    rec = loaded_library.all()[0]
    fig = json.loads(
        plotting.cycles_figure(
            [rec],
            CyclesPlotSpec(
                cell_id=rec.id,
                cycles=[1, 2],
                layout="per_cell",
                x_range=[None, 80.0],
                y_range=[0.0, None],
            ),
        )
    )
    x_lo, x_hi = fig["layout"]["xaxis"]["range"]
    y_lo, y_hi = fig["layout"]["yaxis"]["range"]
    assert x_hi == 80.0 and x_lo < x_hi
    assert y_lo == 0.0 and y_hi > y_lo


def test_ica_figure_xy_ranges(loaded_library):
    rec = loaded_library.all()[0]
    fig = json.loads(
        plotting.ica_figure(
            rec,
            IcaPlotSpec(
                cell_id=rec.id,
                cycles=[1, 2],
                x_range=[0.05, 1.2],
                y_range=[-500.0, 500.0],
            ),
        )
    )
    assert fig["layout"]["xaxis"].get("range") == [0.05, 1.2]
    assert fig["layout"]["yaxis"].get("range") == [-500.0, 500.0]


def test_ica_figure_xy_ranges_one_sided(loaded_library):
    rec = loaded_library.all()[0]
    fig = json.loads(
        plotting.ica_figure(
            rec,
            IcaPlotSpec(
                cell_id=rec.id,
                cycles=[1, 2],
                x_range=[None, 1.0],
                y_range=[-1e6, None],
            ),
        )
    )
    x_lo, x_hi = fig["layout"]["xaxis"]["range"]
    y_lo, y_hi = fig["layout"]["yaxis"]["range"]
    assert x_hi == 1.0 and x_lo < x_hi
    assert y_lo == -1e6 and y_hi > y_lo


def test_ica_figure_partial_x_range_min_only(loaded_library):
    """Leaving max blank still zooms from the given min (fills max from data)."""
    rec = loaded_library.all()[0]
    fig = json.loads(
        plotting.ica_figure(
            rec,
            IcaPlotSpec(cell_id=rec.id, cycles=[1, 2], x_range=[0.5, None]),
        )
    )
    rng = fig["layout"]["xaxis"].get("range")
    assert rng is not None
    assert rng[0] == 0.5
    assert rng[1] > 0.5
    assert fig["layout"]["xaxis"].get("autorange") is False


def _xaxis_title(fig: dict) -> str:
    title = (fig.get("layout") or {}).get("xaxis", {}).get("title")
    if isinstance(title, dict):
        return str(title.get("text") or "")
    return str(title or "")


@pytest.mark.parametrize(
    "mode,must_contain,must_not_contain",
    [
        ("gravimetric", "mAh/g", ()),
        ("areal", "mAh/cm", ("mAh/g",)),
        ("absolute", "mAh", ("mAh/g", "mAh/cm")),
    ],
)
def test_cycles_figure_mode_updates_xaxis_units(
    loaded_library, mode, must_contain, must_not_contain
):
    """Cycles Mode must drive x-axis capacity units (#72)."""
    rec = loaded_library.all()[0]
    spec = CyclesPlotSpec(
        cell_id=rec.id, cycles=[1, 5], mode=mode, method="back-and-forth", layout="per_cell"
    )
    fig = json.loads(plotting.cycles_figure([rec], spec))
    assert len(fig["data"]) >= 1
    xlabel = _xaxis_title(fig)
    assert must_contain in xlabel, xlabel
    for bad in must_not_contain:
        assert bad not in xlabel, xlabel


def test_cycles_collector_layouts(loaded_library):
    """Multi-cell collector supports per_cell and per_cycle layouts (#55)."""
    from cellpy_simple_gui.core import cellpy_adapter

    lib = loaded_library
    if len(lib.all()) < 2:
        lib.add_cell(cellpy_adapter.load_example("rate"), source="ex")
    recs = lib.selected()
    assert len(recs) >= 1
    for layout in ("per_cell", "per_cycle"):
        spec = CyclesPlotSpec(cycles=[1, 2, 3], layout=layout)
        fig = json.loads(plotting.cycles_figure(recs, spec))
        assert len(fig["data"]) >= 1, layout


def test_cycles_figure_empty_selection():
    fig = json.loads(plotting.cycles_figure([], CyclesPlotSpec(cycles=[1])))
    assert "layout" in fig


def _ica_y_values(fig: dict) -> list[float]:
    """Flatten Plotly trace y values (list or binary ``{dtype,bdata}``)."""
    import base64

    import numpy as np

    ys: list[float] = []
    for trace in fig.get("data") or []:
        y = trace.get("y")
        if isinstance(y, dict) and "bdata" in y:
            arr = np.frombuffer(
                base64.b64decode(y["bdata"]), dtype=np.dtype(y["dtype"])
            )
            ys.extend(float(v) for v in arr if v == v)  # skip NaN
            continue
        if not isinstance(y, list):
            continue
        for v in y:
            if v is None:
                continue
            try:
                ys.append(float(v))
            except (TypeError, ValueError):
                continue
    return ys


def test_ica_figure(loaded_library):
    rec = loaded_library.all()[0]
    spec = IcaPlotSpec(
        cell_id=rec.id, cycles=[1, 2, 3], voltage_resolution=0.005, direction="charge"
    )
    fig = json.loads(plotting.ica_figure(rec, spec))
    assert len(fig["data"]) >= 1


def test_ica_figure_discharge(loaded_library):
    rec = loaded_library.all()[0]
    spec = IcaPlotSpec(
        cell_id=rec.id, cycles=[1, 2], voltage_resolution=0.005, direction="discharge"
    )
    fig = json.loads(plotting.ica_figure(rec, spec))
    assert len(fig["data"]) >= 1


def test_ica_figure_charge_differs_from_discharge(loaded_library):
    """Direction selects the half-cycle (#67/#821); cellpy's ica_plotter owns it."""
    rec = loaded_library.all()[0]
    cycles = [1, 2, 3]
    kwargs = dict(cell_id=rec.id, cycles=cycles, voltage_resolution=0.005)
    charge = json.loads(
        plotting.ica_figure(rec, IcaPlotSpec(**kwargs, direction="charge"))
    )
    discharge = json.loads(
        plotting.ica_figure(rec, IcaPlotSpec(**kwargs, direction="discharge"))
    )
    y_c = _ica_y_values(charge)
    y_d = _ica_y_values(discharge)
    assert y_c and y_d
    assert y_c != y_d
    # Typical Si/graphite demo: charge lobe predominantly +dQ/dV, discharge −.
    assert sum(y_c) / len(y_c) > 0
    assert sum(y_d) / len(y_d) < 0


def test_ica_figure_both_overlays_directions(loaded_library):
    """direction="both" overlays charge + discharge on each cycle (#821)."""
    rec = loaded_library.all()[0]
    kwargs = dict(cell_id=rec.id, cycles=[1, 2], voltage_resolution=0.005)
    both = json.loads(plotting.ica_figure(rec, IcaPlotSpec(**kwargs, direction="both")))
    charge = json.loads(
        plotting.ica_figure(rec, IcaPlotSpec(**kwargs, direction="charge"))
    )
    # "both" carries both half-cycles, so more traces than a single direction.
    assert len(both["data"]) > len(charge["data"])
    names = " ".join(str(tr.get("name")) for tr in both["data"]).lower()
    assert "charge" in names and "discharge" in names


def test_select_ica_direction_for_export(loaded_library):
    """Export filter mirrors the chart: charge/discharge slice, "both" keeps all."""
    from cellpy_simple_gui.core import collect

    rec = loaded_library.all()[0]

    def fresh():
        return collect.ica_collection([rec], cycles=(1, 2), voltage_resolution=0.005)

    both = fresh()
    assert set(both.data["direction"].unique().to_list()) == {"charge", "discharge"}

    charge = collect.select_ica_direction(fresh(), "charge")
    discharge = collect.select_ica_direction(fresh(), "discharge")
    kept = collect.select_ica_direction(fresh(), "both")
    assert set(charge.data["direction"].unique().to_list()) == {"charge"}
    assert set(discharge.data["direction"].unique().to_list()) == {"discharge"}
    assert set(kept.data["direction"].unique().to_list()) == {"charge", "discharge"}


def test_ica_figure_empty_cycles(loaded_library):
    rec = loaded_library.all()[0]
    fig = json.loads(plotting.ica_figure(rec, IcaPlotSpec(cell_id=rec.id, cycles=[])))
    assert "layout" in fig


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
    """Group avg averages multi-member groups even when a singleton exists.

    cellpy ≥2.1.2 fixed the all-or-nothing ``group_it`` guard (#816/#27): one
    collection now carries the averaged multi-member group *and* the singleton,
    so the app no longer partitions the selection itself.
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

    # Single collection: cellpy averages group 1 and keeps group 2 (singleton).
    cols = collect.summary_columns_for("capacity_ce", "gravimetric")
    coll = collect.summary_collection(lib.selected(), columns=cols, group_it=True)
    assert collect.is_grouped(coll)
    groups = set(coll.data.get_column("group").unique().to_list())
    assert groups == {1, 2}

    spec = SummaryPlotSpec(plot_type="capacity_ce", group_average=True, spread=True)
    fig = json.loads(plotting.summary_figure(lib.selected(), spec))
    names = {tr.get("name") for tr in fig["data"]}
    # Averaged group legends use the group id; spread adds Upper/Lower Bound traces.
    assert any(
        (isinstance(n, str) and (n in {"1", "2"} or n.startswith("Upper Bound")))
        for n in names
    )
    assert len(fig["data"]) >= 3


def test_group_average_singleton_traces_on_correct_facet(example_cell):
    """Avg group + singleton both render on every variable facet (#39/#816).

    cellpy ≥2.1.2 builds one grouped collection, so each variable's facet row
    carries both the averaged group and the singleton — no app-side merge/remap.
    The singleton is drawn as its own group (std=0), not a stray per-cell trace.
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

    fig = json.loads(
        plotting.summary_figure(
            lib.selected(),
            SummaryPlotSpec(plot_type="capacity_ce", group_average=True, spread=True),
        )
    )

    # capacity_ce has three facets (CE + charge + discharge), one y-axis each.
    axes = {tr.get("yaxis") or "y" for tr in fig["data"]}
    assert len(axes) >= 3

    # Every facet row shows both the averaged group (1) and the singleton (2).
    groups_by_axis: dict[str, set[str]] = {}
    for tr in fig["data"]:
        lg = tr.get("legendgroup")
        if lg is None:
            continue
        ax = tr.get("yaxis") or "y"
        groups_by_axis.setdefault(ax, set()).add(str(lg))
    assert groups_by_axis
    for ax, groups in groups_by_axis.items():
        assert {"1", "2"} <= groups, (ax, groups)


def _yaxis_titles(fig: dict) -> list[str]:
    titles = []
    for key, axis in fig["layout"].items():
        if not key.startswith("yaxis"):
            continue
        title = axis.get("title")
        if isinstance(title, dict):
            title = title.get("text")
        if isinstance(title, str) and title:
            titles.append(title.replace("<br>", " "))
    return titles


def test_summary_figure_pretty_axis_labels(loaded_library):
    """Summary y-titles use cellpy label builders with units (#38)."""
    fig = json.loads(
        plotting.summary_figure(
            loaded_library.selected(),
            SummaryPlotSpec(plot_type="capacity_ce", basis="gravimetric"),
        )
    )
    titles = _yaxis_titles(fig)
    joined = " | ".join(titles)
    assert titles
    assert not any("charge_capacity_" in t for t in titles)
    assert any("mAh/g" in t for t in titles), joined
    assert any("%" in t for t in titles), joined

    areal = json.loads(
        plotting.summary_figure(
            loaded_library.selected(),
            SummaryPlotSpec(plot_type="capacity_ce", basis="areal"),
        )
    )
    areal_titles = _yaxis_titles(areal)
    areal_joined = " | ".join(areal_titles)
    assert any("mAh/cm" in t for t in areal_titles), areal_joined
    assert not any("mAh/g" in t for t in areal_titles if "capacity" in t.lower()), areal_joined


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


def _yaxis_for_pretty_title(fig: dict, title_prefix: str) -> str | None:
    """Layout y-axis whose title starts with ``title_prefix`` (spread-safe)."""
    for key, axis in fig.get("layout", {}).items():
        if not str(key).startswith("yaxis"):
            continue
        title = axis.get("title")
        if isinstance(title, dict):
            title = title.get("text")
        if isinstance(title, str) and (
            title == title_prefix
            or title.startswith(f"{title_prefix} ")
            or title.startswith(f"{title_prefix} (")
        ):
            return key
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


def test_summary_figure_y_ranges_one_sided_max(loaded_library):
    """Summary CE max-only fills min from that panel's data extent."""
    fig = json.loads(
        plotting.summary_figure(
            loaded_library.selected(),
            SummaryPlotSpec(
                plot_type="capacity_ce",
                # CE panels are percent-scale in cellpy plots.
                y_ranges={"coulombic_efficiency": [None, 110.0]},
            ),
        )
    )
    axis = _yaxis_for_variable(fig, "coulombic_efficiency")
    assert axis is not None
    lo, hi = fig["layout"][axis]["range"]
    assert hi == 110.0
    assert lo < hi
    assert fig["layout"][axis].get("autorange") is False


def test_summary_figure_y_ranges_one_sided_min(loaded_library):
    """Summary charge min-only fills max from that panel's data extent."""
    fig = json.loads(
        plotting.summary_figure(
            loaded_library.selected(),
            SummaryPlotSpec(
                plot_type="capacity_ce",
                y_ranges={"charge_capacity_gravimetric": [0.0, None]},
            ),
        )
    )
    axis = _yaxis_for_variable(fig, "charge_capacity_gravimetric")
    assert axis is not None
    lo, hi = fig["layout"][axis]["range"]
    assert lo == 0.0
    assert hi > lo


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


def test_summary_figure_y_ranges_charge_on_multipart_group_avg(loaded_library):
    """Charge y-range on mixed group-avg + singleton path (#60)."""
    import warnings

    from cellpy_simple_gui.core import cellpy_adapter

    lib = loaded_library
    lib.add_cell(cellpy_adapter.load_example("rate"), source="example:rate")
    lib.add_cell(cellpy_adapter.load_example("cellpy"), source="example:cellpy2")
    recs = lib.all()
    recs[0].group = 1
    recs[1].group = 1
    recs[2].group = 2
    for rec in recs:
        rec.selected = True

    charge = [0.0, 200.0]
    ce = [0.9, 1.05]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fig = json.loads(
            plotting.summary_figure(
                lib.selected(),
                SummaryPlotSpec(
                    plot_type="capacity_ce",
                    group_average=True,
                    y_ranges={
                        "charge_capacity_gravimetric": charge,
                        "coulombic_efficiency": ce,
                    },
                ),
            )
        )
    facet_miss = [
        w
        for w in caught
        if "y_ranges" in str(w.message) and "did not match" in str(w.message)
    ]
    assert not facet_miss, facet_miss

    charge_axis = _yaxis_for_variable(fig, "charge_capacity_gravimetric") or (
        _yaxis_for_pretty_title(fig, "Charge Capacity")
    )
    ce_axis = _yaxis_for_variable(fig, "coulombic_efficiency") or (
        _yaxis_for_pretty_title(fig, "Coulombic Efficiency")
    )
    assert charge_axis is not None
    assert ce_axis is not None
    assert fig["layout"][charge_axis].get("range") == charge
    assert fig["layout"][ce_axis].get("range") == ce


def test_summary_panels_for_capacity_ce():
    panels = collect.summary_panels_for("capacity_ce", "gravimetric")
    ids = [p["id"] for p in panels]
    assert ids == [
        "coulombic_efficiency",
        "charge_capacity_gravimetric",
        "discharge_capacity_gravimetric",
    ]
    assert panels[0]["label"] == "CE"


def _summary_facet_titles_top_to_bottom(fig: dict) -> list[str]:
    """Y-axis title texts ordered by Plotly domain (top facet first)."""
    axes: list[tuple[float, str]] = []
    for key, axis in (fig.get("layout") or {}).items():
        if not str(key).startswith("yaxis"):
            continue
        domain = axis.get("domain") or [0, 1]
        title = axis.get("title")
        text = title.get("text") if isinstance(title, dict) else title
        axes.append((float(domain[1]), str(text or "")))
    axes.sort(key=lambda item: item[0], reverse=True)
    return [text for _, text in axes]


@pytest.mark.parametrize("group_average", [False, True])
def test_summary_capacity_ce_facet_order_stable(loaded_library, group_average):
    """CE stays on top with Group avg on or off (#81)."""
    from cellpy_simple_gui.core import cellpy_adapter

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
                group_average=group_average,
                spread=False,
            ),
        )
    )
    titles = _summary_facet_titles_top_to_bottom(fig)
    assert len(titles) >= 3
    assert "Coulombic efficiency" in titles[0]
    assert "Charge capacity" in titles[1]
    assert "Discharge capacity" in titles[2]


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
    spec = CyclesPlotSpec(cell_id=rec.id, cycles=[1, 2], layout="per_cell")
    data, media = export.cycles_export([rec], spec, "csv")
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


# ---- cellpy config diagnostics -------------------------------------------- #

def test_config_diagnostics_shape():
    """Panel data: sections with provenance, paths/units first, no secrets."""
    from cellpy_simple_gui.core import cellpy_config

    d = cellpy_config.diagnostics()
    assert d["cellpy_version"]
    names = [s["name"] for s in d["sections"]]
    assert "paths" in names and "units" in names
    assert "secrets" not in names
    # primary sections sort to the front so the panel opens on what matters
    assert names[:2] == ["paths", "units"]
    assert sum(d["layer_counts"].values()) == sum(len(s["entries"]) for s in d["sections"])
    for entry in next(s for s in d["sections"] if s["name"] == "paths")["entries"]:
        assert entry["layer"] in ("default", "user_file", "project_file", "env", "runtime")


def test_config_diagnostics_masks_credentialish_values(monkeypatch):
    """A legacy Arbin SQL password must never render (cellpy #849)."""
    from cellpy_simple_gui.core import cellpy_config

    monkeypatch.setattr(
        cellpy_config,
        "_config_dump",
        lambda: {"instruments": {"Arbin": {"SQL_PWD": "hunter2", "SQL_server": "db01"}}},
    )
    d = cellpy_config.diagnostics()
    entries = next(s for s in d["sections"] if s["name"] == "instruments")["entries"]
    pwd = next(e for e in entries if e["key"].endswith("SQL_PWD"))
    server = next(e for e in entries if e["key"].endswith("SQL_server"))
    assert pwd["secret"] is True and "hunter2" not in pwd["value"]
    assert server["secret"] is False and server["value"] == "db01"  # not a credential
    assert "hunter2" not in json.dumps(d)


def test_config_diagnostics_warns_on_legacy_fallback(monkeypatch):
    """No cellpy.toml + a legacy YAML => tell the user to migrate."""
    from cellpy_simple_gui.core import cellpy_config

    monkeypatch.setattr(
        cellpy_config,
        "_discovery",
        lambda: {
            "user_config_path": "/nope/cellpy.toml",
            "user_config_exists": False,
            "project_config_path": None,
            "legacy_config_path": "/home/u/.cellpy_prms_default.conf",
            "legacy_fallback": True,
        },
    )
    warnings = cellpy_config.diagnostics()["warnings"]
    assert any("legacy" in w.lower() and "cellpy.toml" in w for w in warnings)


def test_config_diagnostics_survives_broken_provenance(monkeypatch):
    """A failing sources() must degrade to 'default', not break the panel."""
    from cellpy_simple_gui.core import cellpy_config

    monkeypatch.setattr(
        cellpy_config, "_sources", lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    with pytest.raises(RuntimeError):
        cellpy_config._sources()
    monkeypatch.setattr(cellpy_config, "_sources", lambda: {})
    d = cellpy_config.diagnostics()
    assert all(e["layer"] == "default" for s in d["sections"] for e in s["entries"])


# ---- developer mode (#97) ------------------------------------------------- #

@pytest.fixture()
def dev_mode(monkeypatch):
    """Run a block with CSG_DEV_MODE=1 and a fresh settings cache."""
    from cellpy_simple_gui.config import get_settings

    monkeypatch.setenv("CSG_DEV_MODE", "1")
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


def test_dev_mode_off_by_default(monkeypatch):
    from cellpy_simple_gui.config import DEFAULT_MAX_FILES, get_settings

    monkeypatch.delenv("CSG_DEV_MODE", raising=False)
    get_settings.cache_clear()
    try:
        s = get_settings()
        assert s.dev_mode is False
        assert s.max_files == DEFAULT_MAX_FILES
    finally:
        get_settings.cache_clear()


def test_dev_mode_raises_file_ceiling(dev_mode):
    from cellpy_simple_gui.config import DEV_MAX_FILES
    from cellpy_simple_gui.core.files import effective_max_files

    assert dev_mode.dev_mode is True
    assert dev_mode.max_files == DEV_MAX_FILES
    # a client may ask for more than the regular cap, but never past the ceiling
    assert effective_max_files(200) == 200
    assert effective_max_files(10_000) == DEV_MAX_FILES


def test_regular_mode_clamps_file_request(monkeypatch):
    """A hand-made request cannot exceed the regular-user cap."""
    from cellpy_simple_gui.config import DEFAULT_MAX_FILES, get_settings
    from cellpy_simple_gui.core.files import effective_max_files

    monkeypatch.delenv("CSG_DEV_MODE", raising=False)
    get_settings.cache_clear()
    try:
        assert effective_max_files(10_000) == DEFAULT_MAX_FILES
        assert effective_max_files(0) == DEFAULT_MAX_FILES
    finally:
        get_settings.cache_clear()


def test_registry_plot_types_mark_availability(loaded_library):
    """Every cellpy family is listed; the unusable ones say what is missing."""
    types = collect.registry_plot_types(loaded_library.selected())
    assert len(types) > 10  # the whole registry, not the curated set
    assert all(t["id"].startswith(collect.FAMILY_PREFIX) for t in types)
    assert all(t["source"] == "registry" for t in types)

    ok = [t for t in types if not t.get("unavailable_reason")]
    bad = [t for t in types if t.get("unavailable_reason")]
    assert ok and bad, "expected both plottable and unplottable families"
    assert all(t["columns"] and not t["missing"] for t in ok)
    # the reason names the actual missing columns, so it is actionable
    for t in bad:
        if t["missing"]:
            assert all(c in t["unavailable_reason"] for c in t["missing"])


def test_family_plot_type_renders(loaded_library):
    recs = loaded_library.selected()
    ok = next(
        t for t in collect.registry_plot_types(recs) if not t.get("unavailable_reason")
    )
    cols = collect.summary_columns_for(ok["id"], "gravimetric", recs)
    assert cols == tuple(ok["columns"])
    fig = json.loads(plotting.summary_figure(recs, SummaryPlotSpec(plot_type=ok["id"])))
    assert len(fig["data"]) >= 1


def test_unavailable_family_explains_itself(loaded_library):
    """A family the data cannot support must say so, not render blank (#97)."""
    recs = loaded_library.selected()
    bad = next(
        t for t in collect.registry_plot_types(recs)
        if t.get("unavailable_reason") and t["missing"]
    )
    fig = json.loads(plotting.summary_figure(recs, SummaryPlotSpec(plot_type=bad["id"])))
    assert not fig["data"]
    text = " ".join(a.get("text", "") for a in fig["layout"].get("annotations") or [])
    assert text, "an unplottable family must explain itself"
    assert bad["missing"][0] in text
    with pytest.raises(ValueError, match=bad["missing"][0]):
        export.summary_export(recs, SummaryPlotSpec(plot_type=bad["id"]), "csv")


def test_curated_plot_types_unaffected(loaded_library):
    """Regular users still get exactly the curated list."""
    recs = loaded_library.selected()
    assert collect.summary_columns_for("capacity_ce", "gravimetric", recs) == (
        "coulombic_efficiency",
        "charge_capacity_gravimetric",
        "discharge_capacity_gravimetric",
    )


# ---- differential voltage (DVA) ------------------------------------------- #

def test_dva_figure_directions(loaded_library):
    """dV/dQ renders per direction; cellpy's dva_plot is single-cell."""
    from cellpy_simple_gui.core.models import DvaPlotSpec

    rec = loaded_library.all()[0]
    kwargs = dict(cell_id=rec.id, cycles=[1, 2])
    for direction in ("charge", "discharge"):
        fig = json.loads(
            plotting.dva_figure(rec, DvaPlotSpec(**kwargs, direction=direction))
        )
        assert len(fig["data"]) >= 1
        # a single direction draws one consistent style (nothing to distinguish)
        assert len({(t.get("line") or {}).get("dash") for t in fig["data"]}) == 1


def test_dva_both_distinguishes_half_cycles(loaded_library):
    """cellpy #862/#863: the collected DVA path labels and dashes both halves."""
    from cellpy_simple_gui.core.models import DvaPlotSpec

    rec = loaded_library.all()[0]
    fig = json.loads(
        plotting.dva_figure(
            rec, DvaPlotSpec(cell_id=rec.id, cycles=[1, 2], direction="both")
        )
    )
    names = [t.get("name") or "" for t in fig["data"]]
    dashes = [(t.get("line") or {}).get("dash") for t in fig["data"]]
    assert any("charge" in n for n in names) and any("discharge" in n for n in names)
    # the two half-cycles must not be drawn identically (static exports)
    assert len(set(dashes)) > 1


def test_dva_collection_spans_cells(loaded_library):
    """collect_dva (cellpy #863) makes DVA multi-cell, like ICA."""
    from cellpy_simple_gui.core import cellpy_adapter

    lib = loaded_library
    lib.add_cell(cellpy_adapter.load_example("rate"), source="ex:rate")
    recs = lib.selected()
    assert len(recs) >= 2
    coll = collect.dva_collection(recs, cycles=(1, 2))
    assert {"cycle", "direction", "capacity", "dvdq", "cell"} <= set(coll.data.columns)
    assert len(coll.data.get_column("cell").unique().to_list()) == len(recs)


def test_dva_figure_needs_cycles(loaded_library):
    from cellpy_simple_gui.core.models import DvaPlotSpec

    rec = loaded_library.all()[0]
    fig = json.loads(plotting.dva_figure(rec, DvaPlotSpec(cell_id=rec.id, cycles=[])))
    assert not fig["data"]
    assert "dV/dQ" in fig["layout"]["annotations"][0]["text"]


def test_dva_export_matches_chart(loaded_library):
    """Export mirrors the plotted direction and rides the shared polars path."""
    from cellpy_simple_gui.core.models import DvaPlotSpec

    rec = loaded_library.all()[0]
    spec = DvaPlotSpec(cell_id=rec.id, cycles=[1, 2], direction="both")
    coll = collect.dva_collection([rec], cycles=(1, 2))
    assert {"cycle", "direction", "capacity", "dvdq"} <= set(coll.data.columns)
    assert set(coll.data["direction"].unique().to_list()) == {"charge", "discharge"}

    data, media = export.dva_export(rec, spec, "csv")
    assert media == "text/csv"
    header = data.decode().splitlines()[0]
    assert "dvdq" in header and "direction" in header

    charge, _ = export.dva_export(
        rec, DvaPlotSpec(cell_id=rec.id, cycles=[1, 2], direction="charge"), "csv"
    )
    assert "discharge" not in charge.decode()


def test_registry_plot_types_without_cells_says_so(loaded_library):
    """With nothing loaded, availability is unknown — do not claim data is missing.

    The list is built at startup before any cells exist, so the wrong wording
    here made every family look unplottable on a freshly opened project.
    """
    types = collect.registry_plot_types([])
    assert types and all(t["unavailable_reason"] for t in types)
    assert all("load cells" in t["unavailable_reason"] for t in types)
    # ...and with cells it resolves properly again
    with_cells = collect.registry_plot_types(loaded_library.selected())
    assert any(not t.get("unavailable_reason") for t in with_cells)


def test_summary_schema_unions_across_cells(loaded_library):
    """One cell with an unreadable summary must not hide the others' columns."""
    class _Broken:
        @property
        def data(self):
            raise RuntimeError("no summary here")

        @property
        def schema(self):
            raise RuntimeError("no schema here")

    class _Rec:
        cell = _Broken()

    recs = loaded_library.selected()
    hdr, available = collect._summary_schema(recs)
    assert hdr is not None and available
    # a broken cell in the mix leaves the good cells' columns intact
    hdr2, available2 = collect._summary_schema([_Rec(), *recs])
    assert hdr2 is not None
    assert available2 == available


# ---- raw / cycle_info views ----------------------------------------------- #

def test_raw_figure_is_thinned_for_transport(loaded_library):
    """cellpy #867: raw_plot ships the whole frame (~18 MiB); we thin it."""
    from cellpy_simple_gui.core.models import RawPlotSpec

    rec = loaded_library.all()[0]
    raw_rows = len(rec.cell.data.raw)
    assert raw_rows > 10_000, "example cell should be big enough to exercise thinning"

    spec = RawPlotSpec(cell_id=rec.id, plot_type="full", max_points=2000)
    payload = plotting.raw_figure(rec, spec)
    fig = json.loads(payload)
    assert fig["data"]
    # every trace is capped, so the payload stays sane for a browser
    for tr in fig["data"]:
        x = tr.get("x")
        if isinstance(x, list):
            assert len(x) <= spec.max_points + 1
    assert len(payload) < 4_000_000
    # ...and the thinning is disclosed rather than silent
    notes = " ".join(a.get("text", "") for a in fig["layout"].get("annotations") or [])
    assert "point" in notes


def test_raw_figure_plot_types(loaded_library):
    from cellpy_simple_gui.core.models import RawPlotSpec

    rec = loaded_library.all()[0]
    for plot_type in ("voltage-current", "capacity", "full"):
        fig = json.loads(
            plotting.raw_figure(rec, RawPlotSpec(cell_id=rec.id, plot_type=plot_type))
        )
        assert fig["data"], plot_type


def test_cycle_info_figure(loaded_library):
    """cycle_info_plot returns None for plotly unless get_axes=True."""
    from cellpy_simple_gui.core.models import CycleInfoPlotSpec

    rec = loaded_library.all()[0]
    fig = json.loads(
        plotting.cycle_info_figure(rec, CycleInfoPlotSpec(cell_id=rec.id, cycles=[1, 2]))
    )
    assert fig["data"], "expected a figure, not the None cellpy returns by default"


def test_cycle_info_needs_cycles(loaded_library):
    from cellpy_simple_gui.core.models import CycleInfoPlotSpec

    rec = loaded_library.all()[0]
    fig = json.loads(plotting.cycle_info_figure(rec, CycleInfoPlotSpec(cell_id=rec.id)))
    assert not fig["data"]
    assert "cycle" in fig["layout"]["annotations"][0]["text"].lower()


def test_thin_traces_leaves_small_figures_alone(loaded_library):
    """Thinning must be a no-op below the cap — no spurious 'every Nth' note."""
    from cellpy_simple_gui.core.models import IcaPlotSpec

    rec = loaded_library.all()[0]
    fig = json.loads(plotting.ica_figure(rec, IcaPlotSpec(cell_id=rec.id, cycles=[1])))
    notes = " ".join(a.get("text", "") for a in fig["layout"].get("annotations") or [])
    assert "every" not in notes
