"""Tests for long-text-narrow-area-warning feature.

Covers the structured warning emission in operations_service.OperationApplicator,
the session-level warning cache, and basic i18n key completeness for the new
warn.* keys.
"""

import json
from pathlib import Path

import fitz
import pytest

from app.model import DocumentSession, RedactReplace
from app.operations_service import (
    ApplyMode,
    ApplyResult,
    OperationApplicator,
    OpWarning,
)

ROOT = Path(__file__).parent.parent


def _make_page(width: float = 595, height: float = 842) -> fitz.Page:
    doc = fitz.open()
    return doc.new_page(width=width, height=height)


def test_normal_replace_emits_no_warnings():
    """A replacement that easily fits should leave warnings empty."""
    page = _make_page()
    page.insert_text((50, 100), "ORIGINAL", fontsize=12)

    op = RedactReplace(0, [fitz.Rect(50, 90, 200, 110)], "HELLO", fontsize=10)
    applicator = OperationApplicator()
    result = applicator.apply_operations(page, [op], mode=ApplyMode.PREVIEW)

    assert isinstance(result, ApplyResult)
    assert result.warnings == []
    assert result.has_errors is False


def test_narrow_rect_long_text_emits_shrink_warning():
    """Narrow rect with long replacement should emit severity=warn, code=text.shrunk."""
    page = _make_page()
    page.insert_text((50, 100), "X", fontsize=12)

    op = RedactReplace(
        0,
        [fitz.Rect(50, 90, 130, 110)],  # narrow but not impossible
        "A somewhat long replacement",
        fontsize=18,
    )
    applicator = OperationApplicator()
    result = applicator.apply_operations(page, [op], mode=ApplyMode.PREVIEW)

    shrink_warnings = [w for w in result.warnings if w.code == "text.shrunk"]
    assert shrink_warnings, f"expected text.shrunk, got {result.warnings}"
    w = shrink_warnings[0]
    assert w.severity == "warn"
    assert w.op_index == 0
    assert w.detail["text_len"] > 0
    assert w.detail["fontsize_to"] <= w.detail["fontsize_from"]


def test_impossible_rect_emits_overflow_error():
    """A 1x1 rect with a long string should trigger severity=error, code=text.overflow."""
    page = _make_page()
    page.insert_text((50, 100), "X", fontsize=12)

    op = RedactReplace(
        0,
        [fitz.Rect(50, 90, 51, 91)],
        "This text literally cannot fit in a one-point square",
        fontsize=12,
    )
    applicator = OperationApplicator()
    result = applicator.apply_operations(page, [op], mode=ApplyMode.PREVIEW)

    overflow = [w for w in result.warnings if w.code == "text.overflow"]
    assert overflow, f"expected text.overflow, got {result.warnings}"
    assert overflow[0].severity == "error"
    assert result.has_errors is True


def test_opwarning_properties_derive_counts():
    """font_size_adjustments and text_shrink_count are derived from warnings."""
    result = ApplyResult(success=True, operations_applied=0)
    result.warnings = [
        OpWarning(op_index=0, severity="warn", code="text.shrunk", detail={}),
        OpWarning(op_index=1, severity="warn", code="text.shrunk", detail={}),
        OpWarning(op_index=2, severity="error", code="text.overflow", detail={}),
    ]
    assert result.text_shrink_count == 2
    assert result.font_size_adjustments == 2
    assert result.has_errors is True


def test_session_update_warnings_cache_and_signal(simple_pdf, qtbot):
    """DocumentSession.update_warnings stores entries and emits warnings_changed."""
    session = DocumentSession(str(simple_pdf))

    with qtbot.waitSignal(session.warnings_changed, timeout=1000):
        session.update_warnings(0, [{"op_index": 0, "severity": "warn", "code": "text.shrunk", "detail": {}}])

    assert 0 in session.last_preview_warnings
    assert session.last_preview_warnings[0][0]["code"] == "text.shrunk"
    assert session.has_blocking_warnings() is False

    with qtbot.waitSignal(session.warnings_changed, timeout=1000):
        session.update_warnings(0, [{"op_index": 0, "severity": "error", "code": "text.overflow", "detail": {}}])
    assert session.has_blocking_warnings() is True

    # Passing an empty list clears the page entry.
    with qtbot.waitSignal(session.warnings_changed, timeout=1000):
        session.update_warnings(0, [])
    assert 0 not in session.last_preview_warnings


@pytest.mark.parametrize("lang", ["en", "ko"])
def test_warning_i18n_keys_present(lang):
    """All new warn.* keys must exist in both locale files."""
    with open(ROOT / "app" / "i18n" / f"{lang}.json", encoding="utf-8") as handle:
        data = json.load(handle)

    required = {
        "warn.indicator.label",
        "warn.indicator.tooltip",
        "warn.details.title",
        "warn.details.none",
        "warn.code.text.shrunk",
        "warn.code.text.overflow",
        "warn.code.text.wrapped",
        "warn.history.badge_shrunk",
        "warn.history.badge_overflow",
        "warn.history.badge_wrapped",
        "warn.save_with_errors.title",
        "warn.save_with_errors.body",
    }
    missing = required - data.keys()
    assert not missing, f"{lang} missing keys: {sorted(missing)}"
