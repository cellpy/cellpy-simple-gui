"""Compare mode (#169): several cells, each with its own cycles, in one figure.

cellpy collects one ``cycles`` list per batch and only facets (``per_cell`` /
``per_cycle``), so the app narrows the collected frame to the picked
``(cell, cycle)`` pairs and folds the facets onto one axis pair. These tests
pin both halves against the two example cells (``cellpy`` + ``rate``), which
have different lengths and labels — exactly the case the feature exists for.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from cellpy_simple_gui.api.app import create_app
from cellpy_simple_gui.config import get_settings
from cellpy_simple_gui.core import collect, export, plotting
from cellpy_simple_gui.core.library import Library, get_library
from cellpy_simple_gui.core.models import ComparePick, ComparePlotSpec


@pytest.fixture(scope="module")
def two_cells(example_cell):
    """``(cellpy cell, rate cell)`` — distinct labels and cycle counts."""
    from cellpy_simple_gui.core import cellpy_adapter

    try:
        rate = cellpy_adapter.load_example("rate")
    except Exception as exc:  # noqa: BLE001 - offline / download failure
        pytest.skip(f"example data unavailable: {exc}")
    return example_cell, rate


@pytest.fixture()
def two_cell_library(two_cells):
    lib = Library()
    lib.add_cell(two_cells[0], source="example:cellpy")
    lib.add_cell(two_cells[1], source="example:rate")
    return lib


@pytest.fixture()
def picks(two_cell_library):
    a, b = two_cell_library.all()
    return [(a, [1, 3]), (b, [7])]


def _spec(picks, **overrides) -> ComparePlotSpec:
    return ComparePlotSpec(
        picks=[{"cell_id": rec.id, "cycles": cycles} for rec, cycles in picks],
        **overrides,
    )


# --------------------------------------------------------------------------- #
# Spec
# --------------------------------------------------------------------------- #


def test_spec_merges_duplicate_cells_and_sorts_cycles():
    spec = ComparePlotSpec(
        picks=[
            {"cell_id": "a", "cycles": [3, 1, 3]},
            {"cell_id": "b", "cycles": [2]},
            {"cell_id": "a", "cycles": [7]},
        ]
    )
    assert [p.cell_id for p in spec.picks] == ["a", "b"]
    assert spec.picks[0].cycles == [1, 3, 7]
    assert spec.pairs() == {("a", 1), ("a", 3), ("a", 7), ("b", 2)}


def test_spec_rejects_too_many_picks_or_curves():
    with pytest.raises(ValidationError):
        ComparePlotSpec(picks=[{"cell_id": str(i), "cycles": [1]} for i in range(9)])
    with pytest.raises(ValidationError):
        ComparePlotSpec(picks=[])
    with pytest.raises(ValidationError):
        ComparePlotSpec(
            picks=[{"cell_id": str(i), "cycles": list(range(1, 21))} for i in range(5)]
        )
    with pytest.raises(ValidationError):
        ComparePick(cell_id="a", cycles=list(range(41)))


def test_spec_cleans_axis_ranges_like_cycles_spec():
    spec = ComparePlotSpec(
        picks=[{"cell_id": "a", "cycles": [1]}], x_range=[5, 1], y_range=[None, 4.2]
    )
    assert spec.x_range is None
    assert spec.y_range == [None, 4.2]


# --------------------------------------------------------------------------- #
# Core: batch labels, pair filter, overlay
# --------------------------------------------------------------------------- #


def test_batch_keys_match_collected_cell_column(two_cell_library):
    """The filter keys on what cellpy writes to ``cell`` — they must agree."""
    records = two_cell_library.all()
    keys = collect.batch_keys(records)
    collection = collect.cycles_collection(records, cycles=(1,))
    assert set(collection.data["cell"].unique().to_list()) == set(keys)


def test_batch_keys_disambiguate_duplicate_labels(two_cells):
    lib = Library()
    lib.add_cell(two_cells[0], source="x")
    lib.add_cell(two_cells[0], source="x")
    keys = collect.batch_keys(lib.all())
    assert len(set(keys)) == 2
    assert keys[1] == f"{keys[0]} (2)"


def test_restrict_to_cycle_pairs_on_cycles_frame(two_cell_library):
    """Curves frame keys on ``cycle_num``; only the picked pairs survive."""
    records = two_cell_library.all()
    label_a, label_b = collect.batch_keys(records)
    collection = collect.cycles_collection(records, cycles=(1, 3, 7))
    before = set(
        map(tuple, collection.data.select(["cell", "cycle_num"]).unique().rows())
    )
    assert before == {(label_a, 1), (label_a, 3), (label_a, 7), (label_b, 1), (label_b, 3), (label_b, 7)}

    collect.restrict_to_cycle_pairs(collection, {(label_a, 1), (label_a, 3), (label_b, 7)})
    after = set(map(tuple, collection.data.select(["cell", "cycle_num"]).unique().rows()))
    assert after == {(label_a, 1), (label_a, 3), (label_b, 7)}


def test_restrict_to_cycle_pairs_on_ica_frame(two_cell_library):
    """ICA / DVA frames key on ``cycle`` instead — picked by column presence."""
    records = two_cell_library.all()
    label_a, label_b = collect.batch_keys(records)
    collection = collect.ica_collection(records, cycles=(1, 3), voltage_resolution=0.005)
    assert "cycle" in collection.data.columns and "cycle_num" not in collection.data.columns

    collect.restrict_to_cycle_pairs(collection, {(label_a, 3), (label_b, 1)})
    after = set(map(tuple, collection.data.select(["cell", "cycle"]).unique().rows()))
    assert after == {(label_a, 3), (label_b, 1)}


def test_restrict_to_cycle_pairs_leaves_unknown_frames_alone(caplog):
    import polars as pl

    class _Coll:
        data = pl.DataFrame({"x": [1, 2], "y": [3, 4]})

    coll = _Coll()
    with caplog.at_level("WARNING"):
        collect.restrict_to_cycle_pairs(coll, {("a", 1)})
    assert coll.data.height == 2
    assert "compare filter skipped" in caplog.text


def test_overlay_folds_per_cell_facets_onto_one_axis_pair(picks):
    """Real two-cell ``per_cell`` figure → one panel, one entry per curve."""
    spec = _spec(picks)
    fig = json.loads(plotting.compare_figure(picks, spec))

    traces = fig["data"]
    assert len(traces) == 3
    assert {(t.get("xaxis", "x"), t.get("yaxis", "y")) for t in traces} == {("x", "y")}
    axes = [k for k in fig["layout"] if k.startswith(("xaxis", "yaxis"))]
    assert sorted(axes) == ["xaxis", "yaxis"]
    assert not fig["layout"].get("annotations")

    # "<cell> · cycle <n>" per trace, every one in the legend, muting one curve
    # does not take its neighbour with it.
    names = [t["name"] for t in traces]
    assert [n.rsplit("cycle ", 1)[1] for n in names] == ["1", "3", "7"]
    assert all(t.get("showlegend", True) for t in traces)
    assert len({t["legendgroup"] for t in traces}) == 3
    label_a, label_b = collect.batch_keys([rec for rec, _ in picks])
    assert names[0].startswith(label_a[:8]) and names[2].startswith(label_b[:8])
    assert all(len(n) <= collect._LEGEND_NAME_LIMIT for n in names)

    # cellpy colours by cycle number — two cells' cycle 1 would collide — so the
    # overlay runs sequentially through the colorway instead.
    colors = [t["line"]["color"] for t in traces]
    assert len(set(colors)) == 3

    # Axis titles survive from the first facet; the legend says what it lists.
    assert "Capacity" in fig["layout"]["xaxis"]["title"]["text"]
    assert "Voltage" in fig["layout"]["yaxis"]["title"]["text"]
    assert fig["layout"]["legend"]["title"]["text"] == "Cell · cycle"


def test_overlay_keeps_full_identity_in_hover(picks):
    """Legend names are truncated; the PX hovertemplate still carries the cell."""
    fig = json.loads(plotting.compare_figure(picks, _spec(picks)))
    label_a, _ = collect.batch_keys([rec for rec, _ in picks])
    assert f"cell={label_a}" in fig["data"][0]["hovertemplate"]
    assert "cycle_num=1" in fig["data"][0]["hovertemplate"]


def test_overlay_respects_curated_color_scheme(picks):
    fig = json.loads(plotting.compare_figure(picks, _spec(picks, color_scheme="safe")))
    colors = [t["line"]["color"] for t in fig["data"]]
    assert colors == collect.COLOR_SCHEMES["safe"][:3]


def test_side_by_side_keeps_cellpy_facets(picks):
    """``layout=per_cell`` is cellpy's own figure, just narrowed to the picks."""
    fig = json.loads(plotting.compare_figure(picks, _spec(picks, layout="per_cell")))
    pairs = {(t.get("xaxis", "x"), t.get("yaxis", "y")) for t in fig["data"]}
    assert pairs == {("x", "y"), ("x2", "y2")}
    assert len(fig["data"]) == 3
    assert len(fig["layout"]["annotations"]) == 2  # one strip per cell


