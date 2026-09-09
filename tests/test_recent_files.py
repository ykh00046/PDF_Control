"""Tests for app.recent_files (pure config helpers)."""

import os

from app.recent_files import (
    RECENT_FILES_LIMIT,
    add_recent_file,
    clear_recent_files,
    get_recent_files,
    remove_recent_file,
)


def test_add_moves_to_front_and_dedupes(tmp_path):
    config = {}
    a = str(tmp_path / "a.pdf")
    b = str(tmp_path / "b.pdf")
    add_recent_file(config, a)
    add_recent_file(config, b)
    assert get_recent_files(config) == [os.path.abspath(b), os.path.abspath(a)]

    # Re-adding an existing path (different case / relative form) moves it up, no duplicate.
    add_recent_file(config, a.upper())
    recent = get_recent_files(config)
    assert len(recent) == 2
    assert os.path.normcase(recent[0]) == os.path.normcase(a)


def test_add_respects_limit(tmp_path):
    config = {}
    for i in range(RECENT_FILES_LIMIT + 5):
        add_recent_file(config, str(tmp_path / f"{i}.pdf"))
    recent = get_recent_files(config)
    assert len(recent) == RECENT_FILES_LIMIT
    assert recent[0].endswith(f"{RECENT_FILES_LIMIT + 4}.pdf")


def test_remove_and_clear(tmp_path):
    config = {}
    a = str(tmp_path / "a.pdf")
    b = str(tmp_path / "b.pdf")
    add_recent_file(config, a)
    add_recent_file(config, b)
    remove_recent_file(config, a)
    assert get_recent_files(config) == [os.path.abspath(b)]
    clear_recent_files(config)
    assert get_recent_files(config) == []


def test_get_tolerates_bad_config_values():
    assert get_recent_files({"recent_files": "not-a-list"}) == []
    assert get_recent_files({"recent_files": [1, "", None, "ok.pdf"]}) == ["ok.pdf"]
    assert get_recent_files({}) == []


def test_add_ignores_empty_path():
    config = {"recent_files": ["x.pdf"]}
    assert add_recent_file(config, "") == ["x.pdf"]
