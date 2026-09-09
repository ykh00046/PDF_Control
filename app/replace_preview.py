"""Live preview for the replace dialog.

Renders "what the page will look like" around one selection with a
candidate replacement applied, on a throw-away single-page copy, so the
user can tune text / alignment / size / wrap before committing. Pure
PyMuPDF (no Qt) -- the dialog converts the pixmap to a QImage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import fitz

from app.operations import ApplyMode
from app.operations.redact import ALIGN_AUTO, RedactReplace
from app.pdf_engine import apply_page_operations

PREVIEW_SCALE = 2.0
PREVIEW_MARGIN_X = 70.0
PREVIEW_MARGIN_Y = 26.0


@dataclass
class PreviewContext:
    """Everything the preview needs about the selection being replaced."""

    doc: fitz.Document
    page_index: int
    rect: fitz.Rect
    fontname: str
    fontfile: Optional[str]
    fontsize: float
    color: Tuple[float, float, float]
    font_flags: int


def preview_clip(page_rect: fitz.Rect, rect: fitz.Rect) -> fitz.Rect:
    """Region shown in the preview: the selection plus some context."""
    clip = fitz.Rect(
        rect.x0 - PREVIEW_MARGIN_X,
        rect.y0 - PREVIEW_MARGIN_Y,
        rect.x1 + PREVIEW_MARGIN_X * 2,
        rect.y1 + PREVIEW_MARGIN_Y * 2,
    )
    return clip & page_rect


def render_replacement_preview(
    ctx: PreviewContext,
    settings: Dict[str, Any],
    scale: float = PREVIEW_SCALE,
) -> Tuple[fitz.Pixmap, str]:
    """Return ``(pixmap, page_text)`` of the clip with the replacement applied.

    ``settings`` is the replace dialog's dict (``text``, ``align``, ``wrap``,
    ``fontsize`` where 0 means "same as source"). An empty text previews the
    plain deletion. ``page_text`` is the resulting text inside the clip
    (used by tests; cheap to compute).
    """
    preview_doc = fitz.open()
    try:
        preview_doc.insert_pdf(ctx.doc, from_page=ctx.page_index, to_page=ctx.page_index)
        page = preview_doc[0]
        chosen = float(settings.get("fontsize") or 0.0)
        op = RedactReplace(
            0,
            [fitz.Rect(ctx.rect)],
            settings.get("text", "") or "",
            fontname=ctx.fontname,
            fontfile=ctx.fontfile,
            fontsize=chosen if chosen > 0 else ctx.fontsize,
            color=ctx.color,
            font_flags=ctx.font_flags,
            align=settings.get("align", ALIGN_AUTO),
            wrap=settings.get("wrap"),
        )
        apply_page_operations(page, [op], mode=ApplyMode.PREVIEW)
        clip = preview_clip(page.rect, ctx.rect)
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip, alpha=False)
        text = page.get_text("text", clip=clip)
        return pix, text
    finally:
        preview_doc.close()
