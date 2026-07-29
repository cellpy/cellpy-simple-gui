"""Core layer: pure-Python domain logic for cellpy-simple-gui.

Nothing in this package imports FastAPI or any web framework. The single point
of contact with cellpy is :mod:`cellpy_simple_gui.core.cellpy_adapter`; keeping
that boundary tight is what makes the app testable and what will contain any
future cellpy version bump to one module.
"""
