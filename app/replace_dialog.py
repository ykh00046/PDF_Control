"""Replace-selection dialog (natural-replace).

Replaces the bare ``QInputDialog.getText`` prompt with a small form:

* the replacement text (multi-line capable),
* alignment: auto / left / center / right (auto keeps table figures on
  their right edge and prose on the left),
* word-wrap policy for long text (wrap vs. shrink),
* optional fixed font size (0 = keep the source size).

The dialog returns plain values; the handler builds the ``RedactReplace``.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.operations.redact import ALIGN_AUTO, ALIGN_CENTER, ALIGN_LEFT, ALIGN_RIGHT
from app.theme import LIGHT_THEME, label_style

_ALIGN_ORDER = (ALIGN_AUTO, ALIGN_LEFT, ALIGN_CENTER, ALIGN_RIGHT)


class _ReplacementEdit(QPlainTextEdit):
    """Enter accepts, Shift+Enter inserts a line break."""

    def __init__(self, dialog: "ReplaceTextDialog") -> None:
        super().__init__(dialog)
        self._dialog = dialog

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.insertPlainText("\n")
            else:
                self._dialog.accept()
            event.accept()
            return
        super().keyPressEvent(event)


class ReplaceTextDialog(QDialog):
    """Ask for replacement text + layout options for the current selection."""

    def __init__(self, existing_text: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("dialog.replace.title"))
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setSpacing(LIGHT_THEME.space_sm)

        layout.addWidget(QLabel(tr("dialog.replace.prompt"), self))
        self.text_edit = _ReplacementEdit(self)
        self.text_edit.setPlainText(existing_text)
        self.text_edit.setFixedHeight(72)
        self.text_edit.selectAll()
        layout.addWidget(self.text_edit)

        hint = QLabel(tr("dialog.replace.hint"), self)
        hint.setStyleSheet(label_style(LIGHT_THEME, "muted"))
        hint.setWordWrap(True)
        layout.addWidget(hint)

        form = QFormLayout()
        form.setHorizontalSpacing(LIGHT_THEME.space_md)
        self.align_combo = QComboBox(self)
        for value, key in zip(
            _ALIGN_ORDER,
            (
                "dialog.replace.align.auto",
                "dialog.replace.align.left",
                "dialog.replace.align.center",
                "dialog.replace.align.right",
            ),
        ):
            self.align_combo.addItem(tr(key), value)
        form.addRow(tr("dialog.replace.align"), self.align_combo)

        size_row = QHBoxLayout()
        self.size_spin = QDoubleSpinBox(self)
        self.size_spin.setRange(0.0, 200.0)
        self.size_spin.setDecimals(1)
        self.size_spin.setSingleStep(0.5)
        self.size_spin.setSpecialValueText(tr("dialog.replace.size.auto"))
        self.size_spin.setSuffix(" pt")
        self.size_spin.setValue(0.0)
        size_row.addWidget(self.size_spin)
        size_row.addStretch()
        form.addRow(tr("dialog.replace.size"), size_row)
        layout.addLayout(form)

        self.wrap_checkbox = QCheckBox(tr("batch.use_wrap"), self)
        self.wrap_checkbox.setToolTip(tr("batch.use_wrap.tooltip"))
        self.wrap_checkbox.setChecked(True)
        layout.addWidget(self.wrap_checkbox)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("dialog.replace.ok"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("dialog.replace.cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.text_edit.setFocus()

    # ---------------------------------------------------------------- values
    def replacement_text(self) -> str:
        return self.text_edit.toPlainText()

    def settings(self) -> Dict[str, Any]:
        return {
            "text": self.replacement_text(),
            "align": self.align_combo.currentData(),
            "wrap": self.wrap_checkbox.isChecked(),
            "fontsize": float(self.size_spin.value()),
        }

    @classmethod
    def prompt(cls, existing_text: str, parent: Optional[QWidget] = None) -> Optional[Dict[str, Any]]:
        """Modal helper: returns the settings dict, or None when cancelled."""
        dialog = cls(existing_text, parent)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.settings()