@pytest.mark.parametrize("kind", ["dqdv", "dvdq"])
def test_compare_differentials(picks, kind):
    fig = json.loads(plotting.compare_figure(picks, _spec(picks, curve_kind=kind)))
    assert len(fig["data"]) == 3
    assert {(t.get("xaxis", "x"), t.get("yaxis", "y")) for t in fig["data"]} == {("x", "y")}
    expect = "dQ/dV" if kind == "dqdv" else "dV/dQ"
    assert expect in fig["layout"]["yaxis"]["title"]["text"]


def test_compare_both_directions_overlay(picks):
    """``direction=both`` doubles the traces and keeps the half-cycle readable."""
    fig = json.loads(
        plotting.compare_figure(picks, _spec(picks, curve_kind="dqdv", direction="both"))
    )
    assert len(fig["data"]) == 6
    names = [t["name"] for t in fig["data"]]
    assert sum("chg" in n for n in names) == 6
    assert sum("dchg" in n for n in names) == 3
    assert all(len(n) <= collect._LEGEND_NAME_LIMIT for n in names)


def test_compare_axis_ranges(picks):
    fig = json.loads(
        plotting.compare_figure(picks, _spec(picks, x_range=[0, 100], y_range=[None, 4.0]))
    )
    assert fig["layout"]["xaxis"]["range"] == [0, 100]
    lo, hi = fig["layout"]["yaxis"]["range"]
    assert hi == 4.0 and lo < hi


