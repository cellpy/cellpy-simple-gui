# Issue #52: Deep-dive: bump cellpy post-release and delegate more app glue to cellpy

Source: https://github.com/cellpy/cellpy-simple-gui/issues/52

## Original issue text

## Problem / context

cellpy has a new **post-release** that implements more of the amendments we asked for (see `CELLPY_PAINPOINTS.md` and upstream work from building this app). We still carry a fair amount of app-side glue in `core/collect.py`, `core/cellpy_adapter.py`, `core/plotting.py`, and related UI/export paths — some of it may now be redundant.

Goal: **make app-making simple** — prefer cellpy’s public APIs over local workarounds. Every piece we can delete or thin is a win for this app and for future cellpy-based apps.

Current floor: `cellpy>=2.1.1.post2`. Bump to the latest post-release and re-audit.

## Spec

1. **Bump** — Raise the dependency to the new cellpy post-release; refresh `uv.lock`; smoke `uv run pytest` and a short GUI path (load demo → summary/cell plot → export).
2. **Inventory (read-only first)** — Walk app ↔ cellpy boundaries against `CELLPY_PAINPOINTS.md` and the new release notes / changelog. For each workaround or reimplementation, record: *keep* / *delegate now* / *delegate later (still missing upstream)* / *open or update upstream issue*.
   Focus areas at minimum:
   - `core/collect.py` (from_cells, group-avg partition + figure merge, `_restyle`, colorway, labels/hover if any)
   - `core/cellpy_adapter.py` (instruments, load_raw / `.h5` instrument passthrough, warning suppression)
   - `core/plotting.py` / export / figure bytes
   - Open related issues (#36–#41 and any newer plot/ingest gaps) where cellpy now covers them
3. **Delegate** — Implement the clear “delegate now” items in this issue (or a tight follow-up PR listed in the inventory): remove dead shims, prefer cellpy knobs (`y_label_mapper`, theme/templates, group-avg behaviour, figure export helpers, etc.) when they exist and are stable.
4. **Document** — Update `CELLPY_PAINPOINTS.md` status table for what the new post-release fixed; note remaining gaps. Short design note under `.issueflows/04-designs-and-guides/` listing what we now own vs what cellpy owns.
5. If the inventory is too large for one PR, keep this issue as the audit + bump + first cuts, and spawn follow-ups (or `/iflow-epic`) for the rest — do not block the bump on a full rewrite.

## Acceptance criteria

- [ ] App depends on the new cellpy post-release; lockfile updated; tests green.
- [ ] Written inventory of app glue vs cellpy APIs with keep/delegate-now/later decisions (in the issue status/plan or a design note).
- [ ] At least the unambiguous “delegate now” items are landed (or explicitly deferred with linked follow-up issues).
- [ ] `CELLPY_PAINPOINTS.md` reflects the new release; any new friction found during the dive is recorded.
- [ ] No expansion of hand-rolled science/plot logic where an equivalent cellpy API exists.

## Out of scope

- Rewriting the whole UI chrome / Alpine shell.
- Implementing large missing cellpy features ourselves (prefer upstream issues).
- Closing every open plot UX issue (#36–#40) unless the new release makes them trivial one-liners.
