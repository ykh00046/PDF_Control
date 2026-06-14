"""Text export dialog for :class:`app.ui.MainWindow`.

Lets the user pick a scope (whole document or current page) and an output
format (plain text or Markdown), then emits :attr:`export_confirmed` with the
chosen settings. The actual file-save dialog and writing are handled by the
caller (``DialogHandlerMixin.apply_text_export``), mirroring the crop/remove
dialog convention.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr


class TextExportDialog(QDialog):
    """Collects text-export options (scope + format)."""

    # Emits a settings dict:
    #   {"scope": "all"|"current"|"range", "fmt": "txt"|"md", "range": str}
    export_confirmed = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("text_export.title"))
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Scope: whole document / current page / explicit page range.
        self.scope_all = QRadioButton(tr("text_export.scope.all"))
        self.scope_current = QRadioButton(tr("text_export.scope.current"))
        self.scope_range = QRadioButton(tr("text_export.scope.range"))
        self.scope_all.setChecked(True)
        self._scope_group = QButtonGroup(self)
        self._scope_group.addButton(self.scope_all)
        self._scope_group.addButton(self.scope_current)
        self._scope_group.addButton(self.scope_range)

        self.range_edit = QLineEdit()
        self.range_edit.setPlaceholderText(tr("text_export.range.placeholder"))
        self.range_edit.setEnabled(False)
        self.scope_range.toggled.connect(self.range_edit.setEnabled)

        range_row = QHBoxLayout()
        range_row.addWidget(self.scope_range)
        range_row.addWidget(self.range_edit)

        scope_box = QVBoxLayout()
        scope_box.addWidget(self.scope_all)
        scope_box.addWidget(self.scope_current)
        scope_box.addLayout(range_row)
        scope_container = QWidget()
        scope_container.setLayout(scope_box)
        form.addRow(tr("text_export.scope.label"), scope_container)

        # Format: txt vs. md.
        self.format_combo = QComboBox()
        self.format_combo.addItem(tr("text_export.format.txt"), "txt")
        self.format_combo.addItem(tr("text_export.format.md"), "md")
        form.addRow(tr("text_export.format.label"), self.format_combo)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.button(QDialogButtonBox.Ok).setText(tr("text_export.button.export"))
        buttons.button(QDialogButtonBox.Cancel).setText(tr("text_export.button.cancel"))
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_settings(self) -> dict:
        """Return the currently selected export settings.

        ``scope`` is "all" | "current" | "range"; ``range`` carries the raw
        page-range spec (only meaningful when scope == "range").
        """
        if self.scope_all.isChecked():
            scope = "all"
        elif self.scope_range.isChecked():
            scope = "range"
        else:
            scope = "current"
        return {
            "scope": scope,
            "fmt": self.format_combo.currentData(),
            "range": self.range_edit.text(),
        }

    def _on_accept(self) -> None:
        self.export_confirmed.emit(self.get_settings())
        self.accept()
