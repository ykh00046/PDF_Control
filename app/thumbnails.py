"""Shared page-thumbnail rendering.

Used by both the page manager dialog and the thumbnail sidebar so the
fitz->QPixmap conversion lives in one place.
"""

import fitz
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap

from app.theme import LIGHT_THEME

# Default thumbnail width in pixels (page manager grid).
THUMB_WIDTH = 120


def render_page_thumbnail(page: fitz.Page, width: int = THUMB_WIDTH, framed: bool = True) -> QPixmap:
    """Render one PDF page as a QPixmap scaled to the given pixel width.

    ``framed`` draws a 1px page border so a white page reads as a card on
    the white list background instead of dissolving into it.
    """
    page_rect = page.rect
    scale = width / page_rect.width if page_rect.width > 0 else 1.0
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))

    fmt = QImage.Format_RGBA8888 if pix.alpha else QImage.Format_RGB888
    qimage = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)
    # fromImage copies the pixel data, so the fitz buffer may be freed after.
    pixmap = QPixmap.fromImage(qimage)
    if framed:
        painter = QPainter(pixmap)
        painter.setPen(QPen(QColor(LIGHT_THEME.border_strong), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(0, 0, pixmap.width() - 1, pixmap.height() - 1)
        painter.end()
    return pixmap
