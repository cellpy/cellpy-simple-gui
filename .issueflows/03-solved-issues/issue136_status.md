# Issue #136 — Status

- [x] Done

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
- **Stage 1** (`2a73a3e`): labelled *Open* / *Save* rows in the Project
  panel; Data panel = *Load demo cells* (primary) + *Add cells…*; folds to
  one line once cells exist (`dataCollapsed`), unfolds when emptied. G1 + G3
  green; verified live (default sidebar fits the viewport).
- **Stage 3 backend first** (`35fe9c5`, ordering deviation from the plan so
  the modal could be built against a real endpoint): `POST /api/files/preview`
  + `Expansion.total`; tests for literal / missing / glob-cap / served
  refusal. G2 green.
- **Stages 2–4 as one pass** (`de5b419`): Add cells modal (tabs cellpy / raw
  / journal), staged list with statuses (`ok` / `remote` / `unsupported` /
  `missing` / `refused` / `failed`), footer primary labelled by state with a
  disabled-reason line, adaptive source zone (drop, Browse when `canPick`,
  Upload when `!hostPathsAllowed`, typed path or glob with *max*, remote find
  disclosure), remote find stages matches. Loaded rows leave the list,
  failing rows stay marked with the loader's reason, full success closes the
  modal. G1 + G3 green (305 passed). **G4 modes matrix** verified live on two
  servers: loopback (`8578`) — Browse hidden (no pywebview), remote find
  shown, glob + literal + missing staged correctly, partial load kept the
  failed row; served (`CSG_ALLOW_HOST_PATHS=0`, `8579`) — Upload shown, Browse
  and remote find hidden, placeholder *paste a path inside the data
  directory*, host path staged as *refused* with the #120 wording, synthetic
  upload + drop both landed in `uploads/` and staged.
- **Stage 5** (`24e3b00`): result card (`lastResult`) in the modal footer and
  under the Data panel, details disclosure, ok/warn toasts dropped for
  load/ingest; recents in `localStorage["csg.recent"]` (cap 8) as
  `<datalist>` suggestions; static tests (`@click`/`x-show`/`@change`
  identifiers resolve, one `.btn-primary` in the modal, ≤ 4 default-visible
  hints); two e2e tests. **G5**: Playwright + Chromium installed, `-m e2e` →
  4 passed. G3 → 312 passed. `*.log.N` added to `.gitignore` (cellpy's
  rotated debug log appeared during the e2e run).
- **Stage 6** (`214db35`): README Features / Remote files, `docs/deployment.md`
  *Getting files in*, new `loading-ui.md` design record, `otherpath-remote-
  loading.md` §UX updated, `llms-full.txt` regenerated. **G6**: `uv run
  pytest` → **313 passed, 6 skipped, 0 failed** (the baseline `llms-full`
  drift is fixed); `-m e2e` → 4 passed, 1 skipped (mcp prototype).
  Screenshots in `/opt/cursor/artifacts/`: `modal-cellpy-empty.png`,
  `modal-cellpy-staged.png`, `modal-cellpy-after-load.png`, `modal-raw.png`,
  `modal-journal.png`, `modal-served-upload.png`, `modal-result-card.png`,
  `sidebar-result-card.png`.

## Notes / deviations

- Stage ordering: backend preview before the modal; Stages 2–4 landed in one
  commit because the template, JS and CSS for the modal are not meaningfully
  separable.
- `pywebviewFullPath` spike: implemented as planned (stage paths when every
  dropped file carries one, else upload) but **not exercised** here — no
  display / pywebview in this environment. Covered by the upload fallback.
- The failed-row "retry" keeps `failed` rows loadable on purpose (e.g. after
  installing `mdbtools`).
- Hint-budget test treats each `role="tabpanel"` as its own root and excludes
  `x-show` ancestors; it currently counts 1 (sidebar) + 2 (modal).
- No `HISTORY.md` / `CHANGELOG.md` exists in this repo, so there is no
  changelog step.

## Remaining work

- None in scope. Follow-ups worth their own issue: a *recents* menu on the
  Project path field (datalist only today), clearing recents from Diagnostics,
  and a GitHub issue carrying this spec if the owner wants one (the local
  number 136 does not correspond to a GitHub issue).
