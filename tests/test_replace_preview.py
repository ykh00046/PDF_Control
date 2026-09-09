"""Replace dialog live preview + batch-replace alignment option."""

import os

import fitz
import pytest

from app.operations.redact import ALIGN_AUTO, ALIGN_RIGHT
from app.replace_preview import PreviewContext, preview_clip, render_replacement_preview


@pytest.fixture
def doc_with_line():
    doc = fitz.open()
    page = doc.new_page(width=400, height=200)
    page.insert_text((40, 60), "Amount: 1,000 total", fontsize=12)
    yield doc, page
    doc.close()


def _ctx(doc, page, needle):
    rect = page.search_for(needle)[0]
    return PreviewContext(
        doc=doc,
        page_index=0,
        rect=rect,
        fontname="helv",
        fontfile=None,
        fontsize=12.0,
        color=(0, 0, 0),
        font_flags=0,
    )


def test_preview_clip_stays_inside_page(doc_with_line):
    _doc, page = doc_with_line
    clip = preview_clip(page.rect, fitz.Rect(5, 5, 30, 20))
    assert clip.x0 >= 0 and clip.y0 >= 0
    assert clip.x1 <= page.rect.x1 and clip.y1 <= page.rect.y1


def test_render_preview_shows_candidate_not_source(doc_with_line):
    doc, page = doc_with_line
    ctx = _ctx(doc, page, "1,000")
    pix, text = render_replacement_preview(ctx, {"text": "25", "align": ALIGN_AUTO, "wrap": True, "fontsize": 0})
    assert pix.width > 0 and pix.height > 0
    assert "25" in text  # preview mode covers the source (draw_rect) rather than deleting it
    # Source document untouched (preview works on a copy).
    assert "1,000" in page.get_text()


def test_render_preview_empty_text_previews_deletion(doc_with_line):
    doc, page = doc_with_line
    ctx = _ctx(doc, page, "1,000")
    pix, text = render_replacement_preview(ctx, {"text": "", "align": ALIGN_AUTO, "wrap": True, "fontsize": 0})
    assert "Amount" in text
    # The source rect is covered: no dark pixel remains in its middle row.
    clip = preview_clip(page.rect, ctx.rect)
    scale = pix.width / clip.width
    y = int((ctx.rect.y0 + ctx.rect.y1) / 2 * scale - clip.y0 * scale)
    xs = range(int((ctx.rect.x0 - clip.x0) * scale) + 1, int((ctx.rect.x1 - clip.x0) * scale) - 1)
    assert all(min(pix.pixel(x, y)[:3]) > 200 for x in xs)


def test_dialog_updates_preview_on_change(qtbot, doc_with_line):
    from app.replace_dialog import ReplaceTextDialog

    doc, page = doc_with_line
    dialog = ReplaceTextDialog("1,000", preview=_ctx(doc, page, "1,000"))
    qtbot.addWidget(dialog)
    assert dialog.preview_label.pixmap() is not None and not dialog.preview_label.pixmap().isNull()
    first = dialog.preview_label.pixmap().toImage()
    dialog.text_edit.setPlainText("999,999,999")
    assert dialog.refresh_preview() is True
    second = dialog.preview_label.pixmap().toImage()
    assert first != second
    assert dialog.settings()["text"] == "999,999,999"


def test_dialog_without_preview_hides_panel(qtbot):
    from app.replace_dialog import ReplaceTextDialog

    dialog = ReplaceTextDialog("x")
    qtbot.addWidget(dialog)
    assert dialog.preview_label.isHidden()
    assert dialog.refresh_preview() is False


def test_batch_dialog_emits_alignment(qtbot, tmp_path):
    from app.batch_replace_dialog import BatchReplaceDialog
    from app.model import DocumentSession

    path = tmp_path / "b.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 80), "alpha beta alpha", fontsize=12)
    doc.save(path)
    doc.close()
    session = DocumentSession(os.path.abspath(path))
    try:
        dialog = BatchReplaceDialog(session)
        qtbot.addWidget(dialog)
        assert dialog.align_combo.currentData() == ALIGN_AUTO
        dialog.find_what_input.setText("alpha")
        dialog.replace_with_input.setText("omega")
        dialog._find_all_matches()
        idx = dialog.align_combo.findData(ALIGN_RIGHT)
        dialog.align_combo.setCurrentIndex(idx)
        received = []
        dialog.replacements_confirmed.connect(received.append)
        dialog._confirm_replacements()
        assert received and all(r["align"] == ALIGN_RIGHT for r in received[0])
        assert len(received[0]) == 2
    finally:
        session.close()
