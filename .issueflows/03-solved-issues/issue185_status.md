# Status — #185 cell mode does not reach ICA

- [x] Done

## What's done

- ICA and DVA collection translate `full_cell` to `full-cell` for the cellpy call, then restore the app spelling.
- `read_meta` shows a stored `full-cell` as `full_cell` and does not rewrite the cell.
- Regression tests: charge rows follow the charge series for `full_cell` and for `anode`, the attribute is unchanged after ICA and DVA, and the hyphenated spelling displays as `full_cell`.
- `uv run pytest` passed.

## Remaining work

- None. Direction stays default Charge. A file that truly has only one step type still shows one lobe.
