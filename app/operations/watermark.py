"""Text and image watermark operations (semi-transparent overlays).

Non-destructive overlays: they add content on top of the page without
removing anything, so the SAVE and PREVIEW paths share the same apply()
(no mode-specific branch). Text uses TextWriter + a morph matrix (arbitrary
rotation); images use insert_image with a Pixmap alpha channel for opacity
(insert_image has no opacity param and only rotates in 90-degree steps).

Each watermark is either centered (default) or tiled across the page in an
auto-sized grid (``tile=True``), or placed at one of four page corners.
"""

import math
import os
from typing import Any, Dict, List, Literal, Tuple, cast

import fitz

from app.config import TILE_SPACING_FACTOR
from app.logger import get_logger
from app.operations.base import Operation

WatermarkPosition = Literal["center", "top-left", "top-right", "bottom-left", "bottom-right"]
POSITION_OPTIONS: Tuple[WatermarkPosition, ...] = (
    "center",
    "top-left",
    "top-right",
    "bottom-left",
    "bottom-right",
)
WATERMARK_MARGIN = 36.0


def _validate_position(position: str) -> WatermarkPosition:
    if position not in POSITION_OPTIONS:
        raise ValueError(f"Unsupported watermark position: {position!r}")
    return cast(WatermarkPosition, position)


def _rotated_size(width: float, height: float, angle: float) -> Tuple[float, float]:
    """Return the axis-aligned size of a rectangle rotated by ``angle``."""
    radians = math.radians(angle % 360)
    cosine = abs(math.cos(radians))
    sine = abs(math.sin(radians))
    return width * cosine + height * sine, width * sine + height * cosine


def _placement_center(
    page_rect: fitz.Rect,
    width: float,
    height: float,
    position: WatermarkPosition,
    margin: float = WATERMARK_MARGIN,
) -> Tuple[float, float]:
    """Return a placement center, falling back to center on an oversized axis."""
    half_width = width / 2
    half_height = height / 2
    page_center_x = page_rect.x0 + page_rect.width / 2
    page_center_y = page_rect.y0 + page_rect.height / 2

    if position == "center":
        return page_center_x, page_center_y

    fits_x = width + 2 * margin <= page_rect.width
    fits_y = height + 2 * margin <= page_rect.height
    if fits_x:
        center_x = (
            page_rect.x0 + margin + half_width if position.endswith("left") else page_rect.x1 - margin - half_width
        )
    else:
        center_x = page_center_x
    if fits_y:
        center_y = (
            page_rect.y0 + margin + half_height if position.startswith("top") else page_rect.y1 - margin - half_height
        )
    else:
        center_y = page_center_y
    return center_x, center_y


def _tile_centers(page_rect: fitz.Rect, cell_size: float) -> List[Tuple[float, float]]:
    """Centers of an auto-sized grid covering the page (cell ~= cell_size)."""
    cell = max(cell_size, 1.0)
    cols = max(1, int(page_rect.width / cell))
    rows = max(1, int(page_rect.height / cell))
    step_x = page_rect.width / cols
    step_y = page_rect.height / rows
    return [((c + 0.5) * step_x, (r + 0.5) * step_y) for r in range(rows) for c in range(cols)]


class WatermarkText(Operation):
    """A rotated, semi-transparent text watermark, centered or tiled."""

    def __init__(
        self,
        page_index: int,
        text: str,
        fontsize: float = 40.0,
        color: Tuple[float, float, float] = (0.5, 0.5, 0.5),
        opacity: float = 0.3,
        angle: float = 45.0,
        tile: bool = False,
        position: WatermarkPosition = "center",
    ) -> None:
        super().__init__(page_index, [])  # watermark uses no selection rects
        self.text = text
        self.fontsize = fontsize
        self.color = color  # RGB tuple, 0-1
        self.opacity = opacity  # 0-1 (1 = opaque)
        self.angle = angle  # degrees, counter-clockwise
        self.tile = tile  # repeat across the page in a grid
        self.position = _validate_position(position)

    def apply(self, page: fitz.Page) -> None:
        """Draw the watermark centered, or tiled across the page when ``tile``."""
        if not self.text:
            return
        font = fitz.Font("helv")
        text_width = font.text_length(self.text, fontsize=self.fontsize)

        if self.tile:
            cell = max(text_width, self.fontsize) * TILE_SPACING_FACTOR
            centers = _tile_centers(page.rect, cell)
        else:
            # Design Ref: §9 — use rotated bounds so corner placements retain a safe margin.
            rotated_width, rotated_height = _rotated_size(text_width, self.fontsize, self.angle)
            centers = [_placement_center(page.rect, rotated_width, rotated_height, self.position)]

        for center_x, center_y in centers:
            self._draw_at(page, font, text_width, center_x, center_y)

    def _draw_at(
        self,
        page: fitz.Page,
        font: "fitz.Font",
        text_width: float,
        center_x: float,
        center_y: float,
    ) -> None:
        """Draw one rotated text instance centered at (center_x, center_y)."""
        writer = fitz.TextWriter(page.rect, opacity=self.opacity, color=self.color)
        writer.append(
            (center_x - text_width / 2, center_y),
            self.text,
            font=font,
            fontsize=self.fontsize,
        )
        writer.write_text(page, morph=(fitz.Point(center_x, center_y), fitz.Matrix(self.angle)))

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update(
            {
                "text": self.text,
                "fontsize": self.fontsize,
                "color": list(self.color),
                "opacity": self.opacity,
                "angle": self.angle,
                "tile": self.tile,
                "position": self.position,
            }
        )
        return data


class WatermarkImage(Operation):
    """A semi-transparent image watermark, centered or tiled.

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
        tile: bool = False,
        position: WatermarkPosition = "center",
    ) -> None:
        super().__init__(page_index, [])  # no selection rects
        self.image_path = image_path
        self.opacity = opacity  # 0-1
        self.scale = scale  # fraction of page WIDTH
        self.rotate = rotate  # 0/90/180/270 (insert_image limitation)
        self.tile = tile  # repeat across the page in a grid
        self.position = _validate_position(position)

    def apply(self, page: fitz.Page) -> None:
        """Draw the image centered, or tiled across the page when ``tile``.

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

        if self.tile:
            cell = max(target_w, target_h) * TILE_SPACING_FACTOR
            centers = _tile_centers(page.rect, cell)
        else:
            # insert_image rotates inside this target rectangle; unlike TextWriter,
            # the occupied page bounds do not rotate with the image content.
            centers = [_placement_center(page.rect, target_w, target_h, self.position)]

        # Embed once on the first placement, then reuse its xref so a tiled
        # image isn't stored N times.
        img_xref = 0
        for center_x, center_y in centers:
            rect = fitz.Rect(
                center_x - target_w / 2,
                center_y - target_h / 2,
                center_x + target_w / 2,
                center_y + target_h / 2,
            )
            if img_xref:
                page.insert_image(rect, xref=img_xref, rotate=self.rotate)
            else:
                img_xref = page.insert_image(rect, pixmap=pix, keep_proportion=True, rotate=self.rotate)

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update(
            {
                "image_path": self.image_path,
                "opacity": self.opacity,
                "scale": self.scale,
                "rotate": self.rotate,
                "tile": self.tile,
                "position": self.position,
            }
        )
        return data
