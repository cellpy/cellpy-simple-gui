# Plan — Issue #36

## Goal

Theme `.chart-card` with app-shell tokens (no hard-coded white) and default figure theme preference to **Match app**.

## Approach

1. Restyle `.chart-card` to `background: var(--panel)` (+ optional `border: 1px solid var(--line)`) so light/dark shell drives the card.
2. Change JS fallback `localStorage.getItem("csg-figure-theme") || "light"` → `"match"`.
3. Update `plot-appearance.md` default note to Match app.
4. Existing localStorage values stay respected (no migration).

## Files to touch

- `src/cellpy_simple_gui/web/static/css/app.css`
- `src/cellpy_simple_gui/web/static/js/app.js`
- `.issueflows/04-designs-and-guides/plot-appearance.md`

## Test strategy

- Manual visual: dark/light shell × Match/Dark/Light figure theme (no automated CSS test).
- Existing pytest suite must stay green.
