"""
Page Manager Dialog

Provides a visual interface for managing PDF pages:
- Thumbnail preview of all pages
- Drag-and-drop reorder
- Rotate pages (90/180/270 degrees)
- Delete selected pages
- Insert blank pages
"""

import fitz
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QListWidgetItem, QAbstractItemView, QMessageBox, QLabel,
    QToolBar, QSizePolicy
)
from PySide6.QtGui import QPixmap, QImage, QIcon, QAction
from PySide6.QtCore import Qt, Signal, QSize
from app.i18n import tr
from app.logger import get_logger

# Thumbnail rendering constants
THUMB_WIDTH = 120
THUMB_DPI = 72


class PageManagerDialog(QDialog):
    """Dialog for managing PDF pages with visual thumbnails."""

    pages_changed = Signal()  # Emitted when any page operation is performed

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.logger = get_logger()
        self._changes_made = False

        self.setWindowTitle(tr("page_manager.title"))
        self.setMinimumSize(500, 600)
        self.resize(550, 700)

        self._setup_ui()
        self._load_thumbnails()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Info label
        self.info_label = QLabel(tr("page_manager.info"))
        self.info_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(self.info_label)

        # Toolbar
        toolbar = QToolBar()
        toolbar.setIconSize(QSize(20, 20))

        self.rotate_left_action = QAction(tr("page_manager.rotate_left"), self)
        self.rotate_left_action.setToolTip(tr("page_manager.rotate_left.tooltip"))
        self.rotate_left_action.triggered.connect(lambda: self._rotate_selected(-90))
        toolbar.addAction(self.rotate_left_action)

        self.rotate_right_action = QAction(tr("page_manager.rotate_right"), self)
        self.rotate_right_action.setToolTip(tr("page_manager.rotate_right.tooltip"))
        self.rotate_right_action.triggered.connect(lambda: self._rotate_selected(90))
        toolbar.addAction(self.rotate_right_action)

        self.rotate_180_action = QAction(tr("page_manager.rotate_180"), self)
        self.rotate_180_action.setToolTip(tr("page_manager.rotate_180.tooltip"))
        self.rotate_180_action.triggered.connect(lambda: self._rotate_selected(180))
        toolbar.addAction(self.rotate_180_action)

        toolbar.addSeparator()

        self.delete_action = QAction(tr("page_manager.delete"), self)
        self.delete_action.setToolTip(tr("page_manager.delete.tooltip"))
        self.delete_action.triggered.connect(self._delete_selected)
        toolbar.addAction(self.delete_action)

        toolbar.addSeparator()

        self.insert_action = QAction(tr("page_manager.insert_blank"), self)
        self.insert_action.setToolTip(tr("page_manager.insert_blank.tooltip"))
        self.insert_action.triggered.connect(self._insert_blank_page)
        toolbar.addAction(self.insert_action)

        toolbar.addSeparator()

        self.move_up_action = QAction(tr("page_manager.move_up"), self)
        self.move_up_action.setToolTip(tr("page_manager.move_up.tooltip"))
        self.move_up_action.triggered.connect(self._move_up)
        toolbar.addAction(self.move_up_action)

        self.move_down_action = QAction(tr("page_manager.move_down"), self)
        self.move_down_action.setToolTip(tr("page_manager.move_down.tooltip"))
        self.move_down_action.triggered.connect(self._move_down)
        toolbar.addAction(self.move_down_action)

        layout.addWidget(toolbar)

        # Page list with thumbnails
        self.page_list = QListWidget()
        self.page_list.setViewMode(QListWidget.IconMode)
        self.page_list.setIconSize(QSize(THUMB_WIDTH, int(THUMB_WIDTH * 1.414)))  # A4 ratio
        self.page_list.setSpacing(10)
        self.page_list.setResizeMode(QListWidget.Adjust)
        self.page_list.setWrapping(True)
        self.page_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.page_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.page_list.setDefaultDropAction(Qt.MoveAction)
        self.page_list.setMovement(QListWidget.Free)
        self.page_list.model().rowsMoved.connect(self._on_rows_moved)
        layout.addWidget(self.page_list)

        # Status label
        self.status_label = QLabel()
        layout.addWidget(self.status_label)

        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.close_button = QPushButton(tr("page_manager.close"))
        self.close_button.clicked.connect(self.accept)
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)

    def _load_thumbnails(self):
        """Load page thumbnails from the document."""
        self.page_list.clear()
        session = self.controller.session
        if not session or not session.doc:
            return

        doc = session.doc
        for i in range(doc.page_count):
            page = doc[i]
            pixmap = self._render_thumbnail(page)

            item = QListWidgetItem()
            item.setIcon(QIcon(pixmap))
            rotation_info = f" ({page.rotation}°)" if page.rotation != 0 else ""
            item.setText(f"{i + 1}{rotation_info}")
            item.setData(Qt.UserRole, i)  # Store original page index
            item.setTextAlignment(Qt.AlignHCenter | Qt.AlignBottom)
            self.page_list.addItem(item)

        self._update_status()

    def _render_thumbnail(self, page: fitz.Page) -> QPixmap:
        """Render a page thumbnail as QPixmap."""
        # Calculate scale to fit THUMB_WIDTH
        page_rect = page.rect
        scale = THUMB_WIDTH / page_rect.width if page_rect.width > 0 else 1.0
        matrix = fitz.Matrix(scale, scale)

        pix = page.get_pixmap(matrix=matrix)

        # Convert to QImage
        if pix.alpha:
            fmt = QImage.Format_RGBA8888
        else:
            fmt = QImage.Format_RGB888

        qimage = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)
        return QPixmap.fromImage(qimage)

    def _rotate_selected(self, angle: int):
        """Rotate all selected pages by the given angle."""
        selected = self.page_list.selectedItems()
        if not selected:
            return

        for item in selected:
            row = self.page_list.row(item)
            if self.controller.rotate_page(row, angle):
                # Update thumbnail
                page = self.controller.session.doc[row]
                pixmap = self._render_thumbnail(page)
                item.setIcon(QIcon(pixmap))
                rotation_info = f" ({page.rotation}°)" if page.rotation != 0 else ""
                item.setText(f"{row + 1}{rotation_info}")

        self._mark_changed()
        self.logger.info(f"Rotated {len(selected)} page(s) by {angle}°")

    def _delete_selected(self):
        """Delete all selected pages."""
        selected = self.page_list.selectedItems()
        if not selected:
            return

        session = self.controller.session
        if not session:
            return

        # Don't allow deleting all pages
        if len(selected) >= session.doc.page_count:
            QMessageBox.warning(
                self,
                tr("page_manager.error.title"),
                tr("page_manager.error.delete_all")
            )
            return

        # Confirmation
        page_nums = [str(self.page_list.row(item) + 1) for item in selected]
        reply = QMessageBox.question(
            self,
            tr("page_manager.confirm_delete.title"),
            tr("page_manager.confirm_delete.message", ", ".join(page_nums)),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        indices = sorted([self.page_list.row(item) for item in selected], reverse=True)
        if self.controller.delete_pages(indices):
            self._load_thumbnails()
            self._mark_changed()

    def _insert_blank_page(self):
        """Insert a blank page after the current selection."""
        selected = self.page_list.selectedItems()
        if selected:
            after_index = self.page_list.row(selected[-1])
        else:
            after_index = -1  # End of document

        if self.controller.insert_blank_page(after_index):
            self._load_thumbnails()
            self._mark_changed()

    def _move_up(self):
        """Move selected page up (decrease index)."""
        selected = self.page_list.selectedItems()
        if not selected or len(selected) != 1:
            return

        current_row = self.page_list.row(selected[0])
        if current_row <= 0:
            return

        # PyMuPDF move_page: moves page at pno to before page at to
        # To move page 3 to position 2: move_page(3, 2)
        if self.controller.move_page(current_row, current_row - 1):
            self._load_thumbnails()
            self.page_list.setCurrentRow(current_row - 1)
            self._mark_changed()

    def _move_down(self):
        """Move selected page down (increase index)."""
        selected = self.page_list.selectedItems()
        if not selected or len(selected) != 1:
            return

        session = self.controller.session
        if not session:
            return

        current_row = self.page_list.row(selected[0])
        if current_row >= session.doc.page_count - 1:
            return

        # move_page(from, to): to move down, target is current_row + 2
        # because PyMuPDF inserts *before* the target index
        target = current_row + 2 if current_row + 2 <= session.doc.page_count else -1
        if self.controller.move_page(current_row, target):
            self._load_thumbnails()
            self.page_list.setCurrentRow(current_row + 1)
            self._mark_changed()

    def _on_rows_moved(self):
        """Handle drag-and-drop reorder via QListWidget internal move."""
        # After drag-drop, reconstruct the page order from item data
        session = self.controller.session
        if not session:
            return

        # Get the new order of original page indices
        new_order = []
        for i in range(self.page_list.count()):
            item = self.page_list.item(i)
            original_idx = item.data(Qt.UserRole)
            new_order.append(original_idx)

        # Check if order actually changed
        if new_order == list(range(len(new_order))):
            return

        # Apply reorder using PyMuPDF's select method
        try:
            session.doc.select(new_order)
            session._rebuild_after_reorder()
            self._load_thumbnails()
            self._mark_changed()
            self.logger.info(f"Pages reordered via drag-drop: {new_order}")
        except Exception as e:
            self.logger.error(f"Drag-drop reorder failed: {e}")
            QMessageBox.warning(self, tr("page_manager.error.title"), str(e))

    def _mark_changed(self):
        """Mark that changes were made."""
        self._changes_made = True
        self.pages_changed.emit()
        self._update_status()

    def _update_status(self):
        """Update the status label."""
        session = self.controller.session
        if session and session.doc:
            count = session.doc.page_count
            self.status_label.setText(tr("page_manager.status", count))
        else:
            self.status_label.setText("")

    @property
    def changes_made(self) -> bool:
        return self._changes_made