def test_compare_empty_picks_render_prompt(picks):
    a, b = (rec for rec, _ in picks)
    spec = ComparePlotSpec(picks=[{"cell_id": a.id}])
    fig = json.loads(plotting.compare_figure([(a, []), (b, [])], spec))
    assert fig["data"] == []
    assert "Pick one or more cycles" in fig["layout"]["annotations"][0]["text"]


def test_compare_export_rows_cover_only_picked_pairs(picks):
    import io

    import polars as pl

    data, media = export.compare_export(picks, _spec(picks), "csv")
    assert media == "text/csv"
    df = pl.read_csv(io.BytesIO(data))
    label_a, label_b = collect.batch_keys([rec for rec, _ in picks])
    pairs = set(map(tuple, df.select(["cell", "cycle_num"]).unique().rows()))
    assert pairs == {(label_a, 1), (label_a, 3), (label_b, 7)}


def test_compare_export_differential_follows_direction(picks):
    import io

    import polars as pl

    data, _ = export.compare_export(
        picks, _spec(picks, curve_kind="dqdv", direction="discharge"), "csv"
    )
    df = pl.read_csv(io.BytesIO(data))
    assert set(df["direction"].unique().to_list()) == {"discharge"}
    assert set(df["cycle"].unique().to_list()) == {1, 3, 7}


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #


