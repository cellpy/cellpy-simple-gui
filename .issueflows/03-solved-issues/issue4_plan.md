# Issue #4 plan

## Goal

Stop using deprecated `webview.OPEN_DIALOG` in the desktop file picker; use `webview.FileDialog.OPEN` and raise the pywebview lower bound so the API is guaranteed.

## Constraints

- Keep multi-select / file-type filters / `{paths: [...]}` response shape unchanged.
- No new save/folder picker features.
- `--server` mode: `file_picker: false`, pick → 400.

### Prior art

- None found (toolbox empty; only call site is `system.py` `pick`; no existing system/picker tests).

## Approach

1. In `pick`, pass `webview.FileDialog.OPEN` instead of `webview.OPEN_DIALOG`.
2. Grep confirmed no `SAVE_DIALOG` / `FOLDER_DIALOG` usages.
3. `FileDialog` is pywebview 6.0+ only (lock already resolves `6.2.1`) → bump pin to `pywebview>=6.0`.
4. Add TestClient coverage for capabilities + pick rejection (server has no webview window).

## Files to touch

- `src/cellpy_simple_gui/api/routers/system.py` — use `FileDialog.OPEN`
- `pyproject.toml` — `pywebview>=6.0`
- `tests/test_api.py` — capabilities + pick 400 tests
- `.issueflows/01-current-issues/issue4_*` — tracking docs

## Test strategy

`uv run pytest` — existing suite plus new system endpoint tests.

## Open questions

None (yolo auto-confirm).
