"""Integration tests for replacement fidelity (text-fidelity PDCA).

Verifies that a replacement keeps the source's typeface (system-font
matching), size (no rect-based inflation), and vertical position
(baseline anchoring). Uses Arial from the Windows font directory; tests
are skipped where it is unavailable (non-Windows CI).
"""
import os

import fitz
import pytest

from app.fonts import resolve_pdf_fontname
from app.operations import ApplyMode, OperationApplicator
from app.operations.redact import RedactReplace
from app.text_metadata import _extract_text_metadata

ARIAL_PATH = os.path.join(
    os.environ.get("SystemRoot", "C:\\Windows"), "Fonts", "arial.ttf"
)

requires_arial = pytest.mark.skipif(
    not os.path.exists(ARIAL_PATH), reason="Arial font file not available"
)

ORIGINAL_TEXT = "Original sample text"


def _make_arial_pdf(tmp_path, fontsize=10.0):
    """Single-page PDF with one Arial line; returns (path, text rect, baseline)."""
    path = tmp_path / "arial_source.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text(
        (72, 200), ORIGINAL_TEXT,
        fontsize=fontsize, fontname="srcfont", fontfile=ARIAL_PATH,
    )
    rects = page.search_for(ORIGINAL_TEXT)
    assert rects, "source text not found after insertion"
    meta = _extract_text_metadata(page, rects[0])
    doc.save(str(path))
    doc.close()
    return path, rects[0], meta


def _replaced_spans(pdf_path, needle):
    doc = fitz.open(str(pdf_path))
    try:
        # insert_textbox renders inter-word spaces as NBSP (\xa0) in the
        # extracted text -- normalize before matching the needle.
        spans = [
            span
            for block in doc[0].get_text("dict")["blocks"]
            if block["type"] == 0
            for line in block["lines"]
            for span in line["spans"]
            if needle in span["text"].replace("\xa0", " ")
        ]
        return spans
    finally:
        doc.close()


def _apply_replace(tmp_path, src_path, rect, new_text, **op_kwargs):
    out = tmp_path / "replaced.pdf"
    doc = fitz.open(str(src_path))
    page = doc[0]
    op = RedactReplace(0, [fitz.Rect(rect)], new_text, **op_kwargs)
    result = OperationApplicator().apply_operations(page, [op], ApplyMode.SAVE)
    doc.save(str(out))
    doc.close()
    return out, result


# ── M1: system-font matching ─────────────────────────────────────────

@requires_arial
def test_replace_uses_matched_system_font(tmp_path):
    """Without any explicit font choice the replacement stays in Arial."""
    src, rect, _meta = _make_arial_pdf(tmp_path)
    out, _ = _apply_replace(tmp_path, src, rect, "Replaced words")

    spans = _replaced_spans(out, "Replaced")
    assert spans, "replacement text not found in output"
    fontname = spans[0]["font"].lower()
    assert "arial" in fontname, f"expected Arial-family font, got {fontname!r}"


@requires_arial
def test_batch_style_op_gets_matched_font(tmp_path):
    """Batch-created ops carry fontname='helv'; the extracted metadata must
    still drive the match (regression net for the helv-always batch bug)."""
    src, rect, _meta = _make_arial_pdf(tmp_path)
    out, _ = _apply_replace(
        tmp_path, src, rect, "Batch replaced", fontname="helv", fontsize=0
    )

    spans = _replaced_spans(out, "Batch")
    assert spans
    assert "arial" in spans[0]["font"].lower()


@requires_arial
def test_match_rejected_without_glyph_coverage():
    """Arial has no Hangul glyphs, so it must not be chosen for Korean text."""
    assert resolve_pdf_fontname("Arial", must_cover="한글텍스트") is None
    assert resolve_pdf_fontname("Arial", must_cover="latin only") is not None


@requires_arial
def test_uncovered_match_is_not_embedded_end_to_end(tmp_path):
    """Full applicator path: replacing Arial text with Hangul must NOT embed
    Arial for the replacement (coverage rejection -> Base-14 fallback chain)."""
    src, rect, _meta = _make_arial_pdf(tmp_path)
    doc = fitz.open(str(src))
    page = doc[0]
    op = RedactReplace(0, [fitz.Rect(rect)], "한글 텍스트")
    OperationApplicator().apply_operations(page, [op], ApplyMode.SAVE)
    # _prepare_fonts embeds a matched file under its stem alias ("arial");
    # a rejected match must leave no such embedding behind.
    aliases = [entry[3] for entry in page.get_fonts()]
    assert "arial" not in aliases
    doc.close()


# ── M2: baseline anchoring ───────────────────────────────────────────

@requires_arial
def test_replace_preserves_baseline(tmp_path):
    src, rect, meta = _make_arial_pdf(tmp_path)
    assert meta["baseline"] is not None
    out, _ = _apply_replace(tmp_path, src, rect, "Replaced words")

    spans = _replaced_spans(out, "Replaced")
    assert spans
    new_baseline = spans[0]["origin"][1]
    assert abs(new_baseline - meta["baseline"]) <= 1.0, (
        f"baseline drifted: {meta['baseline']:.2f} -> {new_baseline:.2f}"
    )


# ── M3: fontsize must not be inflated by a large selection rect ─────

@requires_arial
def test_extracted_fontsize_not_inflated_by_large_rect(tmp_path):
    src, rect, _meta = _make_arial_pdf(tmp_path, fontsize=10.0)
    # A selection box much taller than the 10pt glyphs (old behavior:
    # rect.height * 0.6 would override the extracted size).
    big_rect = fitz.Rect(rect.x0, rect.y0 - 20, rect.x1 + 40, rect.y1 + 40)
    out, _ = _apply_replace(tmp_path, src, big_rect, "Same size")

    spans = _replaced_spans(out, "Same size")
    assert spans
    assert spans[0]["size"] == pytest.approx(10.0, abs=0.6)


def test_rect_fallback_when_no_text(tmp_path):
    """Empty area: rect-based size estimate survives, baseline is None."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    meta = _extract_text_metadata(page, fitz.Rect(100, 100, 300, 130))
    doc.close()
    assert meta["fontsize"] == pytest.approx(30 * 0.6)
    assert meta["baseline"] is None
