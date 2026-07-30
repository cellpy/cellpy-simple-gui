# Plan: Issue #17 — export success message

## Goal

Show a toast when exporting data: where/what file, and whether it succeeded.

## Approach

In `download()`, on success notify with the download filename; on failure notify the error. Prefer Content-Disposition filename when present.

## Files to touch

- `web/static/js/app.js`

## Test strategy

`uv run pytest` (no API change).
