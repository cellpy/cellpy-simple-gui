# Issue #5 plan

## Goal

Brand the shell with the in-repo cellpy logo: header mark, favicon, and desktop window icon (served from `web/static/img/`).

## Constraints

- Keep “simple gui” subtitle; no chrome redesign.
- UI must not reference unserved repo-root `assets/`.
- Color SVG works on dark/light (blue/yellow mark); no theme swap required.

### Prior art

- Header placeholder: `index.html` `.brand-mark` + CSS gradient box.
- Favicon: generic `web/static/img/favicon.svg`.
- Desktop: `desktop.py` → `webview.create_window` / `webview.start` (icon via `webview.start(icon=…)`).
- Source art: `assets/cellpy-icon.svg`, `assets/cellpy-logo-v1.png`.

## Approach

1. Copy `assets/cellpy-icon.svg` → `web/static/img/cellpy-icon.svg` and replace `favicon.svg` with the same mark.
2. Copy/rasterize PNG + multi-size `.ico` into `web/static/img/` for pywebview (Windows `Icon` expects `.ico`; GTK/Qt accept the same path).
3. Header: `<img class="brand-mark" src="/static/img/cellpy-icon.svg" alt="cellpy">`; restyle `.brand-mark` for image (drop glyph gradient).
4. `desktop.py`: resolve packaged static icon path; pass to `webview.start(icon=…)`.
5. TestClient: assert branding static paths return 200; index HTML has no `◧`.

## Files to touch

- `src/cellpy_simple_gui/web/static/img/*` — logo / favicon / png / ico
- `src/cellpy_simple_gui/web/templates/index.html` — brand mark img
- `src/cellpy_simple_gui/web/static/css/app.css` — `.brand-mark` for img
- `src/cellpy_simple_gui/desktop.py` — window icon
- `tests/test_api.py` — static branding smoke tests
- `.issueflows/…` — tracking + short design note

## Test strategy

`uv run pytest` + new static-asset / index checks.

## Open questions

None (yolo auto-confirm).
