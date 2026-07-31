# Issue #56 — Plan: single-cell dQ/dV in Cell explorer

## Goal

Add a **dQ/dV (ICA)** plot option to Cell explorer with a resolution widget and
charge/discharge direction, wired through cellpy’s `collect_ica` / `ica` family.

## Constraints

- cellpy boundary: only `core/collect.py` (+ adapter) import cellpy.
- Prefer `collect_ica` + `IcaOptions` + `Collection.plot(family_kind="ica")` over
  hand-rolled `dqdv` frames.
- Cell explorer stays **one cell**; multi-cell ICA is out of scope.
- **dV/dQ (dva)** deferred.
- No “both directions on one figure” — cellpy `ica_plotter` only accepts
  `charge` | `discharge` (see CELLPY_PAINPOINTS §16 to add).
- Reuse chart-row / sidepane chrome (`plot-sidepane.md`).

### Prior art

- Cell explorer: `CyclesPlotSpec` + `POST /api/plots/cycles` + sidepane
  from/to / maxCurves / mode / method
  ([`plotting.py`](../../../src/cellpy_simple_gui/core/plotting.py),
  [`app.js`](../../../src/cellpy_simple_gui/web/static/js/app.js)).
- cellpy: `collect_ica(batch, IcaOptions(cycles=, voltage_resolution=))`,
  family `ica`; plot kwarg `direction="charge"|"discharge"`.
- `utils.ica.dqdv` supports `direction="both"` at collect time; plotter does not.
- Toolbox: none.

### Grill decisions (locked)

| # | Decision |
|---|----------|
| Q1 | Plot-kind toggle in Cell explorer (`Voltage curves` \| `dQ/dV`) |
| Q2 | Sidepane: resolution + direction; hide mode/method when dQ/dV |
| Q3 | Direction: `charge` \| `discharge` only (default **charge**) |
| Q4 | `voltage_resolution` number input, default **`0.005`** |
| Q5 | New `IcaPlotSpec` + `POST /api/plots/ica` (+ export) |
| Q6 | Export menu follows active plot kind |
| Q7 | Default plot kind = **voltage curves** |

## Approach

1. **Model** — `IcaPlotSpec`: `cell_id`, `cycles`, `voltage_resolution: float = 0.005`,
   `direction: Literal["charge","discharge"] = "charge"`, theme/color fields.
2. **Core** — `collect.ica_collection(records, …)` wrapping `collect_ica` +
   `IcaOptions`; `plotting.ica_figure(record, spec)` →
   `figure_json(..., family_kind="ica", layout="per_cell", direction=spec.direction)`.
3. **API** — `POST /api/plots/ica`, `POST /api/export/ica` (data + kaleido figures),
   resolve `cell_id` like cycles explorer.
4. **UI** — Cell explorer sidepane: **Plot** select (`curves` / `dqdv`); when
   `dqdv`: show resolution + direction, hide mode/method; `plotCell()` routes to
   cycles vs ica endpoint; export uses matching spec.
5. **Pain point** — Append **§16** to `CELLPY_PAINPOINTS.md`: ICA plotter cannot
   render `both` (only charge/discharge); apps cannot offer honest overlay
   without merging figures.
6. **Design note** — Update `plot-sidepane.md` Cell explorer pane bullets.
7. **Tests** — Core: ICA figure ≥1 trace for demo cell with resolution 0.005 +
   charge; empty cycles empty-figure. API: load example → `POST /api/plots/ica`.

## Files to touch

| Path | Change |
|------|--------|
| `src/cellpy_simple_gui/core/models.py` | `IcaPlotSpec` |
| `src/cellpy_simple_gui/core/collect.py` | `ica_collection` |
| `src/cellpy_simple_gui/core/plotting.py` | `ica_figure` |
| `src/cellpy_simple_gui/core/export.py` | ICA data/figure export |
| `src/cellpy_simple_gui/api/routers/plots.py` | `POST /plots/ica` |
| `src/cellpy_simple_gui/api/routers/export.py` | `POST /export/ica` |
| `src/cellpy_simple_gui/web/templates/index.html` | Plot kind + ICA widgets |
| `src/cellpy_simple_gui/web/static/js/app.js` | State, plot/export routing |
| `tests/test_core.py`, `tests/test_api.py` | ICA coverage |
| `CELLPY_PAINPOINTS.md` | §16 ICA direction/`both` gap |
| `.issueflows/04-designs-and-guides/plot-sidepane.md` | Explorer dQ/dV knobs |

## Test strategy

```bash
uv run pytest
```

## Open questions

_None — resolved in grill-me._
