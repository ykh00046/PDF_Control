"""Tests for the page thumbnail sidebar (app/thumbnail_panel.py)."""

import os

import fitz
import pytest

from app.config import get_config_value
from app.ui import MainWindow


@pytest.fixture
def three_page_pdf(tmp_path):
    """Create a 3-page PDF for sidebar tests."""
    pdf_path = tmp_path / "thumb_sample.pdf"
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page()
        page.insert_text((50, 70), f"Page {i + 1}", fontsize=12)
    doc.save(pdf_path)
    doc.close()
    return os.path.abspath(pdf_path)


@pytest.fixture
def main_window(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    return window


def _load(window, pdf_path):
    window.controller.load_document(pdf_path)
    window.thumbnail_panel.flush_pending_renders()


def test_panel_populates_on_open(main_window, qtbot, three_page_pdf):
    _load(main_window, three_page_pdf)

    panel = main_window.thumbnail_panel
    assert panel.count() == 3
    assert all(not panel.item(i).icon().isNull() for i in range(3))
    # Viewer starts on page 0 and the highlight follows.
    assert panel.currentRow() == 0


def test_panel_clears_on_close(main_window, qtbot, three_page_pdf):
    _load(main_window, three_page_pdf)
    main_window.controller.close_document()

    assert main_window.thumbnail_panel.count() == 0


def test_thumbnail_click_navigates_viewer(main_window, qtbot, three_page_pdf):
    _load(main_window, three_page_pdf)

    # A user-driven row change must navigate the viewer.
    main_window.thumbnail_panel.setCurrentRow(2)

    assert main_window.viewer.current_page_index == 2


def test_viewer_navigation_highlights_row(main_window, qtbot, three_page_pdf):
    _load(main_window, three_page_pdf)

    # Spinbox jump path goes through the shared _go_to_page helper.
    main_window._on_page_spinbox_changed(2)

    assert main_window.viewer.current_page_index == 1
    assert main_window.thumbnail_panel.currentRow() == 1


def test_go_to_page_ignores_out_of_range(main_window, qtbot, three_page_pdf):
    _load(main_window, three_page_pdf)

    main_window._go_to_page(99)
    main_window._go_to_page(-1)

    assert main_window.viewer.current_page_index == 0


def test_pages_changed_refreshes_panel(main_window, qtbot, three_page_pdf):
    _load(main_window, three_page_pdf)

    assert main_window.controller.delete_pages([2])
    main_window._on_pages_changed()
    main_window.thumbnail_panel.flush_pending_renders()

    assert main_window.thumbnail_panel.count() == 2


def test_rotation_shown_in_label(main_window, qtbot, three_page_pdf):
    _load(main_window, three_page_pdf)

    assert main_window.controller.rotate_page(0, 90)
    main_window._on_pages_changed()
    main_window.thumbnail_panel.flush_pending_renders()

    assert "90" in main_window.thumbnail_panel.item(0).text()


def test_toggle_persists_config(main_window, qtbot, three_page_pdf):
    _load(main_window, three_page_pdf)

    main_window._toggle_thumbnail_panel(False)

    assert get_config_value(main_window.config, "ui", "thumbnail_panel_visible", default=True) is False
    assert not main_window.thumbnail_dock.isVisible()

    main_window._toggle_thumbnail_panel(True)
    assert get_config_value(main_window.config, "ui", "thumbnail_panel_visible", default=False) is True


def test_programmatic_highlight_does_not_navigate(main_window, qtbot, three_page_pdf):
    _load(main_window, three_page_pdf)

    # set_current_page is the sync path and must not re-enter navigation.
    fired = []
    main_window.thumbnail_panel.page_selected.connect(lambda idx: fired.append(idx))
    main_window.thumbnail_panel.set_current_page(1)

    assert fired == []
    assert main_window.viewer.current_page_index == 0
