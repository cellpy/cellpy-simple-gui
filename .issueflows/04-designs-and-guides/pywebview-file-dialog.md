# pywebview file dialogs

**Decision (issue #4):** use `webview.FileDialog.OPEN` (and `SAVE` / `FOLDER` if added later), never the deprecated `OPEN_DIALOG` / `SAVE_DIALOG` / `FOLDER_DIALOG` module constants.

**Pin:** `pywebview>=6.0` — `FileDialog` was introduced in 6.0.

**Call site:** `src/cellpy_simple_gui/api/routers/system.py` (`POST /api/system/pick`). Server mode has no window → capabilities report `file_picker: false` and pick returns 400.
