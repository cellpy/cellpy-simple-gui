# Issue #174 — Unclear what happens when opening a new project while already having a project loaded

Source: https://github.com/cellpy/cellpy-simple-gui/issues/174

It is unclear what happens. Does it add it to current? If not, does it properly
clean up previous project? Best would be to have option "append" in addition so
that it is clear that the new project is appended, while if not pressing
"append" it cleans away the old and loads the new.

## Comment

Also noted another thing when opening a new project when already having cells /
project. The group number for the new groups start with one. It should instead
start with a number that is not used by the already existing groups from the
first project.
