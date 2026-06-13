"""Integration tests for replacement fidelity (text-fidelity PDCA).

Verifies that a replacement keeps the source's typeface (system-font
matching), size (no rect-based inflation), and vertical position
(baseline anchoring). Uses Arial from the Windows font directory; tests
are skipped where it is unavailable (non-Windows CI).
"""
import os

import fitz
import pytest

import app.operations.applicator as applicator_module
from app.fonts import extract_embedded_font, resolve_pdf_fontname
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


# ── embedded font reuse (embedded-font-reuse PDCA) ───────────────────

def _reopen(src_path):
    return fitz.open(str(src_path))


def _subset_copy(tmp_path, src_path):
    """Return a copy of src with its embedded fonts reduced to subsets."""
    sub_path = tmp_path / "subset_source.pdf"
    doc = fitz.open(str(src_path))
    doc.subset_fonts()
    doc.save(str(sub_path))
    doc.close()
    return sub_path


@requires_arial
def test_embedded_font_extracted(tmp_path):
    """A fully-embedded source font is extractable and usable."""
    src, _rect, _meta = _make_arial_pdf(tmp_path)
    doc = _reopen(src)
    try:
        buffer = extract_embedded_font(doc[0], "ArialMT", must_cover="Replaced")
        assert buffer, "expected the embedded Arial program"
        assert fitz.Font(fontbuffer=buffer).has_glyph(ord("R"))
    finally:
        doc.close()


@requires_arial
def test_embedded_font_rejects_uncovered(tmp_path):
    src, _rect, _meta = _make_arial_pdf(tmp_path)
    doc = _reopen(src)
    try:
        assert extract_embedded_font(doc[0], "ArialMT", must_cover="한글") is None
    finally:
        doc.close()


@requires_arial
def test_embedded_font_rejects_unknown_name(tmp_path):
    src, _rect, _meta = _make_arial_pdf(tmp_path)
    doc = _reopen(src)
    try:
        assert extract_embedded_font(doc[0], "NoSuchFontXyz", must_cover="x") is None
    finally:
        doc.close()


@requires_arial
def test_embedded_font_subset_rejected(tmp_path):
    """Subset embeds have their cmap stripped (has_glyph==0 for everything),
    so the coverage probe must reject them -- measured behavior pinned."""
    src, _rect, _meta = _make_arial_pdf(tmp_path)
    sub = _subset_copy(tmp_path, src)
    doc = _reopen(sub)
    try:
        assert extract_embedded_font(doc[0], "ArialMT", must_cover="Orig") is None
    finally:
        doc.close()


@requires_arial
def test_replace_reuses_embedded_when_not_installed(tmp_path, monkeypatch):
    """With the system match disabled (simulating a not-installed source
    font), the replacement must reuse the PDF's own embedded font."""
    monkeypatch.setattr(
        applicator_module, "resolve_pdf_fontname", lambda *a, **k: None
    )
    src, rect, meta = _make_arial_pdf(tmp_path)
    out, _ = _apply_replace(tmp_path, src, rect, "Replaced words")

    spans = _replaced_spans(out, "Replaced")
    assert spans
    assert "arial" in spans[0]["font"].lower()
    assert abs(spans[0]["origin"][1] - meta["baseline"]) <= 1.0
    assert spans[0]["size"] == pytest.approx(meta["fontsize"], abs=0.6)


@requires_arial
def test_embedded_aliases_do_not_collide(tmp_path, monkeypatch):
    """Two different embedded fonts replaced in one pass must not share an
    alias (content-derived alias prevents the second op reusing the first
    font's program)."""
    times_path = os.path.join(
        os.environ.get("SystemRoot", "C:\\Windows"), "Fonts", "times.ttf"
    )
    if not os.path.exists(times_path):
        pytest.skip("Times New Roman not available")

    # Page with two lines in two distinct embedded fonts.
    src = tmp_path / "two_fonts.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 200), "Arial line here", fontsize=10.0,
                     fontname="af", fontfile=ARIAL_PATH)
    page.insert_text((72, 300), "Times line here", fontsize=10.0,
                     fontname="tf", fontfile=times_path)
    rA = page.search_for("Arial line here")[0]
    rT = page.search_for("Times line here")[0]
    doc.save(str(src))
    doc.close()

    monkeypatch.setattr(
        applicator_module, "resolve_pdf_fontname", lambda *a, **k: None
    )
    doc = fitz.open(str(src))
    page = doc[0]
    ops = [
        RedactReplace(0, [fitz.Rect(rA)], "Arial replaced"),
        RedactReplace(0, [fitz.Rect(rT)], "Times replaced"),
    ]
    OperationApplicator().apply_operations(page, ops, ApplyMode.SAVE)
    out = tmp_path / "two_fonts_out.pdf"
    doc.save(str(out))
    doc.close()

    arial_spans = _replaced_spans(out, "Arial replaced")
    times_spans = _replaced_spans(out, "Times replaced")
    assert arial_spans and times_spans
    # Each replacement keeps its own typeface -- no cross-contamination.
    assert "arial" in arial_spans[0]["font"].lower()
    assert "times" in times_spans[0]["font"].lower()


@requires_arial
def test_subset_source_falls_back_safely(tmp_path, monkeypatch):
    """Subset source + no system match: no crash, Base-14 fallback used."""
    monkeypatch.setattr(
        applicator_module, "resolve_pdf_fontname", lambda *a, **k: None
    )
    src, rect, _meta = _make_arial_pdf(tmp_path)
    sub = _subset_copy(tmp_path, src)
    out, result = _apply_replace(tmp_path, sub, rect, "Plain fallback")

    spans = _replaced_spans(out, "Plain")
    assert spans, "fallback insertion must still render"
    assert "helv" in spans[0]["font"].lower() or "arial" not in spans[0]["font"].lower()
