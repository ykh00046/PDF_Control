"""Batch-replace page-range targeting (test-gap map §2-2).

``BatchReplaceDialog._get_target_pages`` feeds user range text into
``parse_page_range``. The contract exercised here:

* a range that overshoots the document ("3-99" on 10 pages) is CLAMPED to
  the existing pages (3-10), not rejected, and the find then runs only on
  those pages;
* an empty / whitespace / "all" input targets every page;
* a completely invalid input ("5-2", "0", "-3", "11", "3a", "abc") raises
  ValueError inside the parser, which the dialog turns into a warning box
  and an aborted search (returns None);
* harmless junk mixed with valid parts (blank segments, a reverse range)
  is skipped while the valid parts still apply;
* a failed parse leaves the previous match list untouched (no partial run).
"""

import fitz
import pytest
from PySide6.QtWidgets import QMessageBox

from app.batch_replace_dialog import BatchReplaceDialog
from app.document_session import DocumentSession


@pytest.fixture
def ten_page_needle_pdf(tmp_path):
    """A 10-page PDF with one unique-but-shared needle line per page."""
    pdf_path = tmp_path / "batch_range.pdf"
    doc = fitz.open()
    for number in range(1, 11):
        page = doc.new_page(width=300, height=400)
        page.insert_text((30, 40), f"page {number} NEEDLE text", fontsize=11)
    doc.save(pdf_path)
    doc.close()
    return str(pdf_path)


@pytest.fixture
def batch_dialog(qtbot, ten_page_needle_pdf):
    session = DocumentSession(ten_page_needle_pdf)
    dialog = BatchReplaceDialog(session)
    qtbot.addWidget(dialog)
    yield dialog
    session.close()


def _targets(dialog, text):
    dialog.page_range_input.setText(text)
    return dialog._get_target_pages()


def test_empty_range_targets_all_pages(batch_dialog):
    assert _targets(batch_dialog, "") == set(range(10))


def test_whitespace_range_targets_all_pages(batch_dialog):
    assert _targets(batch_dialog, "   ") == set(range(10))


def test_all_keyword_targets_all_pages(batch_dialog):
    assert _targets(batch_dialog, "all") == set(range(10))


def test_overshooting_range_is_clamped_to_document(batch_dialog):
    """'3-99' on a 10-page document must mean pages 3-10, not an error."""
    assert _targets(batch_dialog, "3-99") == set(range(2, 10))


def test_undershooting_range_is_clamped_to_first_page(batch_dialog):
    assert _targets(batch_dialog, "0-4") == set(range(0, 4))


@pytest.mark.parametrize("bad_range", ["5-2", "0", "-3", "11", "3a", "abc"])
def test_invalid_range_warns_and_aborts_search(batch_dialog, monkeypatch, bad_range):
    """Inputs with no valid page end in a warning box + None (search aborted)."""
    warnings = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda *args, **kwargs: warnings.append(args) or QMessageBox.StandardButton.Ok),
    )
    assert _targets(batch_dialog, bad_range) is None
    assert len(warnings) == 1


def test_harmless_junk_parts_are_skipped(batch_dialog):
    # Blank segments disappear; the lone reverse range "5-2" contributes
    # nothing while the valid "1" still applies.
    assert _targets(batch_dialog, "1,,3") == {0, 2}
    assert _targets(batch_dialog, "1,5-2") == {0}
    assert _targets(batch_dialog, "3a,2") == {1}


def test_find_uses_clamped_range_end_to_end(batch_dialog, monkeypatch):
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))
    batch_dialog.page_range_input.setText("3-99")
    batch_dialog.find_what_input.setText("NEEDLE")
    batch_dialog._find_all_matches()

    matched_pages = {match["page_index"] + 1 for match in batch_dialog.matches}
    # Exactly pages 3-10 carry matches; pages 1-2 exist and contain the
    # needle but sit outside the clamped target set.
    assert matched_pages == set(range(3, 11))
    assert len(batch_dialog.matches) == 8
    assert batch_dialog.replace_all_button.isEnabled()


def test_failed_range_parse_keeps_previous_results(batch_dialog, monkeypatch):
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))
    batch_dialog.page_range_input.setText("2-4")
    batch_dialog.find_what_input.setText("NEEDLE")
    batch_dialog._find_all_matches()
    before = list(batch_dialog.matches)
    assert before  # sanity: the first search found something

    # An invalid range aborts the search while leaving the previous result
    # set untouched (no half-cleared state to replace by accident).
    batch_dialog.page_range_input.setText("5-2")
    batch_dialog._find_all_matches()
    assert batch_dialog.matches == before
    assert batch_dialog.matches_table.rowCount() == len(before)
