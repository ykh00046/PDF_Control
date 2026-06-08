"""Page cropping operation (margin removal via MediaBox adjustment).

Split out of the former monolithic ``app/model.py`` (model-restructure).
"""
from typing import Any, Dict

import fitz

from app.operations.base import Operation


class CropMargins(Operation):
    """Represents a page cropping operation to remove margins."""

    def __init__(self, page_index: int, top: float = 0, bottom: float = 0,
                 left: float = 0, right: float = 0) -> None:
        # CropMargins doesn't use rects, but we pass empty list to satisfy parent
        super().__init__(page_index, [])
        self.top = top        # Points to remove from top
        self.bottom = bottom  # Points to remove from bottom
        self.left = left      # Points to remove from left
        self.right = right    # Points to remove from right

    def apply(self, page: fitz.Page) -> None:
        """Apply cropping by adjusting the page's MediaBox."""
        current_rect = page.mediabox
        new_rect = fitz.Rect(
            current_rect.x0 + self.left,
            current_rect.y0 + self.top,
            current_rect.x1 - self.right,
            current_rect.y1 - self.bottom
        )
        page.set_mediabox(new_rect)
        page.set_cropbox(new_rect)  # Also set cropbox for consistency

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({"top": self.top, "bottom": self.bottom, "left": self.left, "right": self.right})
        return data
