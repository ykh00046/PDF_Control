"""feature-review (2026-09-09): crop actually applies (and respects rotation),
watermarks land in the same visible place on rotated pages, save-time
redaction keeps vector art under the text, blank pages match the document."""

import fitz
import numpy as np
import pytest

from app.model import CropMargins, DocumentSession, RedactDelete, RedactReplace, WatermarkImage, WatermarkText
from app.operations.crop import visible_to_mediabox_margins
from app.operations_service import ApplyMode, OperationApplicator
from app.pdf_engine import save_document_copy


def _rgb(page, scale=2.0):
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3].astype(int)


def _gray_centroid(page):
    a = _rgb(page)
    mask = (abs(a[:, :, 0] - a[:, :, 1]) < 8) & (a.min(axis=2) > 120) & (a.max(axis=2) < 225)
    ys, xs = np.where(mask)
    assert len(xs) > 50, "watermark pixels not found"
    return xs.mean() / 2, ys.mean() / 2


# ------------------------------------------------------------------- crop
@pytest.mark.parametrize(
    "rotation,expected",
    [(0, (3, 1, 4, 2)), (90, (1, 4, 2, 3)), (180, (4, 2, 3, 1)), (270, (2, 3, 1, 4))],
)
def test_visible_to_mediabox_margins(rotation, expected):
    # visible (top=1, bottom=2, left=3, right=4) -> mediabox (left, top, right, bottom)
    assert visible_to_mediabox_margins(rotation, 1, 2, 3, 4) == expected


def test_crop_applies_and_shrinks_page(tmp_path):
    src, dst = tmp_path / "c.pdf", tmp_path / "c_out.pdf"
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    page.insert_text((40, 25), "TOP", fontsize=12)  # inside the 30pt top margin
    page.insert_text((40, 150), "BODY", fontsize=12)
    doc.save(src)
    doc.close()
    save_document_copy(str(src), str(dst), [CropMargins(0, top=30, bottom=30, left=20, right=20)])
    out = fitz.open(dst)
    try:
        assert out[0].rect.width == pytest.approx(360) and out[0].rect.height == pytest.approx(240)
        text = out[0].get_text()
        assert "BODY" in text and "TOP" not in text
    finally:
        out.close()


def test_crop_top_on_rotated_page_cuts_visible_top(tmp_path):
    """On a 90-degree page the visible top is the unrotated left edge."""
    src = tmp_path / "r.pdf"
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    page.insert_text((15, 150), "LEFTEDGE", fontsize=10)  # unrotated left -> visible top after rotate 90
    page.insert_text((200, 150), "MIDDLE", fontsize=10)
    doc.save(src)
    doc.close()
    session = DocumentSession(str(src))
    try:
        session.rotate_page(0, 90)
        session.add_operation(CropMargins(0, top=40))
        session.save_document(str(tmp_path / "r_out.pdf"))
        page = session.doc[0]
        assert page.rotation == 90
        assert page.rect.width == pytest.approx(300) and page.rect.height == pytest.approx(360)
        assert "MIDDLE" in page.get_text() and "LEFTEDGE" not in page.get_text()
    finally:
        session.close()


def test_crop_preview_does_not_raise():
    doc = fitz.open()
    page = doc.new_page()
    result = OperationApplicator().apply_operations(page, [CropMargins(0, 10, 10, 10, 10)], mode=ApplyMode.PREVIEW)
    assert result.success and page.rect.width == pytest.approx(575)


# -------------------------------------------------------------- watermark
@pytest.mark.parametrize("rotation", [90, 180, 270])
def test_text_watermark_matches_unrotated_reference(rotation):
    """Same visible placement as an unrotated page of the same visible size."""
    ref_doc = fitz.open()
    rotated_doc = fitz.open()
    rotated = rotated_doc.new_page(width=400, height=300)
    rotated.set_rotation(rotation)
    ref = ref_doc.new_page(width=rotated.rect.width, height=rotated.rect.height)
    for page in (ref, rotated):
        WatermarkText(0, "WM TEXT", 30, (0.5, 0.5, 0.5), 0.4, 45).apply(page)
    rx, ry = _gray_centroid(ref)
    x, y = _gray_centroid(rotated)
    assert (x, y) == pytest.approx((rx, ry), abs=2.5)
    ref_doc.close()
    rotated_doc.close()


