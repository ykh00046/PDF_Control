"""Configuration load/save and legacy config fallback (test-gap map §2-4).

``app.config.load_config`` / ``save_config`` behaviour pinned here:

* a missing config yields a deep copy of the defaults (no shared state);
* a user config is deep-merged over the defaults (partial sections keep
  default siblings) and unknown keys survive the merge;
* without the ``PDF_CONTROL_APP_DATA_DIR`` isolation override, a legacy
  project-root config.json is used when no app-data config exists yet --
  as a read-through fallback: the legacy file is never moved or deleted;
* once ``save_config`` has written the app-data config, that file wins;
* a save that cannot write returns False instead of raising.
"""

import json
import os

import pytest

import app.config as config


@pytest.fixture
def patch_config_paths(monkeypatch, tmp_path):
    """Point both config resolutions at per-test files."""

    def install(config_name="config.json", legacy_name="legacy.json", with_legacy=False):
        config_path = tmp_path / config_name
        legacy_path = tmp_path / legacy_name
        monkeypatch.setattr(config, "_config_path", lambda: config_path)
        monkeypatch.setattr(config, "_legacy_config_path", lambda: legacy_path)
        if with_legacy:
            legacy_path.write_text("{}", encoding="utf-8")
        return config_path, legacy_path

    return install


def test_missing_config_returns_defaults(patch_config_paths):
    config_path, _legacy = patch_config_paths()
    assert not config_path.exists()

    loaded = config.load_config()
    assert loaded["window"]["width"] == config.DEFAULT_CONFIG["window"]["width"]
    assert loaded["last_directory"] == ""
    assert loaded["ui"]["history_panel_visible"] is True


def test_loaded_defaults_are_not_shared_with_the_template(patch_config_paths):
    """Mutating one load must not leak into the next (deep copy)."""
    patch_config_paths()
    loaded = config.load_config()
    loaded["window"]["width"] = 1
    loaded["memory"]["merge_abort_mb"] = 999

    again = config.load_config()
    assert again["window"]["width"] == config.DEFAULT_CONFIG["window"]["width"]
    assert again["memory"]["merge_abort_mb"] == config.DEFAULT_CONFIG["memory"]["merge_abort_mb"]


def test_partial_config_deep_merges_with_defaults(patch_config_paths):
    config_path, _legacy = patch_config_paths()
    config_path.write_text(json.dumps({"window": {"width": 777}}), encoding="utf-8")

    loaded = config.load_config()
    assert loaded["window"]["width"] == 777  # user value wins
    assert loaded["window"]["height"] == config.DEFAULT_CONFIG["window"]["height"]  # sibling default kept
    assert loaded["zoom_level"] == config.DEFAULT_CONFIG["zoom_level"]  # top-level default kept


def test_unknown_keys_survive_load_and_roundtrip(patch_config_paths):
    config_path, _legacy = patch_config_paths()
    original = {"window": {"width": 640}, "custom_section": {"flag": True}}
    config_path.write_text(json.dumps(original), encoding="utf-8")

    loaded = config.load_config()
    assert loaded["custom_section"] == {"flag": True}

    assert config.save_config(loaded) is True
    reloaded = config.load_config()
    assert reloaded["custom_section"] == {"flag": True}
    assert reloaded["window"]["width"] == 640


def test_legacy_config_used_when_app_data_config_missing(patch_config_paths, monkeypatch):
    config_path, legacy_path = patch_config_paths(with_legacy=True)
    monkeypatch.delenv("PDF_CONTROL_APP_DATA_DIR", raising=False)
    legacy_path.write_text(json.dumps({"window": {"width": 555}, "legacy_only": [1, 2]}), encoding="utf-8")

    loaded = config.load_config()
    assert loaded["window"]["width"] == 555
    assert loaded["legacy_only"] == [1, 2]
    assert loaded["window"]["height"] == config.DEFAULT_CONFIG["window"]["height"]


def test_legacy_file_is_read_through_never_consumed(patch_config_paths, monkeypatch):
    """The legacy fallback must not move/delete the old file: after a save
    the app-data config wins while the legacy file stays untouched on disk."""
    config_path, legacy_path = patch_config_paths(with_legacy=True)
    monkeypatch.delenv("PDF_CONTROL_APP_DATA_DIR", raising=False)
    legacy_payload = json.dumps({"window": {"width": 555}})
    legacy_path.write_text(legacy_payload, encoding="utf-8")

    loaded = config.load_config()
    loaded["window"]["width"] = 888
    assert config.save_config(loaded) is True

    assert legacy_path.exists()
    assert legacy_path.read_text(encoding="utf-8") == legacy_payload
    # The freshly saved app-data config now takes precedence.
    assert config.load_config()["window"]["width"] == 888


def test_isolation_override_ignores_legacy_config(patch_config_paths):
    """With PDF_CONTROL_APP_DATA_DIR set (test harness), the legacy project
    config is never read even when it exists."""
    assert os.environ.get("PDF_CONTROL_APP_DATA_DIR")  # provided by conftest
    _config_path, legacy_path = patch_config_paths(with_legacy=True)
    legacy_path.write_text(json.dumps({"window": {"width": 111}}), encoding="utf-8")

    assert config.load_config()["window"]["width"] == config.DEFAULT_CONFIG["window"]["width"]


def test_save_failure_returns_false(monkeypatch, tmp_path):
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("occupied", encoding="utf-8")
    monkeypatch.setattr(config, "_config_path", lambda: blocker / "config.json")
    assert config.save_config({"window": {"width": 1}}) is False
    assert blocker.read_text(encoding="utf-8") == "occupied"


def test_saved_config_roundtrips_unicode_values(patch_config_paths):
    config_path, _legacy = patch_config_paths()
    loaded = config.load_config()
    loaded["last_directory"] = "C:\\문서\\보고서"
    assert config.save_config(loaded) is True

    raw = json.loads(config_path.read_text(encoding="utf-8"))
    assert raw["last_directory"] == "C:\\문서\\보고서"
    assert config.load_config()["last_directory"] == "C:\\문서\\보고서"


def test_get_set_config_value_roundtrip():
    config_dict = {"window": {"width": 1200}}
    config.set_config_value(config_dict, "window", "width", value=1400)
    config.set_config_value(config_dict, "new_section", "key", value=[1, 2])
    assert config.get_config_value(config_dict, "window", "width") == 1400
    assert config.get_config_value(config_dict, "new_section", "key") == [1, 2]
    assert config.get_config_value(config_dict, "missing", "deep", default="fallback") == "fallback"
