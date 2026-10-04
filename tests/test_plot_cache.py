"""Plot memo: reuse a figure when only the restyle changes, drop it when data does."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from cellpy_simple_gui.api.app import create_app
from cellpy_simple_gui.config import get_settings
from cellpy_simple_gui.core import collect, plot_cache, plotting
from cellpy_simple_gui.core.library import Library, get_library
from cellpy_simple_gui.core.models import SummaryPlotSpec


def _line_colors(figure_json: str) -> list[str]:
    colors = []
    for trace in json.loads(figure_json)["data"]:
        line = trace.get("line") or {}
        color = line.get("color")
        if isinstance(color, str):
            colors.append(color)
    return colors


def _figure(figure_json: str) -> dict:
    """Parsed figure, without empty annotation fonts Plotly writes only on the live object."""
    fig = json.loads(figure_json)
    for ann in (fig.get("layout") or {}).get("annotations") or []:
        if ann.get("font") == {}:
            ann.pop("font", None)
    return fig


def test_cosmetic_fields_share_a_structural_key():
    base = {"plot_type": "capacity_ce", "color_scheme": "cellpy", "figure_theme": "light"}
    painted = {**base, "color_scheme": "safe", "group_shade": False, "shade_spread": 0.2}
    assert plot_cache.structural(base) == plot_cache.structural(painted)
    assert plot_cache.structural(base) != plot_cache.structural({**base, "figure_theme": "dark"})
    assert plot_cache.structural(base) != plot_cache.structural({**base, "plot_type": "end_voltages"})


def test_mutators_bump_revision_and_mark_saved_does_not(example_cell):
    lib = Library()
    assert lib.revision == 0
    rec = lib.add_cell(example_cell, source="ex")
    assert lib.revision == 1
    lib.restore_cell(example_cell, source="ex")
    assert lib.revision == 2
    lib.update(rec.id, label="renamed")
    assert lib.revision == 3
    lib.set_selection(False)
    assert lib.revision == 4
    lib.set_group_label(rec.group, "anode")
    assert lib.revision == 5
    lib.mark_saved(rec.id, "not-a-real-file.cellpy")
    assert lib.revision == 5
    lib.remove(rec.id)
    assert lib.revision == 6
    lib.clear()
    assert lib.revision == 7


def test_same_spec_collects_and_plots_once(loaded_library, monkeypatch):
    calls = {"collect": 0, "plot": 0}
    real_collect = collect.collect_summaries

    def spy_collect(*args, **kwargs):
        calls["collect"] += 1
        return real_collect(*args, **kwargs)

    from cellpy.collect.collection import Collection

    real_plot = Collection.plot

    def spy_plot(self, *args, **kwargs):
        calls["plot"] += 1
        return real_plot(self, *args, **kwargs)

    monkeypatch.setattr(collect, "collect_summaries", spy_collect)
    monkeypatch.setattr(Collection, "plot", spy_plot)
    records = loaded_library.selected()
    spec = SummaryPlotSpec()
    first = plotting.summary_figure(records, spec)
    second = plotting.summary_figure(records, spec)
    assert _figure(first) == _figure(second)
    assert calls == {"collect": 1, "plot": 1}


def test_color_change_restyles_without_replot(loaded_library, monkeypatch):
    calls = {"collect": 0, "plot": 0}
    real_collect = collect.collect_summaries

    def spy_collect(*args, **kwargs):
        calls["collect"] += 1
        return real_collect(*args, **kwargs)

    from cellpy.collect.collection import Collection

    real_plot = Collection.plot

    def spy_plot(self, *args, **kwargs):
        calls["plot"] += 1
        return real_plot(self, *args, **kwargs)

    monkeypatch.setattr(collect, "collect_summaries", spy_collect)
    monkeypatch.setattr(Collection, "plot", spy_plot)
    records = loaded_library.selected()
    safe = plotting.summary_figure(records, SummaryPlotSpec(color_scheme="safe"))
    muted = plotting.summary_figure(records, SummaryPlotSpec(color_scheme="muted"))
    safe_again = plotting.summary_figure(records, SummaryPlotSpec(color_scheme="safe"))
    assert calls == {"collect": 1, "plot": 1}
    assert _line_colors(safe) == _line_colors(safe_again)
    assert _line_colors(safe) != _line_colors(muted)


def test_structural_change_rebuilds(loaded_library, monkeypatch):
    calls = {"collect": 0, "plot": 0}
    real_collect = collect.collect_summaries

    def spy_collect(*args, **kwargs):
        calls["collect"] += 1
        return real_collect(*args, **kwargs)

    from cellpy.collect.collection import Collection

    real_plot = Collection.plot

    def spy_plot(self, *args, **kwargs):
        calls["plot"] += 1
        return real_plot(self, *args, **kwargs)

    monkeypatch.setattr(collect, "collect_summaries", spy_collect)
    monkeypatch.setattr(Collection, "plot", spy_plot)
    records = loaded_library.selected()
    plotting.summary_figure(records, SummaryPlotSpec(basis="gravimetric"))
    plotting.summary_figure(records, SummaryPlotSpec(basis="absolute"))
    plotting.summary_figure(records, SummaryPlotSpec(basis="absolute", figure_theme="dark"))
    assert calls["collect"] == 2
    assert calls["plot"] == 3


def test_cache_off_rebuilds(loaded_library, monkeypatch):
    monkeypatch.setenv("CSG_PLOT_CACHE", "0")
    calls = {"collect": 0}
    real_collect = collect.collect_summaries

    def spy_collect(*args, **kwargs):
        calls["collect"] += 1
        return real_collect(*args, **kwargs)

    monkeypatch.setattr(collect, "collect_summaries", spy_collect)
    records = loaded_library.selected()
    spec = SummaryPlotSpec()
    plotting.summary_figure(records, spec)
    plotting.summary_figure(records, spec)
    assert calls["collect"] == 2


def test_label_edit_misses_the_collect_cache(loaded_library, monkeypatch):
    calls = {"collect": 0}
    real_collect = collect.collect_summaries

    def spy_collect(*args, **kwargs):
        calls["collect"] += 1
        return real_collect(*args, **kwargs)

    monkeypatch.setattr(collect, "collect_summaries", spy_collect)
    records = loaded_library.selected()
    spec = SummaryPlotSpec()
    plotting.summary_figure(records, spec)
    loaded_library.update(records[0].id, label="renamed-for-cache")
    plotting.summary_figure(loaded_library.selected(), spec)
    assert calls["collect"] == 2


@pytest.fixture()
def client():
    get_library().clear()
    token = get_settings().token
    app = TestClient(create_app())
    app.headers.update({"X-CSG-Token": token})
    return app


def test_state_revision_increases_after_edit(client, example_cell):
    before = client.get("/api/state").json()["revision"]
    get_library().add_cell(example_cell, source="ex")
    state = client.get("/api/state").json()
    assert state["revision"] == before + 1
    cell_id = state["cells"][0]["id"]
    updated = client.post(
        f"/api/cells/{cell_id}/update", json={"id": cell_id, "label": "renamed"}
    ).json()
    assert updated["state"]["revision"] == state["revision"] + 1
