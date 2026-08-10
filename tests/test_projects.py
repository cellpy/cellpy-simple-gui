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
    lib.update(
        rec.id,
        label="Anode A",
        group=2,
        selected=False,
        mass=0.42,
        area=1.5,
        nominal_capacity=2000.0,
        nom_cap_specifics="areal",
        cycle_mode="cathode",
    )

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
    assert abs(r.area - 1.5) < 1e-3
    assert abs(r.nominal_capacity - 2000.0) < 1e-3
    assert r.nom_cap_specifics == "areal"
    assert r.cycle_mode == "cathode"
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

    # A save that reuses every file never reaches save_cell (#29), so dirty one
    # cell first — the point here is the write path's rollback.
    lib.update(lib.all()[0].id, mass=1.23)
    monkeypatch.setattr(projects.adapter, "save_cell", boom)
    with pytest.raises(RuntimeError, match="simulated save failure"):
        projects.save_project(lib, "Atomic")

    assert cell_path.read_bytes() == before_cell
    assert (pdir / "project.json").read_text(encoding="utf-8") == before_manifest
    assert not any(
        p.name.startswith(".staging-") or p.name.startswith(".data-bak-")
        for p in pdir.iterdir()
    )


# --------------------------------------------------------------------------- #
# #29 — reuse unchanged .cellpy files on save
# --------------------------------------------------------------------------- #


def _counting_save_cell(monkeypatch):
    """Wrap adapter.save_cell so a test can see how often it actually ran."""
    calls: list[str] = []
    real = projects.adapter.save_cell

    def counted(cell, path):
        calls.append(str(path))
        return real(cell, path)

    monkeypatch.setattr(projects.adapter, "save_cell", counted)
    return calls


@pytest.mark.essential
def test_resave_reuses_unchanged_cells(loaded_library, temp_projects_root, monkeypatch):
    """A label-only change must not re-serialise the cell data (#29)."""
    lib = loaded_library
    projects.save_project(lib, "Reuse")
    pdir = temp_projects_root / "reuse"
    before = {
        p.name: p.read_bytes() for p in (pdir / "data").iterdir() if p.is_file()
    }
    assert before

    calls = _counting_save_cell(monkeypatch)
    lib.update(lib.all()[0].id, label="renamed", group=7, selected=False)
    projects.save_project(lib, "Reuse")

    assert calls == [], "no cell data changed, so nothing should be rewritten"
    after = {p.name: p.read_bytes() for p in (pdir / "data").iterdir() if p.is_file()}
    assert after == before, "reused files must be byte-identical"
    # the organisational change still landed
    manifest = projects.ProjectManifest(
        **__import__("json").loads((pdir / "project.json").read_text())
    )
    entry = next(c for c in manifest.cells if c.id == lib.all()[0].id)
    assert entry.label == "renamed" and entry.group == 7 and entry.selected is False


@pytest.mark.essential
def test_resave_rewrites_cells_whose_data_changed(
    loaded_library, temp_projects_root, monkeypatch
):
    """Editing mass moves the cell, so its file must be rewritten (#29)."""
    lib = loaded_library
    projects.save_project(lib, "Dirty")
    target = lib.all()[0]

    calls = _counting_save_cell(monkeypatch)
    lib.update(target.id, mass=0.77)
    projects.save_project(lib, "Dirty")

    assert len(calls) == 1, calls
    assert calls[0].endswith(f"{target.id}.cellpy")


def test_reuse_declines_when_file_changed_on_disk(
    loaded_library, temp_projects_root, monkeypatch
):
    """Provably untouched means the file too — not just the in-memory cell."""
    lib = loaded_library
    projects.save_project(lib, "Tampered")
    pdir = temp_projects_root / "tampered"
    target = lib.all()[0]
    victim = pdir / "data" / f"{target.id}.cellpy"

    # Something rewrote the file behind the app's back.
    time.sleep(0.01)
    victim.write_bytes(b"not a cellpy file")

    calls = _counting_save_cell(monkeypatch)
    projects.save_project(lib, "Tampered")

    assert [c for c in calls if c.endswith(f"{target.id}.cellpy")], (
        "a file that changed on disk must be rewritten from memory"
    )
    assert victim.read_bytes() != b"not a cellpy file"


