"""Image watermark options dialog.

Collects an image file + style (opacity, scale, 90-step rotation) and scope
(current vs all pages), emitting a settings dict for the handler to turn into
WatermarkImage operations. Rotation is limited to 0/90/180/270 because
``Page.insert_image`` only supports those (unlike the text watermark's
arbitrary-angle morph).
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
)

from app.i18n import tr
from app.logger import get_logger


class ImageWatermarkDialog(QDialog):
    """Configure an image watermark (file, opacity, scale, rotation, scope)."""

    image_watermark_confirmed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._image_path = ""
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle(tr("image_watermark.dialog.title"))
        self.setModal(True)
        layout = QVBoxLayout(self)

        # File picker
        file_row = QHBoxLayout()
        file_row.addWidget(QLabel(tr("image_watermark.label.file")))
        self.file_label = QLabel(tr("image_watermark.no_file"))
        browse_btn = QPushButton(tr("image_watermark.button.browse"))
        browse_btn.clicked.connect(self._browse)
        file_row.addWidget(self.file_label, 1)
        file_row.addWidget(browse_btn)
        layout.addLayout(file_row)

        # Opacity (10-100% -> 0.1-1.0)
        op_row = QHBoxLayout()
        op_row.addWidget(QLabel(tr("image_watermark.label.opacity")))
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setValue(30)
        self.opacity_value = QLabel("30%")
        self.opacity_slider.valueChanged.connect(lambda v: self.opacity_value.setText(f"{v}%"))
        op_row.addWidget(self.opacity_slider)
        op_row.addWidget(self.opacity_value)
        layout.addLayout(op_row)

        # Scale (% of page width)
        scale_row = QHBoxLayout()
        scale_row.addWidget(QLabel(tr("image_watermark.label.scale")))
        self.scale_spin = QSpinBox()
        self.scale_spin.setRange(10, 100)
        self.scale_spin.setValue(50)
        self.scale_spin.setSuffix("%")
        scale_row.addWidget(self.scale_spin)
        layout.addLayout(scale_row)

        # Rotation (90-step only)
        angle_row = QHBoxLayout()
        angle_row.addWidget(QLabel(tr("image_watermark.label.angle")))
        self.angle_combo = QComboBox()
        for deg in (0, 90, 180, 270):
            self.angle_combo.addItem(f"{deg}°", deg)
        angle_row.addWidget(self.angle_combo)
        layout.addLayout(angle_row)

        # Position (ignored while tiling).
        position_row = QHBoxLayout()
        position_row.addWidget(QLabel(tr("image_watermark.label.position")))
        self.position_combo = QComboBox()
        for value in ("center", "top-left", "top-right", "bottom-left", "bottom-right"):
            self.position_combo.addItem(tr(f"watermark.position.{value}"), value)
        position_row.addWidget(self.position_combo)
        layout.addLayout(position_row)

        # Scope
        self.scope_current = QRadioButton(tr("image_watermark.scope.current"))
        self.scope_all = QRadioButton(tr("image_watermark.scope.all"))
        self.scope_all.setChecked(True)
        scope_group = QButtonGroup(self)
        scope_group.addButton(self.scope_current)
        scope_group.addButton(self.scope_all)
        layout.addWidget(self.scope_current)
        layout.addWidget(self.scope_all)

        # Tile across the page
        self.tile_check = QCheckBox(tr("image_watermark.tile"))
        self.tile_check.toggled.connect(lambda checked: self.position_combo.setEnabled(not checked))
        layout.addWidget(self.tile_check)

        # Buttons
        btn_row = QHBoxLayout()
        apply_btn = QPushButton(tr("image_watermark.button.apply"))
        cancel_btn = QPushButton(tr("image_watermark.button.cancel"))
        apply_btn.clicked.connect(self._apply)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(apply_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("image_watermark.dialog.title"),
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif)",
        )
        if path:
            self._image_path = path
            import os

            self.file_label.setText(os.path.basename(path))

    def _apply(self):
        if not self._image_path:
            get_logger().info("Image watermark dialog: no file chosen, cancelled")
            self.reject()
            return
        self.image_watermark_confirmed.emit(
            {
                "image_path": self._image_path,
                "opacity": self.opacity_slider.value() / 100.0,
                "scale": self.scale_spin.value() / 100.0,
                "rotate": self.angle_combo.currentData(),
                "all_pages": self.scope_all.isChecked(),
                "tile": self.tile_check.isChecked(),
                "position": self.position_combo.currentData(),
            }
        )
        self.accept()
