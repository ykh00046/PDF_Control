"""Tests for page management operations (rotate, delete, reorder, insert)."""
import pytest
import fitz
from app.model import DocumentSession, RedactDelete


@pytest.fixture
def multi_page_pdf(tmp_path):
    """Create a 5-page test PDF with text on each page."""
    pdf_path = tmp_path / "multi_page.pdf"
    doc = fitz.open()
    for i in range(5):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), f"Page {i + 1}", fontsize=24)
    doc.save(str(pdf_path))
    doc.close()
    return str(pdf_path)


class TestRotatePage:
    def test_rotate_90(self, multi_page_pdf):
        session = DocumentSession(multi_page_pdf)
        session.rotate_page(0, 90)
        assert session.doc[0].rotation == 90
        assert session.modified is True
        session.close()

    def test_rotate_180(self, multi_page_pdf):
        session = DocumentSession(multi_page_pdf)
        session.rotate_page(2, 180)
        assert session.doc[2].rotation == 180
        session.close()

    def test_rotate_cumulative(self, multi_page_pdf):
        session = DocumentSession(multi_page_pdf)
        session.rotate_page(0, 90)
        session.rotate_page(0, 90)
        assert session.doc[0].rotation == 180
        session.close()

    def test_rotate_360_resets(self, multi_page_pdf):
        session = DocumentSession(multi_page_pdf)
        for _ in range(4):
            session.rotate_page(0, 90)
        assert session.doc[0].rotation == 0
        session.close()

    def test_rotate_invalid_angle(self, multi_page_pdf):
        session = DocumentSession(multi_page_pdf)
        with pytest.raises(ValueError, match="multiple of 90"):
            session.rotate_page(0, 45)
        session.close()

    def test_rotate_clears_page_cache(self, multi_page_pdf):
        session = DocumentSession(multi_page_pdf)
        # Force cache creation
        page = session.doc[0]
        session.pages[0].get_words(page)
        assert session.pages[0]._words is not None
        # Rotate should clear cache
        session.rotate_page(0, 90)
        assert session.pages[0]._words is None
        session.close()


class TestDeletePages:
    def test_delete_single_page(self, multi_page_pdf):
        session = DocumentSession(multi_page_pdf)
        assert session.doc.page_count == 5
        session.delete_pages([2])
        assert session.doc.page_count == 4
        assert session.modified is True
        session.close()

    def test_delete_multiple_pages(self, multi_page_pdf):
        session = DocumentSession(multi_page_pdf)
        session.delete_pages([0, 2, 4])
        assert session.doc.page_count == 2
        session.close()

    def test_delete_all_pages_fails(self, multi_page_pdf):
        session = DocumentSession(multi_page_pdf)
        with pytest.raises(ValueError, match="Cannot delete all pages"):
            session.delete_pages([0, 1, 2, 3, 4])
        assert session.doc.page_count == 5  # Unchanged
        session.close()

    def test_delete_adjusts_operation_indices(self, multi_page_pdf):
        session = DocumentSession(multi_page_pdf)
        # Add operation on page 3 (index 3)
        op = RedactDelete(3, [fitz.Rect(0, 0, 100, 100)])
        session.add_operation(op)
        # Delete page 1 (index 1) - operations on page 3 should shift to page 2
        session.delete_pages([1])
        assert len(session.history) == 1
        assert session.history[0].page_index == 2
        session.close()

    def test_delete_removes_operations_on_deleted_page(self, multi_page_pdf):
        session = DocumentSession(multi_page_pdf)
        op = RedactDelete(2, [fitz.Rect(0, 0, 100, 100)])
        session.add_operation(op)
        session.delete_pages([2])
        assert len(session.history) == 0
        session.close()

    def test_delete_rebuilds_page_models(self, multi_page_pdf):
        session = DocumentSession(multi_page_pdf)
        session.delete_pages([0])
        assert len(session.pages) == 4
        for i, pm in enumerate(session.pages):
            assert pm.index == i
        session.close()


class TestMovePage:
    def test_move_page_forward(self, multi_page_pdf):
        session = DocumentSession(multi_page_pdf)
        # Move page 0 to position 2 (before page 2)
        session.move_page(0, 2)
        assert session.doc.page_count == 5
        assert session.modified is True
        # History should be cleared (reorder invalidates indices)
        assert len(session.history) == 0
        session.close()

    def test_move_same_position_noop(self, multi_page_pdf):
        session = DocumentSession(multi_page_pdf)
        session.move_page(2, 2)
        assert session.modified is False  # No change
        session.close()

    def test_move_rebuilds_pages(self, multi_page_pdf):
        session = DocumentSession(multi_page_pdf)
        session.move_page(0, 3)
        assert len(session.pages) == 5
        session.close()


class TestInsertBlankPage:
    def test_insert_at_end(self, multi_page_pdf):
        session = DocumentSession(multi_page_pdf)
        session.insert_blank_page()
        assert session.doc.page_count == 6
        assert session.modified is True
        session.close()

    def test_insert_after_specific_page(self, multi_page_pdf):
        session = DocumentSession(multi_page_pdf)
        session.insert_blank_page(after_index=1)
        assert session.doc.page_count == 6
        # The new page should be blank (no text)
        new_page = session.doc[2]
        assert new_page.get_text().strip() == ""
        session.close()

    def test_insert_adjusts_operation_indices(self, multi_page_pdf):
        session = DocumentSession(multi_page_pdf)
        op = RedactDelete(2, [fitz.Rect(0, 0, 100, 100)])
        session.add_operation(op)
        # Insert at index 1 -> operations on page 2 shift to page 3
        session.insert_blank_page(after_index=0)
        assert len(session.history) == 1
        assert session.history[0].page_index == 3
        session.close()

    def test_insert_default_a4_size(self, multi_page_pdf):
        session = DocumentSession(multi_page_pdf)
        session.insert_blank_page()
        last_page = session.doc[-1]
        # A4: 595 x 842 points
        assert abs(last_page.rect.width - 595) < 1
        assert abs(last_page.rect.height - 842) < 1
        session.close()


