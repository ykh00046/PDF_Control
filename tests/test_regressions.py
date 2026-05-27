import os
import json
import ast
from datetime import datetime
import logging
from pathlib import Path
from unittest.mock import patch

import fitz
import pytest
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem

import app.logger as app_logger
import app.i18n as i18n_module
from app.controller import EditorController
from app.i18n import load_translations
from app.model import DocumentSession, RedactReplace, RemoveSectionAsImage
from app.operations_service import ApplyMode, OperationApplicator
from app.pdf_engine import render_page_preview, save_document_copy
from app.ui import MainWindow
from app.render_worker import run_render_job
from app.viewer import PDFViewer


def test_ui_remove_section_uses_supported_operation_keywords():
    source = (Path(__file__).parent.parent / "app" / "ui.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    bad_keywords = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "RemoveSectionAsImage":
            continue
        bad_keywords.extend(
            keyword.arg
            for keyword in node.keywords
            if keyword.arg not in {"dpi", "format"}
        )

    assert bad_keywords == []


def test_redact_replace_roundtrip_preserves_font_metadata():
    op = RedactReplace(
        0,
        [fitz.Rect(10, 20, 30, 40)],
        "done",
        fontname="Times-BoldItalic",
        fontsize=11,
        fontfile="C:/Windows/Fonts/times.ttf",
        color=(0.1, 0.2, 0.3),
        font_flags=18,
    )

    from app.model import Operation

    restored = Operation.from_dict(op.to_dict())

    assert restored.fontname == "Times-BoldItalic"
    assert restored.fontsize == 11
    assert restored.fontfile == "C:/Windows/Fonts/times.ttf"
    assert restored.color == (0.1, 0.2, 0.3)
    assert restored.font_flags == 18


def test_operation_applicator_maps_font_flags_to_base14_aliases():
    applicator = OperationApplicator()

    assert applicator._base14_font_alias("Helvetica", 16) == "hebo"
    assert applicator._base14_font_alias("Times", 18) == "tibi"
    assert applicator._base14_font_alias("Courier", 2) == "coit"


def test_batch_replace_uses_emitted_fontsize_payload():
    # process_batch_replacements moved from app/ui.py to
    # app/handlers/dialog_handlers.py as part of the ui_handlers split
    # (DialogHandlerMixin).
    source = (
        Path(__file__).parent.parent
        / "app"
        / "handlers"
        / "dialog_handlers.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    target_func = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "process_batch_replacements"
    )

    redact_replace_calls = [
        node
        for node in ast.walk(target_func)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "RedactReplace"
    ]

    assert any(
        any(keyword.arg == "fontsize" for keyword in node.keywords)
        for node in redact_replace_calls
    )


def test_save_document_rebinds_session_to_saved_file(tmp_path):
    input_path = tmp_path / "input.pdf"
    output_path = tmp_path / "output.pdf"

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 70), "replace me", fontsize=12)
    doc.save(str(input_path))
    doc.close()

    session = None
    saved_doc = None
    try:
        session = DocumentSession(str(input_path))
        rect = session.doc[0].search_for("replace me")[0]
        session.add_operation(RedactReplace(0, [rect], "done", fontsize=8))

        session.save_document(str(output_path))

        assert os.path.abspath(session.file_path) == os.path.abspath(output_path)
        assert "done" in session.doc[0].get_text()
        assert "replace me" not in session.doc[0].get_text()
        assert session.history == []
        assert session.redo_stack == []
        assert session.modified is False

        saved_doc = fitz.open(str(output_path))
        assert "done" in saved_doc[0].get_text()
    finally:
        if saved_doc is not None:
            saved_doc.close()
        if session is not None:
            session.close()


def test_remove_section_preview_matches_saved_geometry():
    source_doc = fitz.open()
    preview_doc = fitz.open()
    save_doc = fitz.open()
    try:
        page = source_doc.new_page(width=595, height=842)
        page.insert_text((50, 100), "TOP", fontsize=20)
        page.insert_text((50, 400), "MID", fontsize=20)
        page.insert_text((50, 700), "BOTTOM", fontsize=20)

        preview_doc.insert_pdf(source_doc, from_page=0, to_page=0)
        save_doc.insert_pdf(source_doc, from_page=0, to_page=0)

        remove_rect = fitz.Rect(0, 300, 595, 500)
        preview_op = RemoveSectionAsImage(0, remove_rect, dpi=150, format="jpeg")
        save_op = RemoveSectionAsImage(0, remove_rect, dpi=150, format="jpeg")

        applicator = OperationApplicator()
        applicator.apply_operations(preview_doc[0], [preview_op], mode=ApplyMode.PREVIEW)
        applicator.apply_operations(save_doc[0], [save_op], mode=ApplyMode.SAVE)

        assert preview_doc[0].rect.height == pytest.approx(save_doc[0].rect.height, abs=1.0)
        assert preview_doc[0].get_text() == save_doc[0].get_text()
    finally:
        preview_doc.close()
        save_doc.close()
        source_doc.close()


