"""Save busy-indicator cursor handling (save-busy-indicator PDCA).

The save path shows a WaitCursor during the blocking save; it MUST always be
restored, including on a save failure -- a leaked override cursor would persist
for the whole session.
"""

import os
from unittest.mock import patch

import fitz
import pytest
from PySide6.QtWidgets import QApplication, QFileDialog

from app.ui import MainWindow


@pytest.fixture
def sample_pdf(tmp_path):
    pdf_path = tmp_path / "busy_sample.pdf"
    doc = fitz.open()
    doc.new_page().insert_text((50, 70), "busy save sample", fontsize=12)
    doc.save(pdf_path)
    doc.close()
    return os.path.abspath(pdf_path)


@pytest.fixture
def main_window(qtbot, sample_pdf):
    window = MainWindow()
    qtbot.addWidget(window)
    window.controller.load_document(sample_pdf)
    return window


def _drain_override_cursors():
    """Clear any leftover override cursors so one test can't leak into another."""
    while QApplication.overrideCursor() is not None:
        QApplication.restoreOverrideCursor()


def test_cursor_restored_after_successful_save(main_window, qtbot, tmp_path):
    _drain_override_cursors()
    out = str(tmp_path / "ok.pdf")
    with patch.object(QFileDialog, "getSaveFileName", return_value=(out, "PDF Files (*.pdf)")):
        assert main_window.save_file_as() is True
    assert QApplication.overrideCursor() is None
    assert os.path.exists(out)


def test_cursor_restored_after_failed_save(main_window, qtbot, tmp_path):
    _drain_override_cursors()
    out = str(tmp_path / "fail.pdf")
    with (
        patch.object(QFileDialog, "getSaveFileName", return_value=(out, "PDF Files (*.pdf)")),
        patch.object(main_window.controller, "save_document", side_effect=RuntimeError("boom")),
        patch("app.handlers.file_handlers.QMessageBox.critical"),
    ):
        assert main_window.save_file_as() is False
    # The WaitCursor must not leak even though the save raised.
    assert QApplication.overrideCursor() is None


def test_cancelled_save_leaves_no_override_cursor(main_window, qtbot):
    _drain_override_cursors()
    with patch.object(QFileDialog, "getSaveFileName", return_value=("", "")):
        assert main_window.save_file_as() is False
    assert QApplication.overrideCursor() is None
