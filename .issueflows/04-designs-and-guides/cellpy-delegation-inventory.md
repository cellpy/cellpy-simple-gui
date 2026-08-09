# cellpy delegation inventory (issue #52)

Against **cellpy 2.1.2a2** (bumped from post7). Goal: prefer cellpy APIs;
keep only app chrome that cellpy still does not own.

## Release-gating note (resolved for #816/#818/#819)

`#816`, `#818`, `#819` shipped in **cellpy 2.1.2a2** (PyPI, 2026-08-08) and
their app workarounds were **removed** in the 2.1.2a2 cleanup pass:

- **#816** — cellpy now averages multi-member groups even when a singleton
  group is present, returning both in **one** collection (verified
  empirically). The app's partition/merge (`summary_collections`,
  `figures_json`, `combined_summary_frame`, `partition_by_group_size`) and the
  `#47` `_apply_share_y` / `_want_share_y` re-link are **gone**; summary
  plotting/export now go straight through `summary_collection` + `figure_json`
  / `export_bytes`. share_y / match_axes are honoured natively on both the
  grouped and grouped+spread paths.
- **#818** — `cellpy.plotting.figures.write_image(fig, fmt, scale=) -> bytes`
  (in-process `to_image`, no temp files/subprocess) plus `image_media_type()`.
  `export.figure_bytes` now delegates to these instead of `fig.write_image`.
- **#819** — a set `instrument=` wins over `.h5`/`.hdf5` suffix auto-pick, so
  `load_raw` no longer forces `auto_pick_cellpy_format=False`.

`#817`, `#820`, `#821` landed earlier (post7). Still open/deferred: the `#821`
ICA `direction` delegation (drop `_filter_ica_by_direction`) is a **follow-up**
— it changes export semantics and wants a "Both" UI option, so it was kept out
of the 2.1.2a2 cleanup.

| Area | Upstream | In 2.1.2a2? | Decision |
|------|----------|-------------|----------|
| `list_instruments` WARNING spam | #786 (post3) | yes | **Delegated** — no root-log silencing |
| Collected figure theme / labels / height | #801 (post4) | yes | **Delegated (partial)** — `_inject_app_chrome`; `_restyle` keeps legend truncation, colorway, grids |
| Unit-bearing y-labels | #801 defaults names-only | yes | **Keep forwarding** `y_label_mapper` (#38 / §18 open) |
| `read_meta(path)` | #799 (post4) | yes | **Wrapper** `read_file_meta` (UI wiring deferred) |
| `instrument_meta_schema` | #800 (post4) | yes | **Wrapper** (ingest form follow-up) |
| `spread_plot` share_y | #817 | yes | **Delegated** — cellpy honours share_y/match_axes on grouped + grouped+spread; `_apply_share_y` removed |
| Cycles facet strip labels | #820 | yes | **Delegated** — clean strips for free, no app code |
| Group-avg all-or-nothing + merge | #816 | **yes (2.1.2a2)** | **Removed** — one collection averages groups + keeps singletons; partition/merge deleted |
| Static figure bytes (kaleido) | #818 | **yes (2.1.2a2)** | **Delegated** — `figure_bytes` → `figures.write_image` + `image_media_type` |
| `.h5` `auto_pick_cellpy_format` | #819 | **yes (2.1.2a2)** | **Removed** — set `instrument=` wins over suffix; no forced `auto_pick=False` |
| ICA `direction` (line + both) | #821 | yes | **Follow-up** — drop `_filter_ica_by_direction`, pass `direction` to `collection.plot`; pairs with a "Both" UI option + export-direction decision |
| Summary facet `category_orders` | §20 open, unfiled | n/a | **Keep forwarding** (#81) |
| Cycles plot `x_unit` vs collect mode | §17 open, unfiled | n/a | **Keep forwarding** (#72) |
| Non-atomic `.cellpy` writes | **#845 filed** | n/a | App stages project saves; single-file save still at cellpy's mercy |
| Selective summary rebuild | **#846 filed** | n/a | App full `make_summary()` after meta edits |

## Removed in the 2.1.2a2 cleanup

- **#816** — deleted `partition_by_group_size`, `summary_collections`,
  `figures_json`, `combined_summary_frame`, `_remap_trace_axes`; `summary_figure`
  / `summary_export` now use `summary_collection` + `figure_json` / `export_bytes`.
- **#817/#47** — deleted `_apply_share_y` / `_want_share_y`; `figure_json` now
  applies per-facet `y_ranges` directly and lets cellpy own axis matching.
- **#818** — `export.figure_bytes` delegates to `cellpy.plotting.figures`.
- **#819** — `load_raw` drops the forced `auto_pick_cellpy_format=False`.

## Remaining follow-ups

- **#821 ICA** — the one removable workaround left; it changes export semantics
  (single- vs both-direction) and wants a "Both" UI option, so do it as its own
  issue rather than in the pin-bump cleanup.

## Still app-owned (no upstream yet / by design)

- Discrete colorways + session figure-theme preference (#32)
- Legend truncation / right margin for long cell names
- Unit-bearing summary `y_label_mapper` (§18), cycles `x_unit` (§17),
  facet `category_orders` (§20) — all unfiled friction
- Desktop Save As + zip packaging (encode itself now delegated to cellpy #818)
- Ingest form layout (until a follow-up consumes `instrument_meta_schema`)
