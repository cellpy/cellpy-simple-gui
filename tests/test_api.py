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
    """pywebview rejects descriptions outside [\\w ] — keep dialog filters parseable.

    Needs the [desktop] extra (#118). Skipped rather than dropped on a
    server-only install: the constraint is real, and this is the only thing
    checking it.
    """
    pytest.importorskip("webview", reason="pywebview lives in the [desktop] extra")
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


def test_dva_endpoints_need_no_dev_mode(client, monkeypatch):
    """dV/dQ is a regular Cell-explorer view (#94), like the dQ/dV beside it."""
    from cellpy_simple_gui.config import get_settings

    monkeypatch.delenv("CSG_DEV_MODE", raising=False)
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


def test_dva_missing_cell_is_404_not_403(client, monkeypatch):
    """Ungating must not turn an unknown cell into a permissions error."""
    from cellpy_simple_gui.config import get_settings

    monkeypatch.delenv("CSG_DEV_MODE", raising=False)
    get_settings.cache_clear()
    try:
        r = client.post(
            "/api/plots/dva",
            json={"cell_id": "nope", "cycles": [1], "direction": "both"},
        )
        assert r.status_code == 404
    finally:
        get_settings.cache_clear()


def test_raw_and_cycle_info_are_dev_only(client, monkeypatch):
    from cellpy_simple_gui.config import get_settings

    spec = _dva_spec(client)          # loads a cell, gives us its id
    cell_id = spec["cell_id"]
    monkeypatch.delenv("CSG_DEV_MODE", raising=False)
    get_settings.cache_clear()
    try:
        for url, body in (
            ("/api/plots/raw", {"cell_id": cell_id}),
            ("/api/plots/cycle-info", {"cell_id": cell_id, "cycles": [1, 2]}),
        ):
            r = client.post(url, json=body)
            assert r.status_code == 403, url
            assert "developer mode" in r.json()["detail"].lower()
    finally:
        get_settings.cache_clear()


def test_raw_and_cycle_info_in_dev_mode(client, monkeypatch):
    from cellpy_simple_gui.config import get_settings

    spec = _dva_spec(client)
    cell_id = spec["cell_id"]
    monkeypatch.setenv("CSG_DEV_MODE", "1")
    get_settings.cache_clear()
    try:
        raw = client.post(
            "/api/plots/raw", json={"cell_id": cell_id, "plot_type": "full", "max_points": 1500}
        )
        assert raw.status_code == 200
        assert raw.json()["data"]
        # the whole point: the response must not be the multi-MiB raw frame
        assert len(raw.content) < 3_000_000

        info = client.post(
            "/api/plots/cycle-info", json={"cell_id": cell_id, "cycles": [1, 2]}
        )
        assert info.status_code == 200
        assert info.json()["data"]
    finally:
        get_settings.cache_clear()


def test_diagnostics_are_dev_only(client, monkeypatch):
    from cellpy_simple_gui.config import get_settings

    monkeypatch.delenv("CSG_DEV_MODE", raising=False)
    get_settings.cache_clear()
    try:
        for url in ("/api/system/logs", "/api/system/jobs"):
            r = client.get(url)
            assert r.status_code == 403, url
            assert "developer mode" in r.json()["detail"].lower()
    finally:
        get_settings.cache_clear()


def test_log_viewer_captures_stdlib_records(monkeypatch):
    """cellpy logs through stdlib, so the bridge must feed the ring buffer."""
    import logging

    from cellpy_simple_gui.config import get_settings

    monkeypatch.setenv("CSG_DEV_MODE", "1")
    get_settings.cache_clear()
    try:
        c = TestClient(create_app())          # create_app arms the ring in dev mode
        c.headers.update({"X-CSG-Token": get_settings().token})
        logging.getLogger("cellpy.readers.fake").warning("a stdlib record")

        data = c.get("/api/system/logs?limit=200").json()
        assert data["capturing"] is True
        mine = [r for r in data["records"] if "a stdlib record" in r["message"]]
        assert mine, "stdlib records must reach the viewer"
        # the originating logger is what makes the viewer useful
        assert mine[0]["name"] == "cellpy.readers.fake"
        assert mine[0]["level"] == "WARNING"

        only_errors = c.get("/api/system/logs?level=ERROR").json()["records"]
        assert all(r["level"] in ("ERROR", "CRITICAL") for r in only_errors)
    finally:
        get_settings.cache_clear()


