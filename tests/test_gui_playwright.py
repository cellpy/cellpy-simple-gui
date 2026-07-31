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
