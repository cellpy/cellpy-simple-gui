# Issue #4: Replace deprecated pywebview OPEN_DIALOG with FileDialog.OPEN

Source: https://github.com/cellpy/cellpy-simple-gui/issues/4

## Original issue text

## Problem / context

Running the desktop shell logs:

```
WARNING:pywebview:OPEN_DIALOG is deprecated and will be removed in a future version. Use 'FileDialog.OPEN' instead.
```

`src/cellpy_simple_gui/api/routers/system.py` still passes `webview.OPEN_DIALOG` into `create_file_dialog`. pywebview 6.x exposes `webview.FileDialog.OPEN` (also `SAVE` / `FOLDER`).

## Spec

- Switch the pick endpoint to `webview.FileDialog.OPEN`.
- Grep for other deprecated dialog constants (`SAVE_DIALOG`, `FOLDER_DIALOG`) and update if present.
- Keep behavior: multi-select for non-journal kinds, same file type filters, same JSON `{paths: [...]}` shape.
- Stay compatible with the project’s `pywebview>=5.1` pin, or bump the lower bound if `FileDialog` is 6.x-only (check and decide in plan).

## Acceptance criteria

- [ ] No `OPEN_DIALOG` / `SAVE_DIALOG` / `FOLDER_DIALOG` deprecation warning when using the desktop file picker.
- [ ] Native open dialog still works for cellpy / raw / journal pick kinds.
- [ ] `--server` mode still reports `file_picker: false` and rejects pick with 400.

## Out of scope

- Broader pywebview upgrades unrelated to this API.
- Folder-picker or save-dialog features that do not exist yet.