def _make_simple_pdf(path, num_pages, label_prefix="Other"):
    """Helper to fabricate a simple multi-page PDF for merge tests."""
    d = fitz.open()
    for i in range(num_pages):
        p = d.new_page(width=595, height=842)
        p.insert_text((72, 72), f"{label_prefix} {i + 1}", fontsize=18)
    d.save(str(path))
    d.close()


class TestDuplicatePages:
    def test_duplicate_single_increases_page_count(self, multi_page_pdf):
        session = DocumentSession(multi_page_pdf)
        original = session.doc.page_count
        added = session.duplicate_pages([0])
        assert added == 1
        assert session.doc.page_count == original + 1
        assert session.modified is True
        session.close()

    def test_duplicate_multiple_pages(self, multi_page_pdf):
        session = DocumentSession(multi_page_pdf)
        added = session.duplicate_pages([0, 2, 4])
        assert added == 3
        assert session.doc.page_count == 5 + 3
        session.close()

    def test_duplicate_preserves_content(self, multi_page_pdf):
        session = DocumentSession(multi_page_pdf)
        original_text = session.doc[2].get_text().strip()
        session.duplicate_pages([2])
        # PyMuPDF copy_page(2, 3) places copy at index 3
        assert session.doc[3].get_text().strip() == original_text
        session.close()

    def test_duplicate_empty_raises(self, multi_page_pdf):
        session = DocumentSession(multi_page_pdf)
        with pytest.raises(ValueError):
            session.duplicate_pages([])
        session.close()

    def test_duplicate_out_of_range_raises(self, multi_page_pdf):
        session = DocumentSession(multi_page_pdf)
        with pytest.raises(IndexError):
            session.duplicate_pages([99])
        session.close()


class TestExtractPages:
    def test_extract_creates_file_with_correct_count(self, multi_page_pdf, tmp_path):
        session = DocumentSession(multi_page_pdf)
        out = tmp_path / "extracted.pdf"
        session.extract_pages([0, 2], str(out))
        assert out.exists()
        with fitz.open(str(out)) as d:
            assert d.page_count == 2
        session.close()

    def test_extract_preserves_original(self, multi_page_pdf, tmp_path):
        session = DocumentSession(multi_page_pdf)
        out = tmp_path / "out.pdf"
        session.extract_pages([1, 3], str(out))
        assert session.doc.page_count == 5
        assert session.modified is False
        session.close()

    def test_extract_preserves_text_content(self, multi_page_pdf, tmp_path):
        session = DocumentSession(multi_page_pdf)
        out = tmp_path / "out.pdf"
        session.extract_pages([1], str(out))
        with fitz.open(str(out)) as d:
            assert "Page 2" in d[0].get_text()
        session.close()

    def test_extract_invalid_index_raises(self, multi_page_pdf, tmp_path):
        session = DocumentSession(multi_page_pdf)
        out = tmp_path / "out.pdf"
        with pytest.raises(IndexError):
            session.extract_pages([0, 99], str(out))
        session.close()

    def test_extract_empty_raises(self, multi_page_pdf, tmp_path):
        session = DocumentSession(multi_page_pdf)
        out = tmp_path / "out.pdf"
        with pytest.raises(ValueError):
            session.extract_pages([], str(out))
        session.close()

    def test_extract_overwriting_source_raises(self, multi_page_pdf):
        session = DocumentSession(multi_page_pdf)
        with pytest.raises(ValueError):
            session.extract_pages([0], multi_page_pdf)
        session.close()


class TestMergePdf:
    def test_merge_appends_at_end(self, multi_page_pdf, tmp_path):
        other = tmp_path / "other.pdf"
        _make_simple_pdf(other, 3)
        session = DocumentSession(multi_page_pdf)
        added = session.merge_pdf(str(other), after_index=-1)
        assert added == 3
        assert session.doc.page_count == 5 + 3
        assert session.modified is True
        session.close()

    def test_merge_at_specific_position(self, multi_page_pdf, tmp_path):
        other = tmp_path / "other.pdf"
        _make_simple_pdf(other, 1, label_prefix="Inserted")
        session = DocumentSession(multi_page_pdf)
        session.merge_pdf(str(other), after_index=1)  # after page index 1
        # Inserted page should be at index 2
        assert "Inserted" in session.doc[2].get_text()
        assert session.doc.page_count == 6
        session.close()

    def test_merge_nonexistent_raises(self, multi_page_pdf, tmp_path):
        session = DocumentSession(multi_page_pdf)
        missing = tmp_path / "does_not_exist.pdf"
        with pytest.raises(FileNotFoundError):
            session.merge_pdf(str(missing))
        session.close()

    def test_merge_invalid_after_index_raises(self, multi_page_pdf, tmp_path):
        other = tmp_path / "other.pdf"
        _make_simple_pdf(other, 1)
        session = DocumentSession(multi_page_pdf)
        with pytest.raises(ValueError):
            session.merge_pdf(str(other), after_index=99)
        session.close()
