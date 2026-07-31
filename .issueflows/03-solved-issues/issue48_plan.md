# Issue #48 — create gui tests (plan)

## Goal

Add a thin Playwright smoke suite that drives the real UI in `--server` / browser mode (not pywebview), covering load-demo → cells appear → summary chart renders.

## Constraints

- Keep yolo-small: one smoke path, not a full interaction matrix.
- Playwright is optional — missing package/browsers → skip, not fail. Essential CI stays on `uv sync --extra dev` + `pytest -m essential`.
- Do not attempt to automate the native pywebview shell; server mode is the supported automation surface (matches design note “optional Playwright”).
- Fixed `CSG_TOKEN` for the live server fixture; clear `get_settings` cache around it.

### Prior art

- `tests/test_api.py` — FastAPI `TestClient` smoke (`test_load_and_plot_flow`); GUI suite complements, does not replace.
- `ServerThread` / `pick_port` in `src/cellpy_simple_gui/server.py` — reuse for in-process live server.
- `cellprocessor-v2-design.md` — already lists optional Playwright next to pytest/httpx.
- Toolbox: none.

## Approach

1. Add optional extra `e2e = ["playwright"]` and pytest marker `e2e`.
2. Fixture starts `ServerThread` on a free port with `CSG_TOKEN` set, yields `server.url`, stops + clears library on teardown.
3. `tests/test_gui_playwright.py`: sync Playwright Chromium — open URL → brand visible → click **Load demo cells** → wait for `.cell-card` → wait for Plotly inside `#summaryChart`. Skip if example data / browser unavailable.
4. Document install + run in `this-project.md` (and a one-line README note if the test section exists).

## Files to touch

| Path | Change |
| --- | --- |
| `pyproject.toml` | `e2e` optional-dep + `e2e` marker |
| `uv.lock` | lock after `uv sync --extra e2e` |
| `tests/test_gui_playwright.py` | new smoke tests + live-server fixture |
| `.issueflows/04-designs-and-guides/this-project.md` | how to run e2e |
| `README.md` | brief e2e pointer (if test/docs section present) |

## Test strategy

```bash
uv sync --extra dev --extra e2e
uv run playwright install chromium
uv run pytest                 # e2e runs when browsers present; else skip
uv run pytest -m e2e          # GUI only
uv run pytest -m essential    # unchanged; no Playwright
```

## Open questions

- None for yolo scope (pywebview coverage deferred).
