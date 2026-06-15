"""Watermark options dialog.

Collects text + style (font size, color, opacity, angle) and scope
(current vs all pages), emitting a settings dict for the handler to turn
into WatermarkText operations.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
)

from app.i18n import tr
from app.logger import get_logger


class WatermarkDialog(QDialog):
    """Configure a text watermark (text, size, color, opacity, angle, scope)."""

    watermark_confirmed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = (0.5, 0.5, 0.5)  # default grey, RGB 0-1
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle(tr("watermark.dialog.title"))
        self.setModal(True)
        layout = QVBoxLayout(self)

        # Text
        layout.addWidget(QLabel(tr("watermark.label.text")))
        self.text_edit = QLineEdit()
        layout.addWidget(self.text_edit)

        # Font size
        size_row = QHBoxLayout()
        size_row.addWidget(QLabel(tr("watermark.label.fontsize")))
        self.size_spin = QSpinBox()
        self.size_spin.setRange(6, 300)
        self.size_spin.setValue(40)
        size_row.addWidget(self.size_spin)
        layout.addLayout(size_row)

        # Opacity (10-100% -> 0.1-1.0)
        op_row = QHBoxLayout()
        op_row.addWidget(QLabel(tr("watermark.label.opacity")))
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setValue(30)
        self.opacity_value = QLabel("30%")
        self.opacity_slider.valueChanged.connect(lambda v: self.opacity_value.setText(f"{v}%"))
        op_row.addWidget(self.opacity_slider)
        op_row.addWidget(self.opacity_value)
        layout.addLayout(op_row)

        # Angle
        angle_row = QHBoxLayout()
        angle_row.addWidget(QLabel(tr("watermark.label.angle")))
        self.angle_spin = QDoubleSpinBox()
        self.angle_spin.setRange(-180.0, 180.0)
        self.angle_spin.setValue(45.0)
        angle_row.addWidget(self.angle_spin)
        layout.addLayout(angle_row)

        # Color
        color_row = QHBoxLayout()
        color_row.addWidget(QLabel(tr("watermark.label.color")))
        self.color_button = QPushButton()
        self._update_color_button()
        self.color_button.clicked.connect(self._pick_color)
        color_row.addWidget(self.color_button)
        layout.addLayout(color_row)

        # Scope
        self.scope_current = QRadioButton(tr("watermark.scope.current"))
        self.scope_all = QRadioButton(tr("watermark.scope.all"))
        self.scope_all.setChecked(True)
        scope_group = QButtonGroup(self)
        scope_group.addButton(self.scope_current)
        scope_group.addButton(self.scope_all)
        layout.addWidget(self.scope_current)
        layout.addWidget(self.scope_all)

        # Tile across the page
        self.tile_check = QCheckBox(tr("watermark.tile"))
        layout.addWidget(self.tile_check)

        # Buttons
        btn_row = QHBoxLayout()
        apply_btn = QPushButton(tr("watermark.button.apply"))
        cancel_btn = QPushButton(tr("watermark.button.cancel"))
        apply_btn.clicked.connect(self._apply)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(apply_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _update_color_button(self):
        r, g, b = (int(c * 255) for c in self._color)
        self.color_button.setStyleSheet(f"background-color: rgb({r},{g},{b});")
        self.color_button.setText(f"#{r:02x}{g:02x}{b:02x}")

    def _pick_color(self):
        r, g, b = (int(c * 255) for c in self._color)
        chosen = QColorDialog.getColor(QColor(r, g, b), self)
        if chosen.isValid():
            self._color = (chosen.redF(), chosen.greenF(), chosen.blueF())
            self._update_color_button()

    def _apply(self):
        text = self.text_edit.text().strip()
        if not text:
            # Empty watermark is meaningless; treat Apply as cancel.
            get_logger().info("Watermark dialog: empty text, cancelled")
            self.reject()
            return
        self.watermark_confirmed.emit(
            {
                "text": text,
                "fontsize": float(self.size_spin.value()),
                "color": self._color,
                "opacity": self.opacity_slider.value() / 100.0,
                "angle": self.angle_spin.value(),
                "all_pages": self.scope_all.isChecked(),
                "tile": self.tile_check.isChecked(),
            }
        )
        self.accept()
