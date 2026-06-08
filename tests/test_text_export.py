"""Tests for text export (extract_text / export_text)."""
import pytest
import fitz
from app.model import DocumentSession


@pytest.fixture
def text_pdf(tmp_path):
    """Create a 3-page PDF with known text on each page."""
    pdf_path = tmp_path / "text_doc.pdf"
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), f"Hello page {i + 1}", fontsize=18)
    doc.save(str(pdf_path))
    doc.close()
    return str(pdf_path)


class TestExtractText:
    def test_whole_document_txt(self, text_pdf):
        session = DocumentSession(text_pdf)
        content = session.extract_text(None, "txt")
        assert "Hello page 1" in content
        assert "Hello page 2" in content
        assert "Hello page 3" in content
        session.close()

    def test_current_page_only(self, text_pdf):
        session = DocumentSession(text_pdf)
        content = session.extract_text([1], "txt")
        assert "Hello page 2" in content
        assert "Hello page 1" not in content
        assert "Hello page 3" not in content
        session.close()

    def test_markdown_has_page_headings(self, text_pdf):
        session = DocumentSession(text_pdf)
        content = session.extract_text(None, "md")
        assert "## Page 1" in content
        assert "## Page 3" in content
        assert "Hello page 2" in content
        session.close()

    def test_source_document_unchanged(self, text_pdf):
        session = DocumentSession(text_pdf)
        session.extract_text(None, "txt")
        assert session.modified is False
        assert session.doc.page_count == 3
        session.close()

    def test_invalid_format_raises(self, text_pdf):
        session = DocumentSession(text_pdf)
        with pytest.raises(ValueError, match="unsupported format"):
            session.extract_text(None, "docx")
        session.close()

    def test_out_of_range_index_raises(self, text_pdf):
        session = DocumentSession(text_pdf)
        with pytest.raises(IndexError, match="out of range"):
            session.extract_text([99], "txt")
        session.close()


class TestExportText:
    def test_writes_txt_file(self, text_pdf, tmp_path):
        session = DocumentSession(text_pdf)
        out = tmp_path / "out.txt"
        written = session.export_text(str(out), None, "txt")
        assert out.exists()
        text = out.read_text(encoding="utf-8")
        assert "Hello page 1" in text
        assert written == len(text)
        session.close()

    def test_writes_md_file(self, text_pdf, tmp_path):
        session = DocumentSession(text_pdf)
        out = tmp_path / "out.md"
        session.export_text(str(out), [0], "md")
        text = out.read_text(encoding="utf-8")
        assert "## Page 1" in text
        assert "Hello page 1" in text
        session.close()

    def test_empty_path_raises(self, text_pdf):
        session = DocumentSession(text_pdf)
        with pytest.raises(ValueError, match="output_path must not be empty"):
            session.export_text("", None, "txt")
        session.close()

    def test_nonexistent_dir_raises(self, text_pdf, tmp_path):
        session = DocumentSession(text_pdf)
        bad = tmp_path / "no_such_dir" / "out.txt"
        with pytest.raises(ValueError, match="output directory does not exist"):
            session.export_text(str(bad), None, "txt")
        session.close()

    def test_overwrite_source_blocked(self, text_pdf):
        session = DocumentSession(text_pdf)
        with pytest.raises(ValueError, match="Cannot overwrite source document"):
            session.export_text(text_pdf, None, "txt")
        session.close()

    def test_char_count_matches_written_file(self, text_pdf, tmp_path):
        session = DocumentSession(text_pdf)
        out = tmp_path / "count.txt"
        written = session.export_text(str(out), None, "txt")
        assert written == len(out.read_text(encoding="utf-8"))
        session.close()


class TestEngine:
    """Direct unit tests for the Qt-free text_export helpers."""

    def test_duplicate_indices_deduped_and_sorted(self, text_pdf):
        session = DocumentSession(text_pdf)
        content = session.extract_text([2, 0, 0], "txt")
        assert "Hello page 1" in content
        assert "Hello page 3" in content
        assert "Hello page 2" not in content
        session.close()

    def test_txt_has_no_markdown_headers(self, text_pdf):
        session = DocumentSession(text_pdf)
        content = session.extract_text(None, "txt")
        assert "## Page" not in content
        session.close()
