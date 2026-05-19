import pytest
import fitz
from PySide6.QtCore import Qt
from app.ui import MainWindow
from app.model import RemoveSectionAsImage
import os

@pytest.fixture
def main_window(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    return window

def test_viewer_render_crash_with_remove_section(main_window, qtbot, tmp_path):
    """Verify that rendering RemoveSectionAsImage in preview doesn't crash the viewer."""
    # Create a dummy PDF
    pdf_path = tmp_path / "test_crash.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Test Page")
    doc.save(str(pdf_path))
    doc.close()
    
    # Load document
    main_window.controller.load_document(str(pdf_path))
    qtbot.waitUntil(lambda: len(main_window.viewer.scene.items()) > 0, timeout=5000)
    baseline_height = main_window.viewer.current_pixmap_item.pixmap().height()
    
    # Add RemoveSectionAsImage operation
    # Removing a middle section
    rect = fitz.Rect(0, 100, 595, 200)
    op = RemoveSectionAsImage(0, rect, dpi=72, format="png")
    
    # This triggers viewer.render_current_page_with_operations() via signal
    main_window.controller.add_operation(op)
    qtbot.waitUntil(
        lambda: (
            main_window.viewer.current_pixmap_item is not None
            and main_window.viewer.current_pixmap_item.pixmap().height() < baseline_height
        ),
        timeout=5000,
    )

    # If we reach here without crash, it's good.
    # Let's verify that the scene has items (meaning render succeeded)
    assert len(main_window.viewer.scene.items()) > 0
    assert main_window.viewer.current_pixmap_item.pixmap().height() < baseline_height
    
    # Verify that the viewer's current page index is still valid
    assert main_window.viewer.current_page_index == 0
    
    print("Viewer handled RemoveSectionAsImage preview without crashing.")
