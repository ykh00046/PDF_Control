"""EditorController._run_session_action guard behavior (r6-quality PDCA).

The controller routes session mutations through a single guard that
distinguishes the no-session case, user-validation rejections (ValueError),
and internal failures -- all previously 14 copies of the same try/except.
"""

import fitz
import pytest

from app.controller import EditorController


@pytest.fixture
def two_page_pdf(tmp_path):
    path = tmp_path / "two_pages.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.new_page()
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def controller(two_page_pdf):
    controller = EditorController()
    assert controller.load_document(str(two_page_pdf)) is True
    yield controller
    controller.close_document()


def test_no_session_returns_default():
    controller = EditorController()
    errors = []
    controller.error_occurred.connect(errors.append)

    assert controller.rotate_page(0, 90) is False
    assert controller.split_document("anywhere", [[0]]) == []
    assert errors == []  # no session is a silent no-op, not an error


def test_value_error_emits_and_keeps_session(controller):
    errors = []
    controller.error_occurred.connect(errors.append)

    # Deleting every page is rejected by the session with ValueError.
    assert controller.delete_pages([0, 1]) is False
    assert errors == ["Cannot delete all pages"]
    assert controller.session is not None
    assert controller.session.doc.page_count == 2  # nothing was deleted


def test_internal_error_emits(controller, monkeypatch):
    errors = []
    controller.error_occurred.connect(errors.append)

    def boom(page_index, angle):
        raise RuntimeError("engine exploded")

    monkeypatch.setattr(controller.session, "rotate_page", boom)
    assert controller.rotate_page(0, 90) is False
    assert errors == ["engine exploded"]


def test_success_emits_operation_applied(controller):
    applied = []
    controller.operation_applied.connect(lambda: applied.append(True))

    assert controller.rotate_page(0, 90) is True
    assert len(applied) == 1


def test_split_returns_paths_without_applied(controller, tmp_path):
    applied = []
    controller.operation_applied.connect(lambda: applied.append(True))

    written = controller.split_document(str(tmp_path), [[0], [1]])
    assert len(written) == 2
    assert applied == []  # read-only action must not trigger a re-render
