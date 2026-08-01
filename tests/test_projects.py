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


def test_failed_resave_keeps_previous_project(loaded_library, temp_projects_root, monkeypatch):
    """Interrupted save must not wipe or corrupt the previous project on disk."""
    lib = loaded_library
    projects.save_project(lib, "Atomic")
    pdir = temp_projects_root / "atomic"
    cell_path = pdir / "data" / f"{lib.all()[0].id}.cellpy"
    before_cell = cell_path.read_bytes()
    before_manifest = (pdir / "project.json").read_text(encoding="utf-8")

    def boom(cell, path):
        raise RuntimeError("simulated save failure")

    monkeypatch.setattr(projects.adapter, "save_cell", boom)
    with pytest.raises(RuntimeError, match="simulated save failure"):
        projects.save_project(lib, "Atomic")

    assert cell_path.read_bytes() == before_cell
    assert (pdir / "project.json").read_text(encoding="utf-8") == before_manifest
    assert not any(
        p.name.startswith(".staging-") or p.name.startswith(".data-bak-")
        for p in pdir.iterdir()
    )


@pytest.mark.essential
def test_open_missing_raises(temp_projects_root):
    with pytest.raises(FileNotFoundError):
        projects.open_project(Library(), "does-not-exist")


def test_classify_import_path(temp_projects_root, tmp_path):
    proj = temp_projects_root / "copied"
    proj.mkdir()
    (proj / "project.json").write_text(
        '{"schema_version":1,"name":"Copied","slug":"copied",'
        '"created":"x","modified":"x","cells":[]}',
        encoding="utf-8",
    )
    assert projects.classify_import_path(str(proj)) == "project"
    assert projects.classify_import_path(str(proj / "project.json")) == "project"

    journal = tmp_path / "batch.json"
    journal.write_text("{}", encoding="utf-8")
    assert projects.classify_import_path(str(journal)) == "journal"

    empty = tmp_path / "empty_dir"
    empty.mkdir()
    with pytest.raises(ValueError, match="missing project.json"):
        projects.classify_import_path(str(empty))
    with pytest.raises(ValueError, match="not found"):
        projects.classify_import_path(str(tmp_path / "nope.json"))


def test_open_via_project_json_file_and_absolute_path(loaded_library, temp_projects_root, tmp_path):
    """#75: open works for absolute folders and project.json file paths."""
    projects.save_project(loaded_library, "Abs Path")
    src = temp_projects_root / "abs_path"
    external = tmp_path / "external_proj"
    # Simulate copy-paste outside projects_root
    import shutil

    shutil.copytree(src, external)

    fresh = Library()
    projects.open_project(fresh, str(external))
    assert fresh.project_name == "Abs Path"
    assert len(fresh) >= 1

    fresh2 = Library()
    projects.open_project(fresh2, str(external / "project.json"))
    assert fresh2.project_name == "Abs Path"

    # Newly copied into projects_root appears in list (refresh data path)
    shutil.copytree(external, temp_projects_root / "pasted_in")
    names = {s.slug for s in projects.list_projects()}
    assert "pasted_in" in names or "abs_path" in names
    assert any(s.path.endswith("pasted_in") or "pasted_in" in s.path for s in projects.list_projects())


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


def test_api_classify_import(temp_projects_root, tmp_path):
    client = TestClient(create_app())
    client.headers.update({"X-CSG-Token": get_settings().token})

    proj = temp_projects_root / "cls"
    proj.mkdir()
    (proj / "project.json").write_text(
        '{"schema_version":1,"name":"Cls","slug":"cls",'
        '"created":"x","modified":"x","cells":[]}',
        encoding="utf-8",
    )
    r = client.post("/api/projects/classify-import", json={"path": str(proj)})
    assert r.status_code == 200
    assert r.json()["kind"] == "project"

    journal = tmp_path / "j.json"
    journal.write_text("{}", encoding="utf-8")
    r = client.post("/api/projects/classify-import", json={"path": str(journal)})
    assert r.status_code == 200
    assert r.json()["kind"] == "journal"

    r = client.post("/api/projects/classify-import", json={"path": str(tmp_path / "missing")})
    assert r.status_code == 400
