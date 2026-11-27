"""Render-worker error-exit handling in PDFViewer (test-gap map §2-10).

``PDFViewer._on_render_process_finished`` covers the paths where the render
subprocess dies instead of producing an image:

* a non-zero exit without a response file surfaces the stderr text, emits
  ``render_finished`` (so the UI never stays in a "rendering" state), and
  cleans up the scratch job/response/image files;
* a response file with a structured error wins over the generic message;
* a result whose request key no longer matches the viewer state is ignored
  entirely (stale guard) but its files are still cleaned up;
* a zero exit whose response reports success=false is an error too;
* after any error the viewer accepts a subsequent render request, and the
  previously rendered page image stays on the scene (no blank viewer).
"""

import json
from pathlib import Path

import fitz
import pytest
from PySide6.QtGui import QImage

from app.document_session import DocumentSession
from app.viewer import PDFViewer


@pytest.fixture
def one_page_pdf(tmp_path):
    pdf_path = tmp_path / "viewer_error.pdf"
    doc = fitz.open()
    doc.new_page().insert_text((50, 80), "viewer error probe", fontsize=12)
    doc.save(pdf_path)
    doc.close()
    return str(pdf_path)


@pytest.fixture
def viewer(qtbot, one_page_pdf):
    view = PDFViewer()
    qtbot.addWidget(view)
    # Assign the session directly: set_document_session() would kick off a
    # real render subprocess, which is exactly what these tests stub away.
    view.session = DocumentSession(one_page_pdf)
    view.current_page_index = 0
    yield view
    if view.session is not None:
        view.session.close()


def _context(viewer, tmp_path, tag):
    job = Path(tmp_path) / f"{tag}.job.json"
    response = Path(tmp_path) / f"{tag}.response.json"
    image = Path(tmp_path) / f"{tag}.png"
    return {
        "request_key": viewer._current_cache_key(),
        "job_path": job,
        "response_path": response,
        "image_path": image,
    }


def test_nonzero_exit_reports_stderr_and_finishes(viewer, qtbot, tmp_path):
    context = _context(viewer, tmp_path, "e1")
    context["job_path"].write_text("{}", encoding="utf-8")
    context["image_path"].write_bytes(b"")

    with qtbot.waitSignal(viewer.render_finished, timeout=1000):
        viewer._on_render_process_finished(1, "worker exploded", context)

    # Scratch files from the failed attempt are gone (no litter in temp).
    assert not context["job_path"].exists()
    assert not context["response_path"].exists()
    assert not context["image_path"].exists()


def test_structured_error_from_response_is_preferred(viewer, qtbot, tmp_path):
    context = _context(viewer, tmp_path, "e2")
    context["response_path"].write_text(json.dumps({"success": False, "error": "structured failure"}), encoding="utf-8")

    with qtbot.waitSignal(viewer.render_finished, timeout=1000):
        viewer._on_render_process_finished(1, "", context)


def test_success_false_response_is_an_error(viewer, qtbot, tmp_path):
    context = _context(viewer, tmp_path, "e3")
    context["response_path"].write_text(json.dumps({"success": False, "error": "page out of range"}), encoding="utf-8")

    with qtbot.waitSignal(viewer.render_finished, timeout=1000):
        viewer._on_render_process_finished(0, "", context)


def test_stale_result_is_ignored_but_files_cleaned(viewer, qtbot, tmp_path):
    context = _context(viewer, tmp_path, "e4")
    context["request_key"] = "a-key-from-a-previous-zoom"
    context["job_path"].write_text("{}", encoding="utf-8")

    with qtbot.assertNotEmitted(viewer.render_finished):
        viewer._on_render_process_finished(1, "boom", context)

    assert not context["job_path"].exists()
    assert len(viewer.image_cache) == 0  # nothing cached from the failure


def test_error_keeps_previous_page_image(viewer, qtbot, tmp_path):
    viewer._update_scene(QImage(60, 80, QImage.Format_RGB32))
    items_before = len(viewer.scene.items())

    context = _context(viewer, tmp_path, "e5")
    with qtbot.waitSignal(viewer.render_finished, timeout=1000):
        viewer._on_render_process_finished(1, "boom", context)

    # The last good page stays on screen; the viewer never goes blank.
    assert len(viewer.scene.items()) == items_before
    assert viewer.current_pixmap_item is not None


def test_viewer_accepts_next_render_after_error(viewer, qtbot, tmp_path):
    context = _context(viewer, tmp_path, "e6")
    with qtbot.waitSignal(viewer.render_finished, timeout=1000):
        viewer._on_render_process_finished(1, "boom", context)

    started = []
    viewer._start_render_process = lambda *args, **kwargs: started.append(args)
    viewer.zoom_level = 2.0  # new key -> cache miss -> fresh render request
    viewer.request_render()
    assert len(started) == 1
    # No half-dead render state is left behind from the failure.
    assert viewer._active_render_process is None
    assert viewer._active_render_context is None
    assert not viewer._render_poll_timer.isActive()


def test_repeated_errors_do_not_wedge_the_viewer(viewer, qtbot, tmp_path):
    for tag in ("r1", "r2", "r3"):
        context = _context(viewer, tmp_path, tag)
        with qtbot.waitSignal(viewer.render_finished, timeout=1000):
            viewer._on_render_process_finished(1, "boom", context)

    started = []
    viewer._start_render_process = lambda *args, **kwargs: started.append(args)
    viewer.request_render()
    assert len(started) == 1
