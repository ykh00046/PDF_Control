"""
Quick integration test for OperationApplicator refactoring.

Tests that the refactored code still works correctly.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fitz

from app.model import DocumentSession, RedactReplace
from app.operations_service import ApplyMode, OperationApplicator


def test_basic_refactoring():
    """Test that refactored OperationApplicator works."""

    # Create a simple test PDF
    test_pdf = Path("test_refactor.pdf")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 100), "Test text to replace", fontsize=12)
    doc.save(str(test_pdf))
    doc.close()

    try:
        # Test with DocumentSession (uses OperationApplicator internally)
        session = DocumentSession(str(test_pdf))
        page = session.doc[0]

        # Find and replace text
        rects = page.search_for("Test text")
        if rects:
            op = RedactReplace(0, [rects[0]], "REPLACED", fontsize=12)
            session.add_operation(op)

            # Save document (should use OperationApplicator with SAVE mode)
            output_pdf = Path("test_refactor_output.pdf")
            session.save_document(str(output_pdf))

            # Verify
            verify_doc = fitz.open(str(output_pdf))
            verify_page = verify_doc[0]
            text = verify_page.get_text()

            assert "REPLACED" in text, f"Expected 'REPLACED' in text, got: {text}"
            assert "Test text" not in text, f"Original text should be removed, got: {text}"

            print("✅ Test passed: Refactored DocumentSession works correctly")

            verify_doc.close()
            output_pdf.unlink()

        session.close()

    finally:
        if test_pdf.exists():
            test_pdf.unlink()


def test_applicator_directly():
    """Test OperationApplicator service directly."""

    # Create test PDF
    test_pdf = Path("test_applicator.pdf")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 100), "Direct test", fontsize=12)
    doc.save(str(test_pdf))
    doc.close()

    try:
        # Use OperationApplicator directly
        doc = fitz.open(str(test_pdf))
        page = doc[0]

        rects = page.search_for("Direct")
        if rects:
            op = RedactReplace(0, [rects[0]], "DIRECT", fontsize=12)

            # Apply with SAVE mode
            applicator = OperationApplicator()
            applicator.apply_operations(page, [op], ApplyMode.SAVE)

            # Save and verify
            output_pdf = Path("test_applicator_output.pdf")
            doc.save(str(output_pdf))
            doc.close()

            verify_doc = fitz.open(str(output_pdf))
            text = verify_doc[0].get_text()

            assert "DIRECT" in text, f"Expected 'DIRECT' in text, got: {text}"

            print("✅ Test passed: OperationApplicator works directly")

            verify_doc.close()
            output_pdf.unlink()

    finally:
        if test_pdf.exists():
            test_pdf.unlink()


if __name__ == "__main__":
    print("Testing refactored code...")
    test_basic_refactoring()
    test_applicator_directly()
    print("\n✅ All quick tests passed!")
