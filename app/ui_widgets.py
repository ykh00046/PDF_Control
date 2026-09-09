"""Small reusable chrome widgets for the main window.

* :class:`DockTitleBar` -- replaces Qt's default dock title (tiny float/close
  glyphs) with a flat label + one close button in the theme's style.
* :class:`EmptyState` -- what the viewer shows before a document is open:
  an icon, a one-line hint and an "Open PDF" button, instead of a blank
  grey canvas.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.icons import icon
from app.theme import LIGHT_THEME


class DockTitleBar(QWidget):
    """Flat title row for a QDockWidget: bold label, close button."""

    def __init__(self, dock: QDockWidget, title: str) -> None:
        super().__init__(dock)
        self.setObjectName("dockTitle")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            LIGHT_THEME.space_md, LIGHT_THEME.space_xs, LIGHT_THEME.space_xs, LIGHT_THEME.space_xs
        )
        layout.setSpacing(LIGHT_THEME.space_xs)

        self.label = QLabel(title, self)
        self.label.setObjectName("dockTitleLabel")
        layout.addWidget(self.label, 1)

        self.close_button = QToolButton(self)
        self.close_button.setObjectName("dockClose")
        self.close_button.setAutoRaise(True)
        self.close_button.setIcon(icon("close", LIGHT_THEME.text_muted, 14))
        self.close_button.setToolTip(tr("dock.close.tooltip"))
        self.close_button.clicked.connect(dock.close)
        layout.addWidget(self.close_button)


def apply_dock_chrome(dock: QDockWidget, title: str) -> DockTitleBar:
    """Install the custom title bar and drop the floatable feature."""
    dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable)
    bar = DockTitleBar(dock, title)
    dock.setTitleBarWidget(bar)
    return bar


class EmptyState(QWidget):
    """Centered placeholder shown in the viewer area when nothing is open."""

    open_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("emptyState")
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QWidget(self)
        card.setObjectName("emptyStateCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(40, 36, 40, 36)
        layout.setSpacing(LIGHT_THEME.space_md)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        glyph = QLabel(card)
        glyph.setPixmap(icon("doc", LIGHT_THEME.accent, 56).pixmap(56, 56))
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(glyph)

        title = QLabel(tr("empty.title"), card)
        title.setObjectName("emptyStateTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        hint = QLabel(tr("empty.hint"), card)
        hint.setObjectName("emptyStateHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.open_button = QPushButton(tr("empty.open"), card)
        self.open_button.setIcon(icon("open", LIGHT_THEME.accent_text, 18))
        self.open_button.setDefault(True)
        self.open_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_button.clicked.connect(self.open_requested)
        layout.addWidget(self.open_button, 0, Qt.AlignmentFlag.AlignCenter)

        outer.addWidget(card)
