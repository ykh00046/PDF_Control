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
