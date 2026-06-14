"""PyInstaller bundling validation.

Validates the spec file and path_helper's frozen-mode behavior without
actually running a full build (which takes several minutes).

Covers:
- path_helper correctly resolves resources under a simulated _MEIPASS
- pdf_control.spec declares i18n data files
- All app.* modules referenced by entry points are listed as hiddenimports
- Excluded packages don't accidentally include things we need at runtime
"""

import re
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
SPEC_PATH = PROJECT_ROOT / "pdf_control.spec"


@pytest.fixture
def spec_source():
    assert SPEC_PATH.exists(), f"Spec file missing: {SPEC_PATH}"
    return SPEC_PATH.read_text(encoding="utf-8")


def test_path_helper_resolves_resources_in_frozen_mode(tmp_path, monkeypatch):
    """Simulate PyInstaller frozen mode and ensure i18n paths resolve."""
    fake_meipass = tmp_path / "_MEIPASS"
    (fake_meipass / "app" / "i18n").mkdir(parents=True)
    (fake_meipass / "app" / "i18n" / "en.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(fake_meipass), raising=False)

    import importlib

    import app.path_helper as ph
    importlib.reload(ph)

    try:
        assert ph.is_frozen() is True
        assert ph.get_base_path() == fake_meipass
        en_path = ph.get_i18n_path("en.json")
        assert en_path.exists(), f"i18n resource not resolvable under frozen: {en_path}"
    finally:
        monkeypatch.delattr(sys, "_MEIPASS", raising=False)
        monkeypatch.setattr(sys, "frozen", False, raising=False)
        importlib.reload(ph)


def test_dev_mode_resolves_real_i18n_files():
    import app.path_helper as ph
    assert not ph.is_frozen()
    assert ph.get_i18n_path("en.json").exists()
    assert ph.get_i18n_path("ko.json").exists()


def test_app_data_dir_isolates_under_env_override(tmp_path, monkeypatch):
    target = tmp_path / "custom_appdata"
    monkeypatch.setenv("PDF_CONTROL_APP_DATA_DIR", str(target))
    import importlib

    import app.path_helper as ph
    importlib.reload(ph)
    assert ph.get_app_data_dir() == target
    assert target.exists()


def test_spec_bundles_i18n_json(spec_source):
    assert 'app/i18n/*.json' in spec_source, "i18n JSON files not bundled in datas"


def test_spec_declares_critical_hidden_imports(spec_source):
    required = [
        "fitz",
        "PIL.Image",
        "PySide6.QtCore",
        "PySide6.QtWidgets",
        "app.batch_replace_dialog",
        "app.crop_dialog",
        "app.fonts",
        "app.pdf_engine",
        "app.remove_section_dialog",
        "app.render_worker",
    ]
    missing = [m for m in required if m not in spec_source]
    assert not missing, f"Missing hiddenimports in spec: {missing}"


def test_spec_does_not_exclude_runtime_dependencies(spec_source):
    """Guard against excludes regressing runtime imports."""
    match = re.search(r"excludes=\[(.*?)\]", spec_source, re.DOTALL)
    assert match, "Could not locate excludes block in spec"
    excludes_block = match.group(1)
    must_not_exclude = ["fitz", "PIL", "PySide6", "app\\."]
    for token in must_not_exclude:
        assert not re.search(r"['\"]" + token, excludes_block), \
            f"Runtime dependency {token!r} incorrectly listed in excludes"


def test_all_app_modules_or_explicitly_excluded():
    """Every module under app/ should be importable (catches broken imports)."""
    app_dir = PROJECT_ROOT / "app"
    failures = []
    for py_file in app_dir.glob("*.py"):
        if py_file.stem == "__init__":
            continue
        module_name = f"app.{py_file.stem}"
        try:
            __import__(module_name)
        except Exception as e:
            failures.append(f"{module_name}: {type(e).__name__}: {e}")
    assert not failures, "Broken app modules (would fail in frozen build):\n" + "\n".join(failures)
