"""Page-level undo/redo contract tests.

Plan SC: page mutations restore both PDF content and pending operation state.
"""

from types import SimpleNamespace

import fitz
import pytest
from PySide6.QtWidgets import QApplication

from app.document_session import PAGE_HISTORY_LIMIT, DocumentSession
from app.operations.redact import RedactDelete
from app.page_manager_dialog import PageManagerDialog


@pytest.fixture
def page_pdf(tmp_path):
    path = tmp_path / "pages.pdf"
    doc = fitz.open()
    for number in range(1, 5):
        page = doc.new_page(width=300, height=400)
        page.insert_text((30, 40), f"Page {number}")
    doc.save(path)
    doc.close()
    return str(path)


def page_texts(session):
    return [session.doc[index].get_text().strip() for index in range(session.doc.page_count)]


@pytest.mark.parametrize(
    "change",
    [
        lambda session: session.rotate_page(0, 90),
        lambda session: session.delete_pages([1]),
        lambda session: session.insert_blank_page(0),
        lambda session: session.move_page(0, 3),
        lambda session: session.reorder_pages([2, 0, 1, 3]),
        lambda session: session.duplicate_pages([1]),
    ],
    ids=["rotate", "delete", "insert", "move", "reorder", "duplicate"],
)
def test_page_change_undo_redo_round_trip(page_pdf, change):
    session = DocumentSession(page_pdf)
    before = (page_texts(session), [session.doc[i].rotation for i in range(session.doc.page_count)])

    change(session)
    after = (page_texts(session), [session.doc[i].rotation for i in range(session.doc.page_count)])
    assert after != before
    assert session.can_undo_page_change

    assert session.undo_page_change() is True
    assert (page_texts(session), [session.doc[i].rotation for i in range(session.doc.page_count)]) == before
    assert session.can_redo_page_change

    assert session.redo_page_change() is True
    assert (page_texts(session), [session.doc[i].rotation for i in range(session.doc.page_count)]) == after
    session.close()


def test_merge_undo_redo_round_trip(page_pdf, tmp_path):
    source_path = tmp_path / "merge.pdf"
    source = fitz.open()
    page = source.new_page(width=300, height=400)
    page.insert_text((30, 40), "Merged")
    source.save(source_path)
    source.close()

    session = DocumentSession(page_pdf)
    session.merge_pdfs([str(source_path)], after_index=0)
    assert page_texts(session)[1] == "Merged"
    assert session.undo_page_change()
    assert page_texts(session) == ["Page 1", "Page 2", "Page 3", "Page 4"]
    assert session.redo_page_change()
    assert page_texts(session)[1] == "Merged"
    session.close()


def test_pending_operation_returns_to_same_physical_page(page_pdf):
    session = DocumentSession(page_pdf)
    operation = RedactDelete(2, [fitz.Rect(0, 0, 10, 10)])
    session.add_operation(operation)

    session.delete_pages([0])
    assert session.history[0].page_index == 1
    assert "Page 3" in session.doc[1].get_text()

    session.undo_page_change()
    assert session.history[0].page_index == 2
    assert "Page 3" in session.doc[2].get_text()
    session.redo_page_change()
    assert session.history[0].page_index == 1
    assert "Page 3" in session.doc[1].get_text()
    session.close()


def test_new_change_invalidates_page_redo(page_pdf):
    session = DocumentSession(page_pdf)
    session.rotate_page(0, 90)
    session.undo_page_change()
    assert session.can_redo_page_change
    session.insert_blank_page()
    assert not session.can_redo_page_change
    session.close()


def test_grouped_changes_use_one_undo_step(page_pdf):
    session = DocumentSession(page_pdf)
    with session.page_change_group():
        session.rotate_page(0, 90)
        session.rotate_page(1, 90)
    assert len(session._page_undo_stack) == 1
    session.undo_page_change()
    assert [session.doc[i].rotation for i in range(4)] == [0, 0, 0, 0]
    session.close()


def test_history_is_bounded(page_pdf):
    session = DocumentSession(page_pdf)
    for _ in range(PAGE_HISTORY_LIMIT + 3):
        session.rotate_page(0, 90)
    assert len(session._page_undo_stack) == PAGE_HISTORY_LIMIT
    session.close()


def test_save_clears_page_history(page_pdf, tmp_path):
    session = DocumentSession(page_pdf)
    session.rotate_page(0, 90)
    session.save_document(str(tmp_path / "saved.pdf"))
    assert not session.can_undo_page_change
    assert not session.can_redo_page_change
    session.close()


def test_page_manager_actions_follow_session_history(page_pdf):
    app = QApplication.instance() or QApplication([])
    session = DocumentSession(page_pdf)
    dialog = PageManagerDialog(SimpleNamespace(session=session))
    assert not dialog.undo_action.isEnabled()
    assert not dialog.redo_action.isEnabled()

    session.rotate_page(0, 90)
    assert dialog.undo_action.isEnabled()
    dialog.undo_action.trigger()
    assert not dialog.undo_action.isEnabled()
    assert dialog.redo_action.isEnabled()
    assert session.doc[0].rotation == 0
    dialog.close()
    session.close()
    app.processEvents()
