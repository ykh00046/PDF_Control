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
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QIcon, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QToolBar,
    QVBoxLayout,
)

from app.i18n import tr
from app.icons import icon
from app.logger import get_logger
from app.page_split import compute_split_groups
from app.split_dialog import SplitDialog
from app.theme import LIGHT_THEME, label_style

# Thumbnail rendering (shared with the sidebar via app.thumbnails)
from app.thumbnails import THUMB_WIDTH, render_page_thumbnail


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
        self.info_label.setStyleSheet(label_style(LIGHT_THEME, "muted"))
        layout.addWidget(self.info_label)

        # Two toolbars: one row overflowed at the default dialog width and
        # hid duplicate/extract/merge/split behind the extension chevron.
        #   row 1 (arrange):  undo/redo | rotate L/R/180 | move up/down
        #   row 2 (pages):    delete / insert blank / duplicate | extract / merge / split
        icon_names = {
            "page_manager.undo": "undo",
            "page_manager.redo": "redo",
            "page_manager.rotate_left": "rotate-left",
            "page_manager.rotate_right": "rotate-right",
            "page_manager.rotate_180": "rotate-180",
            "page_manager.move_up": "up",
            "page_manager.move_down": "down",
            "page_manager.delete": "delete",
            "page_manager.insert_blank": "insert-page",
            "page_manager.duplicate": "duplicate",
            "page_manager.extract": "extract",
            "page_manager.merge": "merge",
            "page_manager.split": "split",
        }

        def make_action(key: str, slot, shortcut=None) -> QAction:
            action = QAction(icon(icon_names[key]), tr(key), self)
            action.setToolTip(tr(f"{key}.tooltip"))
            action.setStatusTip(tr(f"{key}.tooltip"))
            if shortcut is not None:
                action.setShortcut(shortcut)
            action.triggered.connect(slot)
            return action

        arrange_bar = QToolBar()
        arrange_bar.setIconSize(QSize(20, 20))
        arrange_bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.undo_action = make_action("page_manager.undo", self._undo_page_change, QKeySequence.StandardKey.Undo)
        self.redo_action = make_action("page_manager.redo", self._redo_page_change, QKeySequence.StandardKey.Redo)
        arrange_bar.addAction(self.undo_action)
        arrange_bar.addAction(self.redo_action)
        arrange_bar.addSeparator()
        self.rotate_left_action = make_action("page_manager.rotate_left", lambda: self._rotate_selected(-90))
        self.rotate_right_action = make_action("page_manager.rotate_right", lambda: self._rotate_selected(90))
        self.rotate_180_action = make_action("page_manager.rotate_180", lambda: self._rotate_selected(180))
        arrange_bar.addAction(self.rotate_left_action)
        arrange_bar.addAction(self.rotate_right_action)
        arrange_bar.addAction(self.rotate_180_action)
        arrange_bar.addSeparator()
        self.move_up_action = make_action("page_manager.move_up", self._move_up)
        self.move_down_action = make_action("page_manager.move_down", self._move_down)
        arrange_bar.addAction(self.move_up_action)
        arrange_bar.addAction(self.move_down_action)
        layout.addWidget(arrange_bar)

        pages_bar = QToolBar()
        pages_bar.setIconSize(QSize(20, 20))
        pages_bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.delete_action = make_action("page_manager.delete", self._delete_selected)
        self.insert_action = make_action("page_manager.insert_blank", self._insert_blank_page)
        self.duplicate_action = make_action("page_manager.duplicate", self._duplicate_selected)
        pages_bar.addAction(self.delete_action)
        pages_bar.addAction(self.insert_action)
        pages_bar.addAction(self.duplicate_action)
        pages_bar.addSeparator()
        self.extract_action = make_action("page_manager.extract", self._extract_selected)
        self.merge_action = make_action("page_manager.merge", self._merge_pdf)
        self.split_action = make_action("page_manager.split", self._split_document)
        pages_bar.addAction(self.extract_action)
        pages_bar.addAction(self.merge_action)
        pages_bar.addAction(self.split_action)
        layout.addWidget(pages_bar)

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

        session = self.controller.session
        if session:
            session.page_history_changed.connect(self._update_history_actions)
        self._update_history_actions()

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
        return render_page_thumbnail(page, THUMB_WIDTH)

    def _rotate_selected(self, angle: int):
        """Rotate all selected pages by the given angle."""
        selected = self.page_list.selectedItems()
        if not selected:
            return

        session = self.controller.session
        with session.page_change_group():
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
            QMessageBox.warning(self, tr("page_manager.error.title"), tr("page_manager.error.delete_all"))
            return

        # Confirmation
        page_nums = [str(self.page_list.row(item) + 1) for item in selected]
        reply = QMessageBox.question(
            self,
            tr("page_manager.confirm_delete.title"),
            tr("page_manager.confirm_delete.message", ", ".join(page_nums)),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
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

    def _duplicate_selected(self):
        """Duplicate all selected pages (each copy inserted immediately after the original)."""
        selected = self.page_list.selectedItems()
        if not selected:
            QMessageBox.information(
                self,
                tr("page_manager.error.title"),
                tr("page_manager.error.no_selection"),
            )
            return
        indices = [self.page_list.row(item) for item in selected]
        if self.controller.duplicate_pages(indices):
            self._load_thumbnails()
            self._mark_changed()
            self.logger.info(f"Duplicated {len(indices)} page(s)")

    def _extract_selected(self):
        """Save selected pages to a new PDF file."""
        selected = self.page_list.selectedItems()
        if not selected:
            QMessageBox.information(
                self,
                tr("page_manager.error.title"),
                tr("page_manager.error.no_selection"),
            )
            return
        indices = sorted(self.page_list.row(item) for item in selected)
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            tr("page_manager.extract.dialog_title"),
            "",
            "PDF Files (*.pdf)",
        )
        if not output_path:
            return
        if not output_path.lower().endswith(".pdf"):
            output_path += ".pdf"
        if self.controller.extract_pages(indices, output_path):
            QMessageBox.information(
                self,
                tr("page_manager.title"),
                tr("page_manager.extract.success", output_path),
            )

    def _merge_pdf(self):
        """Insert all pages from one or more chosen PDFs after the selection (or end)."""
        source_paths, _ = QFileDialog.getOpenFileNames(
            self,
            tr("page_manager.merge.dialog_title"),
            "",
            "PDF Files (*.pdf)",
        )
        if not source_paths:
            return
        selected = self.page_list.selectedItems()
        if selected:
            after_index = self.page_list.row(selected[-1])
        else:
            after_index = -1
        if self.controller.merge_pdfs(source_paths, after_index):
            self._load_thumbnails()
            self._mark_changed()
            QMessageBox.information(
                self,
                tr("page_manager.title"),
                tr("page_manager.merge.success_multi", len(source_paths)),
            )

    def _split_document(self):
        """Split the whole document into multiple PDFs (source unchanged)."""
        session = self.controller.session
        if not session or not session.doc or session.doc.page_count == 0:
            QMessageBox.information(
                self,
                tr("page_manager.error.title"),
                tr("page_manager.error.no_selection"),
            )
            return

        page_count = session.doc.page_count
        dialog = SplitDialog(page_count, self)
        if dialog.exec() != QDialog.Accepted:
            return

        settings = dialog.get_settings()
        if not settings["output_dir"]:
            QMessageBox.warning(
                self,
                tr("page_manager.error.title"),
                tr("split.output_dir.required"),
            )
            return

        # Turn the chosen mode/params into concrete page-index groups.
        try:
            groups = compute_split_groups(
                page_count,
                settings["mode"],
                every_n=settings["every_n"],
                ranges_spec=settings["ranges_spec"],
            )
        except ValueError as e:
            self.logger.warning(f"Invalid split request: {e}")
            QMessageBox.warning(
                self,
                tr("page_manager.error.title"),
                tr("split.error.invalid_ranges"),
            )
            return

        written = self.controller.split_document(settings["output_dir"], groups)
        if written:
            # Splitting does not modify the source document, so no _mark_changed().
            QMessageBox.information(
                self,
                tr("page_manager.title"),
                tr("split.success", len(written)),
            )

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

        # Apply reorder through the session so pending history is remapped
        # (not discarded) and session invariants stay session-owned.
        try:
            session.reorder_pages(new_order)
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
        self._update_history_actions()

    def _undo_page_change(self):
        session = self.controller.session
        if session and session.undo_page_change():
            self._load_thumbnails()
            self._changes_made = session.modified
            self.pages_changed.emit()
            self._update_history_actions()

    def _redo_page_change(self):
        session = self.controller.session
        if session and session.redo_page_change():
            self._load_thumbnails()
            self._changes_made = session.modified
            self.pages_changed.emit()
            self._update_history_actions()

    def _update_history_actions(self):
        session = self.controller.session
        self.undo_action.setEnabled(bool(session and session.can_undo_page_change))
        self.redo_action.setEnabled(bool(session and session.can_redo_page_change))

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
