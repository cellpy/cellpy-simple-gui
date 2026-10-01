# Issue #136 — Status

- [ ] Done

## What's done

- 2026-10-01: eight loading-UI suggestions reviewed with the owner; decision
  to combine them into **one issue** with a plan that states when tests run.
  Local number **136** chosen by the owner (GitHub #136 is the merged
  container PR — see `issue136_original.md`).
- Captured `issue136_original.md`, plan accepted as `issue136_plan.md`
  (six stages, test gates G0–G7).
- Branch: `cursor/loading-ui-redesign-plan-b3ff` (cloud-agent naming, work
  in place). Draft PR #166 opened with the planning docs.
- **G0 baseline** (`main` @ `e056abe`, this environment): `uv run pytest` →
  301 passed, 7 skipped, 1 failed (`tests/test_agent_docs.py::test_llms_full_txt_is_current`,
  pre-existing: `docs/llms-full.txt` not regenerated after the README icon
  commit), ~24 s. `node` present → `test_app_js_parses` runs. Playwright /
  Chromium not installed → e2e skips (G5 needs `uv sync --extra e2e` +
  `uv run playwright install chromium`). Screenshots of the default and
  all-expanded sidebar saved under `/opt/cursor/artifacts/`
  (`loading-ui-default-collapsed.png`, `loading-sidebar-all-expanded-2col.png`):
  Data panel ~1680 px, sidebar scroll 2223 px at 1440×900, 13 hints, 8 text
  inputs.

## Remaining work

- Stage 1 — sidebar restructure (Project rows with labels; Data = demo +
  *Add cells…*; collapse after load). Gates G1, G3.
- Stage 2 — *Add cells* modal, tabs, footer primary + reason; remove
  disclosures. Gates G1, G3, G5.
- Stage 3 — staged list + `POST /api/files/preview` + tests. Gates G2, G3.
- Stage 4 — adaptive source zone (drop / browse / upload / remote find).
  Gates G3, G4.
- Stage 5 — contextual hints, inline results, recents, static + e2e tests.
  Gates G1, G3, G4, G5.
- Stage 6 — docs, `llms*.txt` regeneration, design record `loading-ui.md`.
  Gate G6.
- `iflow close`: HISTORY (none exists yet), status `- [x] Done`, move to
  `03-solved-issues/`, PR body with screenshots.
