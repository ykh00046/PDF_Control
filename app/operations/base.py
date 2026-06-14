"""Operation abstract base class and deserialization factory.

Split out of the former monolithic ``app/model.py`` (model-restructure).
The concrete operation types live in sibling modules
(:mod:`app.operations.redact`, :mod:`app.operations.crop`,
:mod:`app.operations.remove_section`). ``Operation.from_dict`` imports them
lazily to avoid a base <-> subclass import cycle.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List

import fitz

from app.config import (
    DEFAULT_REMOVE_SECTION_DPI,
    DEFAULT_REMOVE_SECTION_FORMAT,
)


class Operation(ABC):
    """Abstract base class for document modification operations."""

    def __init__(self, page_index: int, rects: List[fitz.Rect]) -> None:
        self.page_index = page_index
        self.rects = rects

    @abstractmethod
    def apply(self, page: fitz.Page) -> None:
        pass

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        return {
            "page_index": self.page_index,
            "rects": [list(r) for r in self.rects],
            "type": self.__class__.__name__,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Operation":
        # Lazy imports keep this base module free of subclass dependencies.
        from app.operations.crop import CropMargins
        from app.operations.redact import RedactDelete, RedactReplace
        from app.operations.remove_section import RemoveSectionAsImage
        from app.operations.watermark import WatermarkText

        op_type = data["type"]
        page_index = data["page_index"]
        rects = [fitz.Rect(r) for r in data["rects"]]
        if op_type == "RedactDelete":
            return RedactDelete(page_index, rects)
        elif op_type == "RedactReplace":
            color = data.get("color", None)
            return RedactReplace(
                page_index, rects, data["new_text"],
                data.get("fontname", "helv"), data.get("fontsize", 0),
                data.get("align", 0), data.get("fontfile", None),
                tuple(color) if color else None,
                data.get("font_flags", 0),
                # Absent key (pre-r4 serialized data) restores to None,
                # i.e. "follow the global TEXT_WRAP_ENABLED default".
                wrap=data.get("wrap", None)
            )
        elif op_type == "CropMargins":
            return CropMargins(
                page_index,
                data.get("top", 0), data.get("bottom", 0),
                data.get("left", 0), data.get("right", 0)
            )
        elif op_type == "RemoveSectionAsImage":
            # RemoveSectionAsImage stores remove_rect separately
            remove_rect = fitz.Rect(data["remove_rect"]) if "remove_rect" in data else fitz.Rect()
            return RemoveSectionAsImage(
                page_index,
                remove_rect,
                data.get("dpi", DEFAULT_REMOVE_SECTION_DPI),
                data.get("format", DEFAULT_REMOVE_SECTION_FORMAT)
            )
        elif op_type == "WatermarkText":
            wm_color = data.get("color")
            return WatermarkText(
                page_index,
                data["text"],
                data.get("fontsize", 40.0),
                tuple(wm_color) if wm_color else (0.5, 0.5, 0.5),
                data.get("opacity", 0.3),
                data.get("angle", 45.0),
            )
        else:
            raise ValueError(f"Unknown operation type: {op_type}")
