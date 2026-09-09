"""natural-replace: replacements sit on the source baseline, keep table
alignment, blend into the page background, extend into free space before
shrinking, and keep paragraph leading."""

import fitz
import pytest

from app.model import RedactDelete, RedactReplace
from app.operations.redact import ALIGN_CENTER, ALIGN_LEFT, ALIGN_RIGHT
from app.operations_service import ApplyMode, OperationApplicator
from app.page_probe import (
    baseline_pitch,
    glyph_follows,
    is_numeric_text,
    line_free_space,
    sample_background_color,
)
from app.pdf_engine import save_document_copy


def _spans(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        for line in b.get("lines", []):
            for s in line["spans"]:
                out.append(s)
    return out


def _span(page, text):
    for s in _spans(page):
        if s["text"].strip() == text:
            return s
    raise AssertionError(f"span {text!r} not found: {[s['text'] for s in _spans(page)]}")


def _replace_and_reopen(tmp_path, build, replacements):
    src = tmp_path / "src.pdf"
    dst = tmp_path / "dst.pdf"
    doc = fitz.open()
    page = doc.new_page(width=500, height=200)
    build(page)
    doc.save(src)
    ops = []
    for needle, new, kwargs in replacements:
        ops.append(RedactReplace(0, [page.search_for(needle)[0]], new, **kwargs))
    doc.close()
    save_document_copy(str(src), str(dst), ops)
    return fitz.open(dst)


# ------------------------------------------------------------ page_probe unit
@pytest.mark.parametrize(
    "text,expected",
    [
        ("1,234.00", True),
        ("12%", True),
        ("(45)", True),
        ("2026-09-30", True),
        ("A-1001", False),
        ("Total", False),
        ("", False),
    ],
)
def test_is_numeric_text(text, expected):
    assert is_numeric_text(text) is expected


def test_baseline_pitch_median_and_single_line():
    assert baseline_pitch([100.0]) is None
    assert baseline_pitch([100.0, 114.0, 128.0]) == pytest.approx(14.0)
    assert baseline_pitch([100.0, 100.01, 114.0]) == pytest.approx(14.0, abs=0.05)


def test_line_free_space_bounded_by_words_and_rules():
    doc = fitz.open()
    page = doc.new_page(width=400, height=100)
    page.insert_text((40, 50), "left", fontsize=12)
    page.insert_text((200, 50), "right", fontsize=12)
    page.draw_line((300, 30), (300, 60), color=(0, 0, 0))
    rect = fitz.Rect(100, 40, 150, 55)
    words = page.get_text("words")
    left, right = line_free_space(page, rect, words=words, drawings=page.get_drawings())
    assert left == pytest.approx(page.search_for("left")[0].x1, abs=0.5)
    assert right == pytest.approx(page.search_for("right")[0].x0, abs=0.5)
    # Nothing on the line to the right past the word -> the rule bounds a rect after it
    left2, right2 = line_free_space(page, fitz.Rect(250, 40, 280, 55), words=words, drawings=page.get_drawings())
    assert right2 == pytest.approx(300, abs=0.5)
    assert glyph_follows(rect, words, within=20) is False
    assert glyph_follows(fitz.Rect(60, 40, 195, 55), words, within=20) is True


def test_sample_background_color_white_and_tinted():
    doc = fitz.open()
    page = doc.new_page(width=200, height=100)
    page.draw_rect(fitz.Rect(20, 20, 180, 60), fill=(0.85, 0.92, 1.0), color=None)
    page.insert_text((30, 45), "Header", fontsize=12)
    tinted = sample_background_color(page, page.search_for("Header")[0])
    assert tinted != (1.0, 1.0, 1.0)
    assert tinted[2] > tinted[0]  # bluish
    assert sample_background_color(page, fitz.Rect(20, 70, 100, 90)) == (1.0, 1.0, 1.0)


# --------------------------------------------------------------- integration
def test_replacement_sits_on_source_baseline_with_existing_font(tmp_path):
    """The page already holds Helvetica; insert_textbox drifted 1.4pt here."""

    def build(page):
        page.insert_text((40, 50), "Invoice number 12345 due today", fontsize=12, fontname="helv")

    doc = _replace_and_reopen(tmp_path, build, [("12345", "67890", {})])
    try:
        assert _span(doc[0], "67890")["origin"][1] == pytest.approx(50.0, abs=0.05)
        assert _span(doc[0], "67890")["size"] == pytest.approx(12.0, abs=0.05)
    finally:
        doc.close()


def test_table_number_keeps_right_edge_and_prose_number_stays_left(tmp_path):
    def build(page):
        page.draw_rect(fitz.Rect(40, 34, 300, 58), color=(0, 0, 0), width=0.8)
        page.draw_line((200, 34), (200, 58), color=(0, 0, 0), width=0.8)
        page.insert_text((48, 50), "Total", fontsize=11)
        w = fitz.get_text_length("1,234.00", fontsize=11)
        page.insert_text((292 - w, 50), "1,234.00", fontsize=11)
        page.insert_text((40, 100), "Invoice number 12345 due today", fontsize=12)

    doc = _replace_and_reopen(tmp_path, build, [("1,234.00", "99.00", {}), ("12345", "9", {})])
    try:
        cell = _span(doc[0], "99.00")
        assert cell["bbox"][2] == pytest.approx(292, abs=0.6)  # right edge kept
        prose = _span(doc[0], "9")
        assert prose["bbox"][0] == pytest.approx(fitz.get_text_length("Invoice number ", fontsize=12) + 40, abs=0.6)
    finally:
        doc.close()


def test_explicit_align_overrides_auto(tmp_path):
    def build(page):
        page.insert_text((40, 50), "Name: Alice Smith here", fontsize=12)

    rect_x1 = None

    def build2(page):
        nonlocal rect_x1
        build(page)
        rect_x1 = page.search_for("Alice")[0].x1

    doc = _replace_and_reopen(tmp_path, build2, [("Alice", "Al", {"align": ALIGN_RIGHT})])
    try:
        assert _span(doc[0], "Al")["bbox"][2] == pytest.approx(rect_x1, abs=0.6)
    finally:
        doc.close()


def test_short_source_extends_into_free_space_instead_of_shrinking(tmp_path):
    def build(page):
        page.insert_text((40, 50), "Ref: 77", fontsize=12)

    doc = _replace_and_reopen(tmp_path, build, [("77", "78901", {})])
    try:
        # Same font/size/baseline as "Ref:" -> the extractor merges both into
        # one span, which is exactly the "looks native" outcome we want.
        s = next(s for s in _spans(doc[0]) if "78901" in s["text"])
        assert s["size"] == pytest.approx(12.0, abs=0.05)
        assert s["origin"][1] == pytest.approx(50.0, abs=0.05)
    finally:
        doc.close()


def test_shrunk_replacement_never_overlaps_next_word(tmp_path):
    def build(page):
        page.insert_text((40, 50), "Invoice number 12345 due today", fontsize=12)

    doc = _replace_and_reopen(tmp_path, build, [("12345", "1234567890", {})])
    try:
        new = _span(doc[0], "1234567890")
        due = next(s for s in _spans(doc[0]) if s["text"].strip().startswith("due"))
        assert new["bbox"][2] <= due["bbox"][0] + 0.6
        assert new["size"] < 12
    finally:
        doc.close()


def test_background_fill_matches_tinted_bar(tmp_path):
    def build(page):
        page.draw_rect(fitz.Rect(40, 34, 300, 60), fill=(0.85, 0.92, 1.0), color=None)
        page.insert_text((48, 52), "REPORT 2025", fontsize=13, fontname="hebo")

    doc = _replace_and_reopen(tmp_path, build, [("2025", "2026", {})])
    try:
        page = doc[0]
        # Sample a pixel inside the replaced area but away from glyphs: still tinted.
        rect = page.search_for("2026")[0]
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=fitz.Rect(rect.x0, rect.y0 - 1.5, rect.x1, rect.y0))
        r, g, b = pix.pixel(pix.width // 2, 0)[:3]
        assert b > r and b >= 240 and r < 235, (r, g, b)
    finally:
        doc.close()


def test_delete_uses_background_fill(tmp_path):
    src = tmp_path / "d.pdf"
    dst = tmp_path / "d_out.pdf"
    doc = fitz.open()
    page = doc.new_page(width=200, height=100)
    page.draw_rect(fitz.Rect(10, 10, 190, 90), fill=(1.0, 0.9, 0.6), color=None)
    page.insert_text((30, 50), "secret", fontsize=12)
    rect = page.search_for("secret")[0]
    doc.save(src)
    doc.close()
    save_document_copy(str(src), str(dst), [RedactDelete(0, [rect])])
    out = fitz.open(dst)
    try:
        pix = out[0].get_pixmap(matrix=fitz.Matrix(2, 2), clip=rect)
        r, g, b = pix.pixel(pix.width // 2, pix.height // 2)[:3]
        assert (r, g, b) != (255, 255, 255)
        assert r >= 250 and 220 <= g <= 240 and 140 <= b <= 165, (r, g, b)
        assert "secret" not in out[0].get_text()
    finally:
        out.close()


def test_multiline_replacement_keeps_source_leading(tmp_path):
    src = tmp_path / "p.pdf"
    dst = tmp_path / "p_out.pdf"
    doc = fitz.open()
    page = doc.new_page(width=500, height=300)
    page.insert_textbox(
        fitz.Rect(40, 30, 300, 120),
        "This agreement is valid for twelve months from the date of signature and renews automatically.",
        fontsize=11,
        lineheight=1.6,
    )
    src_baselines = sorted({round(sp["origin"][1], 2) for sp in _spans(page)})
    src_pitch = src_baselines[1] - src_baselines[0]
    block = fitz.Rect()
    for b in page.get_text("blocks"):
        block |= fitz.Rect(b[:4])  # union of all lines (blocks may split per line)
    doc.save(src)
    doc.close()
    save_document_copy(
        str(src),
        str(dst),
        [
            RedactReplace(
                0,
                [block],
                "This agreement is valid for twenty-four months from the date of signature and does not renew.",  # noqa: E501,
            )
        ],
    )
    out = fitz.open(dst)
    try:
        baselines = sorted({round(s["origin"][1], 2) for s in _spans(out[0])})
        assert len(baselines) >= 2
        assert baselines[1] - baselines[0] == pytest.approx(src_pitch, abs=0.1)
    finally:
        out.close()


def test_preview_and_save_agree_on_alignment_and_baseline():
    def make():
        doc = fitz.open()
        page = doc.new_page(width=400, height=100)
        page.insert_text((40, 50), "Amount:", fontsize=12)
        w = fitz.get_text_length("1,000", fontsize=12)
        page.insert_text((300 - w, 50), "1,000", fontsize=12)
        return doc, page

    results = {}
    for mode in (ApplyMode.PREVIEW, ApplyMode.SAVE):
        doc, page = make()
        op = RedactReplace(0, [page.search_for("1,000")[0]], "25")
        OperationApplicator().apply_operations(page, [op], mode=mode)
        s = _span(page, "25")
        results[mode] = (round(s["bbox"][2], 2), round(s["origin"][1], 2))
        doc.close()
    assert results[ApplyMode.PREVIEW] == results[ApplyMode.SAVE]
    assert results[ApplyMode.SAVE][0] == pytest.approx(300, abs=0.6)


def test_center_alignment_centers_in_rect():
    doc = fitz.open()
    page = doc.new_page(width=400, height=100)
    page.insert_text((100, 50), "CENTERED", fontsize=12)
    rect = page.search_for("CENTERED")[0]
    op = RedactReplace(0, [rect], "MID", align=ALIGN_CENTER)
    OperationApplicator().apply_operations(page, [op], mode=ApplyMode.SAVE)
    s = _span(page, "MID")
    assert (s["bbox"][0] + s["bbox"][2]) / 2 == pytest.approx((rect.x0 + rect.x1) / 2, abs=0.6)
    assert ALIGN_LEFT == 0 and ALIGN_RIGHT == 2
