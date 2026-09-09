"""Tests for the r8-ux-expansion file actions: Save (in place), Close,
Open Recent, the shared unsaved-changes prompt, and history panel labels."""

import os
from unittest.mock import patch

import fitz
import pytest
from PySide6.QtWidgets import QFileDialog, QMessageBox

from app.model import DocumentSession, RedactDelete, WatermarkImage, WatermarkText
from app.recent_files import get_recent_files
from app.ui import MainWindow


@pytest.fixture
def two_page_pdf(tmp_path):
    path = tmp_path / "Report.PDF"  # upper-case extension on purpose
    doc = fitz.open()
    doc.new_page().insert_text((50, 80), "page one", fontsize=12)
    doc.new_page().insert_text((50, 80), "page two", fontsize=12)
    doc.save(path)
    doc.close()
    return os.path.abspath(path)


@pytest.fixture
def window(qtbot, two_page_pdf):
    win = MainWindow()
    qtbot.addWidget(win)
    win.controller.load_document(two_page_pdf)
    return win


# ------------------------------------------------------------ session: Save
def test_session_save_in_place_writes_edits_and_rebinds(two_page_pdf):
    session = DocumentSession(two_page_pdf)
    try:
        session.add_operation(RedactDelete(0, [fitz.Rect(40, 60, 200, 100)]))
        session.delete_pages([1])
        assert session.is_same_file(two_page_pdf)
        assert session.is_same_file(two_page_pdf.lower())

        session.save_document(two_page_pdf)

        assert session.modified is False
        assert session.history == []
        assert session.file_path == two_page_pdf
        assert session.doc.page_count == 1
        assert "page one" not in session.doc[0].get_text()
        assert not os.path.exists(two_page_pdf + ".saving.tmp")
    finally:
        session.close()

    reopened = fitz.open(two_page_pdf)
    try:
        assert reopened.page_count == 1
        assert "page one" not in reopened[0].get_text()
    finally:
        reopened.close()


def test_session_save_in_place_failure_keeps_original(two_page_pdf, monkeypatch):
    session = DocumentSession(two_page_pdf)
    try:
        session.add_operation(RedactDelete(0, [fitz.Rect(40, 60, 200, 100)]))

        def boom(*_args, **_kwargs):
            raise OSError("disk full")

        monkeypatch.setattr("app.document_session.os.replace", boom)
        with pytest.raises(OSError):
            session.save_document(two_page_pdf)

        # Session still usable on the untouched original; temp file cleaned up.
        assert not session.doc.is_closed
        assert session.doc.page_count == 2
        assert session.modified is True
        assert len(session.history) == 1
        assert not os.path.exists(two_page_pdf + ".saving.tmp")
    finally:
        session.close()
    assert fitz.open(two_page_pdf).page_count == 2


# ---------------------------------------------------------- handlers: Save
def test_save_file_overwrites_without_dialog(window, two_page_pdf):
    window.controller.session.add_operation(RedactDelete(0, [fitz.Rect(40, 60, 200, 100)]))
    with patch.object(QFileDialog, "getSaveFileName") as picker:
        assert window.save_file() is True
        picker.assert_not_called()
    assert window.controller.session.modified is False
    assert window.controller.session.file_path == two_page_pdf
    assert two_page_pdf in get_recent_files(window.config)


def test_save_file_redirects_encrypted_document(window, monkeypatch):
    monkeypatch.setattr(window.controller, "is_current_encrypted", lambda: True)
    called = []
    monkeypatch.setattr(window, "save_file_encrypted", lambda: called.append(True) or False)
    assert window.save_file() is False
    assert called == [True]


def test_save_as_suggested_path_uses_splitext(window, two_page_pdf):
    captured = {}

    def fake_picker(_parent, _title, suggested, _filter):
        captured["suggested"] = suggested
        return "", ""

    with patch.object(QFileDialog, "getSaveFileName", side_effect=fake_picker):
        window.save_file_as()
    root, _ext = os.path.splitext(two_page_pdf)
    assert captured["suggested"] == f"{root}_edited.pdf"


# ----------------------------------------------------- handlers: Close/Open
def test_close_file_clears_session_and_actions(window):
    assert window.close_action.isEnabled()
    assert window.close_file() is True
    assert window.controller.session is None
    assert not window.close_action.isEnabled()
    assert not window.save_action.isEnabled()
    assert window.close_file() is False  # nothing to close


def test_close_file_cancel_keeps_document(window, monkeypatch):
    window.controller.session.add_operation(RedactDelete(0, [fitz.Rect(40, 60, 200, 100)]))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Cancel)
    assert window.close_file() is False
    assert window.controller.session is not None


def test_open_recent_file_loads_and_prunes_missing(window, two_page_pdf, tmp_path):
    missing = str(tmp_path / "gone.pdf")
    window.config["recent_files"] = [missing, two_page_pdf]
    with patch.object(QMessageBox, "warning") as warn:
        assert window.open_recent_file(missing) is False
        warn.assert_called_once()
    assert get_recent_files(window.config) == [two_page_pdf]

    window.controller.close_document()
    assert window.open_recent_file(two_page_pdf) is True
    assert window.controller.session.file_path == two_page_pdf


def test_recent_menu_lists_entries_and_clear(window, two_page_pdf):
    window.config["recent_files"] = [two_page_pdf]
    window._populate_recent_menu()
    texts = [a.text() for a in window.recent_menu.actions() if not a.isSeparator()]
    assert any(os.path.basename(two_page_pdf) in t for t in texts)
    window.clear_recent_files()
    window._populate_recent_menu()
    non_sep = [a for a in window.recent_menu.actions() if not a.isSeparator()]
    assert len(non_sep) == 1 and not non_sep[0].isEnabled()


# --------------------------------------------------------- history labels
def test_history_panel_labels_watermarks(window, tmp_path):
    session = window.controller.session
    session.add_operation(WatermarkText(0, "DRAFT"))
    session.add_operation(WatermarkImage(0, str(tmp_path / "logo.png")))
    window._update_history_panel()
    items = [window.history_list_widget.item(i).text() for i in range(window.history_list_widget.count())]
    assert not any("WatermarkText" in t or "WatermarkImage" in t for t in items)
    assert any("logo.png" in t for t in items)
