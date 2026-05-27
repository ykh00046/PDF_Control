"""Backward-compat shim. Mixins now live in :mod:`app.handlers`.

Existing call sites such as ``from app.ui_handlers import FileHandlerMixin``
continue to work; new code should prefer :mod:`app.handlers`.

This shim will be removed after the next PDCA cycle confirms no external
callers rely on the legacy import path.
"""
from app.handlers import (  # noqa: F401
    DialogHandlerMixin,
    EditHandlerMixin,
    FileHandlerMixin,
    StateUpdateMixin,
)

__all__ = [
    "DialogHandlerMixin",
    "EditHandlerMixin",
    "FileHandlerMixin",
    "StateUpdateMixin",
]
