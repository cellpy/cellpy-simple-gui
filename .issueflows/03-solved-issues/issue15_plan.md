# Plan: Issue #15 — update readme

## Goal

Refresh README for recent features and replace outdated screenshots in `docs/img/`.

## Approach

1. Update Features / Status / Development notes for logging, CI essential tests, save/close UX, export toasts, Manage cells, journal error feedback.
2. Recapture key PNGs via headless server + browser screenshots (summary, cell explorer, projects, ingest, manage cells if feasible).
3. Keep image filenames stable where README already references them.

## Files to touch

- `README.md`
- `docs/img/*.png`

## Test strategy

`uv run pytest` (docs-only besides assets).
