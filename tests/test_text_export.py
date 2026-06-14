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


class TestExportRange:
    """text-export-range: page-range scope wired through parse_page_ranges."""

    def test_range_spec_exports_only_those_pages(self, text_pdf, tmp_path):
        from app.page_split import parse_page_ranges

        session = DocumentSession(text_pdf)
        try:
            # Mirror the handler: parse "1-2, ..." -> flatten -> export.
            groups = parse_page_ranges("1-2", session.doc.page_count)
            page_indices = [i for g in groups for i in g]
            out = tmp_path / "range.txt"
            session.export_text(str(out), page_indices, "txt")
            text = out.read_text(encoding="utf-8")
            assert "Hello page 1" in text
            assert "Hello page 2" in text
            assert "Hello page 3" not in text
        finally:
            session.close()

    def test_range_non_contiguous(self, text_pdf, tmp_path):
        from app.page_split import parse_page_ranges

        session = DocumentSession(text_pdf)
        try:
            groups = parse_page_ranges("1, 3", session.doc.page_count)
            page_indices = [i for g in groups for i in g]
            out = tmp_path / "range2.txt"
            session.export_text(str(out), page_indices, "txt")
            text = out.read_text(encoding="utf-8")
            assert "Hello page 1" in text
            assert "Hello page 2" not in text
            assert "Hello page 3" in text
        finally:
            session.close()

    def test_invalid_range_raises(self, text_pdf):
        from app.page_split import parse_page_ranges

        session = DocumentSession(text_pdf)
        try:
            with pytest.raises(ValueError):
                parse_page_ranges("5-9", session.doc.page_count)  # exceeds 3 pages
            with pytest.raises(ValueError):
                parse_page_ranges("", session.doc.page_count)  # empty
        finally:
            session.close()


class TestExportDialogSettings:
    """Dialog get_settings must surface the range scope + spec (was dropped)."""

    def test_range_scope_returns_spec(self, qtbot):
        from app.text_export_dialog import TextExportDialog

        dialog = TextExportDialog()
        qtbot.addWidget(dialog)
        dialog.scope_range.setChecked(True)
        dialog.range_edit.setText("2-4, 6")
        settings = dialog.get_settings()
        assert settings["scope"] == "range"
        assert settings["range"] == "2-4, 6"

    def test_all_scope_default(self, qtbot):
        from app.text_export_dialog import TextExportDialog

        dialog = TextExportDialog()
        qtbot.addWidget(dialog)
        assert dialog.get_settings()["scope"] == "all"

    def test_current_scope(self, qtbot):
        from app.text_export_dialog import TextExportDialog

        dialog = TextExportDialog()
        qtbot.addWidget(dialog)
        dialog.scope_current.setChecked(True)
        assert dialog.get_settings()["scope"] == "current"


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
