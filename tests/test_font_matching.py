"""Unit tests for PDF-font-name -> system-font matching (text-fidelity PDCA)."""
import pytest

import app.fonts as fonts
from app.config import FONT_FLAG_BOLD, FONT_FLAG_ITALIC
from app.fonts import _font_name_candidates, resolve_pdf_fontname


# ── candidate generation (pure) ──────────────────────────────────────

def test_subset_prefix_is_stripped():
    candidates = _font_name_candidates("ABCDEF+Calibri-Bold")
    assert "calibri bold" in candidates
    assert "calibri" in candidates
    assert all(not c.startswith("abcdef+") for c in candidates)


def test_camel_case_is_spaced():
    assert "malgun gothic" in _font_name_candidates("MalgunGothic")


def test_hyphen_and_comma_become_spaces():
    assert "times new roman" in _font_name_candidates("Times-New-Roman")
    assert "arial bold" in _font_name_candidates("Arial,Bold")


def test_flags_add_style_variants():
    candidates = _font_name_candidates("Arial", FONT_FLAG_BOLD)
    assert "arial bold" in candidates
    both = _font_name_candidates("Arial", FONT_FLAG_BOLD | FONT_FLAG_ITALIC)
    assert "arial bold italic" in both


def test_family_fallback_is_last():
    candidates = _font_name_candidates("Calibri-BoldItalic")
    assert candidates[-1] == "calibri"


def test_specific_before_general():
    candidates = _font_name_candidates("ABCDEF+Calibri-Bold")
    assert candidates.index("calibri bold") < candidates.index("calibri")


def test_empty_name_yields_no_candidates():
    assert _font_name_candidates("") == []
    assert _font_name_candidates("   ") == []


# ── resolve with injected cache ──────────────────────────────────────

@pytest.fixture
def fake_font_cache(tmp_path, monkeypatch):
    """Point the registry cache at temp files so resolution is hermetic."""
    calibri = tmp_path / "calibri.ttf"
    calibri_bold = tmp_path / "calibrib.ttf"
    calibri.write_bytes(b"fake")
    calibri_bold.write_bytes(b"fake")
    monkeypatch.setattr(
        fonts,
        "_font_cache",
        {"calibri": str(calibri), "calibri bold": str(calibri_bold)},
    )
    return {"calibri": str(calibri), "calibri bold": str(calibri_bold)}


def test_resolve_prefers_style_match(fake_font_cache):
    # must_cover="" skips the glyph probe, so the fake files are fine.
    assert resolve_pdf_fontname("ABCDEF+Calibri-Bold") == fake_font_cache["calibri bold"]


def test_resolve_falls_back_to_family(fake_font_cache):
    assert resolve_pdf_fontname("Calibri-Light") == fake_font_cache["calibri"]


def test_resolve_unknown_returns_none(fake_font_cache):
    assert resolve_pdf_fontname("NoSuchFontFamily") is None


def test_resolve_missing_file_is_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(
        fonts, "_font_cache", {"ghost": str(tmp_path / "missing.ttf")}
    )
    assert resolve_pdf_fontname("Ghost") is None


def test_resolve_rejects_font_without_coverage(fake_font_cache):
    # The fake files are not parseable fonts, so the coverage probe fails
    # whenever a non-empty must_cover forces it to construct fitz.Font.
    assert resolve_pdf_fontname("Calibri", must_cover="hello") is None
