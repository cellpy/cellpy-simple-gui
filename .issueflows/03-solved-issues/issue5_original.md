# Issue #5: Add cellpy logo and app icon

Source: https://github.com/cellpy/cellpy-simple-gui/issues/5

## Original issue text

## Problem / context

The app brands itself as “cellpy / simple gui” but does not use the cellpy logo. The header uses a text placeholder (`◧`), `static/img/favicon.svg` is a generic gradient mark, and the pywebview window has no icon.

Canonical artwork already exists in-repo under `assets/`:
- `cellpy-icon.svg`
- `cellpy-icon-bw.svg`
- `cellpy-icon-long.svg`

## Spec

- Use the cellpy logo in the top-bar brand mark (header), sized to fit dark/light themes (color or BW variant as needed).
- Replace / align the favicon with the cellpy icon (served from `web/static/img/`).
- Set the desktop (pywebview) window icon where the platform API allows; document if Windows needs a raster (`.ico`/`.png`) derived from the SVG.
- Prefer copying or building static assets from `assets/` into the served static tree — don’t leave the UI pointing at unserved `assets/` paths.
- Keep “simple gui” subtitle; don’t redesign the whole chrome.

## Acceptance criteria

- [ ] Header shows the cellpy logo (not `◧`) in both dark and light themes with readable contrast.
- [ ] Browser / WebView tab favicon is the cellpy icon.
- [ ] Desktop window icon is set when pywebview supports it on Windows; otherwise note the limitation in the PR.
- [ ] No broken image paths in `--server` or desktop mode.

## Out of scope

- Full installer / `.exe` branding / Start-menu shortcuts (separate packaging work).
- Redesigning the cellpy logo itself.
- Replacing all emoji/UI glyphs elsewhere with logo marks.
