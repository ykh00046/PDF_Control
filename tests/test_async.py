import pytest
from PySide6.QtCore import Qt
from app.ui import MainWindow
import time
import fitz
import os

@pytest.fixture
def main_window(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    return window

def test_async_rendering_and_cache(main_window, qtbot, tmp_path):
    """Verify async rendering works and cache is utilized."""
    # Create sample PDF
    pdf_path = tmp_path / "test_async.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Async Test")
    doc.save(str(pdf_path))
    doc.close()
    
    # Load document (triggers render request)
    main_window.controller.load_document(str(pdf_path))
    
    # Wait for render to complete (signal waiter or simple sleep loop)
    # Since we don't have a direct signal exposed on viewer for "render finished" easily reachable from test without mocking,
    # we check if scene has items.
    
    def check_render_complete():
        return len(main_window.viewer.scene.items()) > 0
        
    qtbot.waitUntil(check_render_complete, timeout=5000)
    
    # Verify scene populated
    assert len(main_window.viewer.scene.items()) > 0
    
    # Verify cache populated
    assert len(main_window.viewer.image_cache) == 1
    print("Initial render complete and cached.")
    
    # Zoom change -> should trigger new render
    main_window.viewer.zoom_in()
    
    # Clear scene to verify re-render
    main_window.viewer.scene.clear()
    
    qtbot.waitUntil(check_render_complete, timeout=5000)
    assert len(main_window.viewer.image_cache) == 2 # New zoom level cached
    print("Zoom render complete and cached.")
    
    # Zoom back to original -> should hit cache
    # We can mock _update_scene to verify it's called synchronously?
    # Or check logs? 
    # For now, just ensure it renders correctly.
    main_window.viewer.zoom_out()
    qtbot.waitUntil(check_render_complete, timeout=1000) # Should be fast
    
    # Cache size should remain 2 (original 1.0 and zoomed 1.2)
    assert len(main_window.viewer.image_cache) == 2
    print("Cache hit verified (size did not increase).")

