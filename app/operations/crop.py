"""Page cropping operation (margin removal via MediaBox adjustment).

Split out of the former monolithic ``app/model.py`` (model-restructure).

Margins are given as the user sees them (top/bottom/left/right of the
*displayed* page). A rotated page stores its content unrotated, so the
visible margins are mapped onto the unrotated MediaBox edges first
(feature-review, 2026-09-09: "top 30pt" on a 90-degree page used to cut
the visible left edge, and ``set_cropbox`` after ``set_mediabox`` raised
"CropBox not in MediaBox" on every document).
"""

from typing import Any, Dict, Tuple

import fitz

from app.operations.base import Operation


def visible_to_mediabox_margins(
    rotation: int, top: float, bottom: float, left: float, right: float
) -> Tuple[float, float, float, float]:
    """Map displayed-page margins to unrotated MediaBox margins.

    Returns ``(left, top, right, bottom)`` in MediaBox terms. Measured on
    PyMuPDF: with rotation 90 the visible top edge is the unrotated left
    edge, visible right is unrotated top, and so on around the page.
    """
    rotation = rotation % 360
    if rotation == 90:
        return top, right, bottom, left
    if rotation == 180:
        return right, bottom, left, top
    if rotation == 270:
        return bottom, left, top, right
    return left, top, right, bottom


class CropMargins(Operation):
    """Represents a page cropping operation to remove margins."""

    def __init__(self, page_index: int, top: float = 0, bottom: float = 0, left: float = 0, right: float = 0) -> None:
        # CropMargins doesn't use rects, but we pass empty list to satisfy parent
        super().__init__(page_index, [])
        self.top = top  # Points to remove from the displayed top
        self.bottom = bottom  # Points to remove from the displayed bottom
        self.left = left  # Points to remove from the displayed left
        self.right = right  # Points to remove from the displayed right

    def apply(self, page: fitz.Page) -> None:
        """Shrink the MediaBox (the CropBox follows it automatically)."""
        left, top, right, bottom = visible_to_mediabox_margins(
            page.rotation, self.top, self.bottom, self.left, self.right
        )
        current_rect = page.mediabox
        new_rect = fitz.Rect(
            current_rect.x0 + left,
            current_rect.y0 + top,
            current_rect.x1 - right,
            current_rect.y1 - bottom,
        )
        if new_rect.is_empty or new_rect.width < 1 or new_rect.height < 1:
            raise ValueError("Crop margins leave no page area")
        # set_mediabox re-bases page.rect to (0, 0) and resets the CropBox to
        # the new MediaBox; a second set_cropbox with the same (now off-page)
        # rect is what used to raise "CropBox not in MediaBox".
        page.set_mediabox(new_rect)

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({"top": self.top, "bottom": self.bottom, "left": self.left, "right": self.right})
        return data
