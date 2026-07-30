# Plan: Issue #14 — make saving and closing more obvious

## Goal

Make it clear that project save is manual, show when the session has unsaved edits, and provide a way to close the current project.

## Approach

1. UI copy: tag “no project” (not “unsaved”); hint that Save is manual; toast “Saved …” vs “Opened …”.
2. Client-side `dirty` flag: set on load/edit/remove; clear on save/open/close; show `*` / dirty styling on the project tag.
3. Project panel **Close** button → confirm → existing `POST /api/cells/clear`.

## Files to touch

- `web/templates/index.html`, `web/static/js/app.js`, `web/static/css/app.css`
- `api/routers/projects.py` (action field on save/open results for toast text)

## Test strategy

`uv run pytest` (existing project tests). Manual UI check optional.
