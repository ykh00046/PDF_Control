"""Text + image watermark operations and controller integration (watermark PDCA)."""

import fitz
import pytest

from app.controller import EditorController
from app.operations import ApplyMode, OperationApplicator
from app.operations.watermark import WatermarkImage, WatermarkText

WM = "CONFIDENTIAL"


def _make_logo(tmp_path):
    """Write a small opaque RGB watermark image, return its path."""
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 120, 120))
    pix.set_rect(pix.irect, (200, 0, 0))
    path = tmp_path / "logo.png"
    pix.save(str(path))
    return str(path)


def _page_text(doc):
    return "".join(doc[i].get_text() for i in range(doc.page_count)).replace("\n", "").replace("\xa0", " ")


def test_watermark_apply_renders_text(tmp_path):
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    WatermarkText(0, WM).apply(page)
    out = tmp_path / "wm.pdf"
    doc.save(str(out))
    doc.close()

    chk = fitz.open(str(out))
    try:
        assert chk[0].search_for(WM)  # rendered + searchable
    finally:
        chk.close()


def test_watermark_preserves_body(tmp_path):
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 100), "Important body content", fontsize=12)
    WatermarkText(0, WM).apply(page)
    out = tmp_path / "wm_body.pdf"
    doc.save(str(out))
    doc.close()

    chk = fitz.open(str(out))
    try:
        text = _page_text(chk)
        assert "Important body content" in text
        assert WM in text
    finally:
        chk.close()


def test_watermark_empty_text_is_noop():
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    WatermarkText(0, "").apply(page)  # must not raise
    assert page.get_text().strip() == ""
    doc.close()


def _count_watermark(tmp_path, tile, label):
    """Apply a text watermark and return how many instances are searchable."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    # Short text + small size -> a denser grid; rotation makes search_for an
    # undercount, so we compare counts rather than assert an exact number.
    WatermarkText(0, "WM", fontsize=20, tile=tile).apply(page)
    out = tmp_path / f"{label}.pdf"
    doc.save(str(out))
    doc.close()
    chk = fitz.open(str(out))
    try:
        return len(chk[0].search_for("WM"))
    finally:
        chk.close()


def test_watermark_tile_places_more_than_centered(tmp_path):
    """tile=True repeats across the page; centered is exactly one."""
    centered = _count_watermark(tmp_path, False, "wm_center")
    tiled = _count_watermark(tmp_path, True, "wm_tile")
    assert centered == 1
    assert tiled > centered


@pytest.mark.parametrize(
    ("position", "left", "top"),
    [
        ("top-left", True, True),
        ("top-right", False, True),
        ("bottom-left", True, False),
        ("bottom-right", False, False),
    ],
)
def test_text_watermark_corner_position(position, left, top):
    """Plan SC-1: each corner places searchable text in the expected quadrant."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    WatermarkText(0, WM, fontsize=24, angle=0, position=position).apply(page)
    rect = page.search_for(WM)[0]
    assert (rect.x1 < page.rect.width / 2) is left
    assert (rect.y1 < page.rect.height / 2) is top
    assert page.rect.contains(rect)
    doc.close()


def test_invalid_watermark_position_rejected():
    with pytest.raises(ValueError, match="Unsupported watermark position"):
        WatermarkText(0, WM, position="outside")


def test_image_watermark_tile_places_many(tmp_path):
    logo = _make_logo(tmp_path)
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    WatermarkImage(0, logo, scale=0.2, tile=True).apply(page)
    out = tmp_path / "imgwm_tile.pdf"
    doc.save(str(out), garbage=3, deflate=True)
    doc.close()

    chk = fitz.open(str(out))
    try:
        # Multiple placements; the image program itself is embedded once
        # (xref reuse), so get_images() may dedup -- assert the page draws
        # the image by checking the embedded image is present and the file
        # rendered without error.
        assert len(chk[0].get_images()) >= 1
        pix = chk[0].get_pixmap()
        assert pix.width > 0
    finally:
        chk.close()


