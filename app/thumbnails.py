"""Shared page-thumbnail rendering.

Used by both the page manager dialog and the thumbnail sidebar so the
fitz->QPixmap conversion lives in one place.
"""

import fitz
from PySide6.QtGui import QImage, QPixmap

# Default thumbnail width in pixels (page manager grid).
THUMB_WIDTH = 120


def render_page_thumbnail(page: fitz.Page, width: int = THUMB_WIDTH) -> QPixmap:
    """Render one PDF page as a QPixmap scaled to the given pixel width."""
    page_rect = page.rect
    scale = width / page_rect.width if page_rect.width > 0 else 1.0
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))

    fmt = QImage.Format_RGBA8888 if pix.alpha else QImage.Format_RGB888
    qimage = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)
    # fromImage copies the pixel data, so the fitz buffer may be freed after.
    return QPixmap.fromImage(qimage)