def test_viewer_ignores_stale_render_results(qtbot, tmp_path):
    pdf_path = tmp_path / "viewer.pdf"

    doc = fitz.open()
    doc.new_page()
    doc.save(str(pdf_path))
    doc.close()

    session = DocumentSession(str(pdf_path))
    viewer = PDFViewer()
    qtbot.addWidget(viewer)

    try:
        viewer.session = session
        viewer.current_page_index = 0
        viewer.zoom_level = 2.0

        stale_key = viewer._compute_cache_key(0, 1.0, [])
        image = QImage(8, 8, QImage.Format_RGB32)
        image.fill(0)

        viewer._on_render_finished((0, image, 10.0, 1.0, stale_key))

        assert len(viewer.scene.items()) == 0
    finally:
        session.close()


def test_load_translations_is_cwd_independent(tmp_path):
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        translations = load_translations("en")
        assert translations["app.title"]
    finally:
        os.chdir(original_cwd)


def test_render_worker_job_roundtrip(tmp_path):
    input_path = tmp_path / "worker_input.pdf"
    image_path = tmp_path / "worker_output.png"
    response_path = tmp_path / "worker_response.json"
    job_path = tmp_path / "worker_job.json"

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 70), "Worker render", fontsize=12)
    doc.save(str(input_path))
    doc.close()

    payload = {
        "file_path": str(input_path),
        "page_index": 0,
        "zoom_level": 1.0,
        "operations_data": [],
        "output_path": str(image_path),
        "response_path": str(response_path),
    }
    with open(job_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)

    assert run_render_job(job_path) == 0
    assert image_path.exists()

    with open(response_path, "r", encoding="utf-8") as handle:
        response = json.load(handle)

    assert response["success"] is True
    assert response["duration_ms"] >= 0


def test_pdf_engine_save_document_copy(tmp_path):
    input_path = tmp_path / "engine_input.pdf"
    output_path = tmp_path / "engine_output.pdf"

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 70), "engine save", fontsize=12)
    doc.save(str(input_path))
    doc.close()

    source = fitz.open(str(input_path))
    rect = source[0].search_for("engine save")[0]
    source.close()

    save_document_copy(
        str(input_path),
        str(output_path),
        [RedactReplace(0, [rect], "done", fontsize=8)],
    )

    saved = fitz.open(str(output_path))
    try:
        assert "done" in saved[0].get_text()
        assert "engine save" not in saved[0].get_text()
    finally:
        saved.close()


def test_pdf_engine_render_page_preview(tmp_path):
    input_path = tmp_path / "engine_preview.pdf"
    output_path = tmp_path / "engine_preview.png"

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 70), "engine preview", fontsize=12)
    doc.save(str(input_path))
    doc.close()

    render_page_preview(str(input_path), 0, [], 1.0, output_path)

    image = QImage(str(output_path))
    assert not image.isNull()


def test_logger_falls_back_to_pid_specific_file(tmp_path, monkeypatch):
    def raise_locked(*args, **kwargs):
        raise OSError("locked")

    monkeypatch.setattr(app_logger.logging.handlers, "TimedRotatingFileHandler", raise_locked)

    logger = app_logger.setup_logger(log_dir=tmp_path)
    try:
        logger.info("fallback logger test")
        log_path = app_logger.get_log_file_path()

        assert log_path.exists()
        assert log_path.parent == tmp_path
        assert log_path.name == f"app_{datetime.now().strftime('%Y%m%d')}_{os.getpid()}.log"
    finally:
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)
        app_logger._logger = None
        app_logger._log_file_path = None


def test_failed_load_preserves_existing_session(tmp_path):
    valid_path = tmp_path / "valid.pdf"
    invalid_path = tmp_path / "invalid.pdf"

    doc = fitz.open()
    doc.new_page()
    doc.save(str(valid_path))
    doc.close()
    invalid_path.write_text("not a pdf", encoding="utf-8")

    controller = EditorController()
    errors = []
    controller.error_occurred.connect(errors.append)

    assert controller.load_document(str(valid_path)) is True
    original_session = controller.session
    assert original_session is not None

    assert controller.load_document(str(invalid_path)) is False
    assert controller.session is original_session
    assert controller.session.file_path == str(valid_path)
    assert errors

    controller.close_document()


