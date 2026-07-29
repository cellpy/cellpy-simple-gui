# Branding assets

**Decision (issue #5):** serve cellpy marks from `src/cellpy_simple_gui/web/static/img/`, copied from repo-root `assets/`. Never point the UI at unserved `assets/` paths.

| File | Use |
|------|-----|
| `cellpy-icon.svg` | Header brand mark |
| `favicon.svg` | Same SVG for tab icon |
| `cellpy-icon.png` | Raster source / fallback |
| `cellpy-icon.ico` | Desktop window via `webview.start(icon=…)` (Windows + GTK/Qt/Cocoa) |

Canonical source art stays under `assets/`; regenerate packaged copies when the logo changes.
