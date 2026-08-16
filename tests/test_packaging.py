"""The frozen Windows build's failure modes (#117, #122).

A windowed build has no console, so anything that goes wrong before the window
appears is invisible unless the app arranges otherwise. These tests cover the
arranging.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

from cellpy_simple_gui import logging_setup

pytestmark = pytest.mark.essential

PACKAGING = Path(__file__).resolve().parent.parent / "packaging"


def _load_entry():
    """Import packaging/entry.py without it being on sys.path."""
    spec = importlib.util.spec_from_file_location("_csg_entry", PACKAGING / "entry.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_crash_reporter_agrees_with_the_app_on_where_logs_go():
    """The two are duplicated deliberately; this is the thing keeping them honest.

    ``entry.py`` cannot import the package to find the log directory — the
    failure it is reporting may be that the package does not import. So the path
    is spelled twice, and drift would send users looking in the wrong folder.
    """
    assert _load_entry()._log_dir() == logging_setup.log_dir()


def test_setup_logging_survives_a_windowed_build(monkeypatch, tmp_path):
    """``sys.stderr`` is None in a windowed PyInstaller build.

    Handing that to ``logger.add`` raises, which would kill the app *during
    logging setup* — before it could report anything at all. That is the whole
    failure mode the console-less build introduces.
    """
    monkeypatch.setattr(sys, "stderr", None)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    logging_setup.setup_logging()  # must not raise

    from loguru import logger

    logger.info("hello from a windowed build")
    logger.remove()

    written = list((tmp_path / "cellpy-simple-gui" / "logs").glob("app*.log"))
    assert written, "a windowed build must still log somewhere findable"
    assert "hello from a windowed build" in written[0].read_text(encoding="utf-8")


def test_stderr_usable_rejects_a_broken_handle(monkeypatch):
    """Not just None: a detached handle raises on write."""

    class Broken:
        def write(self, _text):
            raise OSError("handle is invalid")

    monkeypatch.setattr(sys, "stderr", Broken())
    assert logging_setup._stderr_usable() is False


def test_crash_report_is_written_and_the_dialog_names_it(monkeypatch, tmp_path):
    entry = _load_entry()
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(sys, "stderr", None)  # windowed build

    shown: list[str] = []
    monkeypatch.setattr(entry, "_show_dialog", shown.append)

    entry._report_crash(RuntimeError("No module named 'cellpy.readers.filefinder'"))

    report = tmp_path / "cellpy-simple-gui" / "logs" / "startup-error.log"
    assert report.is_file()
    assert "cellpy.readers.filefinder" in report.read_text(encoding="utf-8")

    # The dialog is useless if it does not say where to look, or how to get more.
    assert shown, "a windowed build must tell the user something"
    assert str(report) in shown[0]
    assert "cellpy-simple-gui-console.exe" in shown[0]


def test_crash_goes_to_stderr_when_there_is_a_console(monkeypatch, tmp_path, capsys):
    entry = _load_entry()
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    shown: list[str] = []
    monkeypatch.setattr(entry, "_show_dialog", shown.append)

    entry._report_crash(RuntimeError("boom"))

    assert "boom" in capsys.readouterr().err
    assert not shown, "no dialog when the traceback is already on screen"


def _fake_cellpy_config(monkeypatch, **fields):
    """Stand in for ``cellpy.config``, recording any reload."""
    state = {"reloaded": 0, "fields": dict(fields)}

    def get_config():
        return type("C", (), {"paths": type("P", (), dict(state["fields"]))()})()

    def reload():
        state["reloaded"] += 1
        for field, env_var in app_main_module()._CELLPY_DIRS:
            override = os.environ.get(env_var)
            if override:
                state["fields"][field] = override

    module = type("M", (), {
        "get_config": staticmethod(get_config),
        "reload": staticmethod(reload),
    })
    monkeypatch.setitem(sys.modules, "cellpy", type("C", (), {"config": module}))
    monkeypatch.setitem(sys.modules, "cellpy.config", module)
    return state


def app_main_module():
    from cellpy_simple_gui import __main__ as app_main

    return app_main


def _clear_overrides(monkeypatch):
    for _field, env_var in app_main_module()._CELLPY_DIRS:
        monkeypatch.delenv(env_var, raising=False)


def test_absolute_cellpy_dirs_are_created_but_not_overridden(monkeypatch, tmp_path):
    """Otherwise cellpy writes demo data inside the install directory (#122)."""
    _clear_overrides(monkeypatch)
    examples = tmp_path / "cellpy_data" / "examples"
    logs = tmp_path / "cellpy_data" / "logs"
    _fake_cellpy_config(monkeypatch, examplesdir=str(examples), filelogdir=str(logs))

    app_main_module()._anchor_cellpy_paths()

    assert examples.is_dir() and logs.is_dir()
    # An absolute setting is the user's; it must be left exactly as written.
    assert "CELLPY_PATHS__EXAMPLESDIR" not in os.environ
    assert "CELLPY_PATHS__FILELOGDIR" not in os.environ


def test_relative_cellpy_dirs_are_anchored_at_home_not_cwd(monkeypatch, tmp_path):
    """cellpy's defaults are *relative* (``cellpy_data/examples``, ``.../logs``).

    Resolved against the process cwd, they land wherever the Start-menu shortcut
    happened to start the app — the install folder. The first version of this
    fix did exactly that and moved the mess into the source repo instead of
    removing it, which is why this test exists.
    """
    home = tmp_path / "home"
    cwd = tmp_path / "somewhere-else"
    home.mkdir()
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: home))
    _clear_overrides(monkeypatch)

    state = _fake_cellpy_config(
        monkeypatch,
        examplesdir=str(Path("cellpy_data") / "examples"),
        filelogdir=str(Path("cellpy_data") / "logs"),
    )
    app_main_module()._anchor_cellpy_paths()

    assert (home / "cellpy_data" / "examples").is_dir()
    assert (home / "cellpy_data" / "logs").is_dir()
    assert not (cwd / "cellpy_data").exists(), "resolved against cwd — the original bug"
    # And cellpy has to be told, or example_data still resolves it against cwd.
    assert state["reloaded"] == 1
    assert os.environ["CELLPY_PATHS__EXAMPLESDIR"] == str(
        (home / "cellpy_data" / "examples").resolve()
    )


