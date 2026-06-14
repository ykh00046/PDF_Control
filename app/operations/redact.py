"""Redaction operations: delete and replace text regions.

Split out of the former monolithic ``app/model.py`` (model-restructure).
"""

from typing import Any, Dict, List, Optional, Tuple

import fitz

from app.operations.base import Operation


class RedactDelete(Operation):
    """Represents a redaction operation to delete content."""

    def __init__(self, page_index: int, rects: List[fitz.Rect]) -> None:
        super().__init__(page_index, rects)

    def apply(self, page: fitz.Page) -> None:
        for rect in self.rects:
            page.add_redact_annot(rect, fill=(1, 1, 1))

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
        align: int = 0,
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

    def apply(self, page: fitz.Page) -> None:
        for rect in self.rects:
            page.add_redact_annot(rect, fill=(1, 1, 1))

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
