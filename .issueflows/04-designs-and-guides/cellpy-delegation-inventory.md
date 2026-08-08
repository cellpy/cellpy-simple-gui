# cellpy delegation inventory (issue #52)

Against **cellpy 2.1.1.post7** (bumped from post4). Goal: prefer cellpy APIs;
keep only app chrome that cellpy still does not own.

## Release-gating note (important for cleanup)

`#816`, `#818`, `#819` were closed on cellpy's **master (2026-08-08)** but are
**not in the released post7** — the app still runs their workarounds, and
removing them now breaks (verified: dropping the `#47` share_y re-link breaks the
`#816` group-avg *merge* path, which post7 still needs). `#817`, `#820`, `#821`
landed earlier and **are** in post7.

**So most of this cleanup is gated on the next cellpy release (post8).** Re-run
this pass when post8 ships with #816/#818/#819.

| Area | Upstream | In post7? | Decision |
|------|----------|-----------|----------|
| `list_instruments` WARNING spam | #786 (post3) | yes | **Delegated** — no root-log silencing |
| Collected figure theme / labels / height | #801 (post4) | yes | **Delegated (partial)** — `_inject_app_chrome`; `_restyle` keeps legend truncation, colorway, grids |
| Unit-bearing y-labels | #801 defaults names-only | yes | **Keep forwarding** `y_label_mapper` (#38 / §18 open) |
| `read_meta(path)` | #799 (post4) | yes | **Wrapper** `read_file_meta` (UI wiring deferred) |
| `instrument_meta_schema` | #800 (post4) | yes | **Wrapper** (ingest form follow-up) |
| `spread_plot` share_y | #817 | **yes** | Direct path delegated; **`_apply_share_y` still needed for the #816 merge path** → remove with #816 |
| Cycles facet strip labels | #820 | **yes** | **Delegated** — clean strips for free, no app code |
| ICA `direction` (line + both) | #821 | **yes** | **Ready to delegate** — drop `_filter_ica_by_direction`, pass `direction` to `collection.plot`; pairs with a "Both" UI option + export-direction decision |
| Group-avg all-or-nothing + merge | #816 | **no (merged)** | **Keep** partition/remap until post8 |
| Static figure bytes (kaleido) | #818 | **no (merged)** | **Keep** `export.figure_bytes` until post8 |
| `.h5` `auto_pick_cellpy_format` | #819 | **no (merged)** | **Keep** `auto_pick=False` (harmless defense) |
| Summary facet `category_orders` | §20 open, unfiled | n/a | **Keep forwarding** (#81) |
| Cycles plot `x_unit` vs collect mode | §17 open, unfiled | n/a | **Keep forwarding** (#72) |
| Non-atomic `.cellpy` writes | **#845 filed** | n/a | App stages project saves; single-file save still at cellpy's mercy |
| Selective summary rebuild | **#846 filed** | n/a | App full `make_summary()` after meta edits |

## Cleanup ready now (post7)

- **#820** — already delegated (nothing to remove).
- **#821 ICA** — the one removable workaround, but it changes export semantics
  (single- vs both-direction) and wants a "Both" UI option; do as its own issue.

## Blocked on cellpy post8 (merged, unreleased)

- **#816** group-avg partition + facet remap (`core/collect.py` merge path) and
  the `#47` `_apply_share_y` that serves it.
- **#818** in-memory figure export (`export.figure_bytes`).
- **#819** `load_raw` `auto_pick_cellpy_format=False`.

## Still app-owned (no upstream yet / by design)

- Discrete colorways + session figure-theme preference (#32)
- Legend truncation / right margin for long cell names
- Unit-bearing summary `y_label_mapper` (§18), cycles `x_unit` (§17),
  facet `category_orders` (§20) — all unfiled friction
- In-memory PNG/SVG/PDF export + desktop Save As
- Ingest form layout (until a follow-up consumes `instrument_meta_schema`)
