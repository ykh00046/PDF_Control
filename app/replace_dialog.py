"""Replace-selection dialog (natural-replace + live preview).

Replaces the bare ``QInputDialog.getText`` prompt with a small form:

* the replacement text (multi-line capable),
* alignment: auto / left / center / right (auto keeps table figures on
  their right edge and prose on the left),
* word-wrap policy for long text (wrap vs. shrink),
* optional fixed font size (0 = keep the source size),
* a live preview of the page region with the candidate applied
  (debounced; rendered by :mod:`app.replace_preview`).

The dialog returns plain values; the handler builds the ``RedactReplace``.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QKeyEvent, QPixmap
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
from app.logger import get_logger
from app.operations.redact import ALIGN_AUTO, ALIGN_CENTER, ALIGN_LEFT, ALIGN_RIGHT
from app.replace_preview import PreviewContext, render_replacement_preview
from app.theme import LIGHT_THEME, label_style

_ALIGN_ORDER = (ALIGN_AUTO, ALIGN_LEFT, ALIGN_CENTER, ALIGN_RIGHT)
PREVIEW_DEBOUNCE_MS = 250
PREVIEW_MAX_WIDTH = 520

# Resolves the font file for a candidate replacement text (glyph coverage
# depends on the text, e.g. Hangul needs a Korean font).
FontResolver = Callable[[str], Optional[str]]


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

    def __init__(
        self,
        existing_text: str,
        parent: Optional[QWidget] = None,
        preview: Optional[PreviewContext] = None,
        font_resolver: Optional[FontResolver] = None,
    ) -> None:
        super().__init__(parent)
        self._preview_ctx = preview
        self._font_resolver = font_resolver
        self.setWindowTitle(tr("dialog.replace.title"))
        self.setMinimumWidth(460)

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

        # --- live preview -------------------------------------------------
        self.preview_title = QLabel(tr("dialog.replace.preview"), self)
        self.preview_title.setStyleSheet(label_style(LIGHT_THEME, "muted"))
        self.preview_label = QLabel(self)
        self.preview_label.setObjectName("replacePreview")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(64)
        self.preview_label.setStyleSheet(
            f"background: {LIGHT_THEME.bg_surface}; border: 1px solid {LIGHT_THEME.border}; "
            f"border-radius: {LIGHT_THEME.radius}px; padding: {LIGHT_THEME.space_xs}px;"
        )
        layout.addWidget(self.preview_title)
        layout.addWidget(self.preview_label)
        has_preview = preview is not None
        self.preview_title.setVisible(has_preview)
        self.preview_label.setVisible(has_preview)

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(PREVIEW_DEBOUNCE_MS)
        self._preview_timer.timeout.connect(self.refresh_preview)
        self.text_edit.textChanged.connect(self._schedule_preview)
        self.align_combo.currentIndexChanged.connect(self._schedule_preview)
        self.size_spin.valueChanged.connect(self._schedule_preview)
        self.wrap_checkbox.toggled.connect(self._schedule_preview)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("dialog.replace.ok"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("dialog.replace.cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.text_edit.setFocus()
        if has_preview:
            self.refresh_preview()

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

    # --------------------------------------------------------------- preview
    def _schedule_preview(self, *_args: Any) -> None:
        if self._preview_ctx is not None:
            self._preview_timer.start()

    def refresh_preview(self) -> bool:
        """Render the preview now (also used by tests). Returns success."""
        self._preview_timer.stop()
        ctx = self._preview_ctx
        if ctx is None:
            return False
        settings = self.settings()
        if self._font_resolver is not None:
            try:
                ctx.fontfile = self._font_resolver(settings["text"])
            except Exception as exc:  # never let a font lookup kill the preview
                get_logger().debug(f"Preview font resolve failed: {exc}")
        try:
            pix, _text = render_replacement_preview(ctx, settings)
        except Exception as exc:
            get_logger().warning(f"Replace preview failed: {exc}")
            self.preview_label.setText(tr("dialog.replace.preview.failed"))
            return False
        fmt = QImage.Format.Format_RGBA8888 if pix.alpha else QImage.Format.Format_RGB888
        image = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt).copy()
        pixmap = QPixmap.fromImage(image)
        if pixmap.width() > PREVIEW_MAX_WIDTH:
            pixmap = pixmap.scaledToWidth(PREVIEW_MAX_WIDTH, Qt.TransformationMode.SmoothTransformation)
        self.preview_label.setPixmap(pixmap)
        return True

    @classmethod
    def prompt(
        cls,
        existing_text: str,
        parent: Optional[QWidget] = None,
        preview: Optional[PreviewContext] = None,
        font_resolver: Optional[FontResolver] = None,
    ) -> Optional[Dict[str, Any]]:
        """Modal helper: returns the settings dict, or None when cancelled."""
        dialog = cls(existing_text, parent, preview=preview, font_resolver=font_resolver)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.settings()
