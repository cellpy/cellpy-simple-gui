# Plan: Issue #18 — improve manage cells modal

## Goal

Fix Select group in the Manage cells modal; rename Clear to “remove all cells” and place it far right.

## Approach

1. `selectGroup()` selects only the chosen group (select matching, deselect others) using numeric group compare.
2. Toolbar: drop inline Clear; add “remove all cells” at the far right of the toolbar.

## Files to touch

- `web/static/js/app.js`, `web/templates/index.html`, `web/static/css/app.css` (layout)

## Test strategy

`uv run pytest`.
