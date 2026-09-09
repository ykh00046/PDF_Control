"""Inline "Find" bar shown under the viewer (Ctrl+F).

A thin widget: query field, case-sensitivity toggle, previous/next buttons,
a "current / total" counter and a close button. It owns no search state --
it only emits signals; :class:`app.handlers.search_handlers.SearchHandlerMixin`
runs the search against the session and drives the viewer highlights.

Typing re-runs the search after a short debounce so results update live
without a worker per keystroke. Enter steps to the next hit, Shift+Enter
to the previous one, Escape closes the bar.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QToolButton,
    QWidget,
)

from app.i18n import tr
from app.icons import icon

SEARCH_DEBOUNCE_MS = 250


class FindBar(QWidget):
    """Search input row for the main window."""

    search_requested = Signal(str, bool)  # query, case_sensitive
    next_requested = Signal()
    prev_requested = Signal()
    closed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("findBar")

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(SEARCH_DEBOUNCE_MS)
        self._debounce.timeout.connect(self._emit_search)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)

        layout.addWidget(QLabel(tr("find.label")))

        self.query_edit = QLineEdit(self)
        self.query_edit.setPlaceholderText(tr("find.placeholder"))
        self.query_edit.setClearButtonEnabled(True)
        self.query_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.query_edit, 1)

        self.case_checkbox = QCheckBox(tr("find.case_sensitive"), self)
        self.case_checkbox.toggled.connect(lambda _checked: self._emit_search())
        layout.addWidget(self.case_checkbox)

        self.prev_button = QToolButton(self)
        self.prev_button.setIcon(icon("up", size=16))
        self.prev_button.setToolTip(tr("find.prev.tooltip"))
        self.prev_button.clicked.connect(self.prev_requested)
        layout.addWidget(self.prev_button)

        self.next_button = QToolButton(self)
        self.next_button.setIcon(icon("down", size=16))
        self.next_button.setToolTip(tr("find.next.tooltip"))
        self.next_button.clicked.connect(self.next_requested)
        layout.addWidget(self.next_button)

        self.count_label = QLabel("", self)
        self.count_label.setMinimumWidth(80)
        layout.addWidget(self.count_label)

        self.close_button = QToolButton(self)
        self.close_button.setIcon(icon("close", size=16))
        self.close_button.setAutoRaise(True)
        self.close_button.setToolTip(tr("find.close.tooltip"))
        self.close_button.clicked.connect(self.close_bar)
        layout.addWidget(self.close_button)

        self.set_result_count(-1, 0)

    # ---------------------------------------------------------------- state
    def query(self) -> str:
        return self.query_edit.text()

    def case_sensitive(self) -> bool:
        return self.case_checkbox.isChecked()

    def focus_query(self) -> None:
        self.query_edit.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.query_edit.selectAll()

    def set_result_count(self, current: int, total: int) -> None:
        """Update the counter; ``current`` is 0-based, -1 when nothing is selected."""
        if total <= 0:
            self.count_label.setText(tr("find.no_results") if self.query().strip() else "")
        else:
            self.count_label.setText(tr("find.count", current + 1 if current >= 0 else 0, total))
        has_hits = total > 0
        self.prev_button.setEnabled(has_hits)
        self.next_button.setEnabled(has_hits)

    def close_bar(self) -> None:
        self._debounce.stop()
        self.hide()
        self.closed.emit()

    # ------------------------------------------------------------- internals
    def _on_text_changed(self, _text: str) -> None:
        self._debounce.start()

    def _emit_search(self) -> None:
        self._debounce.stop()
        self.search_requested.emit(self.query(), self.case_sensitive())

    def flush_pending_search(self) -> None:
        """Run a pending debounced search immediately (tests, Enter key)."""
        if self._debounce.isActive():
            self._emit_search()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._debounce.isActive():
                self._emit_search()
            elif event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.prev_requested.emit()
            else:
                self.next_requested.emit()
            event.accept()
            return
        if key == Qt.Key.Key_Escape:
            self.close_bar()
            event.accept()
            return
        super().keyPressEvent(event)