def test_reuse_declines_when_file_is_missing(
    loaded_library, temp_projects_root, monkeypatch
):
    lib = loaded_library
    projects.save_project(lib, "Gone")
    target = lib.all()[0]
    (temp_projects_root / "gone" / "data" / f"{target.id}.cellpy").unlink()

    calls = _counting_save_cell(monkeypatch)
    projects.save_project(lib, "Gone")

    assert [c for c in calls if c.endswith(f"{target.id}.cellpy")]
    assert (temp_projects_root / "gone" / "data" / f"{target.id}.cellpy").is_file()


def test_save_as_new_project_still_copies_every_cell(
    loaded_library, temp_projects_root
):
    """Save-As must produce a complete project, reuse or not (#29)."""
    lib = loaded_library
    projects.save_project(lib, "First")
    projects.save_project(lib, "Second")

    for slug in ("first", "second"):
        data = temp_projects_root / slug / "data"
        assert sorted(p.name for p in data.iterdir()) == sorted(
            f"{r.id}.cellpy" for r in lib.all()
        )
    # and the copies are real, openable cells
    fresh = Library()
    projects.open_project(fresh, str(temp_projects_root / "second"))
    assert len(fresh) == len(lib)


@pytest.mark.essential
def test_reused_project_reopens_intact(loaded_library, temp_projects_root):
    """The end-to-end guarantee: a reused save is still a loadable project."""
    lib = loaded_library
    projects.save_project(lib, "Intact")
    expected = [(r.n_cycles, r.mass) for r in lib.all()]

    fresh = Library()
    projects.open_project(fresh, str(temp_projects_root / "intact"))
    fresh.update(fresh.all()[0].id, label="only a label")
    projects.save_project(fresh, "Intact")  # reuses every file

    again = Library()
    projects.open_project(again, str(temp_projects_root / "intact"))
    assert [(r.n_cycles, r.mass) for r in again.all()] == expected
    assert again.all()[0].label == "only a label"


def test_opened_cells_start_clean_and_dirty_on_edit(
    loaded_library, temp_projects_root
):
    """The flag itself: clean on open, dirty the moment the cell moves."""
    lib = loaded_library
    projects.save_project(lib, "Flags")

    fresh = Library()
    projects.open_project(fresh, str(temp_projects_root / "flags"))
    rec = fresh.all()[0]
    assert rec.data_dirty is False and rec.data_path
    assert fresh.reusable_data_file(rec.id) is not None

    fresh.update(rec.id, label="labels do not touch the data")
    assert fresh.reusable_data_file(rec.id) is not None

    fresh.update(rec.id, mass=0.9)
    assert rec.data_dirty is True
    assert fresh.reusable_data_file(rec.id) is None


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


# ---- per-project cellpy settings ------------------------------------------ #

def _make_project_dir(tmp_path, toml_text: str | None = None):
    pdir = tmp_path / "StudyA"
    (pdir / "data").mkdir(parents=True)
    (pdir / "project.json").write_text("{}", encoding="utf-8")
    if toml_text is not None:
        (pdir / "cellpy.toml").write_text(toml_text, encoding="utf-8")
    return pdir


def test_project_config_activates_and_restores(tmp_path):
    """A project's cellpy.toml wins while open, and is dropped on close."""
    from cellpy import config
    from cellpy_simple_gui.core import cellpy_config

    baseline = config.get_config().reader.cycle_mode
    pdir = _make_project_dir(tmp_path, '[reader]\ncycle_mode = "cathode"\n')
    try:
        activated = cellpy_config.activate_project_config(pdir)
        assert activated == pdir / "cellpy.toml"
        assert config.get_config().reader.cycle_mode == "cathode"
        assert config.sources()["reader.cycle_mode"] == "project_file"
        assert cellpy_config.active_project_config() == activated
    finally:
        cellpy_config.deactivate_project_config()
    assert config.get_config().reader.cycle_mode == baseline
    assert cellpy_config.active_project_config() is None


def test_project_without_config_drops_previous(tmp_path):
    """Settings must not leak from one project into the next."""
    from cellpy import config
    from cellpy_simple_gui.core import cellpy_config

    baseline = config.get_config().reader.cycle_mode
    with_cfg = _make_project_dir(tmp_path, '[reader]\ncycle_mode = "cathode"\n')
    plain = tmp_path / "StudyB"
    (plain / "data").mkdir(parents=True)
    try:
        cellpy_config.activate_project_config(with_cfg)
        assert config.get_config().reader.cycle_mode == "cathode"
        # opening a project with no config reverts rather than inheriting
        assert cellpy_config.activate_project_config(plain) is None
        assert cellpy_config.active_project_config() is None
        assert config.get_config().reader.cycle_mode == baseline
    finally:
        cellpy_config.deactivate_project_config()


