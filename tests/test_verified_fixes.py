"""Regression tests for three verified defects (2026-11-27).

1. Watermark lost after section removal: RemoveSectionAsImage replaces the
   page object, so the watermark pass drew on a stale (deleted) handle and
   silently vanished from both the saved file and the preview render.
2. Regex batch replace sent every match of a repeated string to the first
   rectangle: the Nth occurrence of the same text must take the Nth rect
   found by ``page.search_for``.
3. A corrupt config.json crashed startup (json.JSONDecodeError escaped the
   OSError-only except), and save_config was not atomic.
"""

import json
import os

import fitz
import numpy as np
import pytest

import app.config as config_module
from app.model import DocumentSession, RemoveSectionAsImage, WatermarkText
from app.pdf_engine import render_page_preview, save_document_copy

# ---------------------------------------------------------------- defect 1


def _section_removal_pdf(path):
    """A one-page PDF with a header/middle/footer layout (removable middle)."""
    doc = fitz.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text((40, 60), "HEADER", fontsize=14)
    page.insert_text((40, 300), "MIDDLE TO REMOVE", fontsize=14)
    page.insert_text((40, 560), "FOOTER", fontsize=14)
    doc.save(path)
    doc.close()
    return path


def test_watermark_survives_section_removal_save(tmp_path):
    """Save path: Pass 5 must draw on the page rebuilt by Pass 4."""
    src = _section_removal_pdf(tmp_path / "s.pdf")
    dst = tmp_path / "s_out.pdf"

    operations = [
        RemoveSectionAsImage(0, fitz.Rect(0, 150, 400, 450)),
        WatermarkText(0, "WM-SURVIVES", fontsize=30, angle=0),
    ]
    save_document_copy(str(src), str(dst), operations)  # must not raise

    out = fitz.open(dst)
    try:
        assert out.page_count == 1
        # The rebuilt page is a raster of the top/bottom clips; the only live
        # text on it is the watermark, so get_text is a precise probe.
        assert "WM-SURVIVES" in out[0].get_text()
    finally:
        out.close()


def test_watermark_survives_section_removal_preview(tmp_path):
    """Preview path: the rendered pixmap must reflect the watermark too."""
    src = _section_removal_pdf(tmp_path / "p.pdf")
    section_only = [RemoveSectionAsImage(0, fitz.Rect(0, 150, 400, 450))]
    with_watermark = section_only + [WatermarkText(0, "WM-PREVIEW", fontsize=30, angle=0)]

    plain_png = tmp_path / "plain.png"
    marked_png = tmp_path / "marked.png"
    render_page_preview(str(src), 0, with_watermark, 1.0, marked_png)  # must not raise
    render_page_preview(str(src), 0, section_only, 1.0, plain_png)

    def _pixels(png_path):
        pix = fitz.Pixmap(str(png_path))
        assert pix.width > 0 and pix.height > 0
        return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)

    # With the stale-handle bug the watermark vanished and both renders were
    # identical; with the fix the watermark visibly changes the pixels.
    diff = np.abs(_pixels(marked_png).astype(int) - _pixels(plain_png).astype(int))
    changed = int((diff > 10).sum())
    assert changed > 100, f"preview render does not contain the watermark ({changed} changed pixels)"


# ---------------------------------------------------------------- defect 2


def test_regex_batch_repeated_string_gets_distinct_rects(qtbot, tmp_path):
    """The same date twice on a page: regex mode yields two matches, two rects."""
    from app.batch_replace_dialog import BatchReplaceDialog

    path = tmp_path / "dates.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 100), "Invoice date: 2026-01-15", fontsize=12)
    page.insert_text((50, 500), "Due date: 2026-01-15", fontsize=12)
    doc.save(path)
    doc.close()

    session = DocumentSession(os.path.abspath(path))
    try:
        dialog = BatchReplaceDialog(session)
        qtbot.addWidget(dialog)
        dialog.find_what_input.setText(r"\d{4}-\d{2}-\d{2}")
        dialog.use_regex_checkbox.setChecked(True)
        dialog._find_all_matches()

        assert len(dialog.matches) == 2
        rects = [match["rect"] for match in dialog.matches]
        # Both occurrences of the repeated string used to collapse onto
        # found_rects[0]; they must now land on different rectangles that
        # each cover their own occurrence on its own line.
        assert rects[0] != rects[1]
        assert abs(rects[0].y0 - rects[1].y0) > 100, "both matches landed on the same line"
        live_page = session.doc[0]
        for rect in rects:
            assert "2026-01-15" in live_page.get_textbox(rect)
    finally:
        session.close()


# ---------------------------------------------------------------- defect 3


@pytest.fixture
def isolated_config_file(tmp_path, monkeypatch):
    """Point app.config at a config.json inside tmp_path (never real app data)."""
    config_file = tmp_path / "config.json"
    monkeypatch.setattr(config_module, "_config_path", lambda: config_file)
    return config_file


def test_corrupt_config_json_loads_defaults(isolated_config_file):
    """Invalid JSON must fall back to defaults instead of raising."""
    isolated_config_file.write_text('{"window": {"width": 999, tru', encoding="utf-8")

    loaded = config_module.load_config()  # must not raise

    assert loaded == config_module.DEFAULT_CONFIG


def test_config_save_is_atomic_and_leaves_no_temp_file(isolated_config_file):
    """After a save the file is valid JSON and no temp file remains."""
    payload = {"window": {"width": 1400, "height": 900, "x": 1, "y": 2}, "zoom_level": 2.5}

    assert config_module.save_config(payload) is True

    assert isolated_config_file.exists()
    assert json.loads(isolated_config_file.read_text(encoding="utf-8")) == payload
    # No temporary file may survive the atomic replace (the logger fixture's
    # unrelated "appdata" dir may share tmp_path, so scope the check).
    leftovers = sorted(
        entry.name for entry in isolated_config_file.parent.iterdir() if entry.name.startswith("config.json")
    )
    assert leftovers == ["config.json"], f"temporary file left behind: {leftovers}"
    # And the saved file reloads through the normal path.
    assert config_module.load_config()["window"]["width"] == 1400
