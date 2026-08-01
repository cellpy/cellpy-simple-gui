# pywebview file dialogs

**Decision (issue #4):** use `webview.FileDialog.OPEN` (and `SAVE` / `FOLDER` if added later), never the deprecated `OPEN_DIALOG` / `SAVE_DIALOG` / `FOLDER_DIALOG` module constants.

**Pin:** `pywebview>=6.0` — `FileDialog` was introduced in 6.0.

**Call sites:** `src/cellpy_simple_gui/api/routers/system.py`

| Endpoint | Dialog | Notes |
|---|---|---|
| `POST /api/system/pick` | `FileDialog.OPEN` | Load cellpy / raw / journal (JSON) paths |
| `POST /api/system/pick` `kind=folder` | `FileDialog.FOLDER` | Portable project folder (#75) |
| `POST /api/system/save?filename=` | `FileDialog.SAVE` | Write export body to chosen path (#31) |

Server mode has no window → capabilities report `file_picker: false`; pick/save return 400.

**Why SAVE for exports:** the front-end `<a download>` + blob trick claims “Downloads”
but under pywebview the file often never appears there. Desktop exports POST the
bytes to `/api/system/save` and toast the real path; browser/`--server` keeps the
anchor download with a softer “Download started” toast.
