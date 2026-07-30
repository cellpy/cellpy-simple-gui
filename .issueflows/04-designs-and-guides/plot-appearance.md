# Plot appearance (theme + color scheme)

From issue #32.

## Context

Summary/cell figures always got a hard-coded light restyle (`collect._restyle`)
while the app shell has light/dark chrome. Users also could not pick a plot
colorway. cellpy's `plotting.theme` exposes axis/collector templates, not a
light/dark shell hook.

## Decision

- **API receives resolved theme only** (`figure_theme: light|dark`). The UI
  offers Light / Dark / Match app; `"match"` is resolved client-side from the
  shell theme before POST so export stays deterministic.
- **Color schemes:** `cellpy` (leave upstream colors), `safe` (`library.PALETTE`),
  `muted` (lower-saturation qualitative). Applied post-plot in `_apply_colorway`.
- **Defaults:** figure theme `match` (resolves from app shell) + color scheme `cellpy`.
  Chart card chrome follows shell tokens (`--panel` / `--line`), not figure theme.
- **Persistence:** `localStorage` keys `csg-figure-theme`, `csg-color-scheme`.
  Existing Light/Dark choices in localStorage stay respected.
- **Cell-list swatches** stay on `PALETTE` and do not follow the plot scheme (v1).
- Keep legend/facet polish in app `_restyle`; do not replace it with cellpy
  templates until they cover height/legend/facet strip needs.

## Alternatives considered

- Server-side `"match"` + `shell_theme` field — rejected; duplicates chrome state.
- Sync library swatches to the selected scheme — deferred; nicer but more UI churn.
