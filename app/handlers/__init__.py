"""Event handler mixins for :class:`app.ui.MainWindow`.

Four stateless mixins, each in its own module, supplying handler methods
to ``MainWindow`` through multiple inheritance:

* :class:`FileHandlerMixin`   — open / save / drag-drop / close
* :class:`EditHandlerMixin`   — undo / redo / delete / replace selection
* :class:`DialogHandlerMixin` — launch child dialogs and apply results
* :class:`StateUpdateMixin`   — react to controller / viewer signals

All state remains on ``MainWindow`` (``self.controller``, ``self.viewer``,
``self.config``, etc.); mixins carry no instance state of their own.
"""

from app.handlers.dialog_handlers import DialogHandlerMixin
from app.handlers.edit_handlers import EditHandlerMixin
from app.handlers.file_handlers import FileHandlerMixin
from app.handlers.state_handlers import StateUpdateMixin

__all__ = [
    "DialogHandlerMixin",
    "EditHandlerMixin",
    "FileHandlerMixin",
    "StateUpdateMixin",
]
