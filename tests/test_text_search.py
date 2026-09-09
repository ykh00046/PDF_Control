"""Tests for app.text_search (Find) and its DocumentSession delegate."""

import fitz
import pytest

from app.model import DocumentSession
from app.text_search import MAX_QUERY_LENGTH, find_text, next_hit_index, normalize_query


@pytest.fixture
def search_pdf(tmp_path):
    """Three pages: 'Alpha' twice on p1, 'alpha' once on p2, nothing on p3."""
    path = tmp_path / "search.pdf"
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((50, 80), "Alpha one", fontsize=12)
    p1.insert_text((50, 120), "Alpha two", fontsize=12)
    p2 = doc.new_page()
    p2.insert_text((50, 80), "alpha lower", fontsize=12)
    doc.new_page()
    doc.save(path)
    doc.close()
    return str(path)


def test_find_text_returns_hits_in_page_order(search_pdf):
    doc = fitz.open(search_pdf)
    try:
        hits = find_text(doc, "alpha")
        assert [h.page_index for h in hits] == [0, 0, 1]
        # first hit sits above the second on page 1 (reading order)
        assert hits[0].rect.y0 < hits[1].rect.y0
        assert all(h.rect.width > 0 and h.rect.height > 0 for h in hits)
    finally:
        doc.close()


def test_find_text_case_sensitive_filters(search_pdf):
    doc = fitz.open(search_pdf)
    try:
        assert [h.page_index for h in find_text(doc, "Alpha", case_sensitive=True)] == [0, 0]
        assert [h.page_index for h in find_text(doc, "alpha", case_sensitive=True)] == [1]
    finally:
        doc.close()


def test_find_text_empty_or_blank_query(search_pdf):
    doc = fitz.open(search_pdf)
    try:
        assert find_text(doc, "") == []
        assert find_text(doc, "   ") == []
        assert find_text(doc, "zzz-not-there") == []
    finally:
        doc.close()


def test_find_text_page_subset_and_range_check(search_pdf):
    doc = fitz.open(search_pdf)
    try:
        assert [h.page_index for h in find_text(doc, "alpha", page_indices=[1])] == [1]
        with pytest.raises(IndexError):
            find_text(doc, "alpha", page_indices=[7])
    finally:
        doc.close()


def test_normalize_query_trims_and_caps():
    assert normalize_query("  hi  ") == "hi"
    assert normalize_query(None) == ""  # type: ignore[arg-type]
    assert len(normalize_query("x" * (MAX_QUERY_LENGTH + 50))) == MAX_QUERY_LENGTH


@pytest.mark.parametrize(
    "count,current,step,expected",
    [
        (0, -1, 1, -1),
        (3, -1, 1, 0),
        (3, -1, -1, 2),
        (3, 2, 1, 0),  # wraps forward
        (3, 0, -1, 2),  # wraps backward
        (3, 1, 1, 2),
    ],
)
def test_next_hit_index_cycles(count, current, step, expected):
    assert next_hit_index(count, current, step) == expected


def test_session_find_text_delegates(search_pdf):
    session = DocumentSession(search_pdf)
    try:
        hits = session.find_text("ALPHA")
        assert len(hits) == 3
        assert session.modified is False  # read-only
        assert session.history == []
    finally:
        session.close()
