"""Toolbar construction for MainWindow.

One main toolbar (icon + caption under it, like Windows Photos / Acrobat's
light UI), reusing the QAction instances created by MenuBuilder so menu and
toolbar stay in lock-step (label, tooltip, shortcut, enabled state):

    [open][save] | [undo][redo] | [delete][replace] | [find]
    | [prev][page N / total][next] | [zoom in][zoom out][fit width]

Pre-condition: MenuBuilder.build() must run before ToolbarBuilder.build().
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QSizePolicy, QSpinBox, QWidget

from app.i18n import tr
from app.icons import icon

if TYPE_CHECKING:
    from app.ui import MainWindow

TOOLBAR_ICON_PX = 22


class ToolbarBuilder:
    """Builds the MainWindow toolbar and attaches widgets to the window."""

    def __init__(self, window: "MainWindow") -> None:
        self._win = window

    def build(self) -> None:
        win = self._win
        toolbar = win.addToolBar(tr("toolbar.edit"))
        toolbar.setObjectName("mainToolbar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setIconSize(QSize(TOOLBAR_ICON_PX, TOOLBAR_ICON_PX))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)

        # Document
        toolbar.addAction(win.open_action)
        toolbar.addAction(win.save_action)
        toolbar.addSeparator()

        # History
        toolbar.addAction(win.undo_action)
        toolbar.addAction(win.redo_action)
        toolbar.addSeparator()

        # Selection edits
        toolbar.addAction(win.delete_action)
        toolbar.addAction(win.replace_action)
        toolbar.addSeparator()

        # Find
        toolbar.addAction(win.find_action)
        toolbar.addSeparator()

        # Page navigation: prev | [page N / total] | next
        win.prev_page_action = toolbar.addAction(icon("prev"), tr("toolbar.prev_page"))
        win.prev_page_action.setToolTip(tr("toolbar.prev_page.tooltip"))
        win.prev_page_action.triggered.connect(win.viewer.prev_page)

        win.page_spinbox = QSpinBox()
        win.page_spinbox.setMinimum(1)
        win.page_spinbox.setMaximum(1)
        win.page_spinbox.setPrefix(tr("toolbar.page_prefix"))
        win.page_spinbox.setSuffix("")
        win.page_spinbox.setToolTip(tr("toolbar.page_goto.tooltip"))
        win.page_spinbox.setFixedWidth(120)
        win.page_spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        win.page_spinbox.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        win.page_spinbox.valueChanged.connect(win._on_page_spinbox_changed)
        toolbar.addWidget(win.page_spinbox)

        win.next_page_action = toolbar.addAction(icon("next"), tr("toolbar.next_page"))
        win.next_page_action.setToolTip(tr("toolbar.next_page.tooltip"))
        win.next_page_action.triggered.connect(win.viewer.next_page)

        # Push zoom controls to the right edge.
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        toolbar.addAction(win.zoom_out_action)
        toolbar.addAction(win.zoom_in_action)
        toolbar.addAction(win.fit_to_width_action)

        win._update_edit_action_states()  # Set initial states.
