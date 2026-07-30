# Issue #28 plan — Export cells from Manage cells

## Goal

From the **Manage cells** modal, let users export loaded cells to **`.cellpy` / `.csv` / `.xlsx`** (and **`.parquet` if we agree below) using cellpy’s own cell `save` / `to_csv` / `to_excel` APIs, landing files via the existing desktop Save As / browser download path.

## Constraints

- Prefer **cellpy cell APIs** (`CellpyCell.save`, `.to_csv`, `.to_excel`) over reinventing tabular export; keep cellpy imports in `core/cellpy_adapter.py` (or a thin helper next to it).
- Reuse the existing front-end `download()` helper (desktop → `POST /api/system/save`, browser → `<a download>`).
- Do not confuse this with summary/cycles *plot* export (`/api/export/summary|cycles`) — those stay as-is.
- Manage modal behaviour stays as in [`manage-cells-modal.md`](../04-designs-and-guides/manage-cells-modal.md); this only adds an export control.
- cellpy has **no** `CellpyCell.to_parquet` today (only data-frame parquet inside the `.cellpy` v9 container). Parquet needs an explicit call (see Open questions).

### Prior art

| Hit | Notes |
|---|---|
| `cellpy_adapter.save_cell` | Already wraps `cell.save(..., overwrite=True)` for projects |
| `export.summary_export` / `cycles_export` + `api/routers/export.py` | Pattern for fmt → bytes + `Content-Disposition`; **coexist** — add a cells export route beside them |
| `app.js` `download()` + `/api/system/save` | Desktop Save As / browser download — **reuse** |
| Manage modal (`index.html` / `app.js`) | Toolbar + table; add Export ▾ in modal toolbar/footer |
| `projects.save_project` | Writes many `.cellpy` files into a folder — different UX (named project); do **not** overload Save project |
| cellpy `to_csv` / `to_excel` | Write to disk paths (csv can emit **multiple** files under a datadir) — use a temp dir, then zip or pick primary file |
| Toolbox `00-tools/` | None found |
| Graph | Export community (`export_bytes`, routers) + Manage-cells UI — no new god-node surprises |

## Approach

1. **Selection:** Export the **selected** library cells (same checkboxes as plots). If none selected → toast / 400. Optional later: “export filtered rows”; not in v1 unless you want it.
2. **Formats (proposed):**
   - **`cellpy`** — `save_cell` → one `.cellpy` per cell.
   - **`xlsx`** — `cell.to_excel(path)` → one workbook per cell (cellpy defaults: steps etc.).
   - **`csv`** — `cell.to_csv(datadir=...)` into a temp folder (may produce several files: raw/summary/…).
   - **`parquet`** — only if accepted in Open questions (app writes summary/raw frames); otherwise omit from UI.
3. **Packaging:**
   - **1 cell:** return a single file (`label.cellpy` / `.xlsx`, or a small zip if csv produced multiple files).
   - **N cells:** return a **`.zip`** of per-cell artifacts (clear names from label/id). One Save As / download.
4. **API:** `POST /api/export/cells?fmt=...` with optional JSON `{ "cell_ids": [...] }` (default = currently selected). Response = file bytes + disposition filename (`cells.zip` or `name.cellpy`).
5. **UI:** In Manage cells modal toolbar (near remove-all / Close), **Export ▾** listing formats; call the new endpoint through `download()`.
6. **Painpoint (if needed):** note missing `CellpyCell.to_parquet` / multi-file `to_csv` awkwardness for apps in `CELLPY_PAINPOINTS.md` only if we hit real friction.

```
Manage modal Export ▾
  → POST /api/export/cells?fmt=
  → core: tempfile + cellpy save/to_* (+ zip if needed)
  → download() → Save As (desktop) / browser download
```

## Files to touch

| Path | Change |
|---|---|
| `src/cellpy_simple_gui/core/cellpy_adapter.py` | Thin wrappers if useful (`export_cell_csv` / excel) around `to_csv` / `to_excel` |
| `src/cellpy_simple_gui/core/export.py` | `cells_export(records, fmt) -> (bytes, media, filename)` |
| `src/cellpy_simple_gui/api/routers/export.py` | `POST /export/cells` |
| `src/cellpy_simple_gui/web/templates/index.html` | Export ▾ in Manage cells modal |
| `src/cellpy_simple_gui/web/static/js/app.js` | `exportCells(fmt)` |
| `src/cellpy_simple_gui/web/static/css/app.css` | Minor modal-toolbar spacing if needed |
| `tests/test_core.py` / `tests/test_api.py` | Export one example cell to cellpy/xlsx (and zip for 2 cells); API 400 when none selected |
| `.issueflows/04-designs-and-guides/manage-cells-modal.md` | Document Export control |
| `CELLPY_PAINPOINTS.md` | Only if parquet / multi-file csv needs an upstream wish |

## Test strategy

- `uv run pytest`
- Unit: export one loaded example cell as `.cellpy` and `.xlsx` → non-empty bytes; two cells → zip with two members.
- API: no selection → 400; happy path returns attachment headers.
- Manual: Manage → select cells → Export ▾ → Save As path toast (desktop).

## Open questions

_Resolved on accept (2026-07-30):_

1. **Parquet?** **Omit in v1** (no `CellpyCell.to_parquet`). Formats: `.cellpy` / `.csv` / `.xlsx` only.
2. **Which cells?** **Selected only.**
3. **CSV shape?** Zip cellpy’s multi-file `to_csv` output (single cell may still be a zip if multiple files).
4. **Excel defaults?** cellpy `to_excel` defaults; no toggles in v1.

**Status:** Accepted — ready for `/iflow-build`.
