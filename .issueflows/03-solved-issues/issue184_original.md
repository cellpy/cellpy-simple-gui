# #184 — update plots when cells modal closes

URL: https://github.com/cellpy/cellpy-simple-gui/issues/184

It is not needed to update the plots immediately when we change a value on the
cells modal. Also, the updates seem to be in a queue and then done one-by-one,
so that the figures keeps updating long after modal is closed. Either only
update when modal closes, or figure out a better way to prevent updates to
happen long after modal is closed.
