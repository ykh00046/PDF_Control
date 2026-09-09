"""Page probes that make a text replacement blend into its surroundings.

Pure helpers over a :class:`fitz.Page` (no Qt), used by the applicator:

* :func:`sample_background_color` -- dominant color of the thin ring just
  outside a rect, so a redaction/replacement fills with the page's real
  background (light-blue header bar, grey table row) instead of white.
* :func:`line_free_space` -- how far a replacement may extend left/right on
  the same text line before it would collide with the next glyph or a
  vertical rule (table cell border).
* :func:`baseline_pitch` -- distance between consecutive line baselines
  inside a rect, so multi-line replacements keep the paragraph's leading.
* :func:`is_numeric_text` -- "looks like a number/amount" heuristic used to
  auto right-align replacements of table figures.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, List, Optional, Sequence, Tuple

import fitz

RGB = Tuple[float, float, float]
WHITE: RGB = (1.0, 1.0, 1.0)

# Pixels this close to pure white are treated as white (avoids a faint grey
# fill on a white page caused by anti-aliasing / JPEG noise).
_WHITE_THRESHOLD = 246
# Color quantization step for the mode computation (8 levels per channel).
_QUANT = 8
# Ring thickness (in page points) sampled around the rect.
_RING_PT = 2.0

_NUMERIC_RE = re.compile(r"^[\s\d.,%()+\-/:$€£¥₩#x×]*\d[\s\d.,%()+\-/:$€£¥₩#x×]*$")


def sample_background_color(page: fitz.Page, rect: fitz.Rect, pixmap: Optional[fitz.Pixmap] = None) -> RGB:
    """Return the dominant color in a 2pt ring around ``rect`` (0..1 RGB).

    ``pixmap`` may be a cached 72-dpi render of the page (``page.get_pixmap()``)
    so many rects can be probed with one render. Text pixels inside the ring
    are a minority, so the quantized mode is the background. Anything close
    to white collapses to exact white.
    """
    outer = fitz.Rect(rect).normalize()
    outer = fitz.Rect(outer.x0 - _RING_PT, outer.y0 - _RING_PT, outer.x1 + _RING_PT, outer.y1 + _RING_PT)
    outer = outer & page.rect
    if outer.is_empty or outer.width < 1 or outer.height < 1:
        return WHITE
    inner = fitz.Rect(rect).normalize() & page.rect
    try:
        pix = pixmap if pixmap is not None else page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
    except (RuntimeError, ValueError):
        return WHITE
    if pix.n < 3:
        return WHITE

    counts: Counter = Counter()
    x_start, x_end = int(outer.x0), int(outer.x1)
    y_start, y_end = int(outer.y0), int(outer.y1)
    for y in range(max(y_start, 0), min(y_end, pix.height)):
        for x in range(max(x_start, 0), min(x_end, pix.width)):
            # Skip the interior (the text being replaced); keep the ring only.
            if inner.x0 <= x < inner.x1 and inner.y0 <= y < inner.y1:
                continue
            r, g, b = pix.pixel(x, y)[:3]
            counts[(r // _QUANT, g // _QUANT, b // _QUANT)] += 1
    if not counts:
        return WHITE
    (qr, qg, qb), _ = counts.most_common(1)[0]
    r, g, b = (qr * _QUANT + _QUANT // 2, qg * _QUANT + _QUANT // 2, qb * _QUANT + _QUANT // 2)
    if min(r, g, b) >= _WHITE_THRESHOLD:
        return WHITE
    return (min(r, 255) / 255.0, min(g, 255) / 255.0, min(b, 255) / 255.0)


def _vertical_rules(drawings: Sequence[Dict[str, Any]]) -> List[Tuple[float, float, float]]:
    """Extract (x, y0, y1) vertical strokes from ``page.get_drawings()`` output."""
    rules: List[Tuple[float, float, float]] = []
    for path in drawings:
        for item in path.get("items", []):
            kind = item[0]
            if kind == "l":
                p1, p2 = item[1], item[2]
                if abs(p1.x - p2.x) < 0.75 and abs(p1.y - p2.y) > 1.0:
                    rules.append((p1.x, min(p1.y, p2.y), max(p1.y, p2.y)))
            elif kind == "re":
                r = item[1]
                if r.height > 1.0:
                    rules.append((r.x0, r.y0, r.y1))
                    rules.append((r.x1, r.y0, r.y1))
    return rules


def line_free_space(
    page: fitz.Page,
    rect: fitz.Rect,
    words: Optional[Sequence[Sequence[Any]]] = None,
    drawings: Optional[Sequence[Dict[str, Any]]] = None,
    margin: float = 18.0,
) -> Tuple[float, float]:
    """Return ``(limit_left, limit_right)``: x bounds a replacement may reach.

    Bounds are the nearest glyph box or vertical rule on the same line
    (vertical overlap with ``rect``), otherwise the page edge minus
    ``margin``. ``words``/``drawings`` accept cached ``page.get_text("words")``
    and ``page.get_drawings()`` results so callers can probe many rects
    without re-extracting the page each time.
    """
    rect = fitz.Rect(rect).normalize()
    y_mid = (rect.y0 + rect.y1) / 2
    limit_left = margin
    limit_right = page.rect.x1 - margin

    if words is None:
        words = page.get_text("words")
    for w in words:
        x0, y0, x1, y1 = w[0], w[1], w[2], w[3]
        if y1 <= rect.y0 or y0 >= rect.y1:
            continue  # different line
        if not (y0 <= y_mid <= y1 or rect.y0 <= (y0 + y1) / 2 <= rect.y1):
            continue
        if x1 <= rect.x0 + 0.5:
            limit_left = max(limit_left, x1)
        elif x0 >= rect.x1 - 0.5:
            limit_right = min(limit_right, x0)

    if drawings is None:
        drawings = []
    for x, y0, y1 in _vertical_rules(drawings):
        if y1 < rect.y0 or y0 > rect.y1:
            continue
        if x <= rect.x0 + 0.5:
            limit_left = max(limit_left, x)
        elif x >= rect.x1 - 0.5:
            limit_right = min(limit_right, x)

    return limit_left, limit_right


def glyph_follows(
    rect: fitz.Rect,
    words: Sequence[Sequence[Any]],
    within: float,
) -> bool:
    """True when another glyph box starts within ``within`` pt right of ``rect``
    on the same line -- i.e. the source is mid-sentence, not the last item
    of a table cell / line."""
    rect = fitz.Rect(rect).normalize()
    y_mid = (rect.y0 + rect.y1) / 2
    for w in words:
        x0, y0, y1 = w[0], w[1], w[3]
        if not (y0 <= y_mid <= y1):
            continue
        if rect.x1 - 0.5 <= x0 <= rect.x1 + within:
            return True
    return False


def baseline_pitch(baselines: Sequence[float]) -> Optional[float]:
    """Median distance between consecutive distinct baselines (None if < 2 lines)."""
    ys = sorted({round(b, 2) for b in baselines})
    if len(ys) < 2:
        return None
    gaps = sorted(b - a for a, b in zip(ys, ys[1:]) if b - a > 0.5)
    if not gaps:
        return None
    return gaps[len(gaps) // 2]


def is_numeric_text(text: str) -> bool:
    """True for amounts, quantities, dates-as-digits: '1,234.00', '12%', '(45)'."""
    stripped = (text or "").strip()
    return bool(stripped) and bool(_NUMERIC_RE.match(stripped))
