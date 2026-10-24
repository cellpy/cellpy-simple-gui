# Plan — #174 open project: replace vs append

## Findings

- `projects.open_project()` calls `library.clear()` first, so opening a saved
  project silently **replaces** whatever is loaded (cellpy config switches to
  the opened project too). Nothing in the UI says so and there is no confirm.
- A batch journal (same "Open path" control) silently **appends**, and keeps
  the journal's own group numbers — so a second journal's group 1 lands in
  the already-used group 1 (the comment on the issue).
- The "Close" button already confirms before clearing; Open does not.

## Approach

One explicit **mode** for every open: `replace` (default) or `append`.

1. **Core** — `open_project(library, target, progress, mode="replace")`.
   `replace` clears first (as today). `append` keeps the loaded cells and
   project association and offsets the incoming group numbers by the highest
   group already in use (`Library.group_offset_for_append()`); group names
   (#187) move with their numbers. Appending into an empty library behaves
   like replace (the project becomes current).
2. **API** — `/api/projects/open` and `/api/projects/load-journal` accept
   `mode` (`OpenMode = Literal["replace", "append"]`, default `replace`).
   The journal job clears the library only once the journal yielded cells (a
   corrupt journal must not wipe the library). cellpy project config is only
   switched when the open actually replaces. Results carry `action`
   (`opened` / `appended`) and `n_cells`.
3. **UI** — Project panel gains an "Append to the loaded cells" checkbox
   (`openAppend`, shown once cells exist); the Open / Open path buttons read
   "Append" / "Append path" when it is on. Replacing a non-empty library asks
   for confirmation (mentions unsaved changes when dirty); appending does not.
   Toasts say "Opened …" vs "Appended … to the loaded cells". The panel hint
   explains both behaviours. Append marks the library dirty.
4. **Tests** — core (replace vs append, group offset, group names, empty
   library), API (`mode` for projects and journals, journal group offset),
   template/component drift tests; README + design doc updated.
