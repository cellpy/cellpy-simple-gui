# Loading UI: Add cells modal + staged list (local issue 136)

## Context

Loading grew by accretion: Load demo (collapsed), Add cellpy files, Import raw
and the Project panel each had their own disclosure in the sidebar, two of them
with a nested *Find in a remote folder…* block. Fully expanded, the Data panel
alone was ~1680 px tall, 13 help lines were on screen, eight text inputs took
`;`-separated path strings, and the desktop / served distinction was expressed
by hiding or demoting fields in place. A glob or a remote find wrote its
result back into a text field the user then had to eyeball.

## Decision

1. **One entry point.** The sidebar Data panel holds only *Load demo cells*
   (primary) and *Add cells…*. Everything else moved into a modal with three
   tabs — *cellpy files*, *Raw instrument files*, *Batch journal*. Project
   folders / `project.json` keep opening from the Project panel (that is an
   *open*, not an *add*).
2. **Staged list instead of a path string.** Every source (drop, Browse,
   Upload, typed path or glob, remote find) feeds `staged[kind]` — one row per
   file with `ext`, `name`, `dir`, `source`, `status`, `detail`. Typed input
   goes through `POST /api/files/preview` (`expand_paths` without loading;
   `Expansion.total` reports the pre-cap count) so what the list shows is
   exactly what Load would take. Statuses: `ok`, `remote` (URI, no local
   existence check), `unsupported` (extension not in the tab's accepted set —
   advisory, still sent), `missing`, `refused` (sandbox / served-mode wording
   unchanged), `failed` (loader error after a run; row stays with the reason).
3. **One primary button per modal**, in the footer, labelled by state
   (*Load 3 files* / *Import 2 files* / *Open journal*) with a one-line reason
   next to it while disabled. `loadFiles()` / `ingestRaw()` read the loadable
   staged paths and send `max_files: paths.length`; loaded rows leave the list,
   full success closes the modal.
4. **Adaptive source zone.** `Browse…` shows when `canPick`; `Upload…` and the
   served placeholder when `!hostPathsAllowed`; *Find in a remote folder…* when
   host paths are allowed. Drop: pywebview's `pywebviewFullPath` → stage paths
   directly, otherwise upload the bytes (a loopback desktop instance also
   allows uploads, so nothing is lost).
5. **Outcome as a result card, not toasts.** `reportJobResult` writes
   `lastResult`; it renders in the modal footer, or under the Data panel when
   the modal is closed, with a *details* disclosure. Only outright failure
   still toasts. Staging new files dismisses the previous card.
6. **Recents.** Typed patterns, journals and remote folders are kept in
   `localStorage["csg.recent"]` (cap 8) and offered as `<datalist>`
   suggestions.
7. **Data panel folds** once cells exist (`dataCollapsed`), so the Cells list
   gets the height; *add more…* in the folded line reopens the modal.

## Guard rails (tests)

- `tests/test_api.py`: `/api/files/preview` literal / missing / glob-cap /
  served refusal; every `@click` / `x-show` / `@change` / `@keydown.enter`
  identifier in `index.html` resolves in `app()`; exactly one `.btn-primary`
  inside the Add cells modal; at most four `.hint` elements visible before the
  user touches anything (per-tabpanel roots, `x-show` ancestors excluded).
- `tests/test_gui_playwright.py` (`-m e2e`): Data panel folds after a demo
  load and shows the result card; typed path + missing path → staged rows
  with statuses → *Load 1 file* → loaded row leaves, missing row stays.

## Alternatives considered

- **Segmented control in the sidebar** (no modal): keeps everything visible
  but the raw tab's options alone need ~500 px; the sidebar would still scroll.
- **Keep the `;`-joined string** and only restyle: cheapest, but globs and
  remote find would still dump opaque strings the user cannot edit per file.
- **A slide-in drawer** instead of a modal: nicer for side-by-side with the
  plot, but the existing Manage-cells modal pattern (backdrop, Esc, footer) was
  already understood by users and tests.
- **Server-side staged list**: rejected; the list is a UI concern and the
  preview endpoint already reuses the exact expansion the loader runs.

## Links

- Local issue files: `.issueflows/0*/issue136_*` (no GitHub issue; #136 on
  GitHub is the unrelated container-image PR).
- Related: `otherpath-remote-loading.md` (#160 / #162), #120 sandbox, #133
  uploads, #143 instrument availability.