def test_remote_paths_are_never_touched(monkeypatch, tmp_path):
    """``rawdatadir`` can be an scp:// URL — not absolute, and not ours to fix."""
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path))
    _clear_overrides(monkeypatch)
    _fake_cellpy_config(
        monkeypatch,
        examplesdir="scp://host/home/user/examples",
        filelogdir=str(tmp_path / "logs"),
    )

    app_main_module()._anchor_cellpy_paths()

    assert "CELLPY_PATHS__EXAMPLESDIR" not in os.environ
    assert not (tmp_path / "scp:").exists()


def test_startup_survives_an_unreadable_cellpy_config(monkeypatch):
    """A broken probe must not stop the app from starting."""

    def boom():
        raise RuntimeError("config is unreadable")

    module = type("M", (), {"get_config": staticmethod(boom)})
    monkeypatch.setitem(sys.modules, "cellpy", type("C", (), {"config": module}))
    monkeypatch.setitem(sys.modules, "cellpy.config", module)
    app_main_module()._anchor_cellpy_paths()  # must not raise


def test_installer_removes_its_own_directory_but_never_user_data():
    """Runtime droppings inside {app} would otherwise outlive the uninstall —
    and no uninstall directive may ever point at the projects folder."""
    iss = (PACKAGING / "installer.iss").read_text(encoding="utf-8")
    section = iss.split("[UninstallDelete]")[1].split("[Code]")[0]
    directives = [
        line for line in section.splitlines()
        if line.strip() and not line.strip().startswith(";")  # ; is an Inno comment
    ]
    assert any('Name: "{app}"' in line for line in directives)
    assert not any(".cellpy_simple_gui" in line for line in directives), directives


def test_installer_needs_no_admin():
    iss = (PACKAGING / "installer.iss").read_text(encoding="utf-8")
    assert "PrivilegesRequired=lowest" in iss
    assert "{localappdata}\\Programs" in iss


def _smoke_test_module():
    spec = importlib.util.spec_from_file_location(
        "_csg_smoke", PACKAGING / "smoke_test.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("error", "should_skip"),
    [
        # What a current build reports — the app translates the driver error
        # into advice (#143).
        ("Reading Arbin .res needs the Microsoft Access Database Engine (64-bit)", True),
        ("Reading Arbin .res on Linux/macOS needs mdbtools", True),
        # What the raw driver says underneath, and what older builds emit.
        ("(pyodbc.InterfaceError) ('IM002', '[Microsoft][ODBC Driver Manager] …')", True),
        ("[Errno 2] No such file or directory: 'mdb-export'", True),
        # A real defect must still fail the release.
        ("cycle 3 has a malformed step table", False),
        ("could not parse the file header", False),
    ],
)
def test_smoke_test_skips_only_a_missing_reader(error, should_skip):
    """The skip must track *both* vocabularies (#124, #143).

    It originally matched only the raw driver text — and #143 rewrote that text
    one PR later, silently turning the skip back into a release-blocking
    failure. Matching on a message is fragile in exactly that way, so this pins
    both wordings and, more importantly, pins that a genuine Arbin failure is
    still a failure.
    """
    signatures = _smoke_test_module()._MISSING_ODBC
    assert any(s in error.lower() for s in signatures) is should_skip


def test_spec_ships_both_a_windowed_and_a_console_executable():
    """The console twin is how a user sees a startup error, and how the smoke
    test reads the URL — a windowed exe has no stdout."""
    spec = (PACKAGING / "cellpy-simple-gui.spec").read_text(encoding="utf-8")
    assert 'name="cellpy-simple-gui"' in spec
    assert 'name="cellpy-simple-gui-console"' in spec
    assert "console=False" in spec and "console=True" in spec
