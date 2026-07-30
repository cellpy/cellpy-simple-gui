"""Tests for project persistence (core round-trip + API)."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from cellpy_simple_gui.api.app import create_app
from cellpy_simple_gui.config import get_settings
from cellpy_simple_gui.core import projects
from cellpy_simple_gui.core.library import Library, get_library


@pytest.fixture()
def temp_projects_root(tmp_path, monkeypatch):
    root = tmp_path / "projects"
    root.mkdir()
    monkeypatch.setattr(projects, "projects_root", lambda: root)
    return root


def test_save_open_roundtrip(loaded_library, temp_projects_root):
    lib = loaded_library
    rec = lib.all()[0]
    lib.update(rec.id, label="Anode A", group=2, selected=False, mass=0.42)

    manifest = projects.save_project(lib, "Round Trip")
    assert manifest.slug == "round_trip"
    assert (temp_projects_root / "round_trip" / "project.json").exists()
    assert (temp_projects_root / "round_trip" / "data" / f"{rec.id}.cellpy").exists()

    summaries = projects.list_projects()
    assert any(s.name == "Round Trip" for s in summaries)

    fresh = Library()
    projects.open_project(fresh, "Round Trip")
    assert len(fresh) == 1
    r = fresh.all()[0]
    assert r.label == "Anode A"
    assert r.group == 2
    assert r.selected is False
    assert abs(r.mass - 0.42) < 1e-3
    assert r.n_cycles == rec.n_cycles
    assert fresh.project_name == "Round Trip"


@pytest.mark.essential
def test_open_missing_raises(temp_projects_root):
    with pytest.raises(FileNotFoundError):
        projects.open_project(Library(), "does-not-exist")


def _wait(client, job_id, timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        snap = client.get(f"/api/jobs/{job_id}").json()
        if snap["status"] in ("done", "error", "cancelled"):
            return snap
        time.sleep(0.3)
    raise AssertionError("job timeout")


def test_api_save_and_open(temp_projects_root):
    get_library().clear()
    client = TestClient(create_app())
    client.headers.update({"X-CSG-Token": get_settings().token})

    snap = _wait(client, client.post("/api/load/example", json={"kinds": ["cellpy"]}).json()["job_id"])
    if snap["status"] != "done":
        pytest.skip("example data unavailable")

    # save
    snap = _wait(client, client.post("/api/projects/save", json={"name": "API Proj"}).json()["job_id"])
    assert snap["status"] == "done"
    listing = client.get("/api/projects").json()
    assert any(p["name"] == "API Proj" for p in listing["projects"])
    assert listing["current"]["name"] == "API Proj"

    # clear then reopen
    client.post("/api/cells/clear")
    assert client.get("/api/state").json()["n_cells"] == 0
    snap = _wait(client, client.post("/api/projects/open", json={"target": "API Proj"}).json()["job_id"])
    assert snap["status"] == "done"
    state = client.get("/api/state").json()
    assert state["n_cells"] == 1
    assert state["project"] == "API Proj"


@pytest.mark.essential
def test_api_open_unknown_404(temp_projects_root):
    client = TestClient(create_app())
    client.headers.update({"X-CSG-Token": get_settings().token})
    assert client.post("/api/projects/open", json={"target": "nope"}).status_code == 404