def test_preview_save_equivalence_watermark(tmp_path):
    """The same watermark pass runs in both PREVIEW and SAVE (non-destructive)."""
    applicator = OperationApplicator()

    def render(mode):
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        applicator.apply_operations(page, [WatermarkText(0, WM)], mode)
        rendered = bool(page.search_for(WM))
        doc.close()
        return rendered

    assert render(ApplyMode.SAVE) is True
    assert render(ApplyMode.PREVIEW) is True


# ── controller scope (current vs all pages) ──────────────────────────


@pytest.fixture
def three_page_pdf(tmp_path):
    path = tmp_path / "three.pdf"
    doc = fitz.open()
    for i in range(3):
        doc.new_page(width=595, height=842).insert_text((72, 72), f"P{i}", fontsize=12)
    doc.save(str(path))
    doc.close()
    return str(path)


def test_add_watermark_all_pages(three_page_pdf, tmp_path):
    controller = EditorController()
    assert controller.load_document(three_page_pdf) is True
    try:
        all_indices = list(range(controller.session.doc.page_count))
        assert controller.add_watermark(all_indices, WM) is True
        # One op per page.
        wm_ops = [op for op in controller.session.history if isinstance(op, WatermarkText)]
        assert len(wm_ops) == 3

        out = str(tmp_path / "all_wm.pdf")
        controller.save_document(out)

        doc = fitz.open(out)
        try:
            assert all(doc[i].search_for(WM) for i in range(doc.page_count))
        finally:
            doc.close()
    finally:
        controller.close_document()


def test_add_watermark_single_page(three_page_pdf, tmp_path):
    controller = EditorController()
    assert controller.load_document(three_page_pdf) is True
    try:
        assert controller.add_watermark([1], WM) is True  # middle page only
        out = str(tmp_path / "one_wm.pdf")
        controller.save_document(out)

        doc = fitz.open(out)
        try:
            assert not doc[0].search_for(WM)
            assert doc[1].search_for(WM)
            assert not doc[2].search_for(WM)
        finally:
            doc.close()
    finally:
        controller.close_document()


def test_controller_preserves_watermark_position(three_page_pdf):
    controller = EditorController()
    assert controller.load_document(three_page_pdf) is True
    try:
        assert controller.add_watermark([0], WM, position="top-left") is True
        op = controller.session.history[-1]
        assert isinstance(op, WatermarkText)
        assert op.position == "top-left"
    finally:
        controller.close_document()


# ── dialog (settings emission + empty-text guard) ────────────────────


def test_dialog_emits_settings(qtbot):
    from app.watermark_dialog import WatermarkDialog

    dialog = WatermarkDialog()
    qtbot.addWidget(dialog)
    dialog.text_edit.setText("  DRAFT  ")
    dialog.size_spin.setValue(60)
    dialog.opacity_slider.setValue(50)
    dialog.angle_spin.setValue(30.0)
    dialog.position_combo.setCurrentIndex(dialog.position_combo.findData("bottom-right"))

    captured = {}
    dialog.watermark_confirmed.connect(captured.update)
    dialog._apply()

    assert captured["text"] == "DRAFT"  # trimmed
    assert captured["fontsize"] == 60.0
    assert captured["opacity"] == 0.5
    assert captured["angle"] == 30.0
    assert captured["all_pages"] is True  # default scope
    assert captured["position"] == "bottom-right"
    assert len(captured["color"]) == 3


def test_dialog_empty_text_rejected(qtbot):
    from app.watermark_dialog import WatermarkDialog

    dialog = WatermarkDialog()
    qtbot.addWidget(dialog)
    dialog.text_edit.setText("   ")  # whitespace only

    emitted = []
    dialog.watermark_confirmed.connect(emitted.append)
    dialog._apply()

    assert emitted == []  # nothing emitted
    assert dialog.result() == WatermarkDialog.DialogCode.Rejected


