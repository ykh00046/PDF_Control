"""Text watermark operation + controller integration (watermark PDCA)."""
import fitz
import pytest

from app.controller import EditorController
from app.operations import ApplyMode, OperationApplicator
from app.operations.watermark import WatermarkText

WM = "CONFIDENTIAL"


def _page_text(doc):
    return "".join(
        doc[i].get_text() for i in range(doc.page_count)
    ).replace("\n", "").replace("\xa0", " ")


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


# ── dialog (settings emission + empty-text guard) ────────────────────

def test_dialog_emits_settings(qtbot):
    from app.watermark_dialog import WatermarkDialog

    dialog = WatermarkDialog()
    qtbot.addWidget(dialog)
    dialog.text_edit.setText("  DRAFT  ")
    dialog.size_spin.setValue(60)
    dialog.opacity_slider.setValue(50)
    dialog.angle_spin.setValue(30.0)

    captured = {}
    dialog.watermark_confirmed.connect(captured.update)
    dialog._apply()

    assert captured["text"] == "DRAFT"  # trimmed
    assert captured["fontsize"] == 60.0
    assert captured["opacity"] == 0.5
    assert captured["angle"] == 30.0
    assert captured["all_pages"] is True  # default scope
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