def test_image_watermark_centered_and_upright_on_rotated_page(tmp_path):
    # Asymmetric image: dark left half, light right half -> orientation is detectable.
    img = tmp_path / "wm.png"
    pm = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 40, 40), 0)
    pm.set_rect(fitz.IRect(0, 0, 20, 40), (60, 60, 60))
    pm.set_rect(fitz.IRect(20, 0, 40, 40), (200, 200, 200))
    pm.save(str(img))

    def render(rotation):
        doc = fitz.open()
        page = doc.new_page(width=400, height=300)
        page.set_rotation(rotation)
        WatermarkImage(0, str(img), opacity=1.0, scale=0.2).apply(page)
        a = _rgb(page)
        dark = np.where(a.max(axis=2) < 90)
        light = np.where((a.min(axis=2) > 150) & (a.max(axis=2) < 230))
        rect = fitz.Rect(page.rect)
        doc.close()
        return (dark[1].mean() / 2, dark[0].mean() / 2), (light[1].mean() / 2, light[0].mean() / 2), rect

    for rotation in (0, 90, 270):
        dark_c, light_c, rect = render(rotation)
        center = ((dark_c[0] + light_c[0]) / 2, (dark_c[1] + light_c[1]) / 2)
        assert center == pytest.approx((rect.width / 2, rect.height / 2), abs=2.0), rotation
        # Upright to the viewer: dark half stays on the LEFT of the light half.
        assert dark_c[0] < light_c[0] and abs(dark_c[1] - light_c[1]) < 2.0, rotation


# ------------------------------------------------------------- redaction
def test_save_redaction_keeps_underline_and_shading(tmp_path):
    src, dst = tmp_path / "u.pdf", tmp_path / "u_out.pdf"
    doc = fitz.open()
    page = doc.new_page(width=420, height=160)
    page.draw_rect(fitz.Rect(30, 20, 390, 60), fill=(0.85, 0.92, 1.0), color=None)
    page.insert_text((40, 45), "HEADER secret 2025", fontsize=13)
    page.draw_line((30, 110), (390, 110), color=(0, 0, 0), width=0.8)
    page.insert_text((40, 107), "underlined secret word", fontsize=12)
    r1, r2 = page.search_for("secret")
    doc.save(src)
    doc.close()
    save_document_copy(str(src), str(dst), [RedactDelete(0, [r1]), RedactReplace(0, [r2], "public")])
    out = fitz.open(dst)
    try:
        page = out[0]
        text = page.get_text()
        assert "secret" not in text and "public" in text and "HEADER" in text
        a = _rgb(page)
        # shading still present in the middle of the deleted word
        cx, cy = int((r1.x0 + r1.x1)), int(r1.y0 * 2 + 3)
        assert tuple(a[cy, cx]) != (255, 255, 255) and a[cy, cx][2] > a[cy, cx][0]
        # underline unbroken under the replaced word
        assert a[220, int((r2.x0 + r2.x1))].max() < 120
    finally:
        out.close()


# ----------------------------------------------------------- blank page
def test_blank_page_matches_neighbour_size(tmp_path):
    src = tmp_path / "s.pdf"
    doc = fitz.open()
    doc.new_page(width=400, height=300)
    doc.save(src)
    doc.close()
    session = DocumentSession(str(src))
    try:
        session.insert_blank_page(0)
        assert session.doc[1].rect.width == pytest.approx(400) and session.doc[1].rect.height == pytest.approx(300)
        session.rotate_page(0, 90)  # displayed 300x400
        session.insert_blank_page(0)
        assert session.doc[1].rect.width == pytest.approx(300) and session.doc[1].rect.height == pytest.approx(400)
        session.insert_blank_page(-1, width=100, height=50)  # explicit size still honored
        assert session.doc[-1].rect.width == pytest.approx(100)
    finally:
        session.close()