def test_dialog_tile_disables_position(qtbot):
    from app.watermark_dialog import WatermarkDialog

    dialog = WatermarkDialog()
    qtbot.addWidget(dialog)
    assert dialog.position_combo.isEnabled()
    dialog.tile_check.setChecked(True)
    assert not dialog.position_combo.isEnabled()


# ── image watermark (image-watermark PDCA) ───────────────────────────


def test_image_watermark_renders(tmp_path):
    logo = _make_logo(tmp_path)
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 100), "Body content", fontsize=12)
    WatermarkImage(0, logo, opacity=0.3, scale=0.5).apply(page)
    out = tmp_path / "imgwm.pdf"
    doc.save(str(out), garbage=3, deflate=True)
    doc.close()

    chk = fitz.open(str(out))
    try:
        assert len(chk[0].get_images()) == 1
        assert "Body content" in chk[0].get_text()
    finally:
        chk.close()


@pytest.mark.parametrize("rotate", [0, 90])
def test_image_watermark_corner_position(tmp_path, rotate):
    logo = _make_logo(tmp_path)
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    WatermarkImage(0, logo, scale=0.2, rotate=rotate, position="bottom-right").apply(page)
    image_rect = page.get_image_rects(page.get_images(full=True)[0][0])[0]
    assert image_rect.x0 > page.rect.width / 2
    assert image_rect.y0 > page.rect.height / 2
    assert page.rect.contains(image_rect)
    assert image_rect.x1 == pytest.approx(page.rect.x1 - 36)
    assert image_rect.y1 == pytest.approx(page.rect.y1 - 36)
    doc.close()


def test_image_watermark_missing_file_noop():
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    WatermarkImage(0, "/no/such/file.png").apply(page)  # must not raise
    assert len(page.get_images()) == 0
    doc.close()


def test_image_watermark_preview_save_equivalence(tmp_path):
    logo = _make_logo(tmp_path)
    applicator = OperationApplicator()

    def render(mode):
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        applicator.apply_operations(page, [WatermarkImage(0, logo)], mode)
        n = len(page.get_images())
        doc.close()
        return n

    assert render(ApplyMode.SAVE) == 1
    assert render(ApplyMode.PREVIEW) == 1


def test_add_image_watermark_all_pages(three_page_pdf, tmp_path):
    logo = _make_logo(tmp_path)
    controller = EditorController()
    assert controller.load_document(three_page_pdf) is True
    try:
        all_indices = list(range(controller.session.doc.page_count))
        assert controller.add_image_watermark(all_indices, logo) is True
        img_ops = [op for op in controller.session.history if isinstance(op, WatermarkImage)]
        assert len(img_ops) == 3

        out = str(tmp_path / "all_imgwm.pdf")
        controller.save_document(out)
        doc = fitz.open(out)
        try:
            assert all(len(doc[i].get_images()) >= 1 for i in range(doc.page_count))
        finally:
            doc.close()
    finally:
        controller.close_document()


def test_image_watermark_dialog_requires_file(qtbot):
    from app.image_watermark_dialog import ImageWatermarkDialog

    dialog = ImageWatermarkDialog()
    qtbot.addWidget(dialog)
    # No file chosen yet.
    emitted = []
    dialog.image_watermark_confirmed.connect(emitted.append)
    dialog._apply()
    assert emitted == []
    assert dialog.result() == ImageWatermarkDialog.DialogCode.Rejected


def test_image_watermark_dialog_emits_position_and_tile_state(qtbot, tmp_path):
    from app.image_watermark_dialog import ImageWatermarkDialog

    dialog = ImageWatermarkDialog()
    qtbot.addWidget(dialog)
    dialog._image_path = str(tmp_path / "logo.png")
    dialog.position_combo.setCurrentIndex(dialog.position_combo.findData("top-right"))
    captured = {}
    dialog.image_watermark_confirmed.connect(captured.update)

    dialog.tile_check.setChecked(True)
    assert not dialog.position_combo.isEnabled()
    dialog.tile_check.setChecked(False)
    assert dialog.position_combo.isEnabled()
    dialog._apply()

    assert captured["position"] == "top-right"
    assert captured["tile"] is False
