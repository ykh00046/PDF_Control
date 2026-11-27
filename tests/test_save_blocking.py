"""Save-time blocking-warning flow through MainWindow (test-gap map §2-5).

``FileHandlerMixin._commit_save`` consults
``DocumentSession.has_blocking_warnings`` (severity "error", e.g.
text.overflow) before writing anything:

* Cancel on the confirmation box refuses the save: no file is written, the
  original bytes survive, and the status bar reports "ready";
* choosing Save proceeds and produces the saved file;
* severity "warn" alone (text.shrunk) never blocks;
* an error on ANY page blocks the whole save;
* warnings cleared again (e.g. after the user shortens the replacement and
  the preview re-runs) unblock the save with no dialog.
"""

import os
from unittest.mock import patch

import fitz
import pytest
from PySide6.QtWidgets import QMessageBox

from app.i18n import tr
from app.ui import MainWindow


@pytest.fixture
def sample_pdf(tmp_path):
    pdf_path = tmp_path / "blocking.pdf"
    doc = fitz.open()
    doc.new_page().insert_text((50, 80), "blocking sample", fontsize=12)
    doc.new_page().insert_text((50, 80), "second page", fontsize=12)
    doc.save(pdf_path)
    doc.close()
    return os.fspath(pdf_path)


@pytest.fixture
def window(qtbot, sample_pdf):
    win = MainWindow()
    qtbot.addWidget(win)
    win.controller.load_document(sample_pdf)
    return win


def _overflow_warning():
    return [{"op_index": 0, "severity": "error", "code": "text.overflow", "detail": {}}]


def _shrink_warning():
    return [{"op_index": 0, "severity": "warn", "code": "text.shrunk", "detail": {}}]


def test_blocking_warning_cancel_refuses_save(window, sample_pdf):
    original = open(sample_pdf, "rb").read()
    window.controller.session.update_warnings(0, _overflow_warning())

    with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Cancel) as warn:
        assert window.save_file() is False
        warn.assert_called_once()

    assert open(sample_pdf, "rb").read() == original  # nothing was written
    assert window.statusBar().currentMessage() == tr("status.ready")
    assert window.controller.session.modified is False  # untouched session


def test_blocking_warning_confirm_proceeds_with_save(window, sample_pdf):
    window.controller.session.update_warnings(0, _overflow_warning())

    with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Save):
        assert window.save_file() is True

    assert window.controller.session.modified is False
    reopened = fitz.open(sample_pdf)
    try:
        assert reopened.page_count == 2  # in-place save completed
    finally:
        reopened.close()


def test_warn_severity_alone_does_not_block(window, sample_pdf):
    window.controller.session.update_warnings(0, _shrink_warning())

    with patch.object(QMessageBox, "warning") as warn:
        assert window.save_file() is True
        warn.assert_not_called()


def test_error_on_any_page_blocks_the_whole_save(window):
    # warn on page 0, error on page 1: the error anywhere blocks.
    window.controller.session.update_warnings(0, _shrink_warning())
    window.controller.session.update_warnings(1, _overflow_warning())
    assert window.controller.session.has_blocking_warnings() is True

    with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Cancel) as warn:
        assert window.save_file() is False
        warn.assert_called_once()


def test_cleared_warnings_unblock_save_without_dialog(window, sample_pdf):
    """Shortening the replacement clears the overflow warning via an empty
    preview update; the save must then go through with no dialog."""
    window.controller.session.update_warnings(0, _overflow_warning())
    with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Cancel):
        assert window.save_file() is False

    window.controller.session.update_warnings(0, [])
    assert window.controller.session.has_blocking_warnings() is False

    with patch.object(QMessageBox, "warning") as warn:
        assert window.save_file() is True
        warn.assert_not_called()
