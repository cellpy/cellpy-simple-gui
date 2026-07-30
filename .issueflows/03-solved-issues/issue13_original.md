# Issue #13: add workflows

Source: https://github.com/cellpy/cellpy-simple-gui/issues/13

## Original issue text

- Go through tests and mark the critical ones "essential".
- Add a GitHub Action workflow that runs the tests (pytest, only tests marked "essential") when code changes
- Add a GitHub Action workflow "document mock flow" with the same name that runs when no code is changed (to prevent "stale" PR checks).
