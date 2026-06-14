"""Tests for app.text_utils module."""

import pytest

from app.text_utils import format_page_range, parse_page_range, sanitize_unicode


class TestSanitizeUnicode:
    def test_normal_text_unchanged(self):
        assert sanitize_unicode("Hello World") == "Hello World"

    def test_empty_string(self):
        assert sanitize_unicode("") == ""

    def test_none_returns_none(self):
        assert sanitize_unicode(None) is None

    def test_null_characters_replaced(self):
        assert sanitize_unicode("Hello\x00World") == "Hello\ufffdWorld"

    def test_korean_text_unchanged(self):
        assert sanitize_unicode("안녕하세요") == "안녕하세요"

    def test_mixed_content(self):
        result = sanitize_unicode("Test\x00\x00End")
        assert result == "Test\ufffd\ufffdEnd"
        assert "\x00" not in result


class TestParsePageRange:
    def test_single_page(self):
        assert parse_page_range("1", 10) == {0}

    def test_multiple_pages(self):
        assert parse_page_range("1,3,5", 10) == {0, 2, 4}

    def test_page_range(self):
        assert parse_page_range("1-5", 10) == {0, 1, 2, 3, 4}

    def test_mixed_format(self):
        assert parse_page_range("1,3,5-7", 10) == {0, 2, 4, 5, 6}

    def test_all_keyword(self):
        assert parse_page_range("all", 5) == {0, 1, 2, 3, 4}

    def test_all_keyword_case_insensitive(self):
        assert parse_page_range("ALL", 5) == {0, 1, 2, 3, 4}

    def test_out_of_range_clamped(self):
        # Page 20 doesn't exist in a 5-page document
        result = parse_page_range("1,20", 5)
        assert result == {0}

    def test_range_clamped_to_total(self):
        # Range 3-10 in a 5-page doc -> pages 3,4,5
        result = parse_page_range("3-10", 5)
        assert result == {2, 3, 4}

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            parse_page_range("", 10)

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError):
            parse_page_range("   ", 10)

    def test_invalid_text_raises(self):
        with pytest.raises(ValueError):
            parse_page_range("abc", 10)

    def test_spaces_tolerated(self):
        assert parse_page_range(" 1 , 3 , 5-7 ", 10) == {0, 2, 4, 5, 6}


class TestFormatPageRange:
    def test_empty_set(self):
        assert format_page_range(set()) == ""

    def test_single_page(self):
        assert format_page_range({0}) == "1"

    def test_consecutive_pages(self):
        assert format_page_range({0, 1, 2}) == "1-3"

    def test_mixed(self):
        result = format_page_range({0, 1, 2, 4, 6, 7, 8})
        assert result == "1-3, 5, 7-9"

    def test_non_consecutive(self):
        assert format_page_range({0, 2, 4}) == "1, 3, 5"
