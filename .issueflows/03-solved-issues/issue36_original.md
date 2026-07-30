# Issue #36: Chart card stays white under dark figure theme; default figure theme to Match app

Source: https://github.com/cellpy/cellpy-simple-gui/issues/36

## Original issue text

## Problem / context

After #32, figure theme can be dark / Match app, but the Plotly figure still sits in a hard-coded white `.chart-card` pane (`app.css`: `background: #fff`). In the dark app shell that white card “sticks out” around and past the figure. A second UX gap: the default figure theme is still `light`, so Match app is not the first-run default.

Preferred fix (simple): theme the chart card with the **app shell** tokens (dark/light), and change the default figure theme preference to **Match app**. Deeper coupling of figure theme → card chrome is optional and likely overkill.

## Spec

- Restyle `.chart-card` (and any related chart chrome) to use existing CSS variables (`--panel` / theme tokens) so it follows the app light/dark shell — not the figure-theme control alone.
- Change the default `csg-figure-theme` preference to `match` (UI default + `localStorage` fallback when unset). Keep Light / Dark / Match app options.
- Existing `localStorage` values for users who already chose Light/Dark stay respected.
- Confirm summary and cell explorer chart cards both look intentional in dark and light shells with Match app / Dark / Light figure themes.

## Acceptance criteria

- [ ] In dark app shell + Match app (or Dark figure theme), no large white card surrounds/extends past the Plotly figure.
- [ ] In light app shell, the chart card still looks like a clean light surface (not a dark blob).
- [ ] Fresh session (no `csg-figure-theme` in localStorage) defaults figure theme to **Match app**.
- [ ] Changing shell theme with Match app still re-renders figures as today (#32).

## Out of scope

- Linking chart-card color to the figure-theme control independently of the app shell.
- Per-export card chrome / print styling.
- Redesigning plot layout/margins beyond the white-pane mismatch.
