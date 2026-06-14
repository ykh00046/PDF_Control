"""Toolbar construction for MainWindow.

Builds the edit toolbar (delete/replace/undo/redo/page nav/spinbox) and the
zoom toolbar. Reuses the QAction instances created by MenuBuilder so menu
and toolbar stay in lock-step.

Pre-condition: MenuBuilder.build() must run before ToolbarBuilder.build()
because the toolbar reuses ``undo_action``, ``redo_action``,
``zoom_in_action``, ``zoom_out_action``, ``fit_to_width_action``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QSpinBox

from app.i18n import tr

if TYPE_CHECKING:
    from app.ui import MainWindow


class ToolbarBuilder:
    """Builds the MainWindow toolbars and attaches actions to the window."""

    def __init__(self, window: "MainWindow") -> None:
        self._win = window

    def build(self) -> None:
        win = self._win
        toolbar = win.addToolBar(tr("toolbar.edit"))

        win.delete_action = QAction(tr("toolbar.delete"), win)
        win.delete_action.setToolTip(tr("toolbar.delete.tooltip"))
        win.delete_action.triggered.connect(win.delete_selection)
        toolbar.addAction(win.delete_action)

        win.replace_action = QAction(tr("toolbar.replace"), win)
        win.replace_action.setToolTip(tr("toolbar.replace.tooltip"))
        win.replace_action.triggered.connect(win.replace_selection)
        toolbar.addAction(win.replace_action)

        toolbar.addSeparator()

        # Reuse undo/redo actions from menu to maintain state synchronization.
        toolbar.addAction(win.undo_action)
        toolbar.addAction(win.redo_action)

        toolbar.addSeparator()

        win.prev_page_action = QAction(tr("toolbar.prev_page"), win)
        win.prev_page_action.triggered.connect(win.viewer.prev_page)
        toolbar.addAction(win.prev_page_action)

        # Page jump (GoTo) SpinBox.
        win.page_spinbox = QSpinBox()
        win.page_spinbox.setMinimum(1)
        win.page_spinbox.setMaximum(1)
        win.page_spinbox.setPrefix(tr("toolbar.page_prefix"))
        win.page_spinbox.setSuffix("")
        win.page_spinbox.setToolTip(tr("toolbar.page_goto.tooltip"))
        win.page_spinbox.setFixedWidth(100)
        win.page_spinbox.valueChanged.connect(win._on_page_spinbox_changed)
        toolbar.addWidget(win.page_spinbox)

        win.next_page_action = QAction(tr("toolbar.next_page"), win)
        win.next_page_action.triggered.connect(win.viewer.next_page)
        toolbar.addAction(win.next_page_action)

        zoom_toolbar = win.addToolBar(tr("toolbar.zoom"))
        zoom_toolbar.addAction(win.zoom_in_action)
        zoom_toolbar.addAction(win.zoom_out_action)
        zoom_toolbar.addAction(win.fit_to_width_action)

        win._update_edit_action_states()  # Set initial states.
