"""Playwright GUI smoke tests against --server / browser mode.

Requires the optional ``e2e`` extra and Chromium browsers::

    uv sync --extra dev --extra e2e
    uv run playwright install chromium
    uv run pytest -m e2e

Missing Playwright / browsers → tests skip (default ``uv run pytest`` stays green).
Native pywebview is out of scope; server mode is the automation surface.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import sync_playwright

from cellpy_simple_gui.config import get_settings
from cellpy_simple_gui.core.library import get_library
from cellpy_simple_gui.server import ServerThread, pick_port

_E2E_TOKEN = "csg-playwright-e2e-token"


def _chromium_available() -> bool:
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        return True
    except Exception:  # noqa: BLE001 - missing browser binary, sandbox, etc.
        return False


@pytest.fixture(scope="module")
def live_server():
    """In-process uvicorn with a fixed CSG_TOKEN (same surface as --server)."""
    prev = os.environ.get("CSG_TOKEN")
    os.environ["CSG_TOKEN"] = _E2E_TOKEN
    get_settings.cache_clear()
    get_library().clear()

    host = "127.0.0.1"
    port = pick_port(host, 8599)
    server = ServerThread(host, port)
    server.start(wait=True)
    try:
        yield server
    finally:
        server.stop()
        get_library().clear()
        if prev is None:
            os.environ.pop("CSG_TOKEN", None)
        else:
            os.environ["CSG_TOKEN"] = prev
        get_settings.cache_clear()


@pytest.fixture(scope="module")
def browser_page(live_server):
    if not _chromium_available():
        pytest.skip(
            "Chromium not installed — run: uv run playwright install chromium"
        )
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        # Avoid networkidle — EventSource job streams never go idle.
        page.goto(live_server.url, wait_until="load")
        page.wait_for_selector(".brand-title", timeout=15_000)
        try:
            yield page
        finally:
            browser.close()
            get_library().clear()


@pytest.mark.e2e
def test_shell_loads(browser_page):
    page = browser_page
    assert page.locator(".brand-title").inner_text().strip() == "cellpy"
    # CSS text-transform: uppercase may surface as SIMPLE GUI in the DOM.
    assert page.locator(".brand-sub").inner_text().strip().casefold() == "simple gui"
    assert page.get_by_role("button", name="Load demo cells").is_visible()


@pytest.mark.e2e
def test_load_demo_cells_and_summary_plot(browser_page):
    page = browser_page
    get_library().clear()
    page.reload(wait_until="load")
    page.wait_for_selector(".brand-title", timeout=15_000)

    page.get_by_role("button", name="Load demo cells").click()
    # Demo load may download on first run; allow a generous timeout.
    try:
        page.wait_for_selector(".cell-card", timeout=120_000)
    except Exception as exc:  # noqa: BLE001
        job_err = page.locator(".job-msg").inner_text() if page.locator(".job").is_visible() else ""
        pytest.skip(f"demo cells unavailable: {job_err or exc}")

    cards = page.locator(".cell-card")
    assert cards.count() >= 1

    # Vendored Plotly uses .plot-container.plotly (not .js-plotly-plot).
    page.wait_for_selector("#summaryChart .plot-container.plotly", timeout=60_000)
    assert page.locator("#summaryChart svg.main-svg").count() >= 1


# --------------------------------------------------------------------------- #
# #136 — loading UI: Data panel folds after a load; Add cells modal
# --------------------------------------------------------------------------- #


def _bundled_cellpy_file() -> str:
    """A cellpy file that ships inside the installed cellpy package (no network)."""
    from cellpy.utils import example_data

    return str(example_data.rate_file())


@pytest.mark.e2e
def test_data_panel_collapses_after_load(browser_page):
    """Loading is a start-of-session activity: once cells exist the Data panel
    folds to one line with an 'add more…' link, and unfolds when emptied."""
    page = browser_page
    get_library().clear()
    page.reload(wait_until="load")
    page.wait_for_selector(".brand-title", timeout=15_000)

    demo = page.get_by_role("button", name="Load demo cells")
    assert demo.is_visible()
    assert not page.locator(".collapsed-hint").is_visible()

    demo.click()
    try:
        page.wait_for_selector(".cell-card", timeout=120_000)
    except Exception as exc:  # noqa: BLE001
        job_err = page.locator(".job-msg").inner_text() if page.locator(".job").is_visible() else ""
        pytest.skip(f"demo cells unavailable: {job_err or exc}")

    page.wait_for_selector(".collapsed-hint", state="visible", timeout=10_000)
    assert "cells loaded" in page.locator(".collapsed-hint").inner_text()
    assert not demo.is_visible()
    # The result card replaces the old "Loaded N cells" toast.
    assert "Loaded" in page.locator(".result-card.side .result-summary").inner_text()

    # "show" re-opens the panel without changing anything else.
    page.get_by_role("button", name="show", exact=True).click()
    demo.wait_for(state="visible", timeout=5_000)


@pytest.mark.e2e
def test_add_cells_modal_stages_and_loads(browser_page):
    """Type a path → it lands in the staged list → the one primary button loads it."""
    page = browser_page
    get_library().clear()
    page.reload(wait_until="load")
    page.wait_for_selector(".brand-title", timeout=15_000)

    page.locator(".add-cells-btn").click()
    modal = page.locator(".modal.add-cells")
    modal.wait_for(state="visible", timeout=5_000)
    assert modal.get_by_role("tab", name="cellpy files").get_attribute("aria-selected") == "true"

    primary = modal.locator(".add-cells-foot .btn-primary")
    assert primary.is_disabled()
    assert "Add cellpy files" in modal.locator(".hint.reason").inner_text()

    typed = modal.get_by_label("cellpy file path or glob")
    typed.fill(_bundled_cellpy_file() + "; /nonexistent/nothing.cellpy")
    typed.press("Enter")

    rows = modal.locator(".staged-table tbody tr")
    rows.first.wait_for(state="visible", timeout=10_000)
    assert rows.count() == 2
    assert modal.locator(".status-pill.ok").count() == 1
    assert modal.locator(".status-pill.missing").count() == 1
    assert primary.inner_text().strip() == "Load 1 file"

    primary.click()
    page.wait_for_selector(".cell-card", timeout=120_000)
    # The loaded row left the list; the missing one stays, so the modal stays open.
    page.wait_for_function(
        "() => document.querySelectorAll('.staged-table tbody tr').length === 1", timeout=10_000
    )
    assert modal.is_visible()
    assert modal.locator(".status-pill.missing").count() == 1
    result = modal.locator(".add-cells-foot .result-card")
    assert result.is_visible()
    assert "Loaded 1 cell" in result.locator(".result-summary").inner_text()

    result.locator(".x").click()
    # Role queries skip the hidden tabs' duplicates of this button.
    modal.get_by_role("button", name="clear", exact=True).click()
    reason = modal.locator(".hint.reason")
    reason.wait_for(state="visible", timeout=5_000)
    assert "Add cellpy files" in reason.inner_text()
    page.keyboard.press("Escape")
    modal.wait_for(state="hidden", timeout=5_000)
    assert page.locator(".cell-card").count() == 1


# --------------------------------------------------------------------------- #
# #184 — Manage cells modal defers plot refreshes until it closes
# --------------------------------------------------------------------------- #


def _load_bundled_cell(page) -> None:
    """Stage + load the bundled rate file through the Add cells modal (no network)."""
    page.locator(".add-cells-btn").click()
    modal = page.locator(".modal.add-cells")
    modal.wait_for(state="visible", timeout=5_000)
    typed = modal.get_by_label("cellpy file path or glob")
    typed.fill(_bundled_cellpy_file())
    typed.press("Enter")
    modal.locator(".staged-table tbody tr").first.wait_for(state="visible", timeout=10_000)
    modal.locator(".add-cells-foot .btn-primary").click()
    page.wait_for_selector(".cell-card", timeout=120_000)
    modal.wait_for(state="hidden", timeout=10_000)
    page.wait_for_selector("#summaryChart .plot-container.plotly", timeout=60_000)


@pytest.mark.e2e
def test_cells_modal_defers_plot_refresh_until_close(browser_page):
    """Edits inside Manage cells issue no plot request; Close issues exactly one."""
    page = browser_page
    get_library().clear()
    page.reload(wait_until="load")
    page.wait_for_selector(".brand-title", timeout=15_000)
    _load_bundled_cell(page)

    plot_requests: list[str] = []
    page.on("request", lambda req: plot_requests.append(req.url) if "/api/plots/" in req.url else None)

    page.get_by_role("button", name="Manage", exact=True).click()
    modal = page.locator(".modal[aria-labelledby='cells-manager-title']")
    modal.wait_for(state="visible", timeout=5_000)
    assert "refresh when this dialog closes" in modal.locator(".mgr-foot-hint").inner_text()

    row = modal.locator(".cells-table tbody tr").first
    row.locator(".cell-label").fill("renamed in modal")
    row.locator(".cell-label").press("Enter")
    row.locator(".grp-input").fill("3")
    row.locator(".grp-input").press("Enter")
    modal.get_by_role("button", name="none", exact=True).click()
    modal.get_by_role("button", name="all", exact=True).click()
    # Every edit above is a round-trip; wait for the last to land.
    page.wait_for_function(
        "() => [...document.querySelectorAll('.cell-card .cell-label')].some(i => i.value === 'renamed in modal')",
        timeout=10_000,
    )
    page.wait_for_timeout(500)
    assert plot_requests == [], plot_requests
    assert "Edits saved" in modal.locator(".mgr-foot-hint").inner_text()

    modal.get_by_role("button", name="Close", exact=True).click()
    modal.wait_for(state="hidden", timeout=5_000)
    for _ in range(40):
        if plot_requests:
            break
        page.wait_for_timeout(250)
    page.wait_for_timeout(1_000)
    assert len(plot_requests) == 1 and "/api/plots/summary" in plot_requests[0], plot_requests

    # Reopening without editing does not schedule a redraw.
    page.get_by_role("button", name="Manage", exact=True).click()
    modal.wait_for(state="visible", timeout=5_000)
    modal.get_by_role("button", name="Close", exact=True).click()
    modal.wait_for(state="hidden", timeout=5_000)
    page.wait_for_timeout(500)
    assert len(plot_requests) == 1, plot_requests


# --------------------------------------------------------------------------- #
# #187 — group names
# --------------------------------------------------------------------------- #


@pytest.mark.e2e
def test_cells_modal_names_groups(browser_page):
    """The Groups strip names a group; the name reaches state and the legend."""
    page = browser_page
    get_library().clear()
    page.reload(wait_until="load")
    page.wait_for_selector(".brand-title", timeout=15_000)
    _load_bundled_cell(page)

    page.get_by_role("button", name="Manage", exact=True).click()
    modal = page.locator(".modal[aria-labelledby='cells-manager-title']")
    modal.wait_for(state="visible", timeout=5_000)
    chip = modal.locator(".mgr-group").first
    chip.wait_for(state="visible", timeout=5_000)
    group_id = chip.locator(".mgr-group-id").inner_text().strip()
    name_input = chip.locator(".group-name-input")
    assert name_input.get_attribute("placeholder") == f"group {group_id}"
    assert name_input.input_value() == ""

    name_input.fill("Anodes")
    name_input.press("Enter")
    page.wait_for_function(
        "() => [...document.querySelectorAll('.cells-table .grp-input')]"
        ".some(i => i.title === 'Anodes')",
        timeout=10_000,
    )
    lib = get_library()
    assert lib.group_label(int(group_id)) == "Anodes"
    assert all(m.group_label == "Anodes" for m in lib.metas())
    assert "Edits saved" in modal.locator(".mgr-foot-hint").inner_text()

    # Closing redraws the summary; the named group captions its legend entry.
    modal.get_by_role("button", name="Close", exact=True).click()
    modal.wait_for(state="hidden", timeout=5_000)
    page.wait_for_function(
        "() => { const d = document.getElementById('summaryChart').data || [];"
        " return d.some(t => t.legendgrouptitle && t.legendgrouptitle.text === 'Anodes'); }",
        timeout=60_000,
    )

    # Blank restores the default name.
    page.get_by_role("button", name="Manage", exact=True).click()
    modal.wait_for(state="visible", timeout=5_000)
    name_input = modal.locator(".mgr-group").first.locator(".group-name-input")
    assert name_input.input_value() == "Anodes"
    name_input.fill("")
    name_input.press("Enter")
    page.wait_for_function(
        "() => [...document.querySelectorAll('.cells-table .grp-input')]"
        ".every(i => i.title.startsWith('group '))",
        timeout=10_000,
    )
    assert lib.group_label(int(group_id)) == ""
    modal.get_by_role("button", name="Close", exact=True).click()
    modal.wait_for(state="hidden", timeout=5_000)


# --------------------------------------------------------------------------- #
# #174 — Open replaces the loaded cells unless "Append" is ticked
# --------------------------------------------------------------------------- #


@pytest.mark.e2e
def test_project_open_replace_vs_append(browser_page, tmp_path, monkeypatch):
    from cellpy_simple_gui.core import projects

    monkeypatch.setattr(projects, "projects_root", lambda: tmp_path)
    page = browser_page
    lib = get_library()
    lib.clear()
    page.reload(wait_until="load")
    page.wait_for_selector(".brand-title", timeout=15_000)
    _load_bundled_cell(page)
    first_group = lib.all()[0].group

    # The toggle only appears once something is loaded; default is replace.
    append = page.locator(".proj-append")
    append.wait_for(state="visible", timeout=5_000)
    open_btn = page.locator(".proj-ctl").first.get_by_role("button", name="Open", exact=True)
    assert open_btn.is_visible()

    page.get_by_label("Project name").fill("E2E Append")
    page.get_by_role("button", name="Save", exact=True).click()
    page.wait_for_function(
        "() => [...document.querySelectorAll('.toast')].some(n => /Saved/.test(n.textContent))",
        timeout=60_000,
    )
    page.wait_for_function(
        "() => [...document.querySelectorAll('select[aria-label=\"Saved projects\"] option')]"
        ".some(o => o.textContent.includes('E2E Append'))",
        timeout=10_000,
    )

    # Append: the button says so, no confirm, cells double, groups do not collide.
    append.locator("input").check()
    page.locator("select[aria-label='Saved projects']").select_option(label=f"E2E Append · 1 cells")
    append_btn = page.locator(".proj-ctl").first.get_by_role("button", name="Append", exact=True)
    append_btn.wait_for(state="visible", timeout=5_000)
    dialogs: list[str] = []
    page.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))
    append_btn.click()
    page.wait_for_function(
        "() => document.querySelectorAll('.cell-card').length === 2", timeout=60_000
    )
    assert dialogs == []
    groups = sorted(r.group for r in lib.all())
    assert groups[0] == first_group and groups[1] > first_group
    assert "*" in page.locator(".proj-tag").first.inner_text()  # appended set is unsaved

    # Replace: asks first, then the saved single cell is all that is left.
    append.locator("input").uncheck()
    open_btn.wait_for(state="visible", timeout=5_000)
    open_btn.click()
    page.wait_for_function(
        "() => document.querySelectorAll('.cell-card').length === 1", timeout=60_000
    )
    assert len(dialogs) == 1 and "Replace the 2 loaded cells" in dialogs[0]
    assert [r.group for r in lib.all()] == [first_group]