@pytest.fixture()
def client(two_cells):
    lib = get_library()
    lib.clear()
    lib.add_cell(two_cells[0], source="example:cellpy")
    lib.add_cell(two_cells[1], source="example:rate")
    c = TestClient(create_app())
    c.headers.update({"X-CSG-Token": get_settings().token})
    yield c
    lib.clear()


def _ids(client) -> tuple[str, str]:
    cells = client.get("/api/state").json()["cells"]
    assert len(cells) == 2
    return cells[0]["id"], cells[1]["id"]


@pytest.mark.essential
def test_api_compare_overlay_and_side_by_side(client):
    a, b = _ids(client)
    body = {"picks": [{"cell_id": a, "cycles": [1, 3]}, {"cell_id": b, "cycles": [7]}]}

    r = client.post("/api/plots/compare", json=body)
    assert r.status_code == 200
    fig = r.json()
    assert len(fig["data"]) == 3
    assert {(t.get("xaxis", "x"), t.get("yaxis", "y")) for t in fig["data"]} == {("x", "y")}

    r = client.post("/api/plots/compare", json={**body, "layout": "per_cell"})
    fig = r.json()
    assert {(t.get("xaxis", "x"), t.get("yaxis", "y")) for t in fig["data"]} == {
        ("x", "y"),
        ("x2", "y2"),
    }


@pytest.mark.essential
@pytest.mark.parametrize("kind", ["dqdv", "dvdq"])
def test_api_compare_differentials(client, kind):
    a, b = _ids(client)
    r = client.post(
        "/api/plots/compare",
        json={
            "picks": [{"cell_id": a, "cycles": [2]}, {"cell_id": b, "cycles": [2]}],
            "curve_kind": kind,
            "direction": "charge",
        },
    )
    assert r.status_code == 200
    assert len(r.json()["data"]) == 2


@pytest.mark.essential
def test_api_compare_validation_and_404(client):
    a, _ = _ids(client)
    r = client.post(
        "/api/plots/compare",
        json={"picks": [{"cell_id": a, "cycles": [1]}, {"cell_id": "nope", "cycles": [1]}]},
    )
    assert r.status_code == 404
    assert "nope" in r.json()["detail"]

    r = client.post(
        "/api/plots/compare",
        json={"picks": [{"cell_id": str(i), "cycles": [1]} for i in range(9)]},
    )
    assert r.status_code == 422

    # No cycles anywhere is a prompt, not a 500.
    r = client.post("/api/plots/compare", json={"picks": [{"cell_id": a, "cycles": []}]})
    assert r.status_code == 200
    assert r.json()["data"] == []


@pytest.mark.essential
def test_api_compare_export(client):
    import io

    import polars as pl

    a, b = _ids(client)
    body = {"picks": [{"cell_id": a, "cycles": [1, 3]}, {"cell_id": b, "cycles": [7]}]}

    r = client.post("/api/export/compare?fmt=csv", json=body)
    assert r.status_code == 200
    assert "compare_2_cells.csv" in r.headers["content-disposition"]
    df = pl.read_csv(io.BytesIO(r.content))
    assert set(df["cycle_num"].unique().to_list()) == {1, 3, 7}
    assert df.select(["cell", "cycle_num"]).unique().height == 3

    r = client.post("/api/export/compare?fmt=nope", json=body)
    assert r.status_code == 400

    r = client.post(
        "/api/export/compare?fmt=csv", json={"picks": [{"cell_id": a, "cycles": []}]}
    )
    assert r.status_code == 400

    # Static figure: bytes when kaleido + a browser are present, else a clean 503.
    r = client.post("/api/export/compare?fmt=png", json=body)
    assert r.status_code in (200, 503), r.text
    if r.status_code == 200:
        assert r.content[:8] == b"\x89PNG\r\n\x1a\n"
        assert "compare_2_cells.png" in r.headers["content-disposition"]
