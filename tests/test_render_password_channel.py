"""Render-worker password channel hardening (r4-bugfix PDCA, B3).

The viewer must never write the source password into the on-disk job file
(it could linger in the temp dir after a crash). Instead it announces
``password_stdin`` in the job payload and sends the password over the
worker's stdin pipe.
"""
import io
import json
import subprocess
import sys
from pathlib import Path

from app.document_session import DocumentSession
from app.render_worker import run_render_job
from app.viewer import PDFViewer

# ── DocumentSession.render_password accessor ────────────────────────

def test_render_password_returns_password_for_encrypted(encrypted_pdf):
    session = DocumentSession(str(encrypted_pdf), password="open123")
    try:
        assert session.render_password() == "open123"
    finally:
        session.close()


def test_render_password_is_none_for_plain(simple_pdf):
    session = DocumentSession(str(simple_pdf))
    try:
        assert session.render_password() is None
    finally:
        session.close()


# ── render_worker: stdin protocol ────────────────────────────────────

def _write_job(tmp_path, source_pdf, **extra):
    job = {
        "file_path": str(source_pdf),
        "page_index": 0,
        "zoom_level": 1.0,
        "operations_data": [],
        "output_path": str(tmp_path / "out.png"),
        "response_path": str(tmp_path / "response.json"),
        **extra,
    }
    job_path = tmp_path / "job.json"
    job_path.write_text(json.dumps(job), encoding="utf-8")
    return job_path


def test_worker_reads_password_from_stdin(encrypted_pdf, tmp_path, monkeypatch):
    job_path = _write_job(tmp_path, encrypted_pdf, password_stdin=True)
    monkeypatch.setattr(sys, "stdin", io.StringIO("open123\n"))

    assert run_render_job(job_path) == 0
    assert (tmp_path / "out.png").exists()
    response = json.loads((tmp_path / "response.json").read_text(encoding="utf-8"))
    assert response["success"] is True


class _ExplodingStdin:
    """Fails the test if the worker touches stdin without the flag."""

    def readline(self):
        raise AssertionError("worker must not read stdin without password_stdin")


def test_worker_without_flag_never_touches_stdin(simple_pdf, tmp_path, monkeypatch):
    job_path = _write_job(tmp_path, simple_pdf)
    monkeypatch.setattr(sys, "stdin", _ExplodingStdin())

    assert run_render_job(job_path) == 0
    assert (tmp_path / "out.png").exists()


# ── viewer: job file must not contain the password ───────────────────

class _FakeStdin:
    def __init__(self):
        self.data = ""
        self.closed = False

    def write(self, text):
        self.data += text

    def close(self):
        self.closed = True


class _FakeProcess:
    def __init__(self):
        self.stdin = _FakeStdin()
        self.stderr = None
        self._returncode = None

    def poll(self):
        return self._returncode

    def terminate(self):
        self._returncode = 1

    def kill(self):
        self._returncode = 1

    def wait(self, timeout=None):
        self._returncode = 1
        return self._returncode


def test_viewer_job_file_has_no_password(qtbot, encrypted_pdf, monkeypatch):
    captured = {}

    def fake_popen(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        captured["process"] = _FakeProcess()
        return captured["process"]

    monkeypatch.setattr("app.viewer.subprocess.Popen", fake_popen)

    viewer = PDFViewer()
    qtbot.addWidget(viewer)
    session = DocumentSession(str(encrypted_pdf), password="open123")
    try:
        viewer.set_document_session(session)

        context = viewer._active_render_context
        assert context is not None, "render process was not started"
        payload = json.loads(Path(context["job_path"]).read_text(encoding="utf-8"))

        # The password must never land on disk -- only the announcement flag.
        assert "password" not in payload
        assert payload["password_stdin"] is True

        # And it must travel over the stdin pipe instead.
        assert captured["kwargs"]["stdin"] == subprocess.PIPE
        assert captured["process"].stdin.data == "open123\n"
        assert captured["process"].stdin.closed is True
    finally:
        viewer._cancel_active_render()
        session.close()


def test_viewer_plain_document_uses_no_stdin_pipe(qtbot, simple_pdf, monkeypatch):
    captured = {}

    def fake_popen(args, **kwargs):
        captured["kwargs"] = kwargs
        captured["process"] = _FakeProcess()
        return captured["process"]

    monkeypatch.setattr("app.viewer.subprocess.Popen", fake_popen)

    viewer = PDFViewer()
    qtbot.addWidget(viewer)
    session = DocumentSession(str(simple_pdf))
    try:
        viewer.set_document_session(session)

        context = viewer._active_render_context
        assert context is not None, "render process was not started"
        payload = json.loads(Path(context["job_path"]).read_text(encoding="utf-8"))

        assert "password" not in payload
        assert "password_stdin" not in payload
        assert captured["kwargs"]["stdin"] == subprocess.DEVNULL
        assert captured["process"].stdin.data == ""
    finally:
        viewer._cancel_active_render()
        session.close()