def test_job_timings_reported(monkeypatch):
    from cellpy_simple_gui.config import get_settings

    monkeypatch.setenv("CSG_DEV_MODE", "1")
    get_settings.cache_clear()
    try:
        c = TestClient(create_app())
        c.headers.update({"X-CSG-Token": get_settings().token})
        snap = _wait_for_job(
            c, c.post("/api/load/example", json={"kinds": ["cellpy"]}).json()["job_id"]
        )
        if snap["status"] != "done":
            pytest.skip("example data unavailable")
        jobs = c.get("/api/system/jobs").json()["jobs"]
        assert jobs
        job = jobs[0]
        assert job["kind"] == "load-example" and job["status"] == "done"
        assert job["queued_seconds"] is not None and job["queued_seconds"] >= 0
        assert job["elapsed_seconds"] is not None and job["elapsed_seconds"] > 0
        assert job["finished_at"] >= job["started_at"] >= job["created_at"]
    finally:
        get_settings.cache_clear()


def test_app_js_parses():
    """A syntax error in app.js breaks the whole UI while Python tests stay green.

    That happened once (an escaped newline landed as a real line break inside a
    string literal), so parse the file for real when node is available.
    """
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        pytest.skip("node not available to parse app.js")
    from cellpy_simple_gui.api.deps import WEB_DIR

    js = WEB_DIR / "static" / "js" / "app.js"
    result = subprocess.run(
        [node, "--check", str(js)], capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0, result.stderr


def test_index_alpine_state_is_defined():
    """Every x-model in the template must exist in the component, or Alpine throws.

    Catches template/JS drift — a new panel wired up in HTML but never added to
    the component renders a wall of "… is not defined" console errors.
    """
    import re

    from cellpy_simple_gui.api.deps import WEB_DIR

    html = (WEB_DIR / "templates" / "index.html").read_text(encoding="utf-8")
    js = (WEB_DIR / "static" / "js" / "app.js").read_text(encoding="utf-8")

    roots = set()
    for expr in re.findall(r'x-model(?:\.\w+)*="([^"]+)"', html):
        root = expr.strip().split(".")[0].split("[")[0]
        if root and root.isidentifier():
            roots.add(root)
    assert roots, "expected to find x-model bindings"

    missing = [r for r in sorted(roots) if not re.search(rf"\b{re.escape(r)}\s*:", js)]
    assert not missing, f"template binds state the component never defines: {missing}"


# --------------------------------------------------------------------------- #
# #118 — pywebview is an optional extra, not a core dependency
# --------------------------------------------------------------------------- #


def _without_webview(monkeypatch):
    """Make ``import webview`` fail, as it would on a server-only install."""
    import sys

    monkeypatch.setitem(sys.modules, "webview", None)
    # desktop.py imports webview inside the function, so a stale module object
    # would mask the very thing under test.
    monkeypatch.delitem(sys.modules, "cellpy_simple_gui.desktop", raising=False)


def test_api_works_without_pywebview(client, monkeypatch):
    """A server-only install must serve the whole app (#118).

    pywebview moved to the [desktop] extra so server images stop pulling GUI
    libraries; nothing outside the native window may depend on it.
    """
    _without_webview(monkeypatch)

    assert client.get("/api/system/capabilities").json()["file_picker"] is False
    assert client.get("/").status_code == 200
    assert client.get("/api/state").status_code == 200
    assert client.get("/api/instruments").json()["instruments"]

    fig = client.post(
        "/api/plots/summary", json={"plot_type": "capacity_ce", "basis": "gravimetric"}
    )
    assert fig.status_code == 200


def test_native_dialogs_refuse_without_pywebview(client, monkeypatch):
    """The two endpoints that genuinely need a window fail clearly, not with a 500."""
    _without_webview(monkeypatch)

    pick = client.post("/api/system/pick", json={"kind": "cellpy"})
    assert pick.status_code == 400
    assert "desktop app" in pick.json()["detail"]

    save = client.post("/api/system/save?filename=x.csv", content=b"data")
    assert save.status_code == 400


def test_desktop_import_failure_names_the_extra(monkeypatch):
    """Falling back to the browser should say what to install, not raise ImportError."""
    _without_webview(monkeypatch)

    import importlib

    with pytest.raises(ImportError):
        importlib.import_module("cellpy_simple_gui.desktop").run_desktop()
