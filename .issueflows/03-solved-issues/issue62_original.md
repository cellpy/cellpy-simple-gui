# Issue #62: Add checkbox for group vs individual Plotly legend muting on summary plots

Source: https://github.com/cellpy/cellpy-simple-gui/issues/62

## Original issue text

### Problem / context
cellpy’s collected summary Plotly path supports `group_legend_muting` (and related `group_cells`): when muting is on, a legend click toggles a whole journal group; when off, traces are muted per cell. The app never exposes these knobs, so users can’t choose group vs individual legend behaviour.

### Spec
- Add a Cycle summary control (checkbox), e.g. **Mute by group** (or clearer copy), wired through `SummaryPlotSpec` → `plotting.summary_figure` → `collect.figures_json` / `collection.plot` as `group_legend_muting=…`.
- Default should match cellpy’s default (`True` = mute by group), unless manual check shows the app currently behaves differently.
- When **Group avg** is on, cellpy forces `group_cells=False`; don’t invent conflicting UI — hide or disable the control if muting-by-group is meaningless for that path, or document the limitation.
- Optionally forward `group_cells` only if needed for muting to work; prefer the smallest knob that gives individual vs group legend select/deselect.
- Smoke-test with multi-group project data that legend clicks mute a group when on and a single series when off.

### Acceptance criteria
- [ ] Summary UI checkbox controls `group_legend_muting` end-to-end.
- [ ] With ≥2 cells in one group, legend click mutes the group when enabled and a single cell when disabled (Plotly).
- [ ] Group-avg path doesn’t break; control disabled/hidden or documented if N/A.
- [ ] `uv run --extra dev pytest` still passes (add a light assert that the kwarg is forwarded if easy).

### Out of scope
- Cell-explorer curve legend grouping
- Changing cellpy defaults upstream

## Comments (curated summary)

- **Additional tasks**:
  - Also expose the same control on the Cycles collector plot (not only Cycle summary).

_Note: this section is an interpretive summary of the comment thread, not a verbatim dump. Source comments: 1, last comment by @jepegit on 2026-08-01._
