"""Font metadata extraction from PDF text spans.

Split out of the former monolithic ``app/model.py`` (model-restructure).
Since text-fidelity (2026-06-11) the extracted span fontsize is trusted
as-is; the rect-based estimate (0.6 ratio, 8..72 clamp) only applies when
no text intersects the rect. The first-line baseline is extracted so the
replacement can be anchored on the original baseline.
"""

from typing import Any, Dict, List, Optional, Sequence

import fitz

from app.logger import get_logger
from app.page_probe import baseline_pitch, glyph_follows, line_free_space


def _extract_text_metadata(
    page: fitz.Page,
    original_rect: fitz.Rect,
    words: Optional[Sequence[Sequence[Any]]] = None,
    drawings: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Extract font metadata (size, color, flags, baseline, leading, free space).

    ``words``/``drawings`` are optional cached ``page.get_text("words")`` /
    ``page.get_drawings()`` results; the applicator passes them so a batch
    of replacements probes the page once. Without ``drawings`` only glyphs
    bound the free space (no table-rule detection).
    """
    metadata: Dict[str, Any] = {
        "fontsize": 0.0,
        "color": (0, 0, 0),
        "font_flags": 0,
        "fontname": "helv",
        "baseline": None,
        "line_pitch": None,
        "limit_left": None,
        "limit_right": None,
        "source_text": "",
        # A glyph starts right after the rect on the same line (mid-sentence).
        "glyph_after": False,
    }

    sizes: List[float] = []
    colors = []
    flags = []
    fontnames = []
    baselines: List[float] = []

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
                    baselines.append(span["origin"][1])

    if sizes:
        # Trust the extracted size; the rect is a selection box, not a glyph
        # measure, so it must never inflate the replacement (text-fidelity).
        metadata["fontsize"] = sum(sizes) / len(sizes)
        # Use most frequent color/flags/fontname if multiple exist
        metadata["color"] = max(set(colors), key=colors.count)
        metadata["font_flags"] = max(set(flags), key=flags.count)
        metadata["fontname"] = max(set(fontnames), key=fontnames.count)
        # Topmost (first-line) baseline anchors the replacement vertically.
        metadata["baseline"] = min(baselines)
        metadata["line_pitch"] = baseline_pitch(baselines)

        get_logger().debug(
            f"Extracted metadata: {metadata['fontsize']:.1f}pt, color={metadata['color']}, "
            f"flags={metadata['font_flags']}, font={metadata['fontname']}, "
            f"baseline={metadata['baseline']:.1f}"
        )
    else:
        # Fallback: estimate from the selection rect height (no text found).
        rect_based_fontsize = original_rect.height * 0.6
        metadata["fontsize"] = max(8, min(rect_based_fontsize, 72))
        get_logger().debug(f"Fallback metadata: {metadata['fontsize']:.1f}pt from rect height")

    try:
        metadata["source_text"] = page.get_textbox(original_rect).strip()
    except (RuntimeError, ValueError):
        metadata["source_text"] = ""
    try:
        if words is None:
            words = page.get_text("words")
        limit_left, limit_right = line_free_space(page, original_rect, words=words, drawings=drawings)
        metadata["limit_left"] = limit_left
        metadata["limit_right"] = limit_right
        metadata["glyph_after"] = glyph_follows(original_rect, words, within=1.5 * float(metadata["fontsize"]))
    except (RuntimeError, ValueError, TypeError):
        pass

    return metadata
