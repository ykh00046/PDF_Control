"""Text watermark operation (semi-transparent, rotated overlay).

A non-destructive overlay: it adds rotated, semi-transparent text on top of
the page content without removing anything, so the SAVE and PREVIEW paths
share the same apply() (no mode-specific branch). Rendered via TextWriter +
a morph matrix because insert_textbox only supports 90-degree rotations.
"""
from typing import Any, Dict, Tuple

import fitz

from app.operations.base import Operation


class WatermarkText(Operation):
    """A rotated, semi-transparent text watermark centered on the page."""

    def __init__(
        self,
        page_index: int,
        text: str,
        fontsize: float = 40.0,
        color: Tuple[float, float, float] = (0.5, 0.5, 0.5),
        opacity: float = 0.3,
        angle: float = 45.0,
    ) -> None:
        super().__init__(page_index, [])  # watermark uses no selection rects
        self.text = text
        self.fontsize = fontsize
        self.color = color      # RGB tuple, 0-1
        self.opacity = opacity  # 0-1 (1 = opaque)
        self.angle = angle      # degrees, counter-clockwise

    def apply(self, page: fitz.Page) -> None:
        """Draw the watermark centered on the page, rotated by ``angle``."""
        if not self.text:
            return
        font = fitz.Font("helv")
        writer = fitz.TextWriter(page.rect, opacity=self.opacity, color=self.color)
        text_width = font.text_length(self.text, fontsize=self.fontsize)
        center_x = page.rect.width / 2
        center_y = page.rect.height / 2
        # Place the text so its horizontal midpoint sits on the pivot; the
        # morph then rotates the whole run about that same pivot.
        writer.append(
            (center_x - text_width / 2, center_y),
            self.text, font=font, fontsize=self.fontsize,
        )
        pivot = fitz.Point(center_x, center_y)
        writer.write_text(page, morph=(pivot, fitz.Matrix(self.angle)))

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "text": self.text,
            "fontsize": self.fontsize,
            "color": list(self.color),
            "opacity": self.opacity,
            "angle": self.angle,
        })
        return data
