# Playwright GUI tests

**Context.** Issue #48 — exercise real UI interactions beyond FastAPI `TestClient`.

**Decision.** Thin Playwright smoke suite against `--server` / browser mode only
(`tests/test_gui_playwright.py`, marker `e2e`). Optional extra `e2e` (`playwright`);
missing package or Chromium → skip. Native pywebview is not automated.

**Alternatives.** Full interaction matrix / CI job for e2e — deferred. pywebview
automation — out of scope (no reliable cross-platform path yet).

**Run.** `uv sync --extra dev --extra e2e && uv run playwright install chromium && uv run pytest -m e2e`
