"""UI tests for the Ctrl+F find bar: search, stepping, highlights, resets."""

import os

import fitz
import pytest

from app.ui import MainWindow


@pytest.fixture
def search_pdf(tmp_path):
    path = tmp_path / "find_ui.pdf"
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((50, 80), "needle first", fontsize=12)
    p1.insert_text((50, 120), "needle second", fontsize=12)
    p2 = doc.new_page()
    p2.insert_text((50, 80), "needle third", fontsize=12)
    doc.save(path)
    doc.close()
    return os.path.abspath(path)


@pytest.fixture
def window(qtbot, search_pdf):
    win = MainWindow()
    qtbot.addWidget(win)
    win.controller.load_document(search_pdf)
    return win


def test_find_bar_hidden_until_requested(window):
    # isHidden() reflects the bar's own state even though the offscreen
    # main window is never shown (isVisible() would be False regardless).
    assert window.find_bar.isHidden()
    assert window.find_action.isEnabled()
    window.show_find_bar()
    assert not window.find_bar.isHidden()


def test_find_action_disabled_without_document(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    assert not win.find_action.isEnabled()
    assert not win.save_action.isEnabled()
    assert not win.close_action.isEnabled()


def test_query_finds_hits_and_selects_first(window):
    window.find_bar.query_edit.setText("needle")
    window.find_bar.flush_pending_search()

    assert len(window._search_hits) == 3
    assert window._search_current == 0
    assert window.viewer.current_page_index == 0
    assert window.find_bar.count_label.text() == "1 / 3"
    # Highlights for page 1 (two hits), current marked
    assert len(window.viewer._highlight_rects) == 2
    assert window.viewer._highlight_current == window._search_hits[0].rect


def test_next_prev_wrap_and_follow_pages(window):
    window.find_bar.query_edit.setText("needle")
    window.find_bar.flush_pending_search()

    window.find_next()
    assert window._search_current == 1
    window.find_next()
    assert window._search_current == 2
    assert window.viewer.current_page_index == 1  # jumped to page 2
    assert len(window.viewer._highlight_rects) == 1
    window.find_next()  # wraps
    assert window._search_current == 0
    assert window.viewer.current_page_index == 0
    window.find_prev()  # wraps backward
    assert window._search_current == 2
    assert window.find_bar.count_label.text() == "3 / 3"


def test_case_sensitive_toggle_reruns_search(window):
    window.find_bar.query_edit.setText("NEEDLE")
    window.find_bar.flush_pending_search()
    assert len(window._search_hits) == 3
    window.find_bar.case_checkbox.setChecked(True)  # emits search immediately
    assert window._search_hits == []
    assert window.find_bar.count_label.text() != ""
    assert window.viewer._highlight_rects == []


def test_search_starts_from_current_page(window):
    window._go_to_page(1)
    window.find_bar.query_edit.setText("needle")
    window.find_bar.flush_pending_search()
    assert window._search_current == 2
    assert window.viewer.current_page_index == 1


def test_close_bar_clears_highlights(window):
    window.show_find_bar()
    window.find_bar.query_edit.setText("needle")
    window.find_bar.flush_pending_search()
    assert window.viewer._highlight_rects
    window.find_bar.close_bar()
    assert window._search_hits == []
    assert window.viewer._highlight_rects == []
    assert window.find_bar.isHidden()


def test_document_close_resets_search(window):
    window.find_bar.query_edit.setText("needle")
    window.find_bar.flush_pending_search()
    assert window._search_hits
    window.controller.close_document()
    assert window._search_hits == []
    assert window.viewer._highlight_rects == []


def test_page_change_reruns_search(window):
    """Deleting a page invalidates hit indices; the hook re-runs the query."""
    window.show_find_bar()
    window.find_bar.query_edit.setText("needle")
    window.find_bar.flush_pending_search()
    assert len(window._search_hits) == 3
    window.controller.delete_pages([0])
    window._on_pages_changed()
    assert len(window._search_hits) == 1
    assert window._search_hits[0].page_index == 0


def test_highlights_survive_rerender(window):
    window.find_bar.query_edit.setText("needle")
    window.find_bar.flush_pending_search()
    from PySide6.QtGui import QImage

    window.viewer._update_scene(QImage(100, 100, QImage.Format_RGB32))
    assert len(window.viewer._highlight_items) == 2
