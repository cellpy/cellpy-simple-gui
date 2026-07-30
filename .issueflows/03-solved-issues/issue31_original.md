# Issue #31: Iterative fixes: export download location

Source: https://github.com/cellpy/cellpy-simple-gui/issues/31

## Original issue text

## Interactive `/iflow-fix` session

This issue tracks an interactive iterative-fix session. Individual fixes are recorded in the local status markdown under `.issueflows/` and landed together via `/iflow-close`.

### First reported bug

Figure/data export toast claims the file was saved to the downloads folder, but in the desktop (pywebview) shell the programmatic `<a download>` path often never lands there. Fix: native Save As when a webview window is present; honest toast wording (with path when known).
