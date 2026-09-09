"""Redaction operations: delete and replace text regions.

Split out of the former monolithic ``app/model.py`` (model-restructure).
"""

from typing import Any, Dict, List, Optional, Tuple

import fitz

from app.operations.base import Operation

RGB = Tuple[float, float, float]
WHITE: RGB = (1.0, 1.0, 1.0)

# RedactReplace.align values (PyMuPDF convention for 0/1/2, -1 = decide from
# the source text: numbers/amounts right-align, everything else left).
ALIGN_AUTO = -1
ALIGN_LEFT = 0
ALIGN_CENTER = 1
ALIGN_RIGHT = 2


class RedactDelete(Operation):
    """Represents a redaction operation to delete content."""

    def __init__(self, page_index: int, rects: List[fitz.Rect]) -> None:
        super().__init__(page_index, rects)

    def apply(self, page: fitz.Page, fill: Optional[RGB] = None) -> None:
        """Queue redaction annotations; ``fill`` is the sampled page background."""
        for rect in self.rects:
            page.add_redact_annot(rect, fill=fill or WHITE)

    def to_dict(self) -> Dict[str, Any]:
        return super().to_dict()


class RedactReplace(Operation):
    """Represents a redaction operation to replace content with new text."""

    def __init__(
        self,
        page_index: int,
        rects: List[fitz.Rect],
        new_text: str,
        fontname: str = "helv",
        fontsize: float = 0,
        align: int = ALIGN_AUTO,
        fontfile: Optional[str] = None,
        color: Optional[Tuple[float, float, float]] = None,
        font_flags: int = 0,
        wrap: Optional[bool] = None,
    ) -> None:
        super().__init__(page_index, rects)
        self.new_text = new_text
        self.fontname = fontname
        self.fontsize = fontsize
        self.align = align
        self.fontfile = fontfile
        self.color = color  # RGB tuple (0-1)
        self.font_flags = font_flags  # PyMuPDF font flags
        # Per-operation word-wrap policy for overflowing replacement text:
        #   None  -> follow the global TEXT_WRAP_ENABLED default
        #   True  -> wrap onto multiple lines (preserve font size)
        #   False -> skip wrapping, shrink the font instead
        self.wrap = wrap

    def apply(self, page: fitz.Page, fill: Optional[RGB] = None) -> None:
        """Queue redaction annotations; ``fill`` is the sampled page background."""
        for rect in self.rects:
            page.add_redact_annot(rect, fill=fill or WHITE)

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update(
            {
                "new_text": self.new_text,
                "fontname": self.fontname,
                "fontsize": self.fontsize,
                "align": self.align,
                "fontfile": self.fontfile,
                "color": list(self.color) if self.color else None,
                "font_flags": self.font_flags,
                "wrap": self.wrap,
            }
        )
        return data
