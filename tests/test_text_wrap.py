"""Tests for the text-wrap-replace feature.

Verifies the wrap-first policy in OperationApplicator._insert_text_with_autofit:
long replacement text is wrapped onto multiple lines (preserving font size)
instead of being shrunk, with font shrinking kept as a fallback for cases
wrapping cannot solve (an unbreakable word wider than the box, or no vertical
room before the page edge).
"""

import fitz
import pytest

from app import config
from app.model import RedactReplace
from app.operations_service import ApplyMode, OperationApplicator


def _make_page(width: float = 595, height: float = 842) -> fitz.Page:
    doc = fitz.open()
    return doc.new_page(width=width, height=height)


def test_long_text_wraps_instead_of_shrinking():
    """Short words + a tall page should wrap (info) rather than shrink (warn)."""
    page = _make_page()
    # Box is moderately wide so each short word fits the line width, but the
    # whole string is far too long for one line.
    long_text = "one two one two one two one two one two one two one two one two"
    op = RedactReplace(
        0,
        [fitz.Rect(50, 90, 250, 110)],  # width 200, near top of a tall page
        long_text,
        fontsize=12,
    )
    result = OperationApplicator().apply_operations(page, [op], mode=ApplyMode.PREVIEW)

    wrapped = [w for w in result.warnings if w.code == "text.wrapped"]
    shrunk = [w for w in result.warnings if w.code == "text.shrunk"]

    assert wrapped, f"expected text.wrapped, got {result.warnings}"
    assert not shrunk, f"should not shrink when wrapping fits: {result.warnings}"
    w = wrapped[0]
    assert w.severity == "info"
    assert w.detail["lines"] > 1
    # Font size preserved (wrapping, not shrinking).
    assert w.detail["fontsize"] == pytest.approx(12, abs=0.01)
    assert result.has_errors is False


def test_long_word_falls_back_to_shrink():
    """An unbreakable word wider than the box cannot wrap -> shrink fallback."""
    page = _make_page()
    op = RedactReplace(
        0,
        [fitz.Rect(50, 90, 130, 110)],  # narrow: 80pt wide
        "A somewhat long replacement",  # "replacement" alone overflows the width
        fontsize=18,
    )
    result = OperationApplicator().apply_operations(page, [op], mode=ApplyMode.PREVIEW)

    shrunk = [w for w in result.warnings if w.code == "text.shrunk"]
    wrapped = [w for w in result.warnings if w.code == "text.wrapped"]
    assert shrunk, f"expected text.shrunk fallback, got {result.warnings}"
    assert not wrapped, "long unbreakable word should not wrap"


def test_wrap_respects_page_bottom():
    """A box near the page bottom has no room to expand -> must not wrap there.

    With insufficient vertical room the code falls back to shrinking; either
    way it must never overflow the page or silently drop text.
    """
    page = _make_page(height=200)
    long_text = "one two one two one two one two one two one two one two one two"
    # Place the box so only a few points remain below it.
    op = RedactReplace(
        0,
        [fitz.Rect(20, 180, 180, 195)],  # y1=195 on a 200pt-tall page
        long_text,
        fontsize=12,
    )
    result = OperationApplicator().apply_operations(page, [op], mode=ApplyMode.PREVIEW)

    # No wrap should claim more vertical space than the page has.
    for w in result.warnings:
        if w.code == "text.wrapped":
            line_h = 12 * config.TEXT_WRAP_LINE_HEIGHT_FACTOR
            needed = w.detail["lines"] * line_h
            assert 180 + needed <= page.rect.y1 + 1e-6


def test_wrap_disabled_falls_back_to_shrink(monkeypatch):
    """With the wrap policy off, long text shrinks as before."""
    monkeypatch.setattr(
        "app.operations.applicator.TEXT_WRAP_ENABLED", False
    )
    page = _make_page()
    long_text = "one two one two one two one two one two one two one two one two"
    op = RedactReplace(
        0,
        [fitz.Rect(50, 90, 250, 110)],
        long_text,
        fontsize=12,
    )
    result = OperationApplicator().apply_operations(page, [op], mode=ApplyMode.PREVIEW)

    assert not [w for w in result.warnings if w.code == "text.wrapped"]
    assert [w for w in result.warnings if w.code == "text.shrunk"]