def test_broken_project_config_does_not_block_open(tmp_path):
    """An unparseable cellpy.toml must not stop the project from opening."""
    from cellpy import config
    from cellpy_simple_gui.core import cellpy_config

    baseline = config.get_config().reader.cycle_mode
    pdir = _make_project_dir(tmp_path, "this is not valid toml {{{\n")
    try:
        assert cellpy_config.activate_project_config(pdir) is None
        assert cellpy_config.active_project_config() is None
        assert config.get_config().reader.cycle_mode == baseline
    finally:
        cellpy_config.deactivate_project_config()


def test_diagnostics_reports_project_as_source(tmp_path):
    from cellpy_simple_gui.core import cellpy_config

    pdir = _make_project_dir(tmp_path, '[units]\nmass = "g"\n')
    try:
        cellpy_config.activate_project_config(pdir)
        d = cellpy_config.diagnostics()
        assert d["discovery"]["project_config_source"] == "project"
        assert d["discovery"]["project_config_path"] == str(pdir / "cellpy.toml")
        assert any("own cellpy settings" in w for w in d["warnings"])
    finally:
        cellpy_config.deactivate_project_config()


def test_pin_project_config_writes_safe_sections(tmp_path):
    """Pinning captures interpretation settings — never paths or credentials."""
    from cellpy import config
    from cellpy_simple_gui.core import cellpy_config

    pdir = tmp_path / "StudyP"
    (pdir / "data").mkdir(parents=True)
    try:
        path = cellpy_config.pin_project_config(pdir)
        text = path.read_text(encoding="utf-8")
        assert path == pdir / "cellpy.toml"
        # only the interpretation sections
        headers = {ln.strip("[]").split(".")[0] for ln in text.splitlines() if ln.startswith("[")}
        assert headers == set(cellpy_config.PINNED_SECTIONS)
        # a project is portable: no machine-specific paths baked in
        assert "[paths]" not in text
        assert str(tmp_path.home()) not in text
        # structurally cannot carry a credential
        assert not any(k in text.lower() for k in ("pwd", "password", "uid", "secret", "token"))
        # and it is active immediately
        assert cellpy_config.active_project_config() == path
        assert config.sources()["units.mass"] == "project_file"
    finally:
        cellpy_config.deactivate_project_config()


def test_pin_project_config_round_trips(tmp_path):
    """What is pinned is what a later open reproduces."""
    from cellpy import config
    from cellpy_simple_gui.core import cellpy_config

    pdir = tmp_path / "StudyR"
    (pdir / "data").mkdir(parents=True)
    try:
        pinned_mass = config.get_config().units.mass
        pinned_mode = config.get_config().reader.cycle_mode
        cellpy_config.pin_project_config(pdir)
        cellpy_config.deactivate_project_config()
        cellpy_config.activate_project_config(pdir)
        cfg = config.get_config()
        assert cfg.units.mass == pinned_mass
        assert cfg.reader.cycle_mode == pinned_mode
        assert config.sources()["reader.cycle_mode"] == "project_file"
    finally:
        cellpy_config.deactivate_project_config()


def test_discovery_reports_shadowed_legacy(monkeypatch, tmp_path):
    """A legacy .conf outranked by cellpy.toml is surfaced, not hidden (cellpy #851)."""
    from cellpy.config.loader import ActiveConfigFile
    from cellpy_simple_gui.core import cellpy_config

    legacy = tmp_path / ".cellpy_prms_x.conf"
    toml = tmp_path / "cellpy.toml"
    monkeypatch.setattr(
        cellpy_config,
        "_config_dump",
        lambda: {"reader": {"cycle_mode": "anode"}},
    )
    monkeypatch.setattr(
        "cellpy.config.loader.active_config_file",
        lambda options=None: ActiveConfigFile(
            path=toml, kind="toml", shadowed_legacy=legacy, project_path=None
        ),
    )
    d = cellpy_config.diagnostics()
    assert d["discovery"]["user_config_kind"] == "toml"
    assert d["discovery"]["shadowed_legacy"] == str(legacy)
    assert not d["discovery"]["legacy_fallback"]
    assert any("ignored" in w and str(legacy) in w for w in d["warnings"])
