"""Integration tests for the FastAPI layer using TestClient."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from cellpy_simple_gui.api.app import create_app
from cellpy_simple_gui.config import get_settings
from cellpy_simple_gui.core.library import get_library


@pytest.fixture()
def client():
    get_library().clear()
    token = get_settings().token
    c = TestClient(create_app())
    c.headers.update({"X-CSG-Token": token})
    return c


def _wait_for_job(client, job_id, timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        snap = client.get(f"/api/jobs/{job_id}").json()
        if snap["status"] in ("done", "error", "cancelled"):
            return snap
        time.sleep(0.3)
    raise AssertionError("job did not finish in time")


@pytest.mark.essential
def test_healthz(client):
    assert client.get("/healthz").json() == {"ok": True}


def test_branding_static_assets(client):
    for path in (
        "/static/img/favicon.svg",
        "/static/img/cellpy-icon.svg",
        "/static/img/cellpy-icon.png",
        "/static/img/cellpy-icon.ico",
    ):
        r = client.get(path)
        assert r.status_code == 200, path
        assert len(r.content) > 0


def test_index_uses_cellpy_logo(client):
    html = client.get("/").text
    assert "◧" not in html
    assert "/static/img/cellpy-icon.svg" in html
    assert 'rel="icon" href="/static/img/favicon.svg"' in html


def test_system_capabilities_no_file_picker(client):
    """TestClient has no pywebview window — same as --server mode."""
    caps = client.get("/api/system/capabilities").json()
    assert caps["file_picker"] is False
    assert "dev_mode" in caps and "max_files" in caps


def test_system_pick_rejected_without_webview(client):
    r = client.post("/api/system/pick", json={"kind": "cellpy"})
    assert r.status_code == 400
    assert "desktop" in r.json()["detail"].lower()


@pytest.mark.essential
def test_cellpy_config_diagnostics_endpoint(client):
    """The config panel gets sections + provenance, and never a secrets section."""
    data = client.get("/api/system/cellpy-config").json()
    assert data["cellpy_version"]
    assert data["discovery"]["user_config_path"]
    names = [s["name"] for s in data["sections"]]
    assert "paths" in names and "units" in names
    assert "secrets" not in names  # credentials must never reach the UI
    # paths/units lead so the panel opens on the settings people ask about
    assert names[0] in ("paths", "units")
    paths = next(s for s in data["sections"] if s["name"] == "paths")
    entry = next(e for e in paths["entries"] if e["key"] == "paths.cellpydatadir")
    assert entry["layer"] in ("default", "user_file", "project_file", "env", "runtime")
    assert entry["is_path"] and "exists" in entry
    assert [v["name"] for v in data["secret_env"]]
    assert all("set" in v and "value" not in v for v in data["secret_env"])


def test_webview_file_type_filters_are_valid():
    """pywebview rejects descriptions outside [\\w ] — keep dialog filters parseable."""
    from webview.util import parse_file_type

    from cellpy_simple_gui.api.routers import system

    for kind, types in system._FILE_TYPES.items():
        for ft in types:
            parse_file_type(ft)  # raises ValueError if invalid
    for ft in system._SAVE_TYPE_BY_EXT.values():
        parse_file_type(ft)
    parse_file_type("All files (*.*)")


def test_system_save_rejected_without_webview(client):
    r = client.post(
        "/api/system/save?filename=summary.svg",
        content=b"<svg xmlns='http://www.w3.org/2000/svg'/>",
        headers={"Content-Type": "application/octet-stream"},
    )
    assert r.status_code == 400
    assert "desktop" in r.json()["detail"].lower()


@pytest.mark.essential
def test_token_required():
    c = TestClient(create_app())  # no token header
    assert c.get("/api/state").status_code == 401


def test_job_cancel_unknown(client):
    r = client.post("/api/jobs/does-not-exist/cancel")
    assert r.status_code == 404


def test_job_cancel_running_load(client):
    r = client.post("/api/load/example", json={"kinds": ["cellpy"]})
    job_id = r.json()["job_id"]
    cr = client.post(f"/api/jobs/{job_id}/cancel")
    assert cr.status_code == 200
    assert cr.json()["cancelled"] is True
    snap = _wait_for_job(client, job_id, timeout=90)
    assert snap["status"] in ("cancelled", "done")  # may finish before cancel lands


@pytest.mark.essential
def test_examples(client):
    data = client.get("/api/examples").json()
    ids = {e["id"] for e in data}
    assert {"cellpy", "old_cellpy", "rate"} <= ids


@pytest.mark.essential
def test_load_and_plot_flow(client):
    # kick off a load job for one example cell
    r = client.post("/api/load/example", json={"kinds": ["cellpy"]})
    job_id = r.json()["job_id"]
    snap = _wait_for_job(client, job_id)
    if snap["status"] != "done":
        pytest.skip(f"example data unavailable: {snap.get('message')}")
    assert snap["result"]["added"]

    state = client.get("/api/state").json()
    assert state["n_cells"] == 1
    cell_id = state["cells"][0]["id"]

    # summary figure (cellpy collected plot)
    fig = client.post(
        "/api/plots/summary",
        json={"basis": "gravimetric", "show_charge": True, "show_discharge": True},
    ).json()
    assert len(fig["data"]) >= 1

    # cycles info + single-cell figure (Cell explorer)
    info = client.get(f"/api/cells/{cell_id}/cycles").json()
    assert info["max"] > info["min"]
    cfig = client.post(
        "/api/plots/cycles",
        json={"cell_id": cell_id, "cycles": [1, 5, 10], "layout": "per_cell"},
    ).json()
    assert len(cfig["data"]) >= 1

    # Cycles collector (selected cells, no cell_id)
    bounds = client.get("/api/plots/cycles/bounds").json()
    assert bounds["n_cells"] >= 1
    assert bounds["max"] >= bounds["min"]
    collector = client.post(
        "/api/plots/cycles",
        json={"cycles": [1, 2, 3], "layout": "per_cycle"},
    ).json()
    assert len(collector["data"]) >= 1

    # Cell explorer dQ/dV (ICA)
    ica = client.post(
        "/api/plots/ica",
        json={
            "cell_id": cell_id,
            "cycles": [1, 2, 3],
            "voltage_resolution": 0.005,
            "direction": "charge",
        },
    ).json()
    assert len(ica["data"]) >= 1

    # multi-format export
    for fmt in ("csv", "xlsx", "parquet", "json"):
        r = client.post(f"/api/export/summary?fmt={fmt}", json={"basis": "gravimetric"})
        assert r.status_code == 200, fmt
        assert len(r.content) > 0
    bad = client.post("/api/export/summary?fmt=nope", json={"basis": "gravimetric"})
    assert bad.status_code == 400


def test_edit_cell(client):
    r = client.post("/api/load/example", json={"kinds": ["cellpy"]})
    snap = _wait_for_job(client, r.json()["job_id"])
    if snap["status"] != "done":
        pytest.skip("example data unavailable")
    cell_id = client.get("/api/state").json()["cells"][0]["id"]

    out = client.post(
        f"/api/cells/{cell_id}/update",
        json={
            "id": cell_id,
            "label": "renamed",
            "group": 5,
            "selected": False,
            "mass": 1.25,
            "area": 2.5,
            "nominal_capacity": 1500.0,
            "nom_cap_specifics": "areal",
            "cycle_mode": "cathode",
        },
    ).json()
    assert out["cell"]["label"] == "renamed"
    assert out["cell"]["group"] == 5
    assert out["cell"]["mass"] == 1.25
    assert out["cell"]["area"] == 2.5
    assert out["cell"]["nominal_capacity"] == 1500.0
    assert out["cell"]["nom_cap_specifics"] == "areal"
    assert out["cell"]["cycle_mode"] == "cathode"
    assert out["state"]["n_selected"] == 0


def test_export_cells_requires_selection(client):
    r = client.post("/api/export/cells?fmt=cellpy", json={})
    assert r.status_code == 400
    assert "selected" in r.json()["detail"].lower()


def test_export_cells_cellpy(client):
    r = client.post("/api/load/example", json={"kinds": ["rate"]})
    snap = _wait_for_job(client, r.json()["job_id"])
    if snap["status"] != "done":
        pytest.skip("example data unavailable")
    r = client.post("/api/export/cells?fmt=cellpy", json={})
    assert r.status_code == 200
    assert "attachment" in r.headers.get("content-disposition", "").lower()
    assert len(r.content) > 1000


def test_pin_config_requires_a_project(client):
    """Settings are pinned to a project folder, so there must be one."""
    r = client.post("/api/projects/pin-config")
    assert r.status_code == 400
    assert "project" in r.json()["detail"].lower()


def test_plot_types_curated_by_default(client, monkeypatch):
    """Regular users see only the curated list — no registry families."""
    from cellpy_simple_gui.config import get_settings

    monkeypatch.delenv("CSG_DEV_MODE", raising=False)
    get_settings.cache_clear()
    try:
        data = client.get("/api/plot-types").json()
        assert data["dev_mode"] is False
        assert all(t["source"] == "curated" for t in data["types"])
        assert not any(t["id"].startswith("family:") for t in data["types"])
    finally:
        get_settings.cache_clear()


def test_plot_types_include_registry_in_dev_mode(client, monkeypatch):
    from cellpy_simple_gui.config import get_settings

    monkeypatch.setenv("CSG_DEV_MODE", "1")
    get_settings.cache_clear()
    try:
        data = client.get("/api/plot-types").json()
        assert data["dev_mode"] is True
        families = [t for t in data["types"] if t["source"] == "registry"]
        assert families, "dev mode should expose cellpy's registry"
        assert any(t["source"] == "curated" for t in data["types"])
        caps = client.get("/api/system/capabilities").json()
        assert caps["dev_mode"] is True and caps["max_files"] > 10
    finally:
        get_settings.cache_clear()


def _dva_spec(client):
    """Load one example cell through the API and build a dV/dQ spec for it."""
    snap = _wait_for_job(client, client.post(
        "/api/load/example", json={"kinds": ["cellpy"]}
    ).json()["job_id"])
    if snap["status"] != "done":
        pytest.skip("example data unavailable")
    cell_id = client.get("/api/state").json()["cells"][0]["id"]
    return {"cell_id": cell_id, "cycles": [1, 2], "direction": "both"}


def test_dva_endpoints_hidden_without_dev_mode(client, monkeypatch):
    """dV/dQ is a developer-mode view — refused, with a hint, when off."""
    from cellpy_simple_gui.config import get_settings

    monkeypatch.delenv("CSG_DEV_MODE", raising=False)
    get_settings.cache_clear()
    try:
        spec = _dva_spec(client)
        for url in ("/api/plots/dva", "/api/export/dva?fmt=csv"):
            r = client.post(url, json=spec)
            assert r.status_code == 403, url
            assert "developer mode" in r.json()["detail"].lower()
    finally:
        get_settings.cache_clear()


def test_dva_endpoints_available_in_dev_mode(client, monkeypatch):
    from cellpy_simple_gui.config import get_settings

    monkeypatch.setenv("CSG_DEV_MODE", "1")
    get_settings.cache_clear()
    try:
        spec = _dva_spec(client)
        fig = client.post("/api/plots/dva", json=spec)
        assert fig.status_code == 200
        assert fig.json()["data"]

        data = client.post("/api/export/dva?fmt=csv", json=spec)
        assert data.status_code == 200
        assert data.content.decode().splitlines()[0].startswith("cycle,direction")
        assert "dva_" in data.headers.get("content-disposition", "")
    finally:
        get_settings.cache_clear()
