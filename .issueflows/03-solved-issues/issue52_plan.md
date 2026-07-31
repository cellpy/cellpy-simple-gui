# Issue #52 — Plan: bump cellpy post4 + delegate app glue

## Goal

Bump to **cellpy ≥ 2.1.1.post4**, inventory remaining app-side workarounds against
what post3/post4 shipped, and land the clear “delegate now” cuts so future apps
need less private glue.

## Constraints

- cellpy boundary stays: only `core/cellpy_adapter.py` and `core/collect.py`
  import cellpy (`this-project.md`).
- Prefer public cellpy APIs; do not reimplement science/plot logic.
- Do not block the bump on a full rewrite — inventory + first cuts in this PR;
  spawn follow-ups / `/iflow-epic` for large leftovers.
- Keep #32 appearance UX (theme/colorway UI) working; migrate chrome knobs to
  cellpy where they exist, keep app-only pieces (discrete colorways, legend
  truncation) local.
- No UI chrome rewrite; no inventing missing cellpy features.

### Prior art

- `CELLPY_PAINPOINTS.md` — source inventory of wishes; update status for
  post3/post4 (#786 quiet instruments, #801 figure hooks, #799 `read_meta`,
  #800 `instrument_meta_schema`, #804 y-ranges already in post2).
- `collect._restyle` / `_apply_colorway` / `partition_by_group_size` /
  `figures_json` — [`core/collect.py`](../../../src/cellpy_simple_gui/core/collect.py)
  — **migrate** layout/labels/height toward `Collection.plot` knobs; **keep**
  colorway + legend shorten + mixed group-avg merge for now.
- `cellpy_adapter.list_instruments` log-level / warning brackets —
  [`core/cellpy_adapter.py`](../../../src/cellpy_simple_gui/core/cellpy_adapter.py)
  — **thin** after post3 quiet contract.
- `export.figure_bytes` / kaleido — [`core/export.py`](../../../src/cellpy_simple_gui/core/export.py)
  — **keep** until cellpy has in-memory `to_image` (painpoint §13 still open).
- Design notes: `plot-appearance.md`, `group-average-and-figure-export.md`,
  `summary-independent-y-scales.md` — cite when deciding keep vs migrate.
- Toolbox: none. Graph: collect/partition community hubs confirm touch points.

## Approach

Phased single PR (audit + bump + first cuts). Stop after inventory if something
is ambiguous — prefer a linked follow-up over a risky rewrite.

### Phase A — bump + smoke

1. Set `cellpy>=2.1.1.post4` in `pyproject.toml`, `uv lock` / sync.
2. `uv run pytest`; fix only breakages caused by the bump.
3. Note installed version via `cellpy_adapter.cellpy_version()` if useful in
   `/api`/capabilities (optional, skip if not already exposed).

### Phase B — written inventory

Produce `.issueflows/04-designs-and-guides/cellpy-delegation-inventory.md`
(and refresh the status table in `CELLPY_PAINPOINTS.md`) with decisions:

| Area | post3/post4 status | Decision (expected) |
|------|--------------------|---------------------|
| `list_instruments` WARNING spam (§5 / #786) | Fixed post3 | **Delegate now** — drop/relax adapter log silencing |
| Collected figure theme/label/height (§11 / #801) | `plotly_template=`, `layout_updates=`, pretty facet labels, `y_label_mapper=`, `height_per_panel=` | **Delegate now** — pass knobs from `_restyle` path / plot kwargs; shrink private layout work |
| Pretty axis / facet labels (#38) | Default pretty labels + mapper | **Delegate now** (partial) — stop relying only on `_tidy_facet_annotations`; use cellpy labels |
| Per-panel `y_ranges` / `share_y` (§12 / #804) | post2 | Already forwarded; verify still correct on post4 |
| `read_meta(path)` (§9 / #799) | New | **Delegate now** if we have a list/peek path; else thin adapter wrapper + follow-up to wire UI |
| `instrument_meta_schema` (§10 / #800) | New | **Delegate later / small cut** — adapter wrapper + optional ingest form trim if low-risk; else follow-up issue |
| Group-avg all-or-nothing + figure merge (§3 / #39) | Still app partition + remap | **Keep** / follow-up unless post4 changed behaviour (verify) |
| Colorways / session theme UI (#32) | Not upstream | **Keep** app `_apply_colorway` + theme tokens; map tokens into `layout_updates` / template where clean |
| Static figure bytes (§13) | Still open | **Keep** kaleido `figure_bytes` |
| `.h5` auto_pick (§14 / #41) | Workaround in `load_raw` | **Keep** `auto_pick_cellpy_format=False` until upstream changes |

### Phase C — implement “delegate now”

1. **Instruments** — Remove obsolete WARNING suppression around
   `list_instruments` if post3 makes it quiet; keep only what’s still needed
   for unrelated DeprecationWarnings.
2. **Figure hooks** — Thread `plotly_template` / `layout_updates` /
   `height_per_panel` (and `y_label_mapper` when we have one) through
   `figure_json` / `figures_json` / `plotting.*_figure`. Prefer building
   `layout_updates` from existing theme tokens instead of duplicating
   `update_layout` in `_restyle`. Keep legend truncation + colorway after plot.
3. **Labels** — Drop or narrow `_tidy_facet_annotations` once cellpy’s default
   pretty labels cover `variable=…` strips; add a small test that a human-ish
   axis/facet string appears (ties #38 lightly without requiring full issue close).
4. **`read_meta` / schema** — Add thin adapter wrappers
   (`cellpy_adapter.read_file_meta`, `instrument_meta_schema`). Wire into ingest
   **only** if a small, obvious win (e.g. hide unused fields); otherwise document
   and open/link a follow-up issue.
5. **Verify** group-avg partition still required on post4; if cellpy now averages
   multi groups and leaves singletons, delete partition — else leave + note.

### Phase D — docs

- Update `CELLPY_PAINPOINTS.md` status table for #786/#799/#800/#801.
- Update `this-project.md` cellpy floor to `≥2.1.1.post4`.
- Inventory design note (Phase B) is the durable “what we own vs cellpy” record.

## Files to touch

| Path | Change |
|------|--------|
| `pyproject.toml` / `uv.lock` | `cellpy>=2.1.1.post4` |
| `src/cellpy_simple_gui/core/collect.py` | Pass #801 knobs; thin `_restyle` / facet tidy |
| `src/cellpy_simple_gui/core/plotting.py` | Forward appearance → cellpy plot kwargs |
| `src/cellpy_simple_gui/core/cellpy_adapter.py` | Quiet instruments cleanup; optional `read_meta` / schema wrappers |
| `tests/test_core.py` (and/or adapter tests) | Theme/label path still green; new assert for pretty label / layout hook |
| `CELLPY_PAINPOINTS.md` | Status refresh |
| `.issueflows/04-designs-and-guides/this-project.md` | Version floor |
| `.issueflows/04-designs-and-guides/cellpy-delegation-inventory.md` | **New** inventory |
| `.issueflows/04-designs-and-guides/plot-appearance.md` | Note migration to cellpy layout hooks |

Likely **not** in this PR unless trivial: ingest UI rewrite, #39 facet merge,
#37 spread opacity, #36 chart-card CSS, #40 hover, #41 beyond existing workaround.

## Test strategy

- `uv run pytest` from repo root.
- Add/adjust structural tests: dark/light still sets paper bg (via
  `layout_updates` or restyle); at least one summary figure shows a non–snake_case
  y title / facet label under post4 defaults.
- No pixel asserts; no network-dependent Arbin SQL fixtures required here.

## Open questions

1. **Ingest schema in this PR?** Recommend **wrapper + inventory note only**
   (follow-up issue to drive the form from `instrument_meta_schema`). Or wire a
   minimal “hide unused fields” pass now?
2. **How thin should `_restyle` get?** Recommend **layout/fonts/bg via
   `layout_updates`**, keep legend truncation + colorway local. OK?
3. **Scope if group-avg still all-or-nothing?** Recommend **leave partition**;
   do not expand #39 here. Confirm.
4. **Target version** — PyPI latest is **2.1.1.post4**. Pin
   `>=2.1.1.post4` (not post3-only). Confirm.
