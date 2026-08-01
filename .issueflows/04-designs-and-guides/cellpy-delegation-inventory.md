# cellpy delegation inventory (issue #52)

Against **cellpy 2.1.1.post4** (bumped from post2). Goal: prefer cellpy APIs;
keep only app chrome that cellpy still does not own.

| Area | Upstream | Decision | Notes |
|------|----------|----------|--------|
| `list_instruments` WARNING spam | #786 fixed in **post3** | **Delegated** | Dropped root-log silencing in `cellpy_adapter.list_instruments` |
| Collected figure theme / label / height | #801 in **post4** (`plotly_template`, `layout_updates`, pretty labels, `height_per_panel`) | **Delegated (partial)** | `_inject_app_chrome` passes theme tokens + height; `_restyle` keeps legend truncation, colorway, axis grids |
| Pretty axis / facet labels | #801 defaults (names only) | **Keep forwarding** | App passes unit-bearing `y_label_mapper` via `summary_y_label_mapper` (#38 / painpoint §18). Remap for #39 keys off hover `variable=` |
| Per-panel `y_ranges` / `share_y` | #804 in **post2** | **Keep forwarding** | App still re-applies share_y after spread plots (#47 gap) |
| Summary facet `category_orders` | Painpoint §20 open | **Keep forwarding** | App passes `category_orders={"variable": columns}` (#81); CE-first `capacity_ce` tuple |
| `read_meta(path)` | #799 in **post4** | **Wrapper now** | `cellpy_adapter.read_file_meta` — UI wiring deferred |
| `instrument_meta_schema` | #800 in **post4** | **Wrapper now** | `cellpy_adapter.instrument_meta_schema` — ingest form follow-up |
| Group-avg all-or-nothing + figure merge | Still app (#27 / #39) | **Keep** | Verified post4 still disables avg when any singleton present |
| Colorways / figure theme UI | App (#32) | **Keep** | Not upstream |
| Static figure bytes (kaleido) | Painpoint §13 open | **Keep** | `export.figure_bytes` |
| `.h5` `auto_pick_cellpy_format` | Painpoint §14 / #41 | **Keep** | `load_raw` sets `False` |
| Cycles plot `x_unit` vs collect mode | Defaults `mAh/g`; ignores meta mode | **Keep forwarding** | App passes `x_unit` from `CAPACITY_UNITS` (#72) |

## What the app still owns

- Discrete color schemes + session figure-theme preference
- Legend name truncation / right margin for long cell names
- Mixed multi/singleton group-avg partition + facet axis remapping
- Cycles capacity `x_unit` from Mode until upstream reads collection meta
- Summary `y_label_mapper` with units (CE / C-rate fallbacks) until §18 lands
- In-memory PNG/SVG/PDF export and desktop Save As
- Ingest form field layout (until a follow-up consumes `instrument_meta_schema`)
