"""Preview=Save visual equivalence test.

Verifies that ApplyMode.PREVIEW and ApplyMode.SAVE produce visually identical
page renders. Preview draws white rectangles (non-destructive), Save uses
destructive redaction — but rendered pixels should match within a small
tolerance, since that is what the user actually sees in the viewer.

Note: the underlying PDF text layers intentionally diverge (SAVE removes
text, PREVIEW keeps it under a white fill). Visual parity is the contract.
"""

import fitz
import pytest

from app.operations_service import ApplyMode, OperationApplicator
from app.model import RedactDelete, RedactReplace


@pytest.fixture
def test_pdf_path(tmp_path):
    pdf_path = tmp_path / "equivalence.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 100), "Hello World", fontsize=14)
    page.insert_text((50, 150), "Replace me", fontsize=14)
    page.insert_text((50, 200), "Delete this", fontsize=14)
    doc.save(pdf_path)
    doc.close()
    return pdf_path


def _render_after(apply_mode, pdf_path, ops_builder):
    doc = fitz.open(str(pdf_path))
    page = doc[0]
    OperationApplicator().apply_operations(page, ops_builder(), mode=apply_mode)
    pix = page.get_pixmap(dpi=100, colorspace=fitz.csRGB)
    data = pix.samples
    size = (pix.width, pix.height)
    doc.close()
    return size, data


def _pixel_diff_ratio(a_data, b_data):
    if len(a_data) != len(b_data):
        return 1.0
    diffs = sum(1 for x, y in zip(a_data, b_data) if x != y)
    return diffs / len(a_data)


def test_delete_operation_visual_parity(test_pdf_path):
    def build_ops():
        return [RedactDelete(0, [fitz.Rect(50, 190, 200, 210)])]

    (w1, h1), save_data = _render_after(ApplyMode.SAVE, test_pdf_path, build_ops)
    (w2, h2), preview_data = _render_after(ApplyMode.PREVIEW, test_pdf_path, build_ops)

    assert (w1, h1) == (w2, h2), "Page dimensions diverged"
    diff = _pixel_diff_ratio(save_data, preview_data)
    assert diff < 0.01, f"Delete preview/save pixel diff {diff:.4%} exceeds 1% tolerance"


def test_replace_operation_visual_parity(test_pdf_path):
    def build_ops():
        return [RedactReplace(0, [fitz.Rect(50, 140, 200, 160)], "Replaced", fontsize=14)]

    (w1, h1), save_data = _render_after(ApplyMode.SAVE, test_pdf_path, build_ops)
    (w2, h2), preview_data = _render_after(ApplyMode.PREVIEW, test_pdf_path, build_ops)

    assert (w1, h1) == (w2, h2)
    diff = _pixel_diff_ratio(save_data, preview_data)
    assert diff < 0.02, f"Replace preview/save pixel diff {diff:.4%} exceeds 2% tolerance"


def test_combined_operations_visual_parity(test_pdf_path):
    def build_ops():
        return [
            RedactReplace(0, [fitz.Rect(50, 140, 200, 160)], "Replaced", fontsize=14),
            RedactDelete(0, [fitz.Rect(50, 190, 200, 210)]),
        ]

    (w1, h1), save_data = _render_after(ApplyMode.SAVE, test_pdf_path, build_ops)
    (w2, h2), preview_data = _render_after(ApplyMode.PREVIEW, test_pdf_path, build_ops)

    assert (w1, h1) == (w2, h2)
    diff = _pixel_diff_ratio(save_data, preview_data)
    assert diff < 0.02, f"Combined ops pixel diff {diff:.4%} exceeds 2% tolerance"
