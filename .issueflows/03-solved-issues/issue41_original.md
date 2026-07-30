# Issue #41: Arbin SQL HDF5 import uses cellpy `.h5` loader instead of `arbin_sql_h5`

Source: https://github.com/cellpy/cellpy-simple-gui/issues/41

## Original issue text

## Problem / context

Importing an Arbin SQL HDF5 file with **Instrument = Arbin SQL (HDF5)** fails with e.g. `…h5: 'No object named data_df in the file'`. That message comes from the **cellpy native HDF5** reader (`data_df`), not the Arbin SQL H5 loader — so the wrong loader ran even though the UI instrument was set correctly.

App path: Import raw → `POST /api/ingest` → `cellpy_adapter.load_raw(..., instrument=…)` → `cellpy.get(filename=…, instrument=…)`. Either cellpy is sniffing `.h5` as cellpy-format and ignoring `instrument`, the instrument id from `list_instruments()` does not match what `get` expects, or another path is loading `.h5` without the instrument.

## Spec

- With Instrument = Arbin SQL (HDF5) (whatever id cellpy exposes, e.g. `arbin_sql_h5`), ingest must invoke that loader for the selected `.h5` files — not the cellpy `data_df` reader.
- If cellpy overrides `instrument` based on extension, work around in the adapter if possible and document in `CELLPY_PAINPOINTS.md` + link/open an upstream cellpy issue.
- Improve the error when the wrong loader is clearly being used (hint: wrong instrument / use Import raw with Arbin SQL HDF5, not Load cells).
- Confirm the instruments dropdown id for “Arbin SQL (HDF5)” is the one `cellpy.get` accepts.
- Optional UX: discourage loading Arbin SQL `.h5` via the Load cells (`.cellpy`/`.h5`) picker, which always uses the cellpy file loader.

## Acceptance criteria

- [ ] Selecting Arbin SQL (HDF5) and importing a valid Arbin SQL `.h5` succeeds (or fails with an Arbin-loader error, not `data_df`).
- [ ] Same file via Load cells without instrument still behaves as a cellpy-file load (document expected behaviour).
- [ ] Painpoint / upstream note if cellpy ignores `instrument` for `.h5`.
- [ ] Test or adapter-level assert that `load_raw` passes the selected instrument through (mock/`cellpy.get` kwargs), plus a note on real-file smoke if fixtures exist.

## Out of scope

- Full Arbin SQL feature parity beyond correct loader selection.
- Plot/UI issues (#36–#40).
- Auto-detecting format without using the Instrument dropdown (unless a tiny, safe hint).
