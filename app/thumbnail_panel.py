"""Page thumbnail sidebar for the main window.

A dockable list of page thumbnails: click a thumbnail to navigate the
viewer, and the highlighted row follows the viewer's current page.

Thumbnails are rendered in small batches on the event loop (QTimer) so
opening a large document does not freeze the UI. A generation counter
invalidates queued batches when the document changes or closes, so a
stale timer can never touch a closed fitz document.
"""

from typing import List

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QAbstractItemView, QListWidget, QListWidgetItem

from app.thumbnails import render_page_thumbnail

# Sidebar thumbnails are slimmer than the page manager grid.
SIDEBAR_THUMB_WIDTH = 90
# Pages rendered per event-loop tick; keeps the UI responsive on big docs.
RENDER_BATCH_SIZE = 8


class ThumbnailSidebar(QListWidget):
    """Vertical list of page thumbnails bound to a document session."""

    page_selected = Signal(int)  # User clicked a page (0-indexed)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.session = None
        self._render_queue: List[int] = []
        self._generation = 0
        self._syncing = False

        self.setViewMode(QListWidget.IconMode)
        self.setIconSize(QSize(SIDEBAR_THUMB_WIDTH, int(SIDEBAR_THUMB_WIDTH * 1.414)))
        self.setSpacing(8)
        self.setResizeMode(QListWidget.Adjust)
        self.setWrapping(True)
        self.setMovement(QListWidget.Static)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setMinimumWidth(SIDEBAR_THUMB_WIDTH + 40)

        self.currentRowChanged.connect(self._on_row_changed)

    # ------------------------------------------------------------- binding
    def set_session(self, session) -> None:
        """Bind to a document session (or None to clear) and rebuild."""
        self.session = session
        self.refresh()

    def refresh(self) -> None:
        """Rebuild all items and queue thumbnail rendering."""
        self._generation += 1
        self._render_queue = []
        self._syncing = True
        try:
            self.clear()
        finally:
            self._syncing = False

        doc = getattr(self.session, "doc", None)
        if doc is None or doc.is_closed:
            return

        for i in range(doc.page_count):
            item = QListWidgetItem(self._page_label(doc, i))
            item.setTextAlignment(Qt.AlignHCenter | Qt.AlignBottom)
            self.addItem(item)

        self._render_queue = list(range(doc.page_count))
        generation = self._generation
        QTimer.singleShot(0, lambda: self._render_batch(generation))

    # ----------------------------------------------------------- rendering
    def _page_label(self, doc, index: int) -> str:
        rotation = doc[index].rotation
        return f"{index + 1}" + (f" ({rotation}°)" if rotation else "")

    def _render_batch(self, generation: int) -> None:
        """Render up to RENDER_BATCH_SIZE queued thumbnails, then reschedule."""
        if generation != self._generation:
            return
        doc = getattr(self.session, "doc", None)
        if doc is None or doc.is_closed:
            return

        for _ in range(RENDER_BATCH_SIZE):
            if not self._render_queue:
                return
            index = self._render_queue.pop(0)
            if index >= doc.page_count or index >= self.count():
                continue
            pixmap = render_page_thumbnail(doc[index], SIDEBAR_THUMB_WIDTH)
            item = self.item(index)
            item.setIcon(QIcon(pixmap))
            item.setText(self._page_label(doc, index))

        if self._render_queue:
            QTimer.singleShot(0, lambda: self._render_batch(generation))

    def flush_pending_renders(self) -> None:
        """Render the whole queue synchronously (tests, eager refresh)."""
        while self._render_queue:
            self._render_batch(self._generation)

    # ----------------------------------------------------------- selection
    def set_current_page(self, page_index: int) -> None:
        """Highlight a row without re-emitting page_selected."""
        if page_index < 0 or page_index >= self.count():
            return
        self._syncing = True
        try:
            self.setCurrentRow(page_index)
        finally:
            self._syncing = False

    def _on_row_changed(self, row: int) -> None:
        if self._syncing or row < 0:
            return
        self.page_selected.emit(row)
