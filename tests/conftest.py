"""
Shared pytest fixtures for PDF Control tests.

This module provides reusable fixtures for creating test PDFs,
eliminating dependencies on external sample files.
"""

import os
import shutil
from pathlib import Path

import fitz
import pytest


@pytest.fixture
def tmp_path(request):
    """
    Workspace-local temporary directory.

    This avoids relying on system temp locations that may be unavailable in
    sandboxed or restricted environments.
    """
    root = Path(__file__).resolve().parent.parent / "logs" / "pytest_tmp"
    root.mkdir(parents=True, exist_ok=True)
    case_name = request.node.name.replace(os.sep, "_").replace(":", "_")
    temp_dir = root / case_name
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(autouse=True)
def _suppress_close_confirm_dialog(monkeypatch):
    """Auto-dismiss 'save changes?' modal so qtbot teardown does not hang.

    Any test that instantiates a MainWindow with a modified session would
    otherwise block on QMessageBox.question during pytest-qt teardown.
    """
    try:
        from PySide6.QtWidgets import QMessageBox
    except ImportError:
        return
    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Discard,
    )


@pytest.fixture(autouse=True)
def isolated_app_environment(monkeypatch, tmp_path):
    """Isolate config/log writes per test case."""
    app_data_dir = tmp_path / "appdata"
    monkeypatch.setenv("PDF_CONTROL_APP_DATA_DIR", str(app_data_dir))

    import app.logger as app_logger

    if app_logger._logger is not None:
        for handler in list(app_logger._logger.handlers):
            handler.close()
            app_logger._logger.removeHandler(handler)
        app_logger._logger = None
    app_logger._log_file_path = None

    yield


@pytest.fixture
def simple_pdf(tmp_path):
    """
    Generate a simple single-page PDF for testing.

    Args:
        tmp_path: pytest's temporary directory fixture

    Returns:
        Path: Path to the generated PDF file

    Example:
        >>> def test_open_pdf(simple_pdf):
        ...     doc = fitz.open(simple_pdf)
        ...     assert doc.page_count == 1
    """
    pdf_path = tmp_path / "test_simple.pdf"

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4 size in points

    # Add some text for selection/deletion/replacement tests
    page.insert_text((50, 100), "Test text for selection", fontsize=12)
    page.insert_text((50, 150), "Second line of text", fontsize=12)
    page.insert_text((50, 200), "Third line for batch operations", fontsize=12)

    doc.save(pdf_path)
    doc.close()

    return pdf_path


@pytest.fixture
def encrypted_pdf(tmp_path):
    """Generate an AES-256 encrypted single-page PDF (user password 'open123').

    Returns:
        Path: Path to the password-protected PDF file.
    """
    pdf_path = tmp_path / "test_encrypted.pdf"

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 100), "Secret content for decryption tests", fontsize=12)
    doc.save(
        pdf_path,
        encryption=fitz.PDF_ENCRYPT_AES_256,
        user_pw="open123",
        owner_pw="open123",
    )
    doc.close()

    return pdf_path


@pytest.fixture
def multipage_pdf(tmp_path):
    """
    Generate a multi-page PDF for testing.

    Args:
        tmp_path: pytest's temporary directory fixture

    Returns:
        Path: Path to the generated PDF file with 3 pages
    """
    pdf_path = tmp_path / "test_multipage.pdf"

    doc = fitz.open()

    # Page 1
    page1 = doc.new_page(width=595, height=842)
    page1.insert_text((50, 100), "Page 1 - Test Content", fontsize=14)
    page1.insert_text((50, 150), "Some text to delete", fontsize=12)

    # Page 2
    page2 = doc.new_page(width=595, height=842)
    page2.insert_text((50, 100), "Page 2 - More Content", fontsize=14)
    page2.insert_text((50, 150), "Text for replacement", fontsize=12)

    # Page 3
    page3 = doc.new_page(width=595, height=842)
    page3.insert_text((50, 100), "Page 3 - Final Page", fontsize=14)

    doc.save(pdf_path)
    doc.close()

    return pdf_path


@pytest.fixture
def complex_pdf(tmp_path):
    """
    Generate a PDF with various text styles and formatting.

    Useful for testing font-related operations.

    Args:
        tmp_path: pytest's temporary directory fixture

    Returns:
        Path: Path to the generated PDF file
    """
    pdf_path = tmp_path / "test_complex.pdf"

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    # Different font sizes
    page.insert_text((50, 100), "Large text", fontsize=18)
    page.insert_text((50, 130), "Medium text", fontsize=14)
    page.insert_text((50, 155), "Small text", fontsize=10)

    # Different positions for selection testing
    page.insert_text((50, 200), "Left aligned text", fontsize=12)
    page.insert_text((300, 200), "Right side text", fontsize=12)

    # Long text for wrapping/scaling tests
    long_text = "This is a very long text that might require font scaling when replaced in narrow areas."
    page.insert_text((50, 250), long_text, fontsize=12)

    # Text with special characters
    page.insert_text((50, 300), "Special: @#$%^&*()", fontsize=12)

    doc.save(pdf_path)
    doc.close()

    return pdf_path


@pytest.fixture
def large_pdf(tmp_path):
    """
    Generate a PDF with a large page size for section removal tests.

    Args:
        tmp_path: pytest's temporary directory fixture

    Returns:
        Path: Path to the generated PDF file (A3 size)
    """
    pdf_path = tmp_path / "test_large.pdf"

    doc = fitz.open()
    # A3 size (842 x 1191 points)
    page = doc.new_page(width=842, height=1191)

    # Add content in different sections
    page.insert_text((50, 100), "Top Section - Header", fontsize=16)
    page.insert_text((50, 500), "Middle Section - To Remove", fontsize=14)
    page.insert_text((50, 1000), "Bottom Section - Footer", fontsize=16)

    # Add a rectangle for visual separation
    page.draw_rect(fitz.Rect(40, 450, 802, 550), color=(0, 0, 0), width=2)

    doc.save(pdf_path)
    doc.close()

    return pdf_path


@pytest.fixture
def pdf_with_korean(tmp_path):
    """
    Generate a PDF with Korean text for i18n testing.

    Args:
        tmp_path: pytest's temporary directory fixture

    Returns:
        Path: Path to the generated PDF file
    """
    pdf_path = tmp_path / "test_korean.pdf"

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    # Note: Basic insertion may not render Korean correctly without proper font
    # This is mainly for testing text extraction and selection
    page.insert_text((50, 100), "한글 테스트", fontsize=12)
    page.insert_text((50, 150), "English and 한글 Mixed", fontsize=12)

    doc.save(pdf_path)
    doc.close()

    return pdf_path


@pytest.fixture
def empty_pdf(tmp_path):
    """
    Generate a PDF with a blank page.

    Useful for testing edge cases.

    Args:
        tmp_path: pytest's temporary directory fixture

    Returns:
        Path: Path to the generated PDF file
    """
    pdf_path = tmp_path / "test_empty.pdf"

    doc = fitz.open()
    doc.new_page(width=595, height=842)  # Blank page

    doc.save(pdf_path)
    doc.close()

    return pdf_path
