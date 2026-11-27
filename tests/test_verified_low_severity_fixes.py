"""Regression tests for four verified low-severity defects (2026-11-27).

1. The viewer hard-coded the render DPI (150) in three coordinate
   conversion sites instead of using ``pdf_engine.RENDER_DPI``.
2. The remove-section range warning was a hard-coded English string
   instead of an i18n key, so Korean users saw English.
3. The render worker silently skipped operations that failed to
   deserialize and still reported unqualified success.
4. The render worker caught only OSError/IOError, so any other exception
   killed the worker with a raw traceback instead of a response file.
"""

import json
from types import SimpleNamespace

import fitz
import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem, QMessageBox

from app.i18n import set_locale, tr
from app.remove_section_dialog import RemoveSectionDialog
from app.render_worker import run_render_job
from app.viewer import PDFViewer

# ---------------------------------------------------------------- defect 1
# Each test patches app.viewer.RENDER_DPI to a distinctive value (96) and
# checks it flows through the conversion math; a re-introduced literal 150
# makes the expected values miss by exactly 150/96.


def test_pdf_rect_to_scene_uses_render_dpi(qtbot, monkeypatch):
    """Search-highlight mapping must scale by RENDER_DPI, not a literal DPI."""
    viewer = PDFViewer()
    qtbot.addWidget(viewer)
    viewer.zoom_level = 1.0
    monkeypatch.setattr("app.viewer.RENDER_DPI", 96)

    scaled = viewer._pdf_rect_to_scene(fitz.Rect(0, 0, 72, 72))

    assert scaled.width() == pytest.approx(96.0)
    assert scaled.height() == pytest.approx(96.0)


def test_qrectf_to_fitz_rect_uses_render_dpi(qtbot, monkeypatch, simple_pdf):
    """Selection-to-PDF mapping must scale by RENDER_DPI, not a literal DPI."""
    viewer = PDFViewer()
    qtbot.addWidget(viewer)
    monkeypatch.setattr("app.viewer.RENDER_DPI", 96)
    item = QGraphicsPixmapItem(QPixmap(64, 64))
    viewer.scene.addItem(item)  # item must belong to a scene for mapFromScene
    viewer.current_pixmap_item = item
    viewer.zoom_level = 1.0
    viewer.current_page_index = 0

    doc = fitz.open(simple_pdf)
    try:
        viewer.session = SimpleNamespace(doc=doc)
        pdf_rect = viewer._qrectf_to_fitz_rect(QRectF(0, 0, 96, 48))
    finally:
        doc.close()

    # fitz.Rect exposes width/height as properties, unlike QRectF methods.
    assert pdf_rect.width == pytest.approx(72.0)
    assert pdf_rect.height == pytest.approx(36.0)


def test_fit_to_width_uses_render_dpi(qtbot, monkeypatch, simple_pdf):
    """fit_to_width fallback must derive pixels/point from RENDER_DPI."""
    viewer = PDFViewer()
    qtbot.addWidget(viewer)
    viewer.resize(800, 600)
    monkeypatch.setattr("app.viewer.RENDER_DPI", 96)
    captured = {}
    monkeypatch.setattr(viewer, "set_zoom", lambda level: captured.setdefault("zoom", level))

    doc = fitz.open(simple_pdf)
    try:
        viewer.session = SimpleNamespace(doc=doc)
        viewer.current_page_index = 0
        viewer.zoom_level = 1.0
        viewer.fit_to_width()  # no pixmap yet -> page-size fallback path
    finally:
        doc.close()

    view_width = viewer.viewport().width()
    assert view_width > 0
    assert captured["zoom"] == pytest.approx(view_width / (595.0 * 96 / 72))


# ---------------------------------------------------------------- defect 2


def test_remove_section_invalid_range_warning_is_translated(qtbot, monkeypatch, simple_pdf):
    """The Y1<=Y0 warning must come from tr() so it follows the locale."""
    calls = []
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, text, *args, **kwargs: calls.append(text))

    doc = fitz.open(simple_pdf)
    try:
        dialog = RemoveSectionDialog(doc[0], fitz.Rect(0, 100, 595, 200))
        qtbot.addWidget(dialog)
        dialog.y0_spin.setValue(200)
        dialog.y1_spin.setValue(100)  # y1 <= y0 -> invalid range

        set_locale("en")
        dialog.apply_remove()
        set_locale("ko")
        dialog.apply_remove()
        korean_message = tr("remove.error.invalid_range")
    finally:
        set_locale("en")
        doc.close()

    assert len(calls) == 2
    assert calls[0] == tr("remove.error.invalid_range")
    assert calls[1] == korean_message
    # A real translation, not the tr() key echo or the old English literal.
    assert calls[0] != korean_message
    assert "remove.error.invalid_range" not in calls


# ---------------------------------------------------------------- defects 3+4


def _write_render_job(tmp_path, pdf_path, operations_data):
    """Write a render-worker job file; return (job_path, response_path)."""
    job_path = tmp_path / "job.json"
    response_path = tmp_path / "response.json"
    payload = {
        "file_path": str(pdf_path),
        "page_index": 0,
        "zoom_level": 1.0,
        "operations_data": operations_data,
        "output_path": str(tmp_path / "output.png"),
        "response_path": str(response_path),
    }
    job_path.write_text(json.dumps(payload), encoding="utf-8")
    return job_path, response_path


def _single_page_pdf(tmp_path, name="src.pdf"):
    pdf_path = tmp_path / name
    doc = fitz.open()
    doc.new_page(width=595, height=842)
    doc.save(pdf_path)
    doc.close()
    return pdf_path


def test_render_worker_reports_skipped_operations(tmp_path):
    """One undeserializable op: success stays True but a warning names the count."""
    pdf_path = _single_page_pdf(tmp_path)
    operations_data = [
        {"type": "RedactDelete", "page_index": 0, "rects": [[50, 60, 200, 80]]},
        {"type": "NoSuchOperation", "page_index": 0, "rects": []},
    ]
    job_path, response_path = _write_render_job(tmp_path, pdf_path, operations_data)

    exit_code = run_render_job(job_path)

    response = json.loads(response_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert response["success"] is True
    notices = [entry for entry in response["warnings"] if isinstance(entry, str)]
    assert len(notices) == 1
    assert "1" in notices[0]
    assert "skipped" in notices[0].lower()


def test_render_worker_catches_unexpected_exception(tmp_path, monkeypatch):
    """A non-OSError render failure must yield success False with a one-line error."""

    def _explode(*args, **kwargs):
        raise ValueError("synthetic render failure")

    monkeypatch.setattr("app.render_worker.render_page_preview", _explode)
    pdf_path = _single_page_pdf(tmp_path)
    job_path, response_path = _write_render_job(tmp_path, pdf_path, [])

    exit_code = run_render_job(job_path)

    response = json.loads(response_path.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert response["success"] is False
    assert response["error"] == "ValueError: synthetic render failure"
    assert "\n" not in response["error"]
