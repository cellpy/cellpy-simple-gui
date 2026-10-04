# Plan — #187 name of groups

## Findings

- `collect._batch` already hands cellpy a `group_labels` map, but it is always
  the default `"group <n>"`. cellpy (≥2.1.5) uses that label as the legend name
  of group-averaged traces and writes it into the `group_label` column of the
  collected summary frame.
- Ungrouped summary / `per_cycle` cycles traces carry `legendgroup="<group id>"`
  (and no `legendgrouptitle`), so a group name can be shown there as a Plotly
  legend-group title without touching cellpy.
- cellpy batch journals carry a `group_label` column (`journal_from_frame` →
  `write_journal` → `from_journal` round-trips it); the app currently reads
  only `group`.
- Project manifests (`project.json`) have no group-level section.

## Approach

Group names live on the `Library` (they are group-level, not cell-level):

1. **Core** — `Library._group_labels: dict[int, str]`, `set_group_label()`,
   `group_label()`, `group_labels()` (in-use groups only), `groups()` (id,
   custom label, effective name, cell count, colour). `all()` syncs a
   `CellRecord.group_label` snapshot so collectors need no extra plumbing;
   `CellRecord.group_name()` resolves "custom or `group <n>`". `clear()`
   forgets the names. `CellMeta.group_label` exposes the effective name.
2. **Plots** — `_batch` passes the effective names to `from_cells`; new
   `collect.group_titles(records)` + `figure_json(group_titles=…)` sets
   `legendgrouptitle` on ungrouped traces whose legendgroup is a named group
   (summary + cycles pane).
3. **API** — `_state()` gains `groups`; `POST /api/groups/{group}` with
   `{"label": …}` (empty clears) returns the state.
4. **Persistence** — `ProjectManifest.groups: [{id, label}]` (optional, so old
   manifests still open); saved from `library.group_labels()`, restored on
   open. Journals: `cellpy_adapter.load_journal()` returns cells + group labels
   read from the `group_label` column (skipping the `group <n>` defaults);
   `load_journal_cells()` stays as a thin wrapper; the journal job applies them.
5. **UI** — a *Groups* strip in the Manage cells modal (swatch, id, name input
   with `group <n>` placeholder, cell count); renaming goes through the
   deferred-replot path (#184). Sidebar group inputs show the name as a
   tooltip. All state writes go through one `_applyState()` helper.
6. **Tests** — core (batch labels in grouped legend, legend-group titles),
   projects (round trip + legacy manifest), journal (`group_label` read), API
   (endpoint + state), plus template/component drift tests already in place.
