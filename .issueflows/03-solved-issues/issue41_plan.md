# Plan — Issue #41

## Goal

Import raw with Instrument = Arbin SQL (HDF5) must use `arbin_sql_h5`, not the cellpy `data_df` reader.

## Approach

1. In `load_raw`, always pass `auto_pick_cellpy_format=False` so an explicit instrument is never overridden by `.h5`/`.hdf5` suffix sniffing (cellpy only exempts the exact id `arbin_sql_h5` today).
2. Wrap `_get` errors that mention `data_df` with a hint to use Import raw + Arbin SQL (HDF5), not Load cells.
3. Soften Load-cells UI hint: `.cellpy` / native cellpy `.h5`, not Arbin SQL HDF5.
4. Note in `CELLPY_PAINPOINTS.md`.
5. Unit test: mock `cellpy.get` and assert kwargs include instrument + `auto_pick_cellpy_format=False`; assert `arbin_sql_h5` is listed.

## Files to touch

- `src/cellpy_simple_gui/core/cellpy_adapter.py`
- `src/cellpy_simple_gui/web/templates/index.html`
- `tests/test_ingest.py`
- `CELLPY_PAINPOINTS.md`

## Test strategy

- Mock-based adapter kwargs assert; instruments list includes `arbin_sql_h5`.
- Full pytest.
