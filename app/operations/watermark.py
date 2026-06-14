"""Text watermark operation (semi-transparent, rotated overlay).

A non-destructive overlay: it adds rotated, semi-transparent text on top of
the page content without removing anything, so the SAVE and PREVIEW paths
share the same apply() (no mode-specific branch). Rendered via TextWriter +
a morph matrix because insert_textbox only supports 90-degree rotations.
"""

import os
from typing import Any, Dict, Tuple

import fitz

from app.logger import get_logger
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
        self.color = color  # RGB tuple, 0-1
        self.opacity = opacity  # 0-1 (1 = opaque)
        self.angle = angle  # degrees, counter-clockwise

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
            self.text,
            font=font,
            fontsize=self.fontsize,
        )
        pivot = fitz.Point(center_x, center_y)
        writer.write_text(page, morph=(pivot, fitz.Matrix(self.angle)))

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update(
            {
                "text": self.text,
                "fontsize": self.fontsize,
                "color": list(self.color),
                "opacity": self.opacity,
                "angle": self.angle,
            }
        )
        return data


class WatermarkImage(Operation):
    """A semi-transparent image watermark centered on the page.

    Unlike the text watermark, ``insert_image`` has no opacity parameter and
    only rotates in 90-degree steps, so opacity is applied via the image's
    alpha channel and ``rotate`` is restricted to {0, 90, 180, 270}.
    """

    def __init__(
        self,
        page_index: int,
        image_path: str,
        opacity: float = 0.3,
        scale: float = 0.5,
        rotate: int = 0,
    ) -> None:
        super().__init__(page_index, [])  # no selection rects
        self.image_path = image_path
        self.opacity = opacity  # 0-1
        self.scale = scale  # fraction of page WIDTH
        self.rotate = rotate  # 0/90/180/270 (insert_image limitation)

    def apply(self, page: fitz.Page) -> None:
        """Draw the image centered on the page at ``scale`` * page width.

        A missing/unreadable image is a no-op (logged) so a render is never
        broken by a watermark whose source file moved after the op was added.
        """
        if not self.image_path or not os.path.exists(self.image_path):
            get_logger().warning(f"Watermark image missing: {self.image_path!r}")
            return
        try:
            pix = fitz.Pixmap(self.image_path)
            if not pix.alpha:
                pix = fitz.Pixmap(pix, 1)  # add an alpha channel
            alpha = max(0, min(255, int(self.opacity * 255)))
            pix.set_alpha(bytes([alpha] * (pix.width * pix.height)))
        except Exception as e:  # PyMuPDF/IO errors -> skip, don't break render
            get_logger().warning(f"Watermark image load failed: {e}")
            return

        target_w = page.rect.width * self.scale
        target_h = target_w * pix.height / pix.width
        cx, cy = page.rect.width / 2, page.rect.height / 2
        rect = fitz.Rect(
            cx - target_w / 2,
            cy - target_h / 2,
            cx + target_w / 2,
            cy + target_h / 2,
        )
        page.insert_image(rect, pixmap=pix, keep_proportion=True, rotate=self.rotate)

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update(
            {
                "image_path": self.image_path,
                "opacity": self.opacity,
                "scale": self.scale,
                "rotate": self.rotate,
            }
        )
        return data
