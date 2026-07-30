# Issue #19: stale loading of cellpy batch journal

Source: https://github.com/cellpy/cellpy-simple-gui/issues/19

## Original issue text

Tried loading a cellpy batch journal (that probably is corrupt?) and the spinner just spins and nothing else is happening. Most likely there was an exception raised by cellpy, but never handled by cellpy-simple-gui. Propose surfacing the exception(s) and messaging to user.
