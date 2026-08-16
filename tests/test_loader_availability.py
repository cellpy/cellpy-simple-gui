"""Loaders that need something the machine may not have (#143).

Arbin ``.res`` is an Access database, so reading it needs a platform-specific
reader that is nobody's default install: the Access ODBC driver on Windows,
mdbtools on posix. Both gaps were found by running the app somewhere that
lacked them — a CI runner without Office, and the container — and in both cases
the user-facing result was a raw driver error naming neither the cause nor the
fix.
"""

from __future__ import annotations

import sys

import pytest

from cellpy_simple_gui.core import cellpy_adapter

pytestmark = pytest.mark.essential


# --- turning a driver error into advice ------------------------------------ #


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # The exact text a Windows machine without the driver produces.
        (
            "(pyodbc.InterfaceError) ('IM002', '[IM002] [Microsoft][ODBC Driver "
            "Manager] Data source name not found and no default driver specified "
            "(0) (SQLDriverConnect)')",
            "Access Database Engine",
        ),
        # The posix equivalent, from the container.
        (
            "[Errno 2] No such file or directory: 'mdb-export'",
            "mdbtools",
        ),
    ],
)
def test_environment_errors_name_the_cause_and_the_fix(raw, expected):
    explained = cellpy_adapter.explain_load_error(RuntimeError(raw))
    assert expected in explained
    # The raw driver noise must not survive into the message.
    assert "pyodbc" not in explained
    assert "IM002" not in explained


def test_an_unrecognised_error_is_passed_through_unchanged():
    """A wrong explanation would be worse than a raw one."""
    exc = ValueError("cycle 7 has no discharge step")
    assert cellpy_adapter.explain_load_error(exc) == "cycle 7 has no discharge step"


# --- reporting it before the user picks a file ------------------------------ #


def test_availability_probe_never_raises(monkeypatch):
    """It runs on every instrument listing, so it must be harmless."""

    def boom(*_a, **_k):
        raise OSError("no driver manager here")

    monkeypatch.setattr("shutil.which", boom)
    # Must not propagate, whatever it decides.
    assert cellpy_adapter.arbin_res_reader_available() in (True, False)


def test_instrument_list_carries_availability():
    instruments = cellpy_adapter.list_instruments()
    assert instruments, "discovery returned nothing"
    for entry in instruments:
        assert "available" in entry
        assert "unavailable_reason" in entry
        if entry["available"] is False:
            assert entry["unavailable_reason"], f"{entry['id']} unavailable with no reason"


def test_arbin_res_is_marked_unavailable_when_no_reader(monkeypatch):
    monkeypatch.setattr(cellpy_adapter, "_INSTRUMENTS_CACHE", None)
    monkeypatch.setattr(cellpy_adapter, "arbin_res_reader_available", lambda: False)

    entries = {i["id"]: i for i in cellpy_adapter.list_instruments()}
    monkeypatch.setattr(cellpy_adapter, "_INSTRUMENTS_CACHE", None)

    arbin = entries.get("arbin_res")
    assert arbin is not None, "arbin_res should still be listed, just flagged"
    assert arbin["available"] is False
    assert arbin["unavailable_reason"]

    # Only that one: everything else reads files directly.
    others = [i for i in entries.values() if i["id"] != "arbin_res"]
    assert all(i["available"] for i in others)


@pytest.mark.skipif(sys.platform != "win32", reason="ODBC driver enumeration")
def test_probe_agrees_with_this_machine():
    """This box has Office, hence the driver — which is exactly why the gap
    stayed invisible until CI ran without it."""
    import pyodbc

    has_driver = any("microsoft access driver" in d.lower() for d in pyodbc.drivers())
    assert cellpy_adapter.arbin_res_reader_available() is has_driver
