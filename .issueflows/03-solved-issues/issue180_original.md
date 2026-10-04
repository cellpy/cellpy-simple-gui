# Issue #180: make smarter caching

Source: https://github.com/cellpy/cellpy-simple-gui/issues/180

## Original issue text

The plots seem to be recalculated from scratch when for example switching from one tab to another. Or changing colors. It would be great it we could utilize caching to speed up things. The caching have to respect 100% that when we change the actual data, the plots do not contain any stale data.
