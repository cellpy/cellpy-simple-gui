# Issue #4 status

- [x] Done

## What's done

- Switched `system.pick` to `webview.FileDialog.OPEN`.
- Bumped dependency pin to `pywebview>=6.0` (`FileDialog` is 6.x-only; lock already had 6.2.1).
- Added TestClient coverage for capabilities (`file_picker: false`) and pick → 400 without a webview window.
- Grep: no remaining `OPEN_DIALOG` / `SAVE_DIALOG` / `FOLDER_DIALOG` usages.
- `uv run pytest`: 36 passed.

## Remaining work

None.
