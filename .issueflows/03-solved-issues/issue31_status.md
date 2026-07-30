# Issue #31 status — Iterative fixes: export download location

Interactive `/iflow-fix` session.

- [x] Done

## Iterative fixes log

- 2026-07-30 — **Export Save As (desktop):** programmatic `<a download>` never
  reliably reached Downloads under pywebview. Added `POST /api/system/save`
  (`FileDialog.SAVE` + write bytes); desktop `download()` uses it and toasts the
  real path; browser toast says “Download started…”. Updated
  `pywebview-file-dialog.md`. Test: `test_system_save_rejected_without_webview`.
