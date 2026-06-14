import fitz
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from app.i18n import tr
from app.logger import get_logger


class CropPreviewDialog(QDialog):
    """Dialog to preview and configure page cropping."""

    crop_confirmed = Signal(dict)  # Emits {"top": float, "bottom": float, "left": float, "right": float}

    def __init__(self, page: fitz.Page, selected_rect: fitz.Rect, parent=None):
        super().__init__(parent)
        self.page = page
        self.selected_rect = selected_rect
        self.page_rect = page.rect

        # Calculate crop margins based on selected rect
        self.top_margin = selected_rect.y0
        self.bottom_margin = self.page_rect.height - selected_rect.y1
        self.left_margin = selected_rect.x0
        self.right_margin = self.page_rect.width - selected_rect.x1

        self.init_ui()
        self.render_preview()

    def init_ui(self):
        self.setWindowTitle(tr("crop.dialog.title"))
        self.setModal(True)
        self.resize(800, 600)

        layout = QVBoxLayout(self)

        # Preview area
        preview_label = QLabel(tr("crop.preview.label"))
        layout.addWidget(preview_label)

        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPen.Antialiasing)
        layout.addWidget(self.view)

        # Crop options
        options_group = QGroupBox(tr("crop.options.title"))
        options_layout = QVBoxLayout()

        self.top_check = QCheckBox(tr("crop.option.top", f"{self.top_margin:.1f}"))
        self.bottom_check = QCheckBox(tr("crop.option.bottom", f"{self.bottom_margin:.1f}"))
        self.left_check = QCheckBox(tr("crop.option.left", f"{self.left_margin:.1f}"))
        self.right_check = QCheckBox(tr("crop.option.right", f"{self.right_margin:.1f}"))

        # Check all by default
        self.top_check.setChecked(True)
        self.bottom_check.setChecked(True)
        self.left_check.setChecked(True)
        self.right_check.setChecked(True)

        # Connect to update preview
        self.top_check.toggled.connect(self.update_preview_overlay)
        self.bottom_check.toggled.connect(self.update_preview_overlay)
        self.left_check.toggled.connect(self.update_preview_overlay)
        self.right_check.toggled.connect(self.update_preview_overlay)

        options_layout.addWidget(self.top_check)
        options_layout.addWidget(self.bottom_check)
        options_layout.addWidget(self.left_check)
        options_layout.addWidget(self.right_check)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # Buttons
        button_layout = QHBoxLayout()
        apply_button = QPushButton(tr("crop.button.apply"))
        cancel_button = QPushButton(tr("crop.button.cancel"))

        apply_button.clicked.connect(self.apply_crop)
        cancel_button.clicked.connect(self.reject)

        button_layout.addStretch()
        button_layout.addWidget(apply_button)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

    def render_preview(self):
        """Render the page with crop preview overlay."""
        # Render page
        zoom_matrix = fitz.Matrix(0.5, 0.5)  # 50% zoom for preview
        pix = self.page.get_pixmap(matrix=zoom_matrix)

        # Convert to QImage
        img_data = bytes(pix.samples)
        if pix.alpha:
            img_format = QImage.Format_RGBA8888
        else:
            img_format = QImage.Format_RGB888

        img = QImage(img_data, pix.width, pix.height, pix.stride, img_format).copy()

        # Add to scene
        self.pixmap_item = QGraphicsPixmapItem(QPixmap.fromImage(img))
        self.scene.addItem(self.pixmap_item)

        # Scale factor for overlay (from PDF points to preview pixels)
        self.scale_factor = 0.5

        # Add overlay rectangles
        self.overlay_items = []
        self.update_preview_overlay()

        # Fit in view
        self.scene.setSceneRect(self.pixmap_item.boundingRect())
        self.view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)

    def update_preview_overlay(self):
        """Update the crop preview overlay based on checkbox states."""
        # Remove old overlays
        for item in self.overlay_items:
            self.scene.removeItem(item)
        self.overlay_items.clear()

        # Semi-transparent red for crop areas
        crop_brush = QBrush(QColor(255, 0, 0, 80))
        crop_pen = QPen(QColor(255, 0, 0), 2, Qt.DashLine)

        page_width = self.page_rect.width * self.scale_factor
        page_height = self.page_rect.height * self.scale_factor

        # Top margin
        if self.top_check.isChecked():
            rect = QRectF(0, 0, page_width, self.top_margin * self.scale_factor)
            item = QGraphicsRectItem(rect)
            item.setBrush(crop_brush)
            item.setPen(crop_pen)
            self.scene.addItem(item)
            self.overlay_items.append(item)

        # Bottom margin
        if self.bottom_check.isChecked():
            y_start = (self.page_rect.height - self.bottom_margin) * self.scale_factor
            rect = QRectF(0, y_start, page_width, self.bottom_margin * self.scale_factor)
            item = QGraphicsRectItem(rect)
            item.setBrush(crop_brush)
            item.setPen(crop_pen)
            self.scene.addItem(item)
            self.overlay_items.append(item)

        # Left margin
        if self.left_check.isChecked():
            rect = QRectF(0, 0, self.left_margin * self.scale_factor, page_height)
            item = QGraphicsRectItem(rect)
            item.setBrush(crop_brush)
            item.setPen(crop_pen)
            self.scene.addItem(item)
            self.overlay_items.append(item)

        # Right margin
        if self.right_check.isChecked():
            x_start = (self.page_rect.width - self.right_margin) * self.scale_factor
            rect = QRectF(x_start, 0, self.right_margin * self.scale_factor, page_height)
            item = QGraphicsRectItem(rect)
            item.setBrush(crop_brush)
            item.setPen(crop_pen)
            self.scene.addItem(item)
            self.overlay_items.append(item)

    def apply_crop(self):
        """Emit the crop settings and close dialog."""
        crop_settings = {
            "top": self.top_margin if self.top_check.isChecked() else 0,
            "bottom": self.bottom_margin if self.bottom_check.isChecked() else 0,
            "left": self.left_margin if self.left_check.isChecked() else 0,
            "right": self.right_margin if self.right_check.isChecked() else 0,
        }

        # Check if any cropping is selected
        if all(v == 0 for v in crop_settings.values()):
            get_logger().info("User cancelled crop: no margins selected")
            self.reject()
            return

        get_logger().info(f"User applied crop: {crop_settings}")
        self.crop_confirmed.emit(crop_settings)
        self.accept()
