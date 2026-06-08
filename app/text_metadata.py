"""Font metadata extraction from PDF text spans.

Split out of the former monolithic ``app/model.py`` (model-restructure).
Behavior is preserved exactly, including the rect-based fontsize fallback
literals (0.6 ratio, 8..72 clamp).
"""
from typing import Any, Dict

import fitz

from app.logger import get_logger


def _extract_text_metadata(page: fitz.Page, original_rect: fitz.Rect) -> Dict[str, Any]:
    """Extracts font metadata (size, color, flags) based on original text intersecting the rect."""
    metadata = {
        "fontsize": 0.0,
        "color": (0, 0, 0),
        "font_flags": 0,
        "fontname": "helv"
    }

    sizes = []
    colors = []
    flags = []
    fontnames = []

    text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_LIGATURES | fitz.TEXT_PRESERVE_WHITESPACE)
    for block in text_dict["blocks"]:
        if block["type"] != 0:
            continue  # Only text blocks
        for line in block["lines"]:
            for span in line["spans"]:
                span_rect = fitz.Rect(span["bbox"])
                if span_rect.intersects(original_rect):
                    sizes.append(span["size"])
                    # Convert integer color to RGB tuple
                    c = span["color"]
                    colors.append(((c >> 16 & 255) / 255, (c >> 8 & 255) / 255, (c & 255) / 255))
                    flags.append(span["flags"])
                    fontnames.append(span["font"])

    # Calculate rect-based fontsize as fallback
    rect_height = original_rect.height
    rect_based_fontsize = rect_height * 0.6
    rect_based_fontsize = max(8, min(rect_based_fontsize, 72))

    if sizes:
        metadata["fontsize"] = max(sum(sizes) / len(sizes), rect_based_fontsize)
        # Use most frequent color/flags/fontname if multiple exist
        metadata["color"] = max(set(colors), key=colors.count)
        metadata["font_flags"] = max(set(flags), key=flags.count)
        metadata["fontname"] = max(set(fontnames), key=fontnames.count)

        get_logger().debug(
            f"Extracted metadata: {metadata['fontsize']:.1f}pt, color={metadata['color']}, "
            f"flags={metadata['font_flags']}, font={metadata['fontname']}"
        )
    else:
        metadata["fontsize"] = rect_based_fontsize
        get_logger().debug(f"Fallback metadata: {metadata['fontsize']:.1f}pt from rect height")

    return metadata
