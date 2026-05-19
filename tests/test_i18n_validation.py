"""Pytest wrapper around validate_i18n.I18nValidator so CI catches key drift."""

from pathlib import Path

import pytest

from tests.validate_i18n import I18nValidator


@pytest.fixture(scope="module")
def validator():
    i18n_dir = Path(__file__).parent.parent / "app" / "i18n"
    assert i18n_dir.exists(), f"i18n directory missing: {i18n_dir}"
    v = I18nValidator(i18n_dir)
    en = v.load_json("en.json")
    ko = v.load_json("ko.json")
    return v, en, ko


def test_both_files_load(validator):
    v, en, ko = validator
    assert en, "en.json failed to load or is empty"
    assert ko, "ko.json failed to load or is empty"


def test_no_missing_keys(validator):
    v, en, ko = validator
    v.errors.clear()
    v.validate_keys(en, ko, "en.json", "ko.json")
    v.validate_keys(ko, en, "ko.json", "en.json")
    assert not v.errors, "i18n key mismatch:\n" + "\n".join(v.errors)


def test_format_placeholders_match(validator):
    v, en, ko = validator
    v.errors.clear()
    v.validate_format_strings(en, ko, "en.json", "ko.json")
    assert not v.errors, "Format placeholder mismatch:\n" + "\n".join(v.errors)
