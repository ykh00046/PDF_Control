"""Document text search (Find).

Pure helper over a :class:`fitz.Document`: locate every occurrence of a
query string and return ``(page_index, rect)`` hits in reading order, so
the UI can step through them and draw highlights.

PyMuPDF's ``Page.search_for`` ignores case for ASCII letters and has no
case-sensitive switch, so ``case_sensitive=True`` is implemented as a
post-filter on the text actually enclosed by each hit rectangle (the
approach the PyMuPDF docs recommend). Pending, unsaved edit operations are
NOT reflected: the search runs on the document as opened (plus any page
management already applied), which is the same text the batch replace
dialog sees.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

import fitz

MAX_QUERY_LENGTH = 256


@dataclass(frozen=True)
class SearchHit:
    """One occurrence of the query: page index (0-based) and its bbox."""

    page_index: int
    rect: fitz.Rect


def normalize_query(query: str) -> str:
    """Trim and cap a raw query; returns "" when there is nothing to search."""
    if not query:
        return ""
    return query.strip()[:MAX_QUERY_LENGTH]


def find_text(
    doc: fitz.Document,
    query: str,
    case_sensitive: bool = False,
    page_indices: Optional[Iterable[int]] = None,
) -> List[SearchHit]:
    """Return every occurrence of ``query`` in ``doc`` in page/reading order.

    Args:
        doc: Open document to search.
        query: Needle; whitespace-trimmed, empty query yields no hits.
        case_sensitive: When True, keep only hits whose enclosed text
            contains the query with matching case.
        page_indices: Optional subset of pages (0-based). Defaults to all.

    Raises:
        IndexError: a page index in ``page_indices`` is out of range.
    """
    needle = normalize_query(query)
    if not needle:
        return []

    if page_indices is None:
        indices: List[int] = list(range(doc.page_count))
    else:
        indices = list(page_indices)
        for idx in indices:
            if idx < 0 or idx >= doc.page_count:
                raise IndexError(f"page index out of range: {idx}")

    hits: List[SearchHit] = []
    for page_index in indices:
        page = doc[page_index]
        for rect in page.search_for(needle):
            if case_sensitive and needle not in page.get_textbox(rect):
                continue
            hits.append(SearchHit(page_index, fitz.Rect(rect)))
    return hits


def next_hit_index(hits_count: int, current: int, step: int) -> int:
    """Cycle ``current`` by ``step`` within ``[0, hits_count)``; -1 when empty."""
    if hits_count <= 0:
        return -1
    if current < 0:
        return 0 if step >= 0 else hits_count - 1
    return (current + step) % hits_count
