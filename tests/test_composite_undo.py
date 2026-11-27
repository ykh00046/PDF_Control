"""Composite undo: content operations mixed with page management (test-gap map §2-3).

Pending content operations (replace / watermark) must follow the physical
page they were attached to across delete / move / insert / duplicate /
reorder, and a page-change undo must restore BOTH the page layout and the
operation indices so a redo re-applies each operation to the page it was
originally added to. Saving from any of those states must write each
operation onto the physically correct page.
"""

import fitz
import pytest

from app.document_session import PAGE_HISTORY_LIMIT, DocumentSession
from app.model import RedactReplace, WatermarkText

WATERMARK = "WM-COMP"


@pytest.fixture
def three_page_pdf(tmp_path):
    """Pages carry a unique label so physical identity survives reindexing."""
    pdf_path = tmp_path / "composite.pdf"
    doc = fitz.open()
    for label in ("ALPHA", "BETA", "GAMMA"):
        page = doc.new_page(width=300, height=400)
        page.insert_text((30, 40), label, fontsize=12)
    doc.save(pdf_path)
    doc.close()
    return str(pdf_path)


def _page_texts(session):
    return [session.doc[i].get_text().strip() for i in range(session.doc.page_count)]


def _history_summary(session):
    return [(type(op).__name__, op.page_index) for op in session.history]


def _add_content_ops(session):
    """Replace on the ALPHA page, watermark on the GAMMA page."""
    session.add_operation(RedactReplace(0, [fitz.Rect(20, 25, 120, 50)], "OMEGA"))
    session.add_operation(WatermarkText(2, WATERMARK, angle=0))


def test_middle_page_delete_undo_redo_keeps_ops_on_original_pages(three_page_pdf):
    session = DocumentSession(three_page_pdf)
    _add_content_ops(session)

    session.delete_pages([1])
    assert _history_summary(session) == [("RedactReplace", 0), ("WatermarkText", 1)]
    assert _page_texts(session) == ["ALPHA", "GAMMA"]

    assert session.undo_page_change() is True
    assert _history_summary(session) == [("RedactReplace", 0), ("WatermarkText", 2)]
    assert _page_texts(session) == ["ALPHA", "BETA", "GAMMA"]

    assert session.redo_page_change() is True
    assert _history_summary(session) == [("RedactReplace", 0), ("WatermarkText", 1)]
    assert _page_texts(session) == ["ALPHA", "GAMMA"]
    session.close()


def test_save_after_delete_applies_ops_to_physical_pages(three_page_pdf, tmp_path):
    session = DocumentSession(three_page_pdf)
    _add_content_ops(session)
    session.delete_pages([1])

    out = str(tmp_path / "after_delete.pdf")
    session.save_document(out)
    session.close()

    saved = fitz.open(out)
    try:
        assert saved.page_count == 2
        page0, page1 = saved[0].get_text(), saved[1].get_text()
        # The replacement landed on the ex-ALPHA page...
        assert "OMEGA" in page0 and "ALPHA" not in page0
        # ...and the watermark on the ex-GAMMA page (now index 1).
        assert "GAMMA" in page1 and WATERMARK in page1
    finally:
        saved.close()


def test_save_after_undo_restores_original_page_targets(three_page_pdf, tmp_path):
    session = DocumentSession(three_page_pdf)
    _add_content_ops(session)
    session.delete_pages([1])
    assert session.undo_page_change() is True

    out = str(tmp_path / "after_undo.pdf")
    session.save_document(out)
    session.close()

    saved = fitz.open(out)
    try:
        assert saved.page_count == 3
        assert "OMEGA" in saved[0].get_text() and "ALPHA" not in saved[0].get_text()
        assert saved[1].get_text().strip() == "BETA"  # untouched middle page
        assert WATERMARK in saved[2].get_text() and "GAMMA" in saved[2].get_text()
    finally:
        saved.close()


def test_delete_first_page_drops_its_ops_and_shifts_later(three_page_pdf):
    session = DocumentSession(three_page_pdf)
    _add_content_ops(session)

    session.delete_pages([0])
    # The replacement lived on the deleted page -> gone; watermark 2 -> 1.
    assert _history_summary(session) == [("WatermarkText", 1)]
    assert _page_texts(session) == ["BETA", "GAMMA"]

    assert session.undo_page_change() is True
    assert _history_summary(session) == [("RedactReplace", 0), ("WatermarkText", 2)]
    session.close()


