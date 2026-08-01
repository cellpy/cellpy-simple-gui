# Issue #72: Cycles tab: Mode change does not update x-axis capacity units

Source: https://github.com/cellpy/cellpy-simple-gui/issues/72

## Original issue text

## Problem / context

On the **Cycles** tab, changing **Mode** (e.g. Gravimetric → Areal) does not update the plot x-axis labels. With Mode = **Areal**, the axis still shows **Capacity (mAh/g)** instead of an areal unit (e.g. mAh/cm²). Method / cycle range can still replot, so the data path may update while the axis title/units do not.

Related (broader label polish): #38 — this issue is the concrete Mode ↔ unit mismatch on Cycles.

## Spec

- When Cycles **Mode** changes, replot so x-axis titles/units match the selected mode (gravimetric / areal / absolute).
- Prefer cellpy’s capacity/mode label helpers when available; keep behaviour consistent with whatever path builds Cycles figures today (`collect` / plot restyle).
- Same expectation if Mode is changed after a plot is already on screen (not only on first render).

## Acceptance criteria

- [ ] With Mode = Areal, Cycles x-axis shows areal capacity units (not mAh/g).
- [ ] With Mode = Gravimetric, x-axis shows gravimetric units (mAh/g).
- [ ] With Mode = Absolute (if offered), x-axis shows absolute capacity units.
- [ ] Changing Mode after an existing Cycles plot refreshes the axis label without a full page reload.
- [ ] At least one test covers mode → expected x-axis unit/label substring.

## Out of scope

- Full #38 summary/cell-explorer label mapper work (unless the fix naturally shares a helper).
- Changing which modes/methods are offered in the UI.
