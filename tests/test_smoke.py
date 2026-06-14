
import fitz
import pytest

from app.fonts import get_font_path_by_name
from app.model import DocumentSession, RedactDelete, RedactReplace


@pytest.fixture
def sample_pdf(tmp_path):
    """Creates a sample PDF in a temporary directory."""
    sample_path = tmp_path / "sample.pdf"

    doc = fitz.open()
    page = doc.new_page()

    page.insert_text((50, 70), "This is a sample document for testing purposes.", fontsize=12)
    page.insert_text((50, 100), "The number 12345 should be replaced.", fontsize=12)
    page.insert_text((50, 130), "This sentence needs to be deleted.", fontsize=12)

    doc.save(str(sample_path))
    doc.close()

    return sample_path

@pytest.fixture
def multi_page_pdf(tmp_path):
    """Creates a multi-page PDF for testing."""
    pdf_path = tmp_path / "multipage.pdf"

    doc = fitz.open()

    # Page 1
    page1 = doc.new_page()
    page1.insert_text((50, 70), "Page 1: Text to replace", fontsize=12)

    # Page 2
    page2 = doc.new_page()
    page2.insert_text((50, 70), "Page 2: Another text", fontsize=12)

    # Page 3
    page3 = doc.new_page()
    page3.insert_text((50, 70), "Page 3: More content", fontsize=12)

    doc.save(str(pdf_path))
    doc.close()

    return pdf_path

def test_pdf_redaction_and_replacement_with_custom_font(sample_pdf, tmp_path):
    """
    Tests the core document modification logic, including custom font embedding.
    """
    output_path = tmp_path / "output_edited.pdf"
    session = None
    modified_doc = None
    try:
        # 1. Setup and Find Rects
        session = DocumentSession(str(sample_pdf))
        page = session.doc[0]
        page_index = 0

        replace_rects = page.search_for("12345")
        assert len(replace_rects) > 0, "Could not find '12345' for replacement."
        rect_to_replace = replace_rects[0]

        delete_rects = page.search_for("This sentence needs to be deleted.")
        assert len(delete_rects) > 0, "Could not find 'This sentence needs to be deleted.' for deletion."
        rect_to_delete = delete_rects[0]

        # 2. Find a custom font
        font_name = "Comic Sans MS"
        font_file = get_font_path_by_name(font_name)
        if font_file is None:
            pytest.skip(f"Test font '{font_name}' not available on this system")

        # 3. Apply Operations
        replace_op = RedactReplace(page_index, [rect_to_replace], "REP", fontfile=font_file, fontsize=8)
        session.add_operation(replace_op)
        delete_op = RedactDelete(page_index, [rect_to_delete])
        session.add_operation(delete_op)

        # 4. Save
        session.save_document(str(output_path))

        # 5. Verify
        modified_doc = fitz.open(str(output_path))
        modified_page = modified_doc[0]
        page_text = modified_page.get_text()

        assert "REP" in page_text
        assert "12345" not in page_text
        assert "This sentence needs to be deleted." not in page_text

        # 6. Verify Font Embedding
        page_fonts = modified_doc.get_page_fonts(0)
        embedded_font_found = False

        # Check if any embedded font's name contains the original font name
        for font_info in page_fonts:
            font_name_in_pdf = font_info[3] # Base font name
            if "comic" in font_name_in_pdf.lower():
                embedded_font_found = True
                break

        assert embedded_font_found, (
            f"Custom font '{font_name}' was not embedded correctly. "
            f"Fonts found: {[f[3] for f in page_fonts]}"
        )
        print(f"Test successful: {output_path} verified with custom font embedding.")

    finally:
        if session:
            session.close()
        if modified_doc:
            modified_doc.close()


def test_undo_redo_roundtrip(sample_pdf, tmp_path):
    """Tests undo/redo functionality maintains consistency."""
    session = None
    try:
        session = DocumentSession(str(sample_pdf))
        page = session.doc[0]

        # Find text to replace
        replace_rects = page.search_for("12345")
        assert len(replace_rects) > 0

        # Apply operation
        op = RedactReplace(0, [replace_rects[0]], "XXXXX")
        session.add_operation(op)

        # Verify operation added
        assert len(session.history) == 1
        assert len(session.redo_stack) == 0
        assert session.modified is True

        # Undo
        undone_op = session.undo()
        assert undone_op is not None
        assert len(session.history) == 0
        assert len(session.redo_stack) == 1
        assert session.modified is False

        # Redo
        redone_op = session.redo()
        assert redone_op is not None
        assert len(session.history) == 1
        assert len(session.redo_stack) == 0
        assert session.modified is True

        print("Undo/Redo roundtrip test passed!")

    finally:
        if session:
            session.close()


def test_save_clears_history(sample_pdf, tmp_path):
    """Tests that saving clears history and redo stack."""
    output_path = tmp_path / "saved_output.pdf"
    session = None
    try:
        session = DocumentSession(str(sample_pdf))
        page = session.doc[0]

        # Add operations
        replace_rects = page.search_for("12345")
        op1 = RedactReplace(0, [replace_rects[0]], "AAA")
        session.add_operation(op1)

        delete_rects = page.search_for("This sentence needs to be deleted.")
        op2 = RedactDelete(0, [delete_rects[0]])
        session.add_operation(op2)

        # Verify operations in history
        assert len(session.history) == 2
        assert session.modified is True

        # Save document
        session.save_document(str(output_path))

        # Verify history cleared after save
        assert len(session.history) == 0
        assert len(session.redo_stack) == 0
        assert session.modified is False

        print("Save clears history test passed!")

    finally:
        if session:
            session.close()


def test_multi_page_operations(multi_page_pdf, tmp_path):
    """Tests operations on multiple pages."""
    output_path = tmp_path / "multipage_output.pdf"
    session = None
    modified_doc = None
    try:
        session = DocumentSession(str(multi_page_pdf))

        # Page 1: Replace
        page1 = session.doc[0]
        rects_p1 = page1.search_for("Page 1")
        op1 = RedactReplace(0, [rects_p1[0]], "REP", fontsize=8)
        session.add_operation(op1)

        # Page 2: Delete
        page2 = session.doc[1]
        rects_p2 = page2.search_for("Another text")
        op2 = RedactDelete(1, [rects_p2[0]])
        session.add_operation(op2)

        # Page 3: Replace
        page3 = session.doc[2]
        rects_p3 = page3.search_for("More content")
        op3 = RedactReplace(2, [rects_p3[0]], "MOD", fontsize=8)
        session.add_operation(op3)

        # Verify history
        assert len(session.history) == 3

        # Save
        session.save_document(str(output_path))

        # Verify changes
        modified_doc = fitz.open(str(output_path))

        page1_text = modified_doc[0].get_text()
        assert "REP" in page1_text
        assert "Page 1" not in page1_text

        page2_text = modified_doc[1].get_text()
        assert "Another text" not in page2_text

        page3_text = modified_doc[2].get_text()
        assert "MOD" in page3_text
        assert "More content" not in page3_text

        print("Multi-page operations test passed!")

    finally:
        if session:
            session.close()
        if modified_doc:
            modified_doc.close()