def test_get_system_locale_normalizes_windows_locale_names(monkeypatch):
    monkeypatch.setattr(i18n_module, "_detect_windows_locale", lambda: None)
    monkeypatch.setattr(i18n_module.locale, "getlocale", lambda: ("Korean_Korea", "cp949"))
    for env_key in ("LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(env_key, raising=False)

    assert i18n_module.get_system_locale() == "ko"


def test_duplicate_remove_section_same_page_is_rejected(tmp_path):
    input_path = tmp_path / "duplicate_remove.pdf"

    doc = fitz.open()
    doc.new_page(width=595, height=842)
    doc.save(str(input_path))
    doc.close()

    session = DocumentSession(str(input_path))
    try:
        session.add_operation(RemoveSectionAsImage(0, fitz.Rect(0, 100, 595, 200)))
        with pytest.raises(ValueError, match="Only one section removal operation"):
            session.add_operation(RemoveSectionAsImage(0, fitz.Rect(0, 250, 595, 350)))
    finally:
        session.close()


def test_page_change_updates_actions_and_clears_selection(qtbot, tmp_path):
    pdf_path = tmp_path / "nav_states.pdf"

    doc = fitz.open()
    doc.new_page()
    doc.new_page()
    doc.save(str(pdf_path))
    doc.close()

    window = MainWindow()
    qtbot.addWidget(window)

    try:
        assert window.controller.load_document(str(pdf_path)) is True
        window.last_selected_rect = fitz.Rect(10, 10, 50, 50)
        window._update_edit_action_states()

        assert window.next_page_action.isEnabled() is True
        assert window.prev_page_action.isEnabled() is False
        assert window.delete_action.isEnabled() is True

        window.viewer.next_page()
        qtbot.waitUntil(lambda: window.viewer.current_page_index == 1, timeout=1000)

        assert window.last_selected_rect is None
        assert window.next_page_action.isEnabled() is False
        assert window.prev_page_action.isEnabled() is True
        assert window.delete_action.isEnabled() is False
        assert window.replace_action.isEnabled() is False
    finally:
        window.close()


def test_fit_to_width_uses_rendered_preview_width(qtbot, tmp_path):
    pdf_path = tmp_path / "fit_to_width.pdf"

    doc = fitz.open()
    doc.new_page(width=600, height=800)
    doc.save(str(pdf_path))
    doc.close()

    session = DocumentSession(str(pdf_path))
    viewer = PDFViewer()
    qtbot.addWidget(viewer)

    try:
        viewer.session = session
        viewer.current_page_index = 0
        viewer.zoom_level = 2.0
        viewer.resize(1000, 800)
        viewer.show()
        qtbot.wait(10)

        image = QImage(500, 100, QImage.Format_RGB32)
        image.fill(0)
        viewer.current_pixmap_item = QGraphicsPixmapItem(QPixmap.fromImage(image))

        captured = []

        def capture_zoom(level):
            captured.append(level)

        viewer.set_zoom = capture_zoom
        expected = viewer.zoom_level * viewer.viewport().width() / 500

        viewer.fit_to_width()

        assert captured
        assert captured[0] == pytest.approx(expected)
    finally:
        session.close()


def test_save_document_does_not_log_sensitive_text(tmp_path, caplog):
    input_path = tmp_path / "save_sensitive.pdf"
    output_path = tmp_path / "save_sensitive_out.pdf"

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 70), "ORIGINALSECRET", fontsize=12)
    doc.save(str(input_path))
    doc.close()

    session = DocumentSession(str(input_path))

    try:
        rect = session.doc[0].search_for("ORIGINALSECRET")[0]
        session.add_operation(RedactReplace(0, [rect], "MASKEDVALUE", fontsize=8))

        caplog.set_level(logging.DEBUG, logger="PDFRedactionTool")
        session.save_document(str(output_path))

        messages = "\n".join(record.message for record in caplog.records)
        assert "ORIGINALSECRET" not in messages
        assert "MASKEDVALUE" not in messages
    finally:
        session.close()


def test_replace_selection_does_not_log_sensitive_text(qtbot, tmp_path, caplog):
    pdf_path = tmp_path / "sensitive.pdf"

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 70), "TOPSECRET", fontsize=12)
    doc.save(str(pdf_path))
    doc.close()

    window = MainWindow()
    qtbot.addWidget(window)

    try:
        assert window.controller.load_document(str(pdf_path)) is True
        rect = window.controller.session.doc[0].search_for("TOPSECRET")[0]
        window.last_selected_rect = rect
        window.viewer.current_page_index = 0

        caplog.set_level(logging.DEBUG, logger="PDFRedactionTool")
        with patch("app.ui.QInputDialog.getText", return_value=("MASKED", True)):
            window.replace_selection()

        messages = "\n".join(record.message for record in caplog.records)
        assert "TOPSECRET" not in messages
        assert "MASKED" not in messages
    finally:
        window.controller.close_document()
        window.close()