def test_delete_last_page_keeps_earlier_ops(three_page_pdf):
    session = DocumentSession(three_page_pdf)
    _add_content_ops(session)

    session.delete_pages([2])
    assert _history_summary(session) == [("RedactReplace", 0)]
    assert _page_texts(session) == ["ALPHA", "BETA"]
    session.close()


def test_delete_all_pages_is_rejected_and_preserves_state(three_page_pdf):
    session = DocumentSession(three_page_pdf)
    _add_content_ops(session)

    with pytest.raises(ValueError, match="Cannot delete all pages"):
        session.delete_pages([0, 1, 2])
    # Rejected before any mutation: layout and operations intact, nothing undoable.
    assert _page_texts(session) == ["ALPHA", "BETA", "GAMMA"]
    assert _history_summary(session) == [("RedactReplace", 0), ("WatermarkText", 2)]
    assert not session.can_undo_page_change
    session.close()


def test_mixed_delete_and_move_multi_step_undo(three_page_pdf):
    session = DocumentSession(three_page_pdf)
    _add_content_ops(session)

    session.delete_pages([1])  # -> [ALPHA, GAMMA]; watermark -> 1
    session.move_page(1, 0)  # -> [GAMMA, ALPHA]; watermark -> 0, replace -> 1
    assert _page_texts(session) == ["GAMMA", "ALPHA"]
    assert _history_summary(session) == [("RedactReplace", 1), ("WatermarkText", 0)]

    # Walk both steps back: operations return to their original pages.
    assert session.undo_page_change() is True
    assert _page_texts(session) == ["ALPHA", "GAMMA"]
    assert _history_summary(session) == [("RedactReplace", 0), ("WatermarkText", 1)]
    assert session.undo_page_change() is True
    assert _page_texts(session) == ["ALPHA", "BETA", "GAMMA"]
    assert _history_summary(session) == [("RedactReplace", 0), ("WatermarkText", 2)]

    # Redoing both steps must reproduce the exact mixed state again.
    assert session.redo_page_change() is True
    assert session.redo_page_change() is True
    assert _page_texts(session) == ["GAMMA", "ALPHA"]
    assert _history_summary(session) == [("RedactReplace", 1), ("WatermarkText", 0)]
    session.close()


def test_ops_track_physical_page_across_change_sequence(three_page_pdf):
    """After every page change (and every undo of it), the watermark op's
    index points at the page whose text is GAMMA."""
    session = DocumentSession(three_page_pdf)
    session.add_operation(WatermarkText(2, WATERMARK, angle=0))

    def watermark_page():
        return next(op.page_index for op in session.history if isinstance(op, WatermarkText))

    def assert_tracks():
        assert session.doc[watermark_page()].get_text().find("GAMMA") >= 0

    session.move_page(2, 0)  # [GAMMA, ALPHA, BETA]
    assert_tracks()
    session.delete_pages([2])  # drop BETA -> [GAMMA, ALPHA]
    assert_tracks()
    session.insert_blank_page(0)  # [blank, GAMMA, ALPHA]
    assert_tracks()
    session.duplicate_pages([2])  # copy ALPHA -> [blank, GAMMA, ALPHA, ALPHA]
    assert_tracks()
    session.reorder_pages([2, 0, 3, 1])
    assert_tracks()

    while session.can_undo_page_change:
        assert session.undo_page_change() is True
        assert_tracks()
    assert _page_texts(session) == ["ALPHA", "BETA", "GAMMA"]
    assert watermark_page() == 2
    session.close()


def test_page_history_limit_keeps_operations_intact(three_page_pdf):
    """With the undo stack truncated at PAGE_HISTORY_LIMIT, remapped
    operations still track their page at every reachable snapshot."""
    session = DocumentSession(three_page_pdf)
    session.add_operation(WatermarkText(2, WATERMARK, angle=0))

    # Alternate index-remapping moves with rotations so snapshots near the
    # limit boundary contain remapped operation indices, not just rotations.
    for i in range(PAGE_HISTORY_LIMIT + 2):
        if i % 2:
            session.rotate_page(0, 90)
        else:
            session.move_page(2, 0)
    assert len(session._page_undo_stack) == PAGE_HISTORY_LIMIT

    undos = 0
    while session.can_undo_page_change:
        assert session.undo_page_change() is True
        undos += 1
        op = session.history[0]
        assert "GAMMA" in session.doc[op.page_index].get_text()
    assert undos == PAGE_HISTORY_LIMIT
    session.close()
