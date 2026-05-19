import os
from unittest.mock import patch

import fitz
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog

from app.ui import MainWindow

@pytest.fixture
def sample_pdf(tmp_path):
    """Create a minimal PDF for UI tests."""
    pdf_path = tmp_path / "ui_sample.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 70), "UI sample page", fontsize=12)
    doc.save(pdf_path)
    doc.close()
    return os.path.abspath(pdf_path)


@pytest.fixture
def main_window(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    return window

def test_open_file(main_window, qtbot, sample_pdf):
    with patch.object(QFileDialog, "getOpenFileName", return_value=(sample_pdf, "PDF Files (*.pdf)")):
        main_window.open_file()

    assert main_window.controller.session is not None
    assert main_window.controller.session.file_path == sample_pdf
    assert os.path.basename(sample_pdf) in main_window.windowTitle()


def test_delete_selection(main_window, qtbot, sample_pdf):
    main_window.controller.load_document(sample_pdf)

    rect = fitz.Rect(10, 10, 100, 100)
    main_window.last_selected_rect = rect
    main_window.viewer.current_page_index = 0

    main_window.delete_selection()

    assert len(main_window.controller.session.history) == 1
    op = main_window.controller.session.history[0]
    assert op.__class__.__name__ == "RedactDelete"


def test_undo_redo(main_window, qtbot, sample_pdf):
    main_window.controller.load_document(sample_pdf)

    rect = fitz.Rect(10, 10, 100, 100)
    main_window.last_selected_rect = rect
    main_window.viewer.current_page_index = 0
    main_window.delete_selection()

    assert len(main_window.controller.session.history) == 1

    main_window.undo_operation()
    assert len(main_window.controller.session.history) == 0
    assert len(main_window.controller.session.redo_stack) == 1

    main_window.redo_operation()
    assert len(main_window.controller.session.history) == 1
